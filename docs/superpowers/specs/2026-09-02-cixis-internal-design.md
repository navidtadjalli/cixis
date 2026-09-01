# چیخیش اندرونی Design

## Purpose

Build `چیخیش اندرونی` as a separate Electron product for CiXiS staff
accounting. It replaces the CiXiS screens called `ثبت حضور و مصرف` and
`گزارش ماهانه پرسنل`, works whether CiXiS is open or closed, and ships beside
CiXiS from every CiXiS version tag.

It provides:

- staff roster management;
- staff-order entry;
- attendance entry;
- advances (`مساعده`);
- free-item allowance settings;
- open Jalali-month calculations; and
- immutable finalized Jalali-month reports.

It never calculates salary. Reports show worked time and total advances, plus
the retained attendance and staff-consumption metrics.

## Product and Release Boundary

`چیخیش اندرونی` is a product variant, not a third cafe brand. The build matrix
distinguishes `PRODUCT=pos` from `PRODUCT=internal`; both use the CiXiS brand.

The internal product has:

- Electron app ID `com.cixis.internal`;
- product and shortcut name `چیخیش اندرونی`;
- its own icon, window, single-instance lock, logs, and user-data directory;
- a dedicated React entry point and navigation;
- dedicated Django settings, URL configuration, installed app, and migration
  namespace; and
- an OS-assigned localhost backend port rather than CiXiS port 8000.

A `v*` GitHub tag builds CiXiS and the internal installer from one checkout,
commit, semantic version, backend source tree, and compatibility fingerprint.
The release job runs backend and frontend tests first and uploads exactly:

- `cixis-windows-installer`; and
- `cixis-internal-windows-installer`.

Neither artifact is published when tests fail or either installer fails. The
derived tag version is injected into both frontend packages and backend
runtimes. Majaz keeps its existing `m-v*` release namespace and does not build
the internal product.

## Threat Model and Security Guarantee

All cafe users share one Windows login. This design protects internal data:

- at rest;
- in backups;
- while the internal app is locked or closed;
- against ordinary SQLite/file inspection;
- against undetected row modification, insertion, or deletion; and
- against direct calls to localhost APIs without an authenticated app channel
  and role session.

The protected set is data created in the new internal store. Existing CiXiS
`Employee` names, menu rows, password hashes, legacy quota columns, historical
CiXiS backups, and any unused legacy tracker rows predate this store and remain
outside its confidentiality guarantee. The user explicitly chose to preserve
CiXiS employee names and stated that the old tracker was not used. Internal
copies and every new/changed allowance value are encrypted; the legacy quota
columns become non-authoritative and are never updated by the internal app.

It cannot protect data that an authorized screen deliberately shows, or defeat
a determined attacker who knows an authorized role password and inspects or
modifies an already unlocked process under the same Windows account. It also
cannot detect rollback of the internal database, keyring, and all backups as
one complete set to an older authentic set without a remote or OS-isolated
monotonic anchor. Those stronger guarantees require separate Windows accounts
or a remote service and are outside this scope.

Supervisor credentials can decrypt only supervisor-visible operational data.
Manager-only advances, manager audit details, and finalized reports use a
separate key. God can decrypt keysets only inside password reset, recovery, and
integrity tooling; a God session does not authorize operational domain screens
or APIs. Manager remains the only role that inherits supervisor operations.

## Cryptographic Storage

The internal product owns a separate SQLite database and keyring inside its own
user-data directory. CiXiS operational data never enters this database except
for explicit product and initial-roster snapshots.

### Keys and envelopes

First-run provisioning creates two independent random 256-bit keysets:

- operational keyset: data-encryption, blind-index, and integrity keys for
  roster, attendance, staff orders, and their operational audit events; and
- manager keyset: data-encryption, blind-index, and integrity keys for advances,
  allowance configuration, audit data, and finalized snapshots.

Supervisor password envelopes contain only the operational keyset. Manager and
God envelopes contain both keysets, but God may use them only in reset/recovery
services. Each domain has its own authenticated live-record manifest and
append-only audit chain. Manager report APIs merge both audit streams;
supervisor APIs never expose either stream. Key generations and formats are
versioned.

