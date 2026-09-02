# Task 2 encrypted-store report

## Implementation

- Added `InternalStore` with its own supplied SQLite path; it imports no POS
  code and creates only internal encrypted-record, blind-index, nonce-registry,
  and live-manifest tables.
- Record AES-GCM AAD binds format version, installation ID, key generation,
  opaque UUID, record type, revision, and purpose. The public crypto helper
  still generates fresh random nonces; the store reserves a nonce in SQLite
  before encrypting.
- Added HMAC blind-index persistence and verification after payload
  decryption. Added authenticated per-domain manifests, verified before reads,
  to detect direct live-row insertion and deletion.
- Enables `secure_delete=ON` and `temp_store=MEMORY` for each internal-store
  connection.

## TDD evidence

Initial RED command:

```text
$ DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_store
Found 1 test(s).
System check identified no issues (0 silenced).
E
ModuleNotFoundError: No module named 'internal.store'
FAILED (errors=1)
```

Final GREEN command:

```text
$ DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests
Found 15 test(s).
System check identified no issues (0 silenced).
...............
Ran 15 tests in 0.016s
OK
```

## Files changed

- `backend/internal/crypto.py`
- `backend/internal/store.py`
- `backend/internal/tests/test_store.py`
- `docs/superpowers/plans/2026-09-02-cixis-internal-implementation.md`

## Self-review

- Records persist encrypted binary payloads only; Persian plaintext assertion
  confirms no payload plaintext in the SQLite database file.
- Tests mutate real SQLite rows for ciphertext, revision, blind-index,
  insertion, and deletion checks; no mock assertions are used.
- Nonce reservation has a `(key_generation, nonce)` unique constraint and a
  deterministic collision-retry test.

## Concerns

- Keyring anchoring of live-manifest generations and rollback detection belongs
  to Task 3's encrypted keyring/recovery protocol. This store fails closed for
  missing/mismatched manifests when live records remain, but cannot by itself
  distinguish a database rolled back together with every local artifact.

## Review fix round 1

Implementation commit: `88f5aef`

- `InternalStore` now derives its fixed `internal.sqlite3` path from a required
  authoritative `internal_root`. An optional path is validation-only and must
  equal that derived path before the root is created or SQLite is opened. Task
  11 can route its authoritative user-data directory through `internal_root`
  without importing or inspecting POS code.
- Normal reads verify every record type observed in records or manifests, so a
  direct insertion using a new unmanifested type fails closed.
- SQLite foreign-key enforcement is enabled and reported with the existing
  SQLite hardening pragmas. Removed duplicate manifest-wrapper docstring.

RED command and output:

```text
$ DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_store
Found 13 test(s).
System check identified no issues (0 silenced).
.....F..E....
ImportError: cannot import name 'StoreBoundaryError' from 'internal.store'
AssertionError: IntegrityError not raised
FAILED (failures=1, errors=1)
```

GREEN command and output:

```text
$ DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests
Found 17 test(s).
System check identified no issues (0 silenced).
.................
Ran 17 tests in 0.025s
OK
```

The new real-SQLite tests snapshot CiXiS `sqlite_master` and data before the
rejected constructor call, then assert both remain unchanged. They also insert
an unmanifested `advance` record directly and assert a normal roster read
rejects it.
