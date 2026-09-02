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