Each password key-encryption key is derived with Argon2id using a unique random
16-byte salt, 64 MiB memory, three iterations, parallelism one, and a 32-byte
result. Parameters and format version are stored with the envelope so a later
release can migrate them.

Records and key envelopes use AES-256-GCM with a fresh cryptographically random
96-bit nonce for every encryption. Authenticated additional data binds format
version, installation ID, role/envelope generation, key generation, opaque
record UUID, record type, and record revision. A unique constraint covers
`(key_generation, nonce)`; generation retries a collision before encryption,
so a nonce is never reused with a key.

Searchable staff/month values use HMAC-SHA-256 blind indexes from the applicable
domain keyset. On decryption, the backend recomputes and verifies every blind
index. An authenticated manifest covers the expected UUID, type, and revision
of every live record, detecting direct row deletion or insertion. Each manifest
and audit-chain head/sequence is also anchored in the encrypted keyring.
Database and keyring generation changes use a crash-recovery journal, so
replaying only one file is detected. Each append-only audit chain binds an
entry to its predecessor.

Only schema version, key/wrapper generation, opaque UUIDs, record types,
ciphertext lengths, row counts, and equality of blind indexes may remain
observable. Names, dates, times, prices, quantities, notes, totals, audit
timestamps, and role actions must not appear as plaintext in:

- SQLite tables, indexes, freelists, journals, or WAL files;
- temporary files;
- backups;
- Electron storage or caches;
- backend/frontend logs;
- errors or crash reports; or
- IPC payload logging.

SQLite uses `secure_delete=ON` and memory-backed temporary storage. Domain
models persist encrypted binary payloads only; decrypted payloads never pass
through plaintext ORM columns.

The Windows embedded-Python build installs pinned, CPython-3.13-compatible
`cryptography` and Argon2 dependencies. CI imports them and performs an
encrypt/decrypt smoke test inside the produced Windows bundle.

### Backups and recovery

Backups freeze one committed generation and use SQLite's online backup API,
never raw live-file copying. Each backup bundle contains an encrypted database
snapshot, matching encrypted keyring, recovery journal, schema/key/wrapper
generations, integrity manifest, application version, and SHA-256 inventory.
Creation succeeds only after SQLite integrity checks and full cryptographic
verification.

A password change immediately creates a new backup bundle. A bundle is restored
with the God credential valid for that bundle. Restore first verifies inventory,
SQLite integrity, every ciphertext/tag, manifest, audit chain, schema version,
and complete decryption in a temporary location. Only then may it replace the
live store. Interrupted verification or replacement leaves the current store
untouched. Older bundles retain their matching keyring and therefore require
the credential valid when that bundle was made. Live data/keyring generations
are stored in generation directories selected by one small current-generation
pointer. Restore writes and verifies a new directory, then atomically replaces
the pointer; startup reconciliation removes or completes interrupted swaps.

## Passwords, Provisioning, and Sessions

### Strong-password rule

Supervisor, manager, and God passwords must contain at least 12 Unicode
characters, include at least one letter and one non-letter, differ from their
current value, and not equal the former defaults `1234` or `0000`.
Confirmation must match exactly. Existing strong passwords may be retained
during provisioning after the user enters and verifies them.

### Shared CiXiS settings

The paired CiXiS release migrates the source-level God hash into an
`AppSetting` row named `god_password`, initially preserving the exact
existing hash. Both products then read the same allowlisted password rows:

- `revenue_password`;
- `manager_password`;
- `god_password`;
- `manager_password_changed`;
- `password_generation_revenue`;
- `password_generation_manager`; and
- `password_generation_god`.

CiXiS continues using those hashes to unlock its own authorized screens, but
all password-change/reset UI and mutation endpoints move to the internal app.
Legacy CiXiS password-mutation endpoints are disabled so they cannot orphan
internal key envelopes.

### First-run provisioning

