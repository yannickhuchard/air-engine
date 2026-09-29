"""Deterministic weekly capacity diagnostics; no reservations or authority effects."""
from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Context, Decimal, localcontext
from air.core import INSTANT, REF, URI, record
from air.expr import artifact_digest
from air.foundation import InvalidModel, check_schema, exact, key
from air.projections import SNAPSHOT, snapshot

ENGINE = "air.weekly-planning/0.6"
DECIMAL = {"type": "string", "pattern": "^(0|[1-9][0-9]{0,17})(\\.[0-9]{1,6})?$"}
VECTOR = {"type": "array", "items": DECIMAL, "minItems": 1, "maxItems": 104}
OBSERVATIONS = {**VECTOR, "items": {"anyOf": [DECIMAL, {"type": "null"}]}}
POOL = record({"scope": SNAPSHOT, "source": SNAPSHOT,
    "resource_ids": {"type": "array", "items": URI, "minItems": 1, "maxItems": 1000, "uniqueItems": True},
    "availability": {"enum": ["AVAILABLE", "UNAVAILABLE"]}, "observed_at": INSTANT, "expires_at": INSTANT,
    "gross": OBSERVATIONS, "baseline_obligations": OBSERVATIONS, "existing_reservations": OBSERVATIONS})
DEMAND = record({"baseline": SNAPSHOT, "unit": SNAPSHOT, "pool": REF, "per_week": VECTOR})
REQUEST = record({"basis": {"const": "SCENARIO_INPUT"}, "as_of": INSTANT,
    "unit": {"const": "FTE"}, "periods": {"type": "array", "minItems": 1, "maxItems": 104,
        "items": record({"start": INSTANT, "end": INSTANT})},
    "pools": {"type": "array", "items": POOL, "minItems": 1, "maxItems": 32},
    "demands": {"type": "array", "items": DEMAND, "minItems": 1, "maxItems": 128},
    "dependencies": {"type": "array", "items": record({"before": REF, "after": REF}), "maxItems": 1000, "uniqueItems": True},
    "priority_order": {"type": "array", "items": REF, "minItems": 1, "maxItems": 128, "uniqueItems": True},
    "strategy": {"enum": ["AS_PROPOSED", "SERIAL_EARLIEST_FEASIBLE"]}})


def number(value):
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def reference(identity):
    return {"id": identity[0], "revision": identity[1]}


def prepare(store, request):
    check_schema(request, REQUEST)
    size = len(request["periods"])
    previous = None
    for period in request["periods"]:
        start, end = (datetime.fromisoformat(period[f]) for f in ("start", "end"))
        if end - start != timedelta(days=7) or previous is not None and previous != start:
            raise InvalidModel("Planning requires contiguous half-open seven-day periods")
        previous = end
    pools, seen_resources = {}, set()
    for pool in request["pools"]:
        identity = key(pool["scope"])
        if identity in pools: raise InvalidModel("Duplicate pool scope")
        for field, kind in (("scope", "air.Scope"), ("source", "air.Source")):
            pin = pool[field]
            row = store.get(pin["id"], pin["revision"])
            if row is None or row["digest"] != pin["digest"] or row["object"]["meta"]["type"] != kind:
                raise InvalidModel("Pool scope/source must be readable and exactly pinned")
        members = set(pool["resource_ids"])
        if seen_resources & members: raise InvalidModel("The same resource cannot be counted in multiple pools; disjoint aggregate pools are required")
        seen_resources |= members
        if datetime.fromisoformat(pool["observed_at"]) > datetime.fromisoformat(request["as_of"]):
            raise InvalidModel("Capacity observations cannot come from the future")
        if datetime.fromisoformat(pool["expires_at"]) <= datetime.fromisoformat(pool["observed_at"]):
            raise InvalidModel("Invalid capacity observation validity interval")
        if any(len(pool[f]) != size for f in ("gross", "baseline_obligations", "existing_reservations")):
            raise InvalidModel("Every capacity vector must cover all periods; use null for unknown data")
        pools[identity] = pool
    units, demands, baselines, seen = {}, {}, {}, set()
    for demand in request["demands"]:
        unit, pool = key(demand["unit"]), key(demand["pool"])
        if pool not in pools or (unit, pool) in seen: raise InvalidModel("Missing pool or duplicate unit/pool demand")
        if len(demand["per_week"]) != size: raise InvalidModel("Every demand vector must cover all periods")
        seen.add((unit, pool))
        baseline_key = key(demand["baseline"])
        if baseline_key not in baselines: baselines[baseline_key] = snapshot(store, demand["baseline"])
        baseline = baselines[baseline_key]
        if baseline["digest"] != demand["baseline"]["digest"]: raise InvalidModel("Conflicting baseline pin")
        obj = next((o for o in baseline["objects"] if key(exact(o)) == unit), None)
        from air.core import digest
        if obj is None or obj["meta"]["type"] != "air.ConstructionUnit" or digest(obj) != demand["unit"]["digest"]:
            raise InvalidModel("Demand must target a pinned ConstructionUnit in its exact baseline")
        if unit in units and units[unit] != demand["unit"]: raise InvalidModel("Conflicting unit pin")
        units[unit] = demand["unit"]
        demands[(unit, pool)] = [Decimal(x) for x in demand["per_week"]]
    if len({u[0] for u in units}) != len(units): raise InvalidModel("Select one revision of each construction unit")
    priority = [key(r) for r in request["priority_order"]]
    if set(priority) != set(units): raise InvalidModel("Priority order must name each unit exactly once")
    parents = {u: set() for u in units}
    for edge in request["dependencies"]:
        a, b = key(edge["before"]), key(edge["after"])
        if a not in units or b not in units: raise InvalidModel("Dependency endpoint is outside this plan")
        parents[b].add(a)
    order, remaining = [], set(units)
    while remaining:
        ready = next((u for u in priority if u in remaining and not parents[u] & remaining), None)
        if ready is None: raise InvalidModel("Strict construction precedences must be acyclic")
        order.append(ready);remaining.remove(ready)
    for unit in units:
        if not any(q > 0 for (u, _), vector in demands.items() if u == unit for q in vector):
            raise InvalidModel("Each selected unit needs a positive explicit remaining demand")
    return pools, units, demands, parents, order


