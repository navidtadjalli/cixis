# SDD ledger — plan: docs/superpowers/plans/2026-09-02-cixis-internal-implementation.md

## Pre-flight scan

| Tasks / interface | Producer → consumer | Finding / ruling |
| --- | --- | --- |
| Task 1 → Task 2 | CiXiS compatibility bridge → internal store | Clean: Task 2 must not import or migrate `pos`; no store dependency is needed for this persistence unit. |
| Task 2 → Task 3 | encrypted records / AEAD → keyring and provisioning | Clean: repository takes caller-supplied installation ID and key generation; Task 3 remains responsible for real key provisioning. |
| Task 2 → Tasks 5–10 | encrypted records / manifests → domain services | Clean: opaque records and manifest verification form the shared persistence boundary. |
| Task 2 brief → Resumption State | stale `test_crypto_store` wording → exact resumed `test_store` action | Ruling: use `backend/internal/tests/test_store.py` as the first RED test and implement only the specified temporary internal SQLite store unit; Resumption State is later, explicit, and binding. Cost if wrong: later Task 2 test-file consolidation may be needed, but production behavior and coverage remain correct. |

Task 1: complete (commit 275de39, predates this ledger)
Task 2: in progress (base bc641555bb0c09418700536e7c872e99624b2dbb; resumed encrypted-store unit)
Task 2: review requires fix round 1/5 — Important: reject a CiXiS SQLite path before schema creation; Important: verify manifests across all live record types so a newly inserted type cannot evade detection. Minor: enable SQLite foreign keys and remove duplicate test docstring.
Task 2: fix round 1/5 (4 addressed, 0 open; commits 88f5aef..0cea449; scoped re-review clean)
Task 2: complete (commits 207071c, a1d327a, 88f5aef, 0cea449; task review and scoped re-review clean)

| Tasks / interface | Producer → consumer | Finding / ruling |
| --- | --- | --- |
| Task 2 → Task 3 | InternalStore requires authoritative `internal_root` → provisioning | Task 3 keyring core can take/inject `internal_root`; Task 11 owns application user-data routing. |
| Task 3 → Task 5 / Task 10 | provisioning → roster import / verified initial backup | Conflict: Task 3 asks for full provisioning, while its required initial roster import and verified backup are produced only by later Tasks 5 and 10. Ruling: implement and test Task 3's dependency-ready envelope, password-policy, generation/CAS core now; expose explicit collaborators or defer full provisioning completion until Tasks 5 and 10. Cost if wrong: later integration work, but no fake roster/backup or unsafe CiXiS side effect is introduced. |

Task 3 core: complete (role-separated Argon2id envelopes, strong-password
policy, staged wrapper/CAS protocol, and restart reconciliation).
Task 3 full provisioning: deferred until Task 5 supplies the real idempotent
roster importer and Task 10 supplies verified initial backup. No fake
collaborator or success path is permitted before then.
Task 3: fix round 1/5 complete — Windows-safe atomic persistence, explicit
key/wrapper generations, one retained prior envelope per role, explicit
confirmations, and failure-window/all-role coverage added. Full provisioning
remains deferred to Tasks 5 and 10; no CiXiS write surface changed.
Task 3 core: complete (commits 2d24eab, 153d8f9; task review plus fix-round scoped re-review clean). Full first-run orchestration remains deferred to Tasks 5 and 10.
Task 4: complete. Electron-only channel/session boundary validates an exact
256-bit secret, keeps role capabilities in backend/Electron memory, requires
strict DRF authorization, applies unlock backoff, and revokes on lock, expiry,
or integrity failure. `/api/internal/roster/` remains a protected 501
placeholder for Task 6. Shutdown stays an injected callback for Task 11 to
wire to actual Electron child-process termination.
Task 3: recovery follow-up — generic retained-envelope access rejects God;
Task 10 must provide any God retained-envelope use through an explicit
recovery-only service boundary.
Task 4: fix round 1/5 complete — sessions revoke before shutdown callback;
callback failure is generic, visible, and retryable until callback success.
Only unpadded canonical URL-safe Base64 encodings of exactly 32 bytes authenticate;
standard Base64, padding, malformed pad bits, and malformed headers reject.
Task 4: scoped re-review accepted — retry state now also rejects fresh session
creation after a shutdown callback failure (commit d0bcc4c), preserving fail-closed
process replacement while the injected callback remains retryable. Fresh
`internal.tests` verification: 48 passed. Canonical unpadded URL-safe 32-byte
channel decoding and malformed-header rejection remain covered by the Task 4
boundary suite.
Task 5: complete — verified CiXiS profile contract, read-only active catalog,
and idempotent encrypted roster import are implemented. Import keys every
source employee by installation plus source ID, authenticates existing blind
indexes before reuse, and leaves a full CiXiS SQLite schema/row snapshot
unchanged. First-run provisioning is still deferred: Task 10 must supply the
real verified backup before import is wired into a successful provision path.