The internal app cannot import, clean, or create domain data before provisioning
finishes. Provisioning:

1. Verifies the current God password against CiXiS.
2. Collects and verifies the current supervisor and manager passwords, or lets
   God replace either forgotten/weak password.
3. Requires every resulting password to meet the strong-password rule.
4. Generates the internal keys and role envelopes.
5. Creates the encrypted store and verifies a full round trip.
6. Imports the initial roster idempotently.
7. Writes a durable provisioning generation and verified backup.

Failure at any step leaves the app unprovisioned and retryable.

### Password changes and resets

Supervisor and manager self-service changes require current password, new
password, and confirmation. God self-service change requires current God
password, new password, and confirmation. God can reset supervisor or manager
without their old password after authenticating with God.

Cross-database updates use a crash-recoverable generation protocol:

1. Authenticate and decrypt the current role envelope.
2. Stage and fsync a new envelope with generation N+1 while retaining N.
3. Compare-and-swap the CiXiS hash and generation from N to N+1 in one narrow
   transaction.
4. Activate envelope N+1 and retain N until a clean reconciliation/backup.
5. On startup, reconcile the CiXiS generation with staged/active envelopes and
   deterministically finish or discard the staged change.

God reset uses the God envelope to re-wrap the target keys. Failure injection
after every phase must prove that at least one valid password/envelope pair
survives.

### Backend authorization

The Electron main process generates a random 256-bit channel secret for every
launch and passes it only to the child backend. Renderer requests go through a
narrow, sender-validated preload IPC API; Electron adds the channel secret.
The renderer never receives the secret, data keys, or backend port.

Unlock endpoints require the channel secret, apply exponential rate limiting,
and return a random role-bound token held only by Electron/main and backend
memory. Every internal API route requires both channel and session tokens.
Sessions have a 15-minute idle expiry and 12-hour absolute expiry. Explicit
lock, expiry, password change/reset, and failed integrity verification revoke
sessions and terminate the backend process, after which Electron starts a fresh
locked backend. App quit also terminates it. Process replacement, rather than a
claim of Python byte-array zeroization, defines key eviction.

The internal backend enables no permissive CORS path and rejects direct browser,
curl, wrong-channel, expired-token, and insufficient-role requests. Electron
keeps `contextIsolation` and renderer sandboxing enabled, Node integration
disabled, navigation/new-window creation blocked, and IPC senders validated.

## CiXiS Database Safety

### Location and compatibility

The CiXiS profile defines one immutable Windows user-data directory name. The
internal product derives the database path from that profile and
`app.getPath("appData")`; it never scans for databases or silently chooses a
file. Missing or multiple/relocated data is an error with recovery guidance.

The paired CiXiS release seeds a random `cixis_installation_id` and an
`internal_compatibility_version`. Internal startup verifies:

- expected SQLite header;
- expected installation ID;
- exact supported CiXiS migration fingerprint;
- compatible application version; and
- absence of another incompatible process on CiXiS port 8000.

When an older/newer or currently running incompatible CiXiS is detected, the
internal app remains locked and instructs the operator to install or close the
matching CiXiS release. The internal app never runs CiXiS migrations itself.

### Connections and writes

Normal menu access uses a dedicated SQLite URI connection with `mode=ro`,
`PRAGMA query_only=ON`, and a bounded busy timeout. It reads only active
categories/products and never writes through Django ORM.

Two isolated modules may write the CiXiS database:

- the paired CiXiS data migration that clears legacy tracker rows; and
- the allowlisted password-generation writer described above.

No internal model, table, index, trigger, or migration is installed in CiXiS
SQLite. Tests compare full `sqlite_master` output and all table contents before
and after internal operations, allowing only the exact documented migration and
password-setting changes.

### Legacy feature removal

Before CiXiS applies its destructive cleanup data migration, Electron startup
creates and verifies an immediate SQLite online backup of the exact database.
Backup or integrity-check failure aborts migration and app startup. Every
management command exit status is checked.

