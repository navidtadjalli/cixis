# چیخیش اندرونی Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the separate, encrypted `چیخیش اندرونی` Electron product with safe CiXiS interoperability, complete staff-accounting workflows, paired releases, and acceptance-level tests.

**Architecture:** `backend/internal` is a Django app with its own settings, URLs, migration namespace, and SQLite database; its repository persists only encrypted binary payloads, blind indexes, manifests, and append-only audit records. `backend/pos` remains the CiXiS store and is read only by the internal backend except for its explicitly allowlisted compatibility/password-generation rows. A separate Electron main/preload/React entry point owns an ephemeral channel secret and all renderer-to-backend traffic.

**Tech Stack:** Python 3.13, Django 5.1, DRF, SQLite, `cryptography`, `argon2-cffi`, React 18, TypeScript, Vite, Electron 31, Vitest, Django test runner, GitHub Actions Windows builds.

**Spec:** `docs/superpowers/specs/2026-09-02-cixis-internal-design.md`

## Global Constraints

- `PRODUCT=pos` and `PRODUCT=internal` use the CiXiS brand; internal app ID is `com.cixis.internal`, its displayed product/shortcut name is `چیخیش اندرونی`, and it never uses port 8000.
- No internal model, table, index, trigger, or migration may be created in CiXiS SQLite. Internal storage is a separate, dedicated SQLite database in the internal user-data directory.
- CiXiS reads use a dedicated `mode=ro`, `query_only=ON` SQLite connection. Only the paired CiXiS migration and a narrow compare-and-swap password-generation writer may modify CiXiS.
- Encrypted payloads are AES-256-GCM with 96-bit fresh nonces and versioned AAD; password envelopes use Argon2id (16-byte salt, 64 MiB, 3 iterations, parallelism 1, 32 bytes); blind indexes are HMAC-SHA-256.
- Supervisor envelopes expose only operational keys. Manager envelopes expose operational and manager keys. God uses both only for provisioning, reset, recovery, and integrity tooling, never operational-domain APIs.
- Every live encrypted record is covered by a domain manifest and every domain action by an append-only, predecessor-bound audit chain. Database/keyring generation changes are journaled and recoverable.
- No sensitive plaintext may reach SQLite/WAL/journal/temp/backup/log/cache files, Electron storage/caches, errors, crash reports, or IPC logging.
- Strong role passwords have at least 12 Unicode characters, at least one letter and one non-letter, differ from the current password, and are not `1234` or `0000`.
- Renderer never receives channel secret, session token, key material, backend port, or decrypted persistence data beyond what an authorized screen displays. Every API requires valid channel and role-bound session tokens.
- Sessions expire after 15 idle minutes or 12 absolute hours. Lock, expiry, role password mutation, failed integrity, and quit terminate the backend process and require a fresh locked process.
- Business dates/months are Jalali only: UI accepts/displays Persian digits in `YYYY/MM/DD` and `YYYY/MM`; APIs/payloads use zero-padded ASCII `YYYY-MM-DD` and `YYYY-MM`; business time zone is `Asia/Tehran`.
- All domain mutation uses an immediate transaction, rechecks month locks, updates encrypted manifest/audit atomically, and rejects finalized month changes.
- Do not push, tag, publish, or modify remote state. Make small local commits only after their focused tests pass.

## Progress

- [x] Repository/spec inspection and baseline frontend test run.
- [x] Durable implementation plan written and self-reviewed.
- [ ] Task 1: Establish CiXiS compatibility settings and migration safety.
- [ ] Task 2: Create isolated internal Django runtime and encrypted persistence primitives.
- [ ] Task 3: Implement keyring, provisioning, and password-generation protocol.
- [ ] Task 4: Enforce channel/session authentication and role authorization.
- [ ] Task 5: Implement CiXiS compatibility checks, read-only catalog access, and roster import.
- [ ] Task 6: Implement Jalali contract and encrypted roster domain.
- [ ] Task 7: Implement attendance entry, calculations, and correction rules.
- [ ] Task 8: Implement product snapshots, exact money, and allowance allocation.
- [ ] Task 9: Implement advances, reports, corrections, finalization, and audit views.
- [ ] Task 10: Implement verified backup, restore, and crash recovery.
- [ ] Task 11: Build secure internal Electron host and IPC transport.
- [ ] Task 12: Build internal React screens and Jalali user experience.
- [ ] Task 13: Remove deprecated CiXiS tracker/password mutation surfaces and migrate legacy rows safely.
- [ ] Task 14: Build paired release pipeline and complete integration/security verification.