def capacities(pools, request):
    result, reasons = {}, []
    as_of = datetime.fromisoformat(request["as_of"])
    for identity, pool in sorted(pools.items()):
        unavailable = pool["availability"] != "AVAILABLE" or datetime.fromisoformat(pool["expires_at"]) <= as_of
        vector = []
        for i, (gross, obligation, reserved) in enumerate(zip(pool["gross"], pool["baseline_obligations"], pool["existing_reservations"])):
            if unavailable or None in (gross, obligation, reserved):
                vector.append(None)
                reasons.append({"code": "AIR_CAPACITY_UNKNOWN", "pool": reference(identity), "period": i,
                                "reason": "Source unavailable, expired, or incomplete"})
            else:
                net = Decimal(gross) - Decimal(obligation) - Decimal(reserved)
                vector.append(net)
                if net < 0: reasons.append({"code": "AIR_EXISTING_OVERCOMMITMENT", "pool": reference(identity), "period": i})
        result[identity] = vector
    return result, reasons


def spans(demands):
    points = {}
    for (unit, _), vector in demands.items():
        points.setdefault(unit, set()).update(i for i, q in enumerate(vector) if q > 0)
    return {u: (min(p), max(p) + 1) for u, p in points.items()}


def assessment(pools, demands, parents, net, size):
    details, known_shortfall, unknown, violated = [], Decimal(0), False, False
    for pool in sorted(pools):
        cells = []
        for i in range(size):
            demand = sum((v[i] for (u, p), v in demands.items() if p == pool), Decimal(0))
            capacity = net[pool][i]
            shortfall = max(Decimal(0), demand - capacity) if capacity is not None else None
            if shortfall is None: unknown = True
            else:
                known_shortfall += shortfall
                violated |= shortfall > 0
            cells.append({"period": i, "gross": pools[pool]["gross"][i], "baseline_obligations": pools[pool]["baseline_obligations"][i],
                "existing_reservations": pools[pool]["existing_reservations"][i], "net_after_reservations": number(capacity) if capacity is not None else None,
                "demand": number(demand), "shortfall": number(shortfall) if shortfall is not None else None})
        details.append({"pool": reference(pool), "periods": cells})
    schedule = spans(demands)
    precedence = [{"before": reference(parent), "after": reference(unit), "code": "AIR_PRECEDENCE_VIOLATED"}
                  for unit in sorted(parents) for parent in sorted(parents[unit]) if schedule[parent][1] > schedule[unit][0]]
    result = "VIOLATED" if violated or precedence else "UNKNOWN" if unknown else "SATISFIED"
    return {"result": result, "capacity_feasible": not violated and not unknown, "precedence_satisfied": not precedence, "feasible_under_model": result == "SATISFIED", "pools": details,
        "known_shortfall_FTE_weeks": number(known_shortfall), "total_shortfall_FTE_weeks": None if unknown else number(known_shortfall),
        "precedence_diagnostics": precedence,
        "schedule": [{"unit": reference(u), "start_period": start, "end_period_exclusive": end} for u, (start, end) in sorted(schedule.items())]}


