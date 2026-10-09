"""Read-only exact-baseline projections: diff, reference impact and dossier view."""
from collections import deque
import hashlib
from html import escape
import json
from air.core import CONSTRUCTION_PROFILE, REF, canonical, record, reference_slots
from air.expr import artifact_digest
from air.foundation import InvalidModel, check_schema, exact, key
from air.construction import validate_construction
from air.storage import Conflict

ENGINE = "air.projections/0.6"
LIST_KEYS = ("name", "code", "operation", "id")
SNAPSHOT = record({**REF["properties"], "digest": {"type": "string", "pattern": "^sha256:[a-f0-9]{64}$"}})


def snapshot(store, ref):
    result = store.export_baseline({"id": ref["id"], "revision": ref["revision"]})
    if result["digest"] != ref["digest"]:
        raise Conflict("Projection targets a different baseline digest")
    return result


def _keyed(items):
    """A list of records is compared by its identifying field when every record carries a distinct one."""
    if not items or not all(isinstance(i, dict) for i in items): return None
    for field in LIST_KEYS:
        values = [i.get(field) for i in items]
        if all(isinstance(v, str) for v in values) and len(set(values)) == len(values):
            return field
    return None


def changes(before, after, prefix=""):
    if before == after:
        return []
    if isinstance(before, list) and isinstance(after, list):
        field = _keyed(before) if before else _keyed(after)
        if field and (not after or _keyed(after) == field) and (not before or _keyed(before) == field):
            old = {i[field]: i for i in before};new = {i[field]: i for i in after};result = []
            for name in sorted(old.keys() | new.keys()):
                location = prefix + "/[" + field + "=" + name.replace("~", "~0").replace("/", "~1") + "]"
                if name not in old: result.append({"path": location, "change": "ADD", "after": new[name]})
                elif name not in new: result.append({"path": location, "change": "REMOVE", "before": old[name]})
                else: result.extend(changes(old[name], new[name], location))
            return result
    if isinstance(before, dict) and isinstance(after, dict):
        result = []
        for field in sorted(before.keys() | after.keys()):
            location = prefix + "/" + field.replace("~", "~0").replace("/", "~1")
            if field not in before:
                result.append({"path": location, "change": "ADD", "after": after[field]})
            elif field not in after:
                result.append({"path": location, "change": "REMOVE", "before": before[field]})
            else:
                result.extend(changes(before[field], after[field], location))
        return result
    return [{"path": prefix, "change": "REPLACE", "before": before, "after": after}]


def reference_neutral(obj):
    """The object with its own revision, record time and every exact reference revision masked."""
    from copy import deepcopy
    masked = deepcopy(obj)
    masked["meta"]["revision"] = 0;masked["meta"].pop("recorded_at", None)
    for _, ref, _ in reference_slots(masked):
        ref["revision"] = 0;ref.pop("digest", None)
    return canonical(masked)


def _schema_properties(store, obj):
    """Flattened JSON Schema properties and required fields of a DataSchema file, or None when it cannot be read."""
    from air import artifacts
    from air.packages import reference as manifest_reference
    principal, policy = getattr(store, 'principal', None), getattr(store, 'policy', None)
    raw_store = getattr(store, 'store', store)
    try:
        manifest = raw_store.get_record(obj['body']['artifact']['locator'])
        if not manifest or manifest['kind'] != 'artifact_manifest': return None
        data = artifacts.download(raw_store, principal, policy, {'artifact': manifest_reference(manifest)})[1]
        parsed = json.loads(data.decode('utf-8'))
    except Exception:
        return None
    found = {}
    def walk(node, path):
        if not isinstance(node, dict): return
        for name, sub in (node.get('properties') or {}).items():
            where = path + '/' + name
            found[where] = {'type': sub.get('type') if isinstance(sub, dict) else None, 'required': name in (node.get('required') or [])}
            walk(sub, where)
        if isinstance(node.get('items'), dict): walk(node['items'], path + '/[]')
    walk(parsed, '')
    return found


def _schema_changes(store, a, b):
    if a['meta']['type'] != 'air.DataSchema' or a['body'].get('artifact') == b['body'].get('artifact'): return None
    old, new = _schema_properties(store, a), _schema_properties(store, b)
    if old is None or new is None: return {'status': 'FILE_UNREADABLE'}
    return {'added': sorted(new.keys() - old.keys()), 'removed': sorted(old.keys() - new.keys()),
            'changed': sorted(k for k in old.keys() & new.keys() if old[k] != new[k])}


