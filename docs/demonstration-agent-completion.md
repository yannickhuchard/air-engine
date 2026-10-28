# Review the agent workflow, 16 October 2026

This demonstration uses an isolated fictional quote-service dossier. The agent
designs the next change; AIR checks its scope, permissions, candidate model and
readiness. It does not execute the future quote service.

The generated walkthrough is in
`tmp/agent-review-20261016/review/index.html`, with the complete generated dossier
and 34 linked MCP requests and responses. The directory is intentionally ignored
by Git. The technical receipt (historical receipt, not bundled) preserves
the exact baseline references, outcomes, evidence hashes and regression results.

## What was actually exercised

The connected AIR plugin returned HTTP 429 when reading capabilities. The agent
therefore used AIR's local MCP Session/APIClient transport, with a fresh session
for each call. This is a local agent workflow and protocol demonstration, not a
native ChatGPT, Claude, Cursor or Antigravity acceptance. No other connected
registry, ProxiBot dossier, tunnel or installed plugin was modified.

The initial administrator setup created two fictional identities in the isolated
home. The architect has `authorize_design`; the agent has read/write access to
the example namespace and cannot authorize itself. Their credentials remain in
protected files and are not part of the review site or the receipt.

## Follow the ten steps

| Step | Agent or architect action | Observed AIR result |
| --- | --- | --- |
| 1 | Read identity, scope and readiness; create a completion run for 1 to 100 units at EUR 1.25 per unit | Baseline r1, 24 objects, 7/13 criteria met |
| 2 | Attempt self-authorization, then have the separate architect identity grant the fictional demo mandate | Self-authorization refused. Mandate: 2 hours, 3 cycles, 40 objects, six allowed technical types |
| 3 | Describe ComplianceMapping, validate a PLANNED control mapping and prepare it | Candidate links the existing control to both construction units and their planned test; baseline remains r1 |
| 4 | Save the proposal in CHECKPOINT; read it in a fresh MCP session | The exact pending_change is recovered; no draft regeneration or implicit commit |
| 5 | Preview and atomically apply; retry the identical request | Baseline r2, one applied cycle, same receipt on retry; 8/13 criteria met |
| 6 | Design the next gap without obtaining another mandate | Five planned topology objects: environment, zone, two services and encrypted connection. Baseline r3, 9/13 criteria met |
| 7 | Verify supplied exchanges against the contract | Two units with a 250-cent total PASS; the same request with 251 cents FAIL, as expected |
| 8 | Escalate the hosting/data-location decision for the whole Scope; attempt an affected technical change | Candidate is ineligible and apply is refused. Baseline stays r3; applied cycles stay at two |
| 9 | Inspect and correct the outcome-reporting defect exposed by this case | The same baseline and checkpoint now report BLOCKED_ON_DECISION, with AUTHORIZED_DECISION as the next action |
| 10 | Pause for user review and export the dossier | PAUSED; 9/13; four readiness criteria still open; no inferred approval |

The first improvement closes declared control coverage, not compliance
certification. The second maps architecture blocks to a future production
design; it provisions no infrastructure. The interface checks execute pure
design predicates on supplied JSON, without calling a business endpoint.

VERIFICATION is already MET in this fixture because its runtime TEST is planned
as construction acceptance and there is no outstanding design-time case. It
does not mean that the future implementation was tested.

## Defect found and corrected

Before the correction, the write guard correctly refused a change affected by
an open Scope-level decision, but the outcome remained REQUIRES_MORE_DESIGN
because design tasks were still listed. This could direct an agent to keep
preparing changes that it could not apply.

An open question referencing the agreed Scope now takes priority in the
completion outcome and next-action guidance. The remaining design tasks stay
visible. The change does not alter readiness, grant authority, resolve the
question or rewrite checkpoints. Questions with narrower references retain
the existing dependency checks, so independent technical work can continue.

The regression test fails before the correction and the full 18-test completion
suite passes afterward. The three Asteria dossiers pass DEMO-METIER-1 again.
Twelve browser views, four widths, keyboard disclosure and all walkthrough
links pass; the protected private home is not served. No CI was launched.

## What remains for the example

Construction-chain coverage, delivery planning, contextual completeness and an
effective independent review remain NOT_MET. The hosting question is deliberately
unanswered and the run is paused for this review. Neither the fictional architect
identity nor this walkthrough constitutes a real independent acceptance.

Review the mandate boundaries, the usefulness of the two design changes, the
distinction between plans and evidence, and the pause/resume experience. User
review acceptance has not yet been recorded. This demonstration does not merge
or publish the implementation.