## File Map

| Path | Responsibility |
| --- | --- |
| `backend/pos/migrations/0017_internal_compatibility.py` | Seeds immutable installation/compatibility settings and copies the source God hash without changing POS data. |
| `backend/pos/migrations/0018_remove_legacy_staff_tracker.py` | Verified, one-time CiXiS backup plus exact legacy tracker-row clearing. |
| `backend/pos/internal_bridge.py` | Allowlisted AppSetting CAS writer and readonly CiXiS catalog/profile inspection. |
| `backend/internal_config/` | Dedicated Django settings, URL config, ASGI/WSGI for the internal product. |
| `backend/internal/crypto.py`, `keyring.py`, `store.py`, `recovery.py` | AEAD, blind indexes, role envelopes, encrypted SQLite persistence, journals, backup/restore. |
| `backend/internal/auth.py`, `permissions.py`, `services/` | Channel/session validation plus role-domain services. |
| `backend/internal/models.py`, `migrations/`, `repositories.py` | Internal-only encrypted-record tables and persistence boundary. |
| `backend/internal/jalali.py` | Persian digit normalization, real Jalali validation/conversion, Tehran business-date rules. |
| `backend/internal/views.py`, `urls.py` | Internal API only; no POS router imports. |
| `backend/internal/tests/` | Unit, transaction, tamper, role-denial, and end-to-end tests. |
| `frontend/internal/` | Separate Vite app entry, API client, screens, components, and tests. |
| `frontend/electron/internal-main.cjs`, `internal-preload.cjs` | Internal single-instance host, backend lifecycle, channel-secret IPC. |
| `frontend/electron-builder.internal.yml` | Internal app ID/name/icon/user-data release configuration. |
| `.github/workflows/windows-build.yml` | One `v*` run that tests then uploads exactly both CiXiS installers. |

---

### Task 1: Establish CiXiS compatibility settings and migration safety

**Files:**
- Create: `backend/pos/migrations/0017_internal_compatibility.py`, `backend/pos/internal_bridge.py`, `backend/pos/tests/test_internal_compatibility.py`
- Modify: `backend/pos/management/commands/init_settings.py`, `backend/config/settings.py`, `backend/requirements.txt`

**Interfaces:**
- Produces `internal_bridge.open_catalog_readonly(profile)`, `internal_bridge.compare_and_swap_password_setting(...)`, `internal_bridge.sqlite_schema_and_rows(path)`, and versioned `AppSetting` rows used by Tasks 3, 5, and 13.
- Consumes existing `AppSetting`, current God password hash, and `CIXIS_DB_PATH` rules without altering POS rows.

- [ ] **Step 1: Write failing compatibility tests**

```python
def test_migration_preserves_existing_god_hash_and_seeds_profile_settings(self):
    before = sqlite_snapshot(self.cixis_db)
    call_command("migrate", "pos", "0017_internal_compatibility")
    self.assertEqual(AppSetting.objects.get(key="god_password").value, before.god_hash)
    self.assertRegex(AppSetting.objects.get(key="cixis_installation_id").value, UUID_RE)
```

- [ ] **Step 2: Run the focused test and confirm it fails because settings/bridge do not exist**

Run: `rtk npm run test:backend -- pos.tests.test_internal_compatibility`

- [ ] **Step 3: Add minimal migration and bridge implementation**

```python
def open_catalog_readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA busy_timeout=3000")
    return connection
```

- [ ] **Step 4: Re-run focused test, add a write-rejection/CAS conflict case, and run full POS tests**

Run: `rtk npm run test:backend`

- [ ] **Step 5: Commit coherent migration/bridge change**

```bash
git add backend/pos backend/config/settings.py backend/requirements.txt
git commit -m "feat: add internal compatibility bridge"
```

### Task 2: Create isolated internal Django runtime and encrypted persistence primitives

**Files:**
- Create: `backend/internal_config/{__init__,settings,urls,wsgi,asgi}.py`, `backend/internal/{__init__,apps,models,crypto,repositories,store,views,urls}.py`, `backend/internal/migrations/{__init__,0001_initial}.py`, `backend/internal/tests/test_crypto_store.py`
- Modify: `backend/manage.py`, `backend/requirements.txt`

**Interfaces:**
- Produces `internal.store.InternalStore`, `EncryptedRecord`, `encrypt_payload`, `decrypt_payload`, `blind_index`, and `verify_live_manifest` for all domain tasks.
- Consumes only an internal database/keyring path supplied by Task 11; POS database access is forbidden here.