def diff(store, request):
    check_schema(request, record({"before": SNAPSHOT, "after": SNAPSHOT}))
    before, after = (snapshot(store, request[field]) for field in ("before", "after"))
    old = {o["meta"]["id"]: o for o in before["objects"]}
    new = {o["meta"]["id"]: o for o in after["objects"]}
    result = []
    for object_id in sorted(old.keys() | new.keys()):
        a, b = old.get(object_id), new.get(object_id)
        if a is None:
            result.append({"change": "ADD", "after": exact(b), "type": b["meta"]["type"]})
        elif b is None:
            result.append({"change": "REMOVE", "before": exact(a), "type": a["meta"]["type"]})
        elif canonical(a) != canonical(b):
            nature = "REFERENCE_ONLY" if reference_neutral(a) == reference_neutral(b) else "CONTENT"
            entry = {"change": "REPLACE", "nature": nature, "before": exact(a), "after": exact(b), "type": b["meta"]["type"],
                     "fields": changes(json.loads(canonical(a)), json.loads(canonical(b)))}
            schema_changes = _schema_changes(store, a, b)
            if schema_changes is not None: entry["schema_changes"] = schema_changes
            result.append(entry)
    summary = {"added": sum(1 for c in result if c["change"] == "ADD"), "removed": sum(1 for c in result if c["change"] == "REMOVE"),
               "content_changes": sum(1 for c in result if c.get("nature") == "CONTENT"),
               "reference_only_changes": sum(1 for c in result if c.get("nature") == "REFERENCE_ONLY")}
    report = {"engine": ENGINE, "before": request["before"], "after": request["after"], "summary": summary, "changes": result,
              "profile_changed": before["baseline"]["body"]["profiles"] != after["baseline"]["body"]["profiles"],
              "semantic_compatibility": "NOT_EXECUTED", "authorization_granted": False}
    report["report_digest"] = artifact_digest(report)
    return report


def impact(store, request):
    check_schema(request, record({"baselines": {"type": "array", "items": SNAPSHOT, "minItems": 1, "maxItems": 32, "uniqueItems": True},
                                  "targets": {"type": "array", "items": REF, "minItems": 1, "maxItems": 256, "uniqueItems": True}}))
    roots = {key(r) for r in request["targets"]}
    reports = []
    path_steps = 0
    for ref in sorted(request["baselines"], key=key):
        exported = snapshot(store, ref)
        objects = {key(exact(o)): o for o in exported["objects"]}
        reverse = {}
        for identity, obj in objects.items():
            for field, link, _ in reference_slots(obj):
                reverse.setdefault(key(link), []).append((identity, field))
        found = roots & objects.keys()
        queue = deque(sorted(found))
        paths = {r: [] for r in found}
        while queue:
            current = queue.popleft()
            for consumer, field in sorted(reverse.get(current, [])):
                if consumer not in paths:
                    path_steps += len(paths[current]) + 1
                    if path_steps > 10000:
                        raise InvalidModel("Impact exceeds 10000 path steps; narrow the supplied baselines")
                    paths[consumer] = paths[current] + [{"from": exact(objects[consumer]), "field": field,
                                                         "to": {"id": current[0], "revision": current[1]}}]
                    queue.append(consumer)
        reports.append({"baseline": ref, "selected_targets": [{"id": i, "revision": r} for i, r in sorted(found)],
            "targets_not_selected": [{"id": i, "revision": r} for i, r in sorted(roots - found)],
            "affected": [{"object": exact(objects[k]), "name": objects[k]["meta"]["name"],
                          "qualification": "SELECTED_TARGET" if k in roots else "POTENTIAL_REFERENCE_DEPENDENCY",
                          "path": paths[k]} for k in sorted(paths)]})
        if len(json.dumps(reports, ensure_ascii=False).encode()) > 8 * 1024 * 1024:
            raise InvalidModel("Impact report exceeds 8 MiB; narrow the supplied baselines")
    report = {"engine": ENGINE, "targets": sorted(request["targets"], key=key), "baselines": reports,
              "coverage": "Only supplied exact baselines and declared references; not an enterprise-wide completeness claim",
              "authorization_granted": False, "automatic_changes": False}
    report["report_digest"] = artifact_digest(report)
    return report


STYLE = """
:root{color-scheme:light;font:16px/1.6 'Segoe UI',Arial,sans-serif;color:#153653;background:#f2f6fa}
*{box-sizing:border-box}body{margin:0}a{color:#2457a6}a:focus-visible,summary:focus-visible{outline:3px solid #8a5800;outline-offset:4px}
header{background:#153653;color:white;padding:2rem max(5vw,1rem)}header p{max-width:75ch}h1{font-size:2rem;line-height:1.25;margin:.5rem 0}
main{max-width:1200px;margin:auto;padding:2rem 1.25rem}h2{font-size:1.45rem;margin:2rem 0 .8rem}h3{font-size:1.1rem}
.notice{border-left:5px solid #a52839;padding:1rem 1.25rem;background:white}.chain{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin:1.5rem 0}
.step{padding:1rem;background:white;border-top:4px solid #2457a6;overflow-wrap:anywhere}.step p{margin:.5rem 0}
.caption{color:#52657a;font-size:.9rem}.warning{color:#8a5800}.blocked{color:#a52839;font-weight:650}
table{width:100%;border-collapse:collapse;background:white}th,td{padding:.7rem;text-align:left;border-bottom:1px solid #d5e0eb;vertical-align:top;overflow-wrap:anywhere}
details{background:white;padding:1rem;margin:.6rem 0}summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.85rem;background:#f2f6fa;padding:1rem}
.digest{overflow-wrap:anywhere;font-size:.8rem}nav{display:flex;gap:1.2rem;flex-wrap:wrap;margin:1rem 0}footer{padding:2rem 0;color:#52657a}
@media(max-width:760px){.chain{grid-template-columns:1fr}main{padding:1rem}h1{font-size:1.6rem}table{font-size:.9rem}}
@media print{header{background:white;color:#153653}main{max-width:none}details{break-inside:avoid}a{color:inherit}}
"""


