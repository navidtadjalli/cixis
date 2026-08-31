# Configurable Features and Brand Profiles

## Purpose

Cixis and Majaz currently share one codebase but decide several capabilities at
build time by checking `brand.id`. That approach works for two known venues but
makes each new venue another source-code branch. This change separates product
identity from per-installation feature availability:

- a build profile defines installer identity and safe initial defaults;
- owner settings define which optional features and visual customizations are
  active for one installed database;
- turning a feature off never deletes or rewrites its domain data;
- one CI workflow and one Electron Builder configuration build every supported
  profile.

The design must preserve existing Cixis and Majaz behavior on first launch after
the update and make a third profile a data/configuration addition rather than an
application fork.

## Scope

This work includes:

- an explicit catalog of optional features;
- per-installation feature toggles in owner settings;
- runtime cafe name, logo glyph, and accent-color settings;
- centralized frontend and backend feature checks;
- build-profile defaults for Cixis and Majaz;
- one brand-aware Electron Builder configuration;
- one GitHub Actions workflow that produces both installers;
- regression tests proving feature changes preserve existing records.

This work does not include:

- deleting dormant feature data;
- dynamically changing the installed Windows executable or shortcut icon;
- letting an operator change `appId`, product name, or data directory;
- supporting arbitrary uploaded logo images;
- redesigning existing feature screens.

Executable identity remains a build concern because changing it at runtime can
move an installation to a different Electron `userData` directory and make its
database appear missing. The owner may customize the in-app name, glyph, and
accent without changing that identity.

## Chosen Approach

Use runtime installation settings layered over build-profile defaults.

Alternatives rejected:

1. **Build-time feature flags only.** This keeps data handling simple but retains
   the maintenance problem: every feature decision requires another build or
   source branch.
2. **One fully white-label installer.** This is flexible but loses stable product
   identity. Cixis, Majaz, and a future venue could share one Windows identity
   and `userData` directory, which creates unacceptable database-mixing risk.
3. **Runtime settings plus stable build profiles (chosen).** Each installer keeps
   a distinct `appId`, icon, product name, and database directory while every
   optional module can be configured from the same owner screen.

## Configuration Layers

### Build profile

`frontend/brands/<brand-id>.json` remains the source of truth for a product
profile. Each profile contains:

- `id`;
- Electron `appId`;
- installer `productName` and `shortcutName`;
- Windows and Linux icon paths;
- default in-app cafe name and logo glyph;
- event-order wording;
- default accent palette;
- default feature flags.

Build-profile fields are immutable at runtime. Cixis keeps `com.cixis.pos` and
Majaz keeps `com.majaz.pos`, so both continue using their existing Electron
`userData` directories. Their SQLite filename may remain `cixis.sqlite3`; it is
already isolated by the containing `userData` directory.

The brand generator emits frontend constants and a small generated JSON file for
Electron. Electron passes the active profile path or serialized defaults to the
local Django process. Development and management commands fall back to the
Cixis profile when no brand is supplied.

### Installation configuration

The existing `AppSetting` table stores owner choices. No schema migration or new
domain table is required. New keys are additive and created with `get_or_create`:

- `feature_event_orders`;
- `feature_order_reports`;
- `feature_day_closing`;
- `feature_staff_tracking`;
- `feature_guest_codes`;
- `feature_online_menu`;
- `appearance_cafe_name`;
- `appearance_logo_glyph`;
- `appearance_accent`.

Boolean values use the existing lowercase text convention (`"true"` and
`"false"`). Missing or invalid values resolve to the active build profile's
default. Initialization never overwrites a row that already exists.

Appearance keys are separate from the existing remote/publishing `cafe_name`
setting. This avoids changing remote payload behavior and avoids inheriting the
old Cixis-specific default in existing Majaz databases.

## Feature Catalog

Core POS functions remain permanently available: table ordering, payments, menu
and product management, table management, and owner settings. Making these
switchable could leave an installation without a usable entry screen and is not
needed for the known products.

Optional features are:

| Key | Owner label | Frontend scope | Backend scope |
| --- | --- | --- | --- |
| `event_orders` | سفارش‌های رویداد / کد دعوت | Event-mode action and screen; event-code setup card | Event-order creation/filtering and bulk preset-code route |
| `order_reports` | گزارش سفارش‌ها | Paid-order report navigation and screen | Paid-order report endpoint |
| `day_closing` | بستن روز | Day-closing navigation, gate, and screen | Preview, close, history/detail, resource, and sync actions owned by closing |
| `staff_tracking` | حضور و مصرف پرسنل | Attendance entry/report and free-allowance settings | Employee, attendance, staff-consumption, monthly staff report, and related manager flows |
| `guest_codes` | کدهای مهمان | Guest-code navigation and screen | Guest-code endpoints |
| `online_menu` | انتشار منوی آنلاین | Publish controls and storage-settings section | Menu-publish and storage-settings save operations |