- [ ] **Step 1: Write failing crypto/store tests**

```python
def test_record_round_trip_has_no_plaintext_and_binds_its_revision(self):
    record = self.store.create("roster", {"name": "آرش", "jalali_date": "1405-06-11"})
    self.assertEqual(self.store.read(record.uuid)["name"], "آرش")
    self.assertNotIn("آرش".encode(), self.store.database_path.read_bytes())
    with self.assertRaises(IntegrityError): self.store.read_with_revision(record.uuid, record.revision + 1)
```

- [ ] **Step 2: Run test under `internal_config` and confirm missing-module failure**

Run: `cd backend && DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_crypto_store`

- [ ] **Step 3: Implement versioned AES-GCM records and internal-only schema**

```python
def encrypt_payload(key: bytes, aad: bytes, payload: Mapping[str, object]) -> Ciphertext:
    nonce = secrets.token_bytes(12)
    return Ciphertext(nonce=nonce, value=AESGCM(key).encrypt(nonce, canonical_json(payload), aad))
```

- [ ] **Step 4: Verify nonce uniqueness, tampered ciphertext, blind-index mismatch, manifest insertion/deletion, secure-delete, and temp-memory behavior**

Run: `cd backend && DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_crypto_store`

- [ ] **Step 5: Commit isolated runtime and encrypted-store primitives**

```bash
git add backend/internal backend/internal_config backend/manage.py backend/requirements.txt
git commit -m "feat: add encrypted internal storage runtime"
```

### Task 3: Implement keyring, provisioning, and password-generation protocol

**Files:**
- Create: `backend/internal/keyring.py`, `backend/internal/provisioning.py`, `backend/internal/tests/test_keyring.py`, `backend/internal/tests/test_provisioning.py`
- Modify: `backend/internal/store.py`, `backend/pos/internal_bridge.py`

**Interfaces:**
- Produces `validate_strong_password`, `InternalKeyring.provision`, `change_password`, `reset_role_password`, and `reconcile_generations` used by API/backup tasks.
- Consumes Task 1 CAS writer and Task 2 AEAD primitives; exposes keysets only to authorized service methods.

- [ ] **Step 1: Write failing role-envelope and password-policy tests**

```python
def test_supervisor_envelope_cannot_decrypt_manager_keyset(self):
    provisioned = provision_fixture()
    self.assertRaises(KeyAccessDenied, provisioned.keyring.unlock("supervisor", "قوی-رمز-۱۲۳۴" ).manager)

def test_password_policy_rejects_old_default_and_missing_nonletter(self):
    self.assertFalse(validate_strong_password("1234", current="old"))
    self.assertFalse(validate_strong_password("onlyletterslong", current="old"))
```

- [ ] **Step 2: Run focused tests and confirm absent provisioning/keyring behavior**

Run: `cd backend && DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_keyring internal.tests.test_provisioning`

- [ ] **Step 3: Implement Argon2id envelopes, staged generations, and idempotent provisioning**

```python
KDF_PARAMS = {"memory_cost": 65536, "time_cost": 3, "parallelism": 1, "hash_len": 32}
def derive_kek(password: str, salt: bytes) -> bytes:
    return hash_secret_raw(password.encode(), salt, Type.ID, **KDF_PARAMS)
```

- [ ] **Step 4: Test every injected pre-commit failure, exact current-password/confirmation rules, God reset, restart reconciliation, and initial verified backup**

Run: `cd backend && DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_keyring internal.tests.test_provisioning`

- [ ] **Step 5: Commit provision/recovery protocol**

```bash
git add backend/internal backend/pos/internal_bridge.py
git commit -m "feat: provision internal role keyrings"
```

### Task 4: Enforce channel/session authentication and role authorization

**Files:**
- Create: `backend/internal/auth.py`, `backend/internal/permissions.py`, `backend/internal/middleware.py`, `backend/internal/tests/test_auth.py`
- Modify: `backend/internal_config/settings.py`, `backend/internal/views.py`, `backend/internal/urls.py`

**Interfaces:**
- Produces `ChannelSessionAuthentication`, `require_role`, `SessionRegistry`, and `/api/internal/unlock/`, `/lock/`, `/health/` endpoints.
- Consumes an Electron-provided channel secret and Task 3 keyring roles; domain endpoints in Tasks 6–10 use these decorators only.

