# Task 3 keyring/password core report

## Status

Implemented dependency-ready Task 3 core. It creates a versioned encrypted
keyring below a supplied authoritative `internal_root`; it does not create an
internal store, import a roster, or claim an initial backup.

## Implementation

- Added AES-256-GCM password envelopes over independent operational and manager
  256-bit keysets. Each envelope records Argon2id parameters, a fresh 16-byte
  salt, fresh 96-bit nonce, installation ID, role, key generation, and wrapper
  generation; envelope AAD binds all of that metadata.
- `derive_kek` uses Argon2id: 64 MiB, 3 iterations, parallelism 1, 32-byte
  result. Keyring writes are atomic, file-fsynced, directory-fsynced, and mode
  0600.
- Supervisor unlock exposes operational material only; manager exposes both;
  ordinary God unlock is denied and recovery-only God unlock is limited to
  reset/recovery methods.
- Added Unicode-aware strong-password validation: at least 12 characters, at
  least one letter and one non-letter, not `1234`/`0000`, different from a
  supplied current password, and exact confirmation when supplied.
- Added staged wrapper generations plus `change_password`, God reset, and
  restart reconciliation. Services require an explicit Task 1 CAS collaborator
  before activating a staged wrapper; CAS conflict preserves a recoverable
  staged state.

## TDD evidence

Initial RED command:

```text
$ DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_keyring internal.tests.test_provisioning -v 2
Found 8 test(s).
ModuleNotFoundError: No module named 'internal.keyring'
ModuleNotFoundError: No module named 'internal.provisioning'
FAILED (errors=8)
```

Safety-gap RED command:

```text
$ DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_provisioning -v 2
Found 5 test(s).
FAIL: test_god_reset_requires_the_real_cixis_cas_collaborator
AssertionError: ValueError not raised
FAILED (failures=1)
```

Final GREEN evidence:

```text
$ DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_keyring internal.tests.test_provisioning internal.tests.test_crypto internal.tests.test_store internal.tests.test_settings -v 1
Found 27 test(s).
...........................
Ran 27 tests in 4.928s
OK

$ .venv/bin/python manage.py test pos.tests.test_internal_compatibility -v 1
Found 5 test(s).
.....
Ran 5 tests in 0.852s
OK
```

The last focused keyring/provisioning run after the CAS safety regression added
found 10 tests and passed. `git diff --check` and Python byte compilation also
completed with exit status 0.

## Files changed

- `backend/internal/keyring.py`
- `backend/internal/provisioning.py`
- `backend/internal/tests/test_keyring.py`
- `backend/internal/tests/test_provisioning.py`
- `docs/superpowers/plans/2026-09-02-cixis-internal-implementation.md`

## Self-review

- Tests exercise real Argon2id/AES-GCM, file persistence, restart loading, and
  envelope decryptions. They prove a supervisor cannot access manager material,
  normal God unlock is denied, and recovery-only God reset re-wraps target keys.
- A failed CAS retains the old usable envelope after reconciliation; a committed
  generation activates the staged wrapper. Reset cannot stage anything when
  CAS collaborators are absent.
- The Task 1 bridge remains unchanged. Existing real Django test-DB tests prove
  its allowlisted CAS remains limited to password/generation rows.

## Deferrals / concerns

- Full first-run provisioning is intentionally deferred. Task 5 must provide a
  real idempotent roster importer and Task 10 a verified-backup collaborator;
  no fake success path exists here.
- This core accepts CAS/hash collaborators by injection to preserve the internal
  product's POS-import boundary. API wiring must pass Task 1's
  `compare_and_swap_password_setting` plus current hashes/generations once Task
  4 session services exist.

## Review fix round 1

### Root causes corrected

- `_persist` called POSIX-only `os.fchmod` and opened a directory with
  `os.O_DIRECTORY` unconditionally. It now preserves file flush plus atomic
  replace everywhere, while POSIX mode/directory fsync run only off Windows.
- `UnlockedKeysets.generation` conflated the immutable data-key generation with
  the mutable password-wrapper generation. It now exposes `key_generation` and
  `wrapper_generation` separately; a re-wrap keeps `key_generation == 1` and
  a reopened `InternalStore` can still decrypt existing records.
- Activation/reconciliation discarded active wrappers. State now retains the
  immediately prior envelope per role, validates retained metadata on load,
  and authenticates it only through `unlock_retained` until backup cleanup.
- New password confirmation is mandatory. Provisioning requires a complete
  explicit role-confirmation mapping; stage/change/reset paths carry the exact
  supplied confirmation rather than echoing the new password.

### Review RED/GREEN evidence

RED command:

```text
$ DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_keyring internal.tests.test_provisioning -v 2
Found 14 test(s).
ERROR: ...test_windows_persistence... AttributeError from os.fchmod
ERROR: ...test_unlocked_keysets... no attribute 'key_generation'
ERROR: ...test_activation_retains... no attribute 'unlock_retained'
FAIL: ...test_provisioning_rejects... ValueError not raised
FAILED (failures=1, errors=3)
```

GREEN commands:

```text
$ DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_keyring internal.tests.test_provisioning -v 1
Found 20 test(s).
....................
Ran 20 tests in 10.633s
OK

$ DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests -v 1
Found 37 test(s).
.....................................
Ran 37 tests in 10.647s
OK

$ DJANGO_SETTINGS_MODULE=config.settings .venv/bin/python manage.py test pos.tests.test_internal_compatibility -v 1
Found 5 test(s).
.....
Ran 5 tests in 0.856s
OK
```

The focused coverage injects failures before/after staged persistence, during
password hashing/CAS, and after successful CAS before activation. Each asserts
a real reloaded keyring retains at least one authorized envelope; manager/God
self-change, God manager-reset, retained generation N, and Windows behavior
are covered. Python compilation and `git diff --check` also passed.

## Recovery follow-up

- `unlock_retained` now rejects the God role, so an old recovery envelope
  cannot bypass God’s recovery-only access boundary through the generic retained
  wrapper API. Future Task 10 recovery/backup wiring must expose any needed God
  retained-envelope path as an explicit recovery-only service method.
- RED/GREEN: `test_generic_retained_unlock_rejects_god_envelopes` first failed
  because generic retained unlock returned God material; it passes after the
  role gate was added.
- Final recovery verification: focused keyring/provisioning suite passed 21
  tests; full `internal.tests` suite passed 38 tests; POS compatibility under
  `config.settings` passed 5 tests; `git diff --check` passed.