The idempotent migration deletes rows from `ShiftAttendance` and
`StaffConsumption` only. It preserves their empty schema, `Employee`, menu,
POS, and every unrelated row. A durable migration marker prevents repeated
backup/deletion after successful completion. The paired source also removes:

- old attendance/monthly-report sidebar entries and screens;
- old roster, attendance, consumption, and staff-monthly API routes;
- old free-allowance UI from CiXiS settings; and
- legacy password-change endpoints superseded by the internal product.

This prevents a running updated CiXiS from recreating plaintext tracker rows.
An older CiXiS process detected on port 8000 blocks internal startup. Every
internal startup also checks that the two legacy tables remain empty. If an old
executable repopulated them while the internal app was closed, startup blocks
until God authorizes another verified-backup-and-clear operation.

## Jalali Contract

All business dates and months are Jalali. The UI displays and accepts Persian
digits with `YYYY/MM/DD` and `YYYY/MM` presentation. The API and encrypted
payload normalize them to zero-padded ASCII `YYYY-MM-DD` and `YYYY-MM`.
Gregorian business dates are rejected.

Validation uses the real Jalali calendar, including month lengths and leap
years. Ordering uses canonical zero-padded values. “Today” and future-date
checks use `Asia/Tehran`. Audit/session instants are stored inside encrypted
payloads as UTC ISO-8601 timestamps and displayed as Jalali date plus Tehran
time; they are not business-date inputs or filters.

Entry is allowed for today or a past date in any unfinalized Jalali month.
Future dates and every date in a finalized month are rejected server-side.

## Navigation and Staff Roster

The internal navigation contains:

- `پرسنل`;
- `ثبت سفارش پرسنل`;
- `ثبت ساعات کاری`;
- `مساعده` (manager);
- `گزارش ماه‌های باز` (manager);
- `گزارش‌های نهایی` (manager);
- `تنظیمات سهمیه` (manager);
- `تغییر رمز`; and
- `مدیریت رمزها` (God).

Every staff-selection surface reuses the same tile-grid component and interaction
pattern as the CiXiS Tables screen: responsive equal-size clickable cards,
visible selected state, and keyboard focus/activation.

First-run import copies CiXiS `Employee` source ID, name, active state, and sort
order into stable internal UUID identities. Import is idempotent by installation
ID plus source employee ID and verifies counts/hashes before marking completion.
It never modifies CiXiS `Employee` rows.

Supervisor and manager may add staff and edit names. Only manager may
soft-delete or reactivate. The `پرسنل` screen has active and inactive filters;
inactive tiles expose reactivation only to manager. Soft-deleted staff
disappear from new-entry grids but remain in open/finalized history.

Unfinalized views use the current name. Finalized snapshots preserve the name at
finalization and never change after later rename/deactivation/reactivation.

## Attendance

`ثبت ساعات کاری` is separate from order entry. User selects Jalali date,
fixed shift, and staff tile, then enters start/end time through four
numpad-friendly integer inputs:

- hour: 0–23;
- minute: 0–59.

Fixed shifts remain:

- morning: 09:00–17:00;
- evening: 16:00–24:00.

One attendance record may exist per staff UUID, Jalali date, and shift.
Supervisor duplicate save is rejected and the existing row remains read-only;
it is never silently upserted. Manager correction uses the correction flow.
A person working both shifts has two rows.

Checkout at or before check-in belongs to the next day. Therefore 16:33 to
01:10 is 8 hours 37 minutes; equal start/end is 24 hours. Each record calculates:

- actual worked minutes;
- late minutes: check-in after scheduled start;
- early minutes: check-in before scheduled start;
- overtime minutes: checkout after scheduled end; and
- shift count: one.

All calculations use integer minutes and are tested at midnight and bounds.

## Staff Orders and Product Snapshots

`ثبت سفارش پرسنل` accepts records at any time for today or a past date in an
unfinalized month. User selects Jalali date, shift, staff tile, category,
product, and quantity.