- [ ] **Step 1: Write failing authentication boundary tests**

```python
def test_domain_route_rejects_direct_http_and_wrong_channel(self):
    self.assertEqual(self.client.get("/api/internal/roster/").status_code, 401)
    self.assertEqual(self.channel_client("wrong").get("/api/internal/roster/").status_code, 401)
```

- [ ] **Step 2: Run auth tests and confirm unauthenticated routes are not yet protected**

Run: `cd backend && DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_auth`

- [ ] **Step 3: Implement in-memory role tokens, exponential unlock throttling, and strict DRF authentication**

```python
def require_role(*roles: Role):
    return permission_classes([ChannelSessionAuthentication, RolePermission(roles)])
```

- [ ] **Step 4: Verify manager/supervisor/God denials, idle/absolute expiry, lock revocation, failed-integrity shutdown hook, and no CORS allowance**

Run: `cd backend && DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_auth`

- [ ] **Step 5: Commit authentication boundary**

```bash
git add backend/internal backend/internal_config
git commit -m "feat: secure internal channel sessions"
```

### Task 5: Implement CiXiS compatibility checks, read-only catalog access, and roster import

**Files:**
- Create: `backend/internal/compatibility.py`, `backend/internal/catalog.py`, `backend/internal/importer.py`, `backend/internal/tests/test_compatibility.py`, `backend/internal/tests/test_importer.py`
- Modify: `backend/internal/provisioning.py`

**Interfaces:**
- Produces `verify_cixis_profile`, `CatalogReader.active_products`, and `import_initial_roster` for provisioning and staff orders.
- Consumes Task 1 profile rows/readonly bridge and Task 2 encrypted records.

- [ ] **Step 1: Write failing fail-closed and idempotent-import tests**

```python
def test_import_is_idempotent_by_installation_and_source_employee_id(self):
    first = import_initial_roster(self.profile)
    second = import_initial_roster(self.profile)
    self.assertEqual((first.created, second.created), (2, 0))

def test_catalog_write_attempt_is_rejected(self):
    with self.assertRaises(sqlite3.OperationalError): self.catalog.connection.execute("DELETE FROM pos_product")
```

- [ ] **Step 2: Run tests and confirm compatibility/import services are missing**

Run: `cd backend && DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_compatibility internal.tests.test_importer`

- [ ] **Step 3: Implement header, installation-ID, fingerprint, app-version, port, and legacy-table checks plus catalog snapshot reader**

```python
def verify_cixis_profile(profile: CixisProfile) -> None:
    require_sqlite_header(profile.database_path)
    require_exact_fingerprint(profile.database_path, profile.fingerprint)
    require_empty_legacy_tracker_tables(profile.database_path)
```

- [ ] **Step 4: Verify missing/moved/wrong/new/old/running CiXiS blocks startup and source employee/POS/menu rows never change**

Run: `cd backend && DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_compatibility internal.tests.test_importer`

- [ ] **Step 5: Commit compatibility and catalog bridge**

```bash
git add backend/internal backend/pos/internal_bridge.py
git commit -m "feat: validate cixis profile for internal app"
```

### Task 6: Implement Jalali contract and encrypted roster domain

**Files:**
- Create: `backend/internal/jalali.py`, `backend/internal/services/roster.py`, `backend/internal/tests/test_jalali.py`, `backend/internal/tests/test_roster.py`
- Modify: `backend/internal/views.py`, `backend/internal/urls.py`, `backend/internal/repositories.py`

**Interfaces:**
- Produces `parse_jalali_date`, `parse_jalali_month`, `tehran_today`, `RosterService`, and roster APIs for Tasks 7–10.
- Consumes authenticated manager/supervisor sessions and imported stable UUID identities.

- [ ] **Step 1: Write failing Jalali and role tests**

```python
def test_persian_digits_normalize_and_real_leap_date_validates(self):
    self.assertEqual(parse_jalali_date("۱۴۰۳/۱۲/۳۰"), "1403-12-30")
    with self.assertRaises(JalaliValidationError): parse_jalali_date("1402/12/30")

def test_supervisor_cannot_deactivate_roster_member(self):
    self.assertEqual(self.supervisor.delete(self.member_url).status_code, 403)
```

- [ ] **Step 2: Run tests and confirm desired API is absent**

Run: `cd backend && DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_jalali internal.tests.test_roster`

- [ ] **Step 3: Implement calendar parser and encrypted roster CRUD**