All optional features depend only on permanent core functions. No optional flag
depends on another optional flag, avoiding confusing cascade behavior in the
settings screen.

Default matrix:

| Feature | Cixis | Majaz |
| --- | --- | --- |
| Event orders | On | On |
| Order reports | On | On |
| Day closing | On | On |
| Staff tracking | On | Off |
| Guest codes | Off | On |
| Online menu | On | On |

These defaults exactly match current navigation behavior. A future profile must
provide every default explicitly; profile validation fails a build when a key is
missing or unknown.

## Backend Design

Create a focused configuration module responsible for:

- loading and validating build-profile defaults;
- parsing `AppSetting` booleans;
- returning the effective feature map and appearance;
- saving only recognized owner-configurable keys;
- exposing `is_feature_enabled(key)` and a DRF feature guard.

Public endpoint:

`GET /api/application-config/`

It returns only non-secret values:

```json
{
  "brand_id": "cixis",
  "features": {
    "event_orders": true,
    "order_reports": true,
    "day_closing": true,
    "staff_tracking": true,
    "guest_codes": false,
    "online_menu": true
  },
  "appearance": {
    "cafe_name": "خروج",
    "logo_glyph": "Ç",
    "accent": "#e0a96d"
  }
}
```

Owner endpoints:

- `POST /api/settings/owner/unlock/` validates the existing GOD code and returns
  application configuration plus current masked publishing settings;
- `POST /api/settings/application/` validates the GOD code and atomically saves
  the complete recognized feature and appearance payload;
- the existing publishing-save route remains responsible only for storage
  credentials.

The owner unlock route is never feature-gated. The online-menu flag controls the
publishing section and write/publish operations, not access to owner settings.

Feature-specific API operations return HTTP 403 with stable code
`feature_disabled` and a Persian detail message while disabled. Generic order
operations remain available, but creating an event-mode order is rejected when
`event_orders` is off. Listing event-mode orders for the event screen is also
rejected. Existing event orders are not changed.

Guards must be placed at service/API boundaries, not only in navigation. They
must not guard data migrations, initialization, backups, owner settings, or
read-only internal operations needed to preserve data.

Saving configuration uses `transaction.atomic()` and `update_or_create()` only
for the recognized `AppSetting` keys. It must never call `delete()` on any model.
Unknown keys are rejected with HTTP 400 so stale or misspelled clients cannot
create uncontrolled configuration.

## Frontend Design

Add an application-configuration context loaded once before the normal app
screen mounts. It provides:

- effective feature flags;
- runtime appearance;
- a refresh/update operation after owner settings are saved;
- build-profile values as a fallback if the local configuration endpoint is
  temporarily unavailable.

Navigation becomes a pure function of the feature map rather than `brand.id`.
Brand checks are removed from `Sidebar`, `App`, and `OwnerScreen`. The Cixis and
Majaz build constants remain available for product identity and event wording.

Feature flags also control entry points inside otherwise-core screens. For
example, disabling event orders removes the event-mode action from the tables
screen and its bulk-code card from setup. Disabling online menu removes publish
actions and the publishing-settings owner section.

If an owner disables the feature for the currently open screen, the app moves to
the core tables screen, clears any transient screen state, and locks protected
revenue values. Existing open orders are untouched.

### Owner settings UI

The owner page gains an "Application configuration" section before destructive
setup tools. It contains:

- one switch per optional feature, with a short explanation;
- cafe display-name input;
- logo-glyph input;
- accent color input and live preview;
- a single save action and visible success/error state.

Settings are staged locally and sent only on save. A save failure keeps the old
effective configuration and leaves entered values available for correction.

The logo glyph is text, matching the current `Ç` and `مَ` design. It is limited
to eight Unicode code points and rendered as text, so it cannot inject markup.
Uploaded image logos are deferred because they introduce file lifecycle,
backup, decoding, and size-limit concerns that are unnecessary for the current
brands.

Only one accent color is editable. The client deterministically derives the
secondary accent by mixing the selected color with black and chooses black or
white accent text based on the higher WCAG contrast ratio. The saved value must
match `#[0-9a-fA-F]{6}`. Other dark-theme surface colors remain fixed.

## Packaging and Brand Icons

Replace `electron-builder.yml` and `electron-builder.majaz.yml` with one
brand-aware JavaScript configuration. It reads `BRAND` (default `cixis`), loads
the matching validated JSON profile, and supplies:

- `appId`;
- `productName`;
- shortcut name;
- Windows/Linux icons;
- brand-specific output directory;
- the shared files and backend resources;
- the active brand profile as a packaged resource.