def view(store, request):
    check_schema(request, record({"baseline": SNAPSHOT}))
    exported = snapshot(store, request["baseline"])
    objects = {key(exact(o)): o for o in exported["objects"]}
    baseline = exported["baseline"]
    report = validate_construction(exported["objects"]) if baseline["body"]["profiles"] == [CONSTRUCTION_PROFILE] else exported["validation"]
    def anchor(ref):
        return "obj-" + hashlib.sha256((ref["id"] + "@" + str(ref["revision"])).encode()).hexdigest()[:24]
    def link(ref):
        obj = objects[key(ref)]
        return '<a href="#' + anchor(ref) + '">' + escape(obj["meta"]["name"]) + '</a>'
    chunks = ['<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
              '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">',
              '<title>' + escape(baseline["meta"]["name"]) + ' - AIR</title><style>' + STYLE + '</style></head><body>',
              '<header><p>Dossier d’architecture • AIR</p><h1>' + escape(baseline["meta"]["name"]) + '</h1><p>' + escape(baseline["meta"]["description"]) + '</p></header><main>',
              '<aside class="notice"><strong>Conception à vérifier</strong><p>Cette vue décrit le système prévu. Les scénarios de réception ne sont pas exécutés ; aucune approbation ou action métier n’est accordée.</p></aside>',
              '<nav aria-label="Sections"><a href="#construction">Construction</a><a href="#reception">Réception</a><a href="#unknowns">Inconnues</a><a href="#registre">Registre et sources</a></nav>',
              '<section id="construction"><h2>Du besoin à sa réalisation</h2>']
    for row in report.get("traceability", []):
        chunks.append('<div class="chain">')
        for field, label in [("requirement", "Exigence"), ("function", "Fonction"), ("contract", "Contrat"), ("unit", "Travail prévu")]:
            chunks.append('<div class="step"><p class="caption">' + label + '</p><h3>' + link(row[field]) + '</h3></div>')
        chunks.append('</div>')
    if not report.get("traceability"):
        chunks.append('<p>Aucune chaîne de construction complète disponible dans cette baseline.</p>')
    chunks.append('</section><section id="reception"><h2>Réception et contrôles</h2>')
    chunks.append('<p>Structure : <strong>' + ('vérifiée dans le sous-profil' if report.get("construction_ready") else 'à compléter') + '</strong>. <span class="blocked">Réception métier non accordée.</span></p>')
    for diagnostic in report["diagnostics"]:
        chunks.append('<p class="blocked">' + escape(diagnostic["code"] + ': ' + diagnostic["message"]) + '</p>')
    chunks.append('<table><thead><tr><th>Scénario</th><th>Résultat attendu</th><th>Exécution</th></tr></thead><tbody>')
    for obj in sorted(objects.values(), key=lambda o: key(exact(o))):
        if obj["meta"]["type"] == "air.VerificationCase":
            chunks.append('<tr><td>' + link(exact(obj)) + '</td><td>' + escape(obj["body"]["oracle"]) + '</td><td class="warning">Non exécuté</td></tr>')
    chunks.append('</tbody></table></section><section id="unknowns"><h2>Inconnues à résoudre</h2>')
    for unknown in report.get("open_unknowns", []):
        obj = objects[key(unknown["reference"])]
        chunks.append('<details open><summary>' + escape(obj["body"]["question"]) + '</summary><p>Responsable : ' + escape(obj["body"]["resolution_owner"]) + '</p><p>Politique : ' + escape(unknown["blocking_policy"]) + '</p></details>')
    chunks.append('</section><section id="registre"><h2>Registre et sources</h2>')
    mappings = []
    for identity, obj in sorted(objects.items()):
        dom_id = anchor(exact(obj))
        mappings.append({"anchor": dom_id, "object": exact(obj)})
        chunks.append('<details id="' + dom_id + '"><summary>' + escape(obj["meta"]["name"]) + '</summary><p class="caption">' + escape(obj["meta"]["type"]) + ' • révision ' + str(identity[1]) + '</p><pre>' + escape(json.dumps(obj, ensure_ascii=False, indent=2)) + '</pre></details>')
    chunks.append('</section><footer><p>Vue dérivée en lecture seule. Toute correction passe par une nouvelle révision et une proposition.</p><p class="digest">Baseline : ' + escape(request["baseline"]["id"]) + ' - ' + escape(request["baseline"]["digest"]) + '</p></footer></main></body></html>')
    content = ''.join(chunks)
    return {"engine": ENGINE, "baseline": request["baseline"], "media_type": "text/html; charset=utf-8",
            "content": content, "digest": "sha256:" + hashlib.sha256(content.encode()).hexdigest(), "mapping": mappings,
            "authorization_granted": False, "business_scenarios_executed": False}