```python
def assert_mutable_business_date(value: str, finalized_months: FinalizedMonths) -> str:
    normalized = parse_jalali_date(value)
    if normalized > tehran_today() or finalized_months.contains(normalized[:7]): raise DateLockedError()
    return normalized
```

- [ ] **Step 4: Verify sort/filter, add/edit rights, manager-only soft deletion/reactivation, name updates for open data, and frozen snapshots remain untouched**

Run: `cd backend && DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_jalali internal.tests.test_roster`

- [ ] **Step 5: Commit Jalali and roster behavior**

```bash
git add backend/internal
git commit -m "feat: add encrypted internal roster"
```

### Task 7: Implement attendance entry, calculations, and correction rules

**Files:**
- Create: `backend/internal/services/attendance.py`, `backend/internal/tests/test_attendance.py`
- Modify: `backend/internal/repositories.py`, `backend/internal/views.py`, `backend/internal/urls.py`

**Interfaces:**
- Produces `calculate_attendance`, `AttendanceService.create`, and preview/confirm correction APIs.
- Consumes Task 6 staff/date rules and Task 4 role sessions.

- [ ] **Step 1: Write failing metric, duplicate, role, and finalized-month tests**

```python
def test_evening_cross_midnight_reports_exact_metrics(self):
    metrics = calculate_attendance("evening", 16, 33, 1, 10)
    self.assertEqual((metrics.worked, metrics.late, metrics.overtime), (517, 33, 70))

def test_equal_times_count_as_24_hours(self):
    self.assertEqual(calculate_attendance("morning", 9, 0, 9, 0).worked, 1440)
```

- [ ] **Step 2: Run tests and observe missing attendance service failure**

Run: `cd backend && DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_attendance`

- [ ] **Step 3: Implement integer-minute calculation and one-row-per-staff/date/shift persistence**

```python
SHIFT_START = {"morning": 9 * 60, "evening": 16 * 60}
SHIFT_END = {"morning": 17 * 60, "evening": 24 * 60}
```

- [ ] **Step 4: Verify all numeric bounds, both shifts, duplicate rejection, supervisor immutability, manager preview token conflict, audit append, and transaction rollback**

Run: `cd backend && DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_attendance`

- [ ] **Step 5: Commit attendance domain**

```bash
git add backend/internal
git commit -m "feat: add encrypted staff attendance"
```

### Task 8: Implement product snapshots, exact money, and allowance allocation

**Files:**
- Create: `backend/internal/services/orders.py`, `backend/internal/services/allowances.py`, `backend/internal/tests/test_staff_orders.py`, `backend/internal/tests/test_allowances.py`
- Modify: `backend/internal/catalog.py`, `backend/internal/repositories.py`, `backend/internal/views.py`, `backend/internal/urls.py`

**Interfaces:**
- Produces canonical `parse_quantity`, `StaffOrderService.create`, `AllowanceService.preview`, and frozen allocation values used by Task 9.
- Consumes readonly catalog and stored Jalali staff records.

- [ ] **Step 1: Write failing decimal/snapshot/allocation tests**

```python
def test_rejects_json_number_and_preserves_exact_snapshot_total(self):
    response = self.supervisor.post(self.orders_url, {"quantity": 1.5})
    self.assertEqual(response.status_code, 400)
    saved = create_order(quantity="1.25", unit_price=17)
    self.assertEqual(saved.payload["line_total"], "21.25")
```

- [ ] **Step 2: Run focused tests and confirm parser/service failures**

Run: `cd backend && DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_staff_orders internal.tests.test_allowances`

- [ ] **Step 3: Implement canonical decimal parser, consistent source snapshot, and chronological allowance allocation**

```python
QUANTITY_RE = re.compile(r"^[0-9]{1,8}(\\.[0-9]{1,2})?$")
def parse_quantity(raw: object) -> Decimal:
    if not isinstance(raw, str) or not QUANTITY_RE.fullmatch(raw): raise ValidationError("quantity")
    return Decimal(raw)
```

- [ ] **Step 4: Verify zero/negative/overflow rejection, product precedence after exhaustion, fractions, inactive menu snapshots, configuration previews, and finalized allocation freeze**

Run: `cd backend && DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_staff_orders internal.tests.test_allowances`

- [ ] **Step 5: Commit order and allowance domains**

```bash
git add backend/internal
git commit -m "feat: track staff orders and allowances"
```

### Task 9: Implement advances, reports, corrections, finalization, and audit views