Package scripts provide explicit Cixis and Majaz commands that call one shared
build implementation. Both build from the same source and configuration logic.

The installed executable and shortcut icon come from the build profile and do
not change through owner settings. This preserves Windows identity and avoids
creating stale shortcuts. Adding a third branded installer requires a profile,
valid ICO/PNG assets, and a CI matrix entry; no React or Django branch is needed.

## Unified CI Pipeline

Keep one workflow at `.github/workflows/windows-build.yml` and delete
`.github/workflows/windows-build-majaz.yml`.

The workflow uses a matrix with `cixis` and `majaz`. A single `v*` tag builds
both at the same semantic version and uploads two separately named artifacts.
Manual runs do the same using the committed development version. Each matrix job
sets `BRAND`, builds the embedded Python backend, installs dependencies, runs the
shared brand build command, and uploads only its brand-specific release folder.

The old `m-v*` tag namespace is retired. Existing released installers are not
affected; this changes only how future artifacts are produced.

## Data-Preservation Guarantees

1. No domain model or existing field is removed or renamed.
2. No data migration is required; only new `AppSetting` rows are added.
3. Initialization uses `get_or_create` and never overwrites existing settings.
4. Saving or toggling features updates only the nine recognized configuration
   rows.
5. Disabling a feature never deletes, archives, resets, or mutates its records.
6. Re-enabling a feature exposes the same records and identifiers again.
7. Cixis and Majaz retain their current `appId` values, so Electron retains their
   current `userData` and database locations.
8. Existing pre-update database snapshots still run before initialization and
   migrations.

Destructive setup actions remain separate, explicitly labeled, password-checked,
and confirmation-gated. Feature toggles do not call those endpoints.

## Error Handling

- Missing configuration rows: use active profile defaults.
- Invalid stored boolean or accent: ignore that value, use the profile default,
  and leave the row intact for diagnostics.
- Invalid owner payload: return HTTP 400 without partial updates.
- Wrong GOD code: return HTTP 401 without revealing settings.
- Disabled feature API: return HTTP 403 with `feature_disabled`.
- Public configuration load failure: frontend uses compiled profile defaults and
  shows the app; owner save remains unavailable until backend recovers.
- Unknown/malformed brand profile during a build: fail generation/build before
  Electron Builder runs.

## Testing Strategy

### Backend

- verify Cixis and Majaz defaults independently;
- verify initialization adds missing settings but preserves existing values;
- create representative records for every optional feature, disable all flags,
  and assert every record still exists with the same primary key and field data;
- verify guarded endpoints return 403 while disabled;
- re-enable each feature and verify its API returns the original records;
- verify invalid/unknown configuration is rejected atomically;
- verify feature save queries affect `AppSetting` only;
- verify owner unlock never depends on optional feature state.

The preservation test covers at least orders/items/payments, event orders,
closings, employees/attendance/consumption, guest codes, menu rows, and publish
records. It snapshots field values before toggling and compares them afterward,
not only row counts.

### Frontend

- test navigation generation for both default profiles and mixed custom flags;
- test feature-specific entry points disappear and return after configuration
  refresh;
- test disabling the active screen redirects to tables;
- test owner save payload and error handling;
- test runtime name, logo glyph, and accent application;
- keep all existing screen behavior tests passing.

### Build and CI

- validate every brand JSON against the same required profile shape;
- build/type-check frontend once for Cixis and once for Majaz locally;
- verify generated Electron config resolves existing app IDs, product names,
  shortcut names, and icon files for both profiles;
- ensure the unified workflow has two matrix artifacts and no Majaz-only workflow
  remains.

## Rollout

1. Ship both installers from the unified pipeline at the same version.
2. On first updated launch, Electron takes the existing pre-update DB snapshot.
3. `init_settings` adds missing configuration rows using that installer's profile
   without touching existing rows.
4. Cixis and Majaz open with the same features and appearance they had before.
5. Owner may then change optional features or in-app appearance.

Rollback to an older binary leaves the new `AppSetting` rows unused. Existing
domain data remains compatible because no domain schema is changed.

## Acceptance Criteria

- Existing Cixis and Majaz databases retain all records through update and every
  feature off/on round trip.
- Default updated navigation matches current Cixis and Majaz navigation.
- Owner can enable or disable every optional feature and changes apply without
  restart.
- Owner can change in-app cafe name, logo glyph, and accent color.
- Disabled feature APIs reject new feature activity without mutating old data.
- Cixis and Majaz keep distinct app IDs, icons, and database directories.
- One Electron Builder configuration builds both products.
- One GitHub Actions workflow produces separately named Cixis and Majaz Windows
  installers from one `v*` tag.
- Adding a third profile requires no application source branching.
- Full backend and frontend suites pass, and both brand builds succeed.
