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