**Files:**
- Create: `backend/internal/services/advances.py`, `backend/internal/services/reports.py`, `backend/internal/services/finalization.py`, `backend/internal/services/corrections.py`, `backend/internal/tests/test_advances.py`, `backend/internal/tests/test_finalization.py`, `backend/internal/tests/test_corrections.py`, `backend/internal/tests/test_audit.py`
- Modify: `backend/internal/repositories.py`, `backend/internal/views.py`, `backend/internal/urls.py`

**Interfaces:**
- Produces manager-only advance APIs, open/finalized report APIs, signed correction tokens, immutable month snapshots, and merged manager audit chronology.
- Consumes Tasks 6–8 encrypted source records and Task 2 transaction/manifest API.

- [ ] **Step 1: Write failing aggregation/atomicity/snapshot tests**

```python
def test_finalize_creates_one_immutable_snapshot_and_blocks_later_write(self):
    finalized = self.manager.post(finalize_url("1405-05"), {"confirm": True})
    self.assertEqual(finalized.status_code, 201)
    self.assertEqual(self.manager.post(advance_url, advance_payload).status_code, 409)

def test_failed_finalization_keeps_month_open(self):
    with inject_commit_failure(): self.manager.post(finalize_url("1405-05"), {"confirm": True})
    self.assertFalse(self.reports.month_is_finalized("1405-05"))
```

- [ ] **Step 2: Run tests and confirm report/finalization APIs are absent**

Run: `cd backend && DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_advances internal.tests.test_finalization internal.tests.test_corrections internal.tests.test_audit`

- [ ] **Step 3: Implement manager-only advances and sorted immediate-transaction finalization**

```python
with store.immediate_transaction(lock_months=sorted(affected_months)):
    assert_preview_token_current(token)
    assert_not_finalized(month)
    snapshot = recompute_month(month)
    store.save_final_snapshot(month, snapshot)
```

- [ ] **Step 4: Verify prior open month reports, inactive historical staff, exact totals, stale/cross-month previews, concurrent mutation race, audit append-only rules, and read-only finalized detail**

Run: `cd backend && DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_advances internal.tests.test_finalization internal.tests.test_corrections internal.tests.test_audit`

- [ ] **Step 5: Commit reports, audits, and finalization**

```bash
git add backend/internal
git commit -m "feat: finalize encrypted staff months"
```

### Task 10: Implement verified backup, restore, and crash recovery

**Files:**
- Create: `backend/internal/recovery.py`, `backend/internal/tests/test_recovery.py`, `backend/internal/tests/test_plaintext_scan.py`
- Modify: `backend/internal/keyring.py`, `backend/internal/store.py`, `backend/internal/provisioning.py`

**Interfaces:**
- Produces `create_verified_backup`, `restore_verified_backup`, and `reconcile_generation_directories` used at startup and password flows.
- Consumes internal database/keyring generations and God-only recovery session.

- [ ] **Step 1: Write failing backup/restore/tamper tests**

```python
def test_restore_tampered_bundle_never_replaces_live_generation(self):
    live = self.store.current_generation
    bundle = create_verified_backup(self.store, self.keyring)
    bundle.database.write_bytes(bundle.database.read_bytes()[:-1] + b"x")
    with self.assertRaises(RecoveryVerificationError): restore_verified_backup(bundle, god_password)
    self.assertEqual(self.store.current_generation, live)
```

- [ ] **Step 2: Run recovery tests and observe absent backup/recovery behavior**

Run: `cd backend && DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_recovery internal.tests.test_plaintext_scan`

- [ ] **Step 3: Implement online backup, inventory, full verify-to-temp, and atomic current-pointer replacement**

```python
source.backup(destination)
verify_sqlite(destination)
verify_every_ciphertext_and_manifest(destination, keyring)
atomic_replace(current_pointer, verified_generation_pointer)
```

- [ ] **Step 4: Verify interrupted backups/restores, incomplete swap reconciliation, wrong historical God credential, WAL/temp/log/cache plaintext scans, and whole-set rollback limitation text**

Run: `cd backend && DJANGO_SETTINGS_MODULE=internal_config.settings .venv/bin/python manage.py test internal.tests.test_recovery internal.tests.test_plaintext_scan`

- [ ] **Step 5: Commit recovery system**

```bash
git add backend/internal
git commit -m "feat: add verified internal recovery"
```

### Task 11: Build secure internal Electron host and IPC transport

