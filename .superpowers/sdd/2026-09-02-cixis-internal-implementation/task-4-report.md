# Task 4 auth/session boundary report

## Status

Implemented dependency-ready internal authentication boundary. It adds no
CiXiS or POS imports/writes and no roster data service.

## Delivered

- Electron channel header is a URL-safe Base64 encoding of exactly 32 bytes and
  is compared in constant time. Missing, malformed, and wrong channel values
  fail without reflecting secret material.
- `/api/internal/unlock/` requires that channel, authenticates role credentials
  through a runtime collaborator or Task 3 keyring, then returns a random,
  role-bound in-memory session token. Failed attempts use capped exponential
  backoff and generic responses.
- `ChannelSessionAuthentication` requires both channel and session token;
  `require_role` attaches it with explicit DRF role permissions. Supervisor and
  manager can reach only the Task 4 roster placeholder; God remains denied
  from operational-domain contract.
- Sessions expire after 15 minutes idle or 12 hours absolute. Lock, expiry,
  and failed integrity verification clear every session and invoke an injected
  shutdown callback. Task 11 owns wiring that callback to Electron process
  termination.
- `/lock/`, `/health/`, and protected `/roster/` route contracts exist. Roster
  returns 501 until Task 6 supplies real services/data.
- Internal-origin requests are rejected before DRF and no permissive CORS
  middleware/configuration is enabled.

## TDD evidence

RED, before route/auth implementation:

```text
$ DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_auth
Found 1 test(s).
Resolver404: path 'api/internal/roster/'
FAILED (errors=1)
```

GREEN:

```text
$ DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_auth
Found 8 test(s).
........
Ran 8 tests in 0.027s
OK

$ DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests
Found 46 test(s).
..............................................
Ran 46 tests in 36.156s
OK
```

Tests use Django/DRF requests and cover missing/wrong channel, valid unlock,
role denial, idle/absolute revocation, explicit lock callback, integrity
failure callback, unlock throttle, and browser-origin rejection.

## Deferred wiring

- Task 6 replaces roster placeholder; no data or service layer was invented.
- Task 10 supplies real integrity verifier.
- Task 11 supplies Electron main-process lifecycle callback and keeps secrets,
  tokens, and backend port out of renderer scope.

## Security fix round 1

`SessionRegistry.terminate()` now clears sessions before invoking its callback.
If the callback fails, it raises a generic `ShutdownCallbackFailed` error and
leaves termination pending, so a later `terminate()` retries it. A callback is
marked complete only after it returns. This preserves fail-closed session
revocation without silently suppressing a failed Electron termination request.

Channel parsing now accepts only canonical, unpadded URL-safe Base64 for exactly
32 bytes. It rejects standard `+`/`/` alphabet forms, `=` padding, nonzero
unused pad bits, and malformed values before constant-time comparison.

RED:

```text
$ DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_auth
Found 10 test(s).
FAIL: callback RuntimeError not raised
FAIL: standard Base64, padding, and noncanonical pad-bit channel headers returned 501, not 401
FAILED (failures=4)
```

GREEN:

```text
$ DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_auth
Found 10 test(s).
..........
Ran 10 tests in 0.029s
OK

$ DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests
Found 48 test(s).
................................................
Ran 48 tests in 26.396s
OK
```