def schedule(demands, parents, order, net, size):
    if any(q is None for vector in net.values() for q in vector):
        return None, "UNKNOWN_CAPACITY", 0
    if any(q < 0 for vector in net.values() for q in vector):
        return None, "EXISTING_OVERCOMMITMENT", 0
    used = {p: [Decimal(0)] * size for p in net}
    original = spans(demands)
    assigned, ends, steps = {}, {}, 0
    for unit in order:
        start, end = original[unit]
        earliest = max([start] + [ends[p] for p in parents[unit]])
        selected = [(pool, vector) for (u, pool), vector in demands.items() if u == unit]
        found = False
        for proposed in range(earliest, size - (end - start) + 1):
            steps += 1
            if steps > 10000: return None, "SEARCH_BUDGET_EXHAUSTED", steps
            shift = proposed - start
            shifted = {pool: [Decimal(0)] * shift + vector[:size - shift] for pool, vector in selected}
            if all(used[p][i] + vector[i] <= net[p][i] for p, vector in shifted.items() for i in range(size)):
                for p, vector in shifted.items():
                    assigned[(unit, p)] = vector
                    used[p] = [a + b for a, b in zip(used[p], vector)]
                ends[unit] = end + shift
                found = True
                break
        if not found: return None, "NO_FEASIBLE_SCHEDULE_FOUND", steps
    return assigned, "FEASIBLE_NOT_PROVEN_OPTIMAL", steps


def plan(store, request):
    with localcontext(Context(prec=50)):
        pools, units, demands, parents, order = prepare(store, request)
        net, diagnostics = capacities(pools, request)
        size = len(request["periods"])
        proposed = assessment(pools, demands, parents, net, size)
        candidate, status, steps = None, "EVALUATED_AS_PROPOSED", 0
        if request["strategy"] == "SERIAL_EARLIEST_FEASIBLE":
            assigned, status, steps = schedule(demands, parents, order, net, size)
            if assigned is not None:
                candidate = assessment(pools, assigned, parents, net, size)
                candidate["allocations"] = [{"unit": reference(u), "pool": reference(p), "per_week": [number(q) for q in vector]} for (u, p), vector in sorted(assigned.items())]
            result = candidate["result"] if candidate else "VIOLATED" if status == "EXISTING_OVERCOMMITMENT" else "UNKNOWN"
        else:
            result = proposed["result"]
        normalized = deepcopy(request)
        normalized["pools"] = sorted(normalized["pools"], key=lambda p: key(p["scope"]))
        for p in normalized["pools"]: p["resource_ids"].sort()
        normalized["demands"] = sorted(normalized["demands"], key=lambda d: (key(d["unit"]), key(d["pool"])))
        normalized["dependencies"] = sorted(normalized["dependencies"], key=lambda e: (key(e["before"]), key(e["after"])))
        report = {"engine": ENGINE, "result": result, "basis": "DECLARED_SCENARIO_INPUTS", "as_of": request["as_of"],
            "request_digest": artifact_digest(normalized), "periods": request["periods"], "unit": "FTE",
            "proposed": proposed, "candidate": candidate, "diagnostics": diagnostics,
            "solver": {"status": status, "strategy": request["strategy"], "search_steps": steps, "step_limit": 10000,
                       "optimality_proven": False, "optimality_gap": None, "bound": None},
            "authorization_granted": False, "reservations_created": False,
            "limitations": ["Declared scenario quantities are not authenticated resource commitments", "Disjoint aggregate pools, contiguous seven-day periods, constant weekly FTE",
                "Serial scheduling delays whole demand patterns and follows supplied priorities; no global optimality claim", "No skill substitution, money, holidays, protected work in progress, or external effects"]}
        report["report_digest"] = artifact_digest(report)
        return report