**Files:**
- Create: `frontend/electron/internal-main.cjs`, `frontend/electron/internal-preload.cjs`, `frontend/electron-builder.internal.yml`, `frontend/internal/vite.config.ts`, `frontend/internal/index.html`, `frontend/internal/tests/electron-contract.test.ts`
- Modify: `frontend/package.json`, `frontend/scripts/gen-brand.mjs`

**Interfaces:**
- Produces `window.internalApi` sender-validated request bridge, distinct internal data/log paths, random per-launch channel secret, OS-assigned backend port, and safe backend lifecycle.
- Consumes Tasks 3–5 backend startup arguments and routes.

- [ ] **Step 1: Write failing Electron security/lifecycle tests**

```typescript
it("does not expose channel secret or backend port to renderer", () => {
  expect(Object.keys(window.internalApi)).not.toContain("channelSecret");
  expect(Object.keys(window.internalApi)).not.toContain("backendPort");
});
```

- [ ] **Step 2: Run focused Vitest contract test and confirm internal preload is absent**

Run: `rtk npm --prefix frontend test -- internal/tests/electron-contract.test.ts`

- [ ] **Step 3: Implement separate app lock/window/process host and narrow preload**

```javascript
contextBridge.exposeInMainWorld("internalApi", {
  request: (request) => ipcRenderer.invoke("internal:request", request),
  lock: () => ipcRenderer.invoke("internal:lock"),
});
```

- [ ] **Step 4: Verify sandbox/context isolation/node integration/navigation/window denial, sender validation, port collision retry, app quit lock/kill, and distinct CiXiS ownership**

Run: `rtk npm --prefix frontend test -- internal/tests/electron-contract.test.ts`

- [ ] **Step 5: Commit secure Electron host**

```bash
git add frontend/electron frontend/internal frontend/electron-builder.internal.yml frontend/package.json
git commit -m "feat: add secure internal electron host"
```

### Task 12: Build internal React screens and Jalali user experience

**Files:**
- Create: `frontend/internal/src/{main,App,index.css}.tsx`, `frontend/internal/src/lib/{api,jalali,format}.ts`, `frontend/internal/src/components/{TileGrid,JalaliInput,PasswordGate}.tsx`, `frontend/internal/src/screens/{Roster,StaffOrders,Attendance,Advances,OpenReports,FinalReports,AllowanceSettings,PasswordChange,PasswordManagement}.tsx`, `frontend/internal/src/__tests__/internal-flow.test.tsx`
- Modify: `frontend/package.json`

**Interfaces:**
- Produces Persian RTL internal navigation and role-gated screens calling only `window.internalApi.request`.
- Consumes Task 11 bridge and Task 6–10 JSON contracts.

- [ ] **Step 1: Write failing screen-flow tests**

```tsx
it("shows manager-only مساعده after manager unlock and uses Persian Jalali input", async () => {
  render(<App />);
  await unlockAs("manager");
  await user.click(screen.getByRole("link", { name: "مساعده" }));
  expect(screen.getByDisplayValue("۱۴۰۵/۰۶/۱۱")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run focused UI test and confirm separate app entry/screens are absent**

Run: `rtk npm --prefix frontend test -- internal/src/__tests__/internal-flow.test.tsx`

- [ ] **Step 3: Implement tile-grid, role navigation, error states, and Jalali-only inputs**

```tsx
<TileGrid members={activeMembers} selectedId={staffId} onSelect={setStaffId} />
```

- [ ] **Step 4: Verify screen access by role, keyboard tile activation, current versus frozen names, correction preview/confirmation, finalized read-only detail, and no raw internal API URL use**

Run: `rtk npm --prefix frontend test -- internal/src/__tests__/internal-flow.test.tsx`

- [ ] **Step 5: Commit internal frontend**

```bash
git add frontend/internal frontend/package.json
git commit -m "feat: add internal staff accounting screens"
```

### Task 13: Remove deprecated CiXiS tracker/password mutation surfaces and migrate legacy rows safely

**Files:**
- Create: `backend/pos/migrations/0018_remove_legacy_staff_tracker.py`, `backend/pos/tests/test_legacy_tracker_removal.py`
- Modify: `backend/pos/urls.py`, `backend/pos/views/attendance.py`, `backend/pos/views/misc.py`, `backend/pos/serializers.py`, `frontend/src/App.tsx`, `frontend/src/components/Sidebar.tsx`, `frontend/src/screens/{AttendanceEntryScreen,StaffReportScreen}.tsx`, `frontend/src/components/FreeAllowanceConfig.tsx`, affected POS tests

**Interfaces:**
- Produces empty preserved legacy tracker tables and CiXiS routes/UI free of deprecated tracker and password-mutation surfaces.
- Consumes Task 1 backup/profile helper and leaves only allowlisted internal password mutation service.

- [ ] **Step 1: Write failing isolation/removal tests**

```python
def test_cleanup_deletes_only_tracker_rows_after_verified_online_backup(self):
    before = sqlite_snapshot(self.db)
    call_command("migrate", "pos", "0018_remove_legacy_staff_tracker")
    self.assertEqual(tracker_row_counts(self.db), (0, 0))
    self.assertEqual(non_tracker_rows(self.db), before.non_tracker_rows)
