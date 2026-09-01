# چیخیش اندرونی Design

## Purpose

Build `چیخیش اندرونی` as a separately packaged Electron desktop application
for the CiXiS staff-calculation workflows. It replaces the old `ثبت حضور و
مصرف` and `گزارش ماهانه پرسنل` flows, works whether CiXiS is open or closed,
and is released with every CiXiS version tag.

## Fixed Decisions

- A `v*` tag builds both CiXiS and `چیخیش اندرونی` installers from the same
  commit. There is no separate tag namespace.
- The internal app shares CiXiS menu data and password settings, but sensitive
  internal operational data is not stored in CiXiS's ordinary SQLite file.
- It starts its own backend on a different localhost port.
- Every internal-app date input, display, filter, API value, and month key is
  Jalali. Gregorian dates are not accepted or displayed.
- Finalizing a month is an accounting lock and snapshot only. It never creates
  a CiXiS POS order, payment, settlement, or day closing.

## Security and Database Boundaries

### Protected internal data

`چیخیش اندرونی` owns a separate encrypted local store for:

- internal roster;
- attendance;
- staff orders;
- advances (`مساعده`);
- free-item allowance settings;
- correction/deletion audit records;
- finalized snapshots; and
- encryption key-wrapping metadata.

Sensitive payloads use authenticated encryption. Changed ciphertext,
authentication tags, or protected indexes fail verification and are never read
as valid data. Encrypted backups are made before internal-store migrations.

The data key is random and never stored plaintext in source, configuration,
logs, or either database. It is wrapped for authorized password holders and
held only during an unlocked session. Password changes and God resets re-wrap
the key safely.

With everybody using one Windows account, no local-only app can prevent a
determined person who knows an authorized password or examines an already
unlocked process. This design does prevent direct disk reads and valid silent
SQLite edits. Separate OS accounts or a remote service would be required for a
strict boundary against that stronger attacker.

### CiXiS SQLite contract

The internal app opens CiXiS SQLite read-only for product/category data. Staff
orders save product snapshots in the encrypted store, so they never create or
change POS orders, payments, closings, inventory, tables, or menu rows.

On first internal release migration:

1. Copy all existing CiXiS employee names into the protected roster.
2. Delete only legacy `ShiftAttendance` and `StaffConsumption` rows.
3. Preserve `Employee` and all unrelated CiXiS records exactly.

The existing CiXiS pre-update backup must succeed before the one-time cleanup.
After it, the only allowed CiXiS writes are explicit password-setting values.
They use a narrow transaction and key allowlist. No internal operational model
is added to CiXiS's Django migrations.

## Passwords and Roles

All password hashes/settings remain CiXiS-compatible.

| Role | Access |
| --- | --- |
| Supervisor/revenue password | Add/view staff orders and attendance; add/edit staff names |
| Manager password | Supervisor access; correct/delete unfinalized entries; delete/reactivate staff; free-item settings; advances; reports; finalization |
| God password | Change own password with current/new/confirmation; reset supervisor or manager by setting new/confirmation |

Supervisor and manager password changes require current password, new password,
and matching confirmation. God resets never reveal a password.

## Screens and Staff Selection

Staff names render as the existing CiXiS table-style clickable tile grid.

| Screen | Role | Behavior |
| --- | --- | --- |
| `ثبت سفارش پرسنل` | Supervisor, manager | Jalali date/shift; staff tiles; category/product and decimal quantity |
| `ثبت ساعات کاری` | Supervisor, manager | Jalali date/shift; staff tiles; bounded numpad time entry |
| `مساعده` | Manager | Staff tiles; Jalali date, amount, optional note, history |
| `گزارش ماه جاری` | Manager | Current month totals, corrections, and finalization |
| `گزارش‌های نهایی` | Manager | Jalali month picker then staff tiles for immutable details |
| `تنظیمات` | Manager | Free-item rules and manager password change |
| `مدیریت رمزها` | God | Password resets and God password change |

The protected roster initially copies CiXiS employee names. Supervisor and
manager can add staff and edit names. Only manager can soft-delete/reactivate.
Soft-deleted staff leave active grids but remain in historical records.

## Attendance

Attendance is on its own screen. The user selects a staff tile, Jalali date,
and fixed shift:

- morning: 09:00–17:00;
- evening: 16:00–24:00.

Start/end use numpad-friendly number fields: hours 0–23 and minutes 0–59.
Saving is explicit. A supervisor cannot alter an attendance row after saving.
A manager may correct/delete an unfinalized row after an impact confirmation.

Checkout at or before check-in means next day. Thus 16:33 to 01:10 is 8:37.
Each row computes worked duration, late minutes, early minutes, overtime
minutes, and one shift count. Late is time after scheduled start; early is time
before scheduled start; overtime is time after scheduled end.

## Staff Orders and Free Allowance

Staff orders are internal records, not POS orders. Supervisor/manager can enter
them at any time for a Jalali date and selected shift. Quantities retain
two-decimal support.

Manager settings select a CiXiS category or product and monthly free quantity.
Product-level allowance overrides category allowance, preventing double grants.
Old default values and consumption ordering semantics are retained.

## Advances and Corrections

`مساعده` is a dedicated manager-only screen. Each row has staff, Jalali date,
amount, and optional note. Multiple advances per person/month are allowed.
Reports show their total only; the app does not calculate salary or remaining
salary.

Before a manager changes/deletes any unfinalized attendance, order, or advance,
the confirmation shows exact before/after impact:

- worked duration and late/early/overtime;
- gross/free/net staff consumption; or
- monthly advance total.

Every correction/deletion writes an encrypted audit record with actor role,
time, old value, new value, and action.

## Monthly Reports

The current report groups by Jalali month. Per staff it shows shifts, total
worked hours, late/early/overtime, gross consumption, free allowance, net
consumption, and total advances.

`اتمام محاسبات ماه` requires manager confirmation, rejects an already-final
month, freezes every source entry, and writes one immutable encrypted monthly
snapshot. No entry in that month can then be added, changed, or deleted.

`گزارش‌های نهایی` is a separate screen. Manager picks a Jalali month and then
a table-style staff tile to view frozen totals and details.

## Release Runtime

Add a third Electron build profile and dedicated builder configuration for
`چیخیش اندرونی`. Product identity, icon, window, backend port, and app-data
directory are distinct. The app locates CiXiS's database but never renames or
moves it.

The existing `v*` Actions workflow gains an internal-app build job. Both
installers use one backend source, migration set, and version; the workflow
uploads two artifacts.

## Acceptance Tests

1. Snapshot every CiXiS model before internal migration/actions; only the
   intended legacy attendance/consumption cleanup may differ after migration.
   Normal internal use changes no CiXiS row. Password tests permit only named
   password-setting rows.
2. Staff orders do not affect CiXiS POS orders, payments, stock, closings, menu
   rows, or tables.
3. Jalali-only validation, rendering, filtering, month boundaries, and
   snapshot lookup.
4. Attendance numeric bounds, shift metrics, overnight duration, and
   supervisor immutability.
5. Manager correction/delete previews and encrypted audit history.
6. Decimal quantities and free-allowance precedence/default behavior.
7. Multiple advances and monthly aggregation.
8. Roster role rights, name edits, soft deletion/reactivation, and historic
   names.
9. Manager-only finalization, one snapshot per Jalali month, and source locks.
10. Password-change/reset authorization and matching confirmation.
11. Encryption round trip, no plaintext in the internal store, tamper
    rejection, and encrypted backup recovery.
12. Tag workflow builds compatible CiXiS and internal Windows installers.