Client sends only source product ID and quantity. Quantity crosses IPC/API as a
canonical decimal string matching `^[0-9]{1,8}(\\.[0-9]{1,2})?$`; JSON numeric,
exponent, signed, comma, and binary-float forms are rejected. Backend re-reads
an active/available product from CiXiS inside one consistent read transaction
and stores an encrypted snapshot:

- source installation, category, and product IDs;
- category and product names;
- unit price in thousand Tomans;
- availability at entry;
- staff UUID and current name;
- Jalali date and shift;
- positive fixed-point quantity; and
- exact line total.

Quantity is `Decimal(max_digits=10, decimal_places=2)`, minimum 0.01. Binary
floating-point is forbidden. Unit price is an integer thousand-Toman value;
line total uses `Decimal(max_digits=22, decimal_places=2)` multiplication,
must fit that field exactly, and is also serialized as a canonical decimal
string.

Staff orders never create or modify CiXiS orders, order items, payments,
closings, tables, menu rows, or inventory, and never appear in POS sales.

## Free-Item Allowances

Allowance configuration is encrypted manager data. It defines at most one
category rule and one product rule. Each quota is a nonnegative whole-number
quantity granted separately to every staff member in every Jalali month. Zero
or no selection disables that rule.

First provisioning imports the existing positive CiXiS category/product quota
configuration when present. When absent, defaults are:

- category `قهوه`: 10 units per staff/Jalali month; and
- peanut-butter shake product under `شیک‌ها` (current menu label
  `بادوم زمینی`): 1 unit per staff/Jalali month.

If a named default is absent or ambiguous, no silent substitute is chosen; the
manager must select it.

Consumption is applied in Jalali-date then creation-sequence order. Fractions
consume the same fraction of quota and price. A product rule always takes
precedence over a category rule for that product, including units after the
product quota is exhausted; those excess units do not fall through to the
category quota. Inactive/deleted source menu rows remain calculable from order
snapshots.

Changing allowance settings previews recalculated totals for every affected
unfinalized staff-month. The latest configuration applies to all unfinalized
months after confirmation; finalized snapshots retain their frozen rule and
allocation details.

## Advances

`مساعده` is manager-only. Staff tiles lead to entry and history. Each
advance contains staff UUID/name, Jalali date, positive integer amount in
thousand Tomans, and optional note. Amount range is 1 through 9,999,999,999.
Multiple advances per person/month are allowed. Reports sum them; no salary or
remaining salary is calculated.

## Corrections and Audit

Supervisor can add/view orders and attendance but cannot edit/delete saved
rows. Manager can correct/delete attendance, staff orders, and advances in
unfinalized months.

Preview recomputes and displays every affected staff-month before/after value,
including both source and destination when staff/date/month changes:

- worked time, shifts, late, early, and overtime;
- gross/free/net consumption and allowance allocation; or
- advance total.

Preview returns a signed revision token covering source revisions, target
months, current allowance generation, and calculated impact. Confirmation
starts one immediate transaction, locks all affected months in sorted order,
revalidates the token/finalization state, applies the mutation, appends audit,
updates integrity manifest, and commits. Stale previews return conflict and
must be reviewed again.

Audit entries are append-only: no update/delete API exists. They record actor
role, UTC time, action, reason if supplied, and encrypted before/after values.
Roster name/status changes, allowance changes, finalization, and password
generation changes are also audited. Supervisor-authored roster, attendance,
order, and supervisor-password events append to the operational audit stream
using the operational keyset. Manager-only events append to the manager stream.
Manager has both keysets and sees one merged chronology; supervisor APIs expose
neither stream.

## Open-Month Reports and Finalization

`گزارش ماه‌های باز` has a Jalali month selector defaulting to the current
month. It can open any current/past unfinalized month, including a previous
month not finalized before rollover. Future months cannot be finalized.

Per staff it shows:

- shift count;
- total worked hours/minutes;
- late, early, and overtime;
- gross staff consumption;
- free allowance value and units;
- net staff consumption; and
- total advances.

The report includes active staff plus inactive staff with records in that
month. Manager can enter the correction flow from its details.

`اتمام محاسبات ماه` requires explicit manager confirmation. Backend uses
one immediate transaction and unique month constraint to:

1. lock the Jalali month;
2. reject an existing snapshot or changed source revision;
3. recompute all rows from encrypted sources;
4. create one immutable snapshot;
5. mark the month finalized;
6. append audit and update integrity manifest; and
7. commit everything together.

Every create/correct/delete endpoint checks the same month lock inside its write
transaction. Concurrent writes cannot land after snapshot calculation.
Transaction failure leaves both month and source data open and unchanged.

## Finalized Reports

`گزارش‌های نهایی` is separate. Manager selects a finalized Jalali month,
then a table-style staff tile. Snapshot includes every staff active at
finalization plus inactive staff with month data.

Each frozen staff payload contains:

- stable UUID and name at finalization;
- attendance details and calculated metrics;
- staff-order product/category/price/quantity details;
- allowance rule and per-order allocation;
- advance rows and total;
- all report totals;
- month source revision;
- finalization UTC/Jalali display timestamp; and
- finalizing role.

Snapshots have read-only APIs; correction, deletion, re-finalization, or
late-entry APIs reject the finalized month.

## Acceptance Evidence

### Security and authorization

- Strong-password validation and first-run enrollment for all roles.
- Role-separated envelope tests prove supervisor cannot decrypt manager data.
- Supervisor/manager/God self-change tests require correct current password and
  matching confirmation, never reveal hashes/passwords, re-wrap the exact
  authorized keysets, reconcile generations after restart, and preserve old
  access after every injected pre-commit failure. God-reset tests require God,
  do not require/reveal the forgotten target password, and activate only the
  confirmed new target password.
- Direct HTTP, missing/wrong channel, expired/revoked token, and role-denial
  tests cover every endpoint.
- Idle/absolute expiry, explicit lock, app quit, and password change/reset
  terminate the unlocked backend and restart locked.
- No sensitive plaintext scan across DB/WAL/journal/temp/backup/log/cache files.
- Ciphertext/index/manifest/audit-chain tampering and row deletion are detected.
- Whole-set rollback limitation is documented in recovery UI.
- Windows embedded bundle imports pinned crypto dependencies and passes smoke.

### CiXiS isolation and migration

- Full pre/post `sqlite_master` and table snapshots allow only documented
  legacy-row clearing and password/compatibility setting rows; legacy table
  schemas remain present and empty.
- Verified online backup failure, integrity failure, or command failure aborts
  cleanup/startup.
- Employee rows and every POS/menu/payment/closing row remain unchanged.
- No internal table/index/trigger appears in CiXiS SQLite.
- Read-only catalog connection rejects writes.
- Old tracker/password mutation routes are absent.
- Missing/old/new/moved/wrong-installation databases fail closed.

### Domain behavior

- Jalali digit normalization, real leap/month validation, Tehran boundaries,
  ordering, filters, and prior-open-month selection.
- Attendance uniqueness, numeric bounds, both shifts, midnight rollover,
  equal-time 24 hours, metrics, and supervisor immutability.
- Positive fixed-point quantities, exact money totals, product snapshots, and
  zero/negative/overflow rejection.
- Default/imported allowances, fractional chronological consumption,
  product-over-category precedence, setting previews, and finalized freeze.
- Multiple advances and exact monthly aggregation.
- Roster add/edit rights, manager-only soft delete/reactivation, import
  idempotency, current-name behavior, and frozen historical names.
- Revision-bound correction previews, cross-month effects, stale conflict,
  month-lock order, and append-only audits.
- Simultaneous add/correct/finalize requests yield one atomic outcome and one
  snapshot per Jalali month.
- Finalized month rejects every later mutation and exposes complete month then
  staff-tile details.

### Runtime and release

- Windows integration launches each app alone and both together, verifying
  distinct process/port/user-data ownership, concurrent catalog reads, lock
  handling, independent shutdown, and no orphan backend.
- Port collision chooses another internal port without exposing it to renderer.
- Every `v*` run gates on tests and emits exactly two distinct installers with
  matching version, commit, and compatibility fingerprint.