```

- [ ] **Step 2: Run focused tests and confirm legacy UI/routes are still present**

Run: `rtk npm run test:backend -- pos.tests.test_legacy_tracker_removal`

- [ ] **Step 3: Implement verified online backup-and-clear migration and remove obsolete endpoints/navigation**

```python
with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as source:
    source.backup(backup_connection)
assert_verified_backup(backup_path)
ShiftAttendance.objects.all().delete()
StaffConsumption.objects.all().delete()
```

- [ ] **Step 4: Verify backup/integrity/command failure aborts safely, schemas remain, legacy password routes return 404, and every POS/menu/payment/closing/employee row is unchanged**

Run: `rtk npm run test:backend && rtk npm run test:frontend`

- [ ] **Step 5: Commit CiXiS cleanup boundary**

```bash
git add backend/pos frontend/src
git commit -m "feat: retire legacy staff tracker"
```

### Task 14: Build paired release pipeline and complete integration/security verification

**Files:**
- Create: `backend/internal/tests/test_release_bundle.py`, `frontend/internal/tests/runtime-integration.test.ts`
- Modify: `.github/workflows/windows-build.yml`, `frontend/electron-builder.yml`, `frontend/electron-builder.internal.yml`, `backend/build_win_python.py`, `backend/requirements.txt`, root `package.json`, `README.md`

**Interfaces:**
- Produces a `v*` workflow that gates backend/frontend tests and uploads exactly `cixis-windows-installer` and `cixis-internal-windows-installer`; Majaz workflow remains `m-v*` and excludes internal output.
- Consumes all completed product build entries and backend crypto dependencies.

- [ ] **Step 1: Write failing bundle/release contract tests**

```python
def test_windows_bundle_imports_argon2_and_cryptography_and_round_trips_aead(self):
    result = run_embedded_python("from internal.crypto import smoke; smoke()")
    self.assertEqual(result.returncode, 0, result.stderr)
```

- [ ] **Step 2: Run focused release/runtime tests and confirm current build emits only POS installer**

Run: `rtk npm run test:backend -- internal.tests.test_release_bundle`

- [ ] **Step 3: Implement dependency pins, paired build scripts, version/fingerprint injection, and test-gated artifact upload**

```yaml
- name: Upload internal installer
  uses: actions/upload-artifact@v5
  with:
    name: cixis-internal-windows-installer
    path: frontend/release-internal/*.exe
    if-no-files-found: error
```

- [ ] **Step 4: Run full required verification including isolation/tamper/failure-injection suites, POS and frontend suites, production builds, and workflow lint/inspection**

Run: `rtk npm run test:backend && rtk npm run test:frontend && rtk npm run build`

- [ ] **Step 5: Commit release and verification changes**

```bash
git add .github backend frontend package.json README.md
git commit -m "feat: ship paired cixis internal releases"
```

## Plan Self-Review

**Spec coverage:** Tasks 1, 5, and 13 cover CiXiS compatibility, read-only isolation, password settings, and legacy cleanup. Tasks 2–4 and 10 cover encryption, key hierarchy, provisioning, channel/session security, integrity, journals, backups, and recovery. Tasks 6–9 cover every staff domain behavior, Jalali contract, correction/revision/audit rules, reports, and immutable finalization. Tasks 11–12 cover a separate product process, secure IPC, and all required navigation. Task 14 covers paired artifacts and Windows dependency smoke evidence.

**Placeholder scan:** No deferred or unspecified task markers are present; each task names concrete files, interfaces, test behavior, execution command, implementation shape, and commit.

**Type consistency:** All domain tasks call `InternalStore` through repositories/services, use canonical Jalali strings, authenticate through `ChannelSessionAuthentication`, and make role decisions through `require_role`. Finalization consumes attendance/order/advance repository records and returns snapshot payloads used by the React final-report screen.
