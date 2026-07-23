# Legal Documents

Versioned legal documents (terms of use, sales terms, privacy policy) with **provable,
version-bound consent**: the app can demonstrate that a given user accepted a specific,
immutable version of a document at a specific time.

App: `lys.apps.legal`. Renders PDFs through the [`_core/pdf`](../_core/pdf.md) utility and
stores them through `file_management`. The document **content** (the Markdown source) is
**application-owned**, not part of lys.

## Table of Contents

1. [Overview](#overview)
2. [Scope](#scope)
3. [Data model](#data-model)
4. [Publication lifecycle](#publication-lifecycle)
5. [Consent flow](#consent-flow)
6. [Retention and anonymization](#retention-and-anonymization)
7. [Open points](#open-points)

## Overview

A **document type** (terms of use, sales terms, privacy policy…) has **versions**. Each
version is an immutable artifact: a Markdown source is rendered once to a PDF, frozen in
object storage, and fingerprinted. Users **accept** a specific version; each acceptance is
an append-only proof record carrying a self-contained identity snapshot, so the proof
survives later anonymization of the user account.

Two hashes serve two distinct purposes:
- the **Markdown hash** identifies the version and drives idempotent publication (same
  source → same version, never republished);
- the **PDF hash** is the legal integrity fingerprint of the exact artifact the user
  accepted.

## Scope

**In scope (lys)**: the entities, publication/versioning, the consent-proof service and
its GraphQL surface, and the retention/anonymization jobs (daily reconciliation + purge).

**Out of scope**: the document **text** (application content); legal drafting; the
signup/login wiring that *consumes* the service (belongs to `user_auth` / `licensing`);
PDF rendering itself (see `_core/pdf`).

## Data model

Three entities in `lys.apps.legal`. IDs of non-parametric entities and all soft foreign
keys use `Uuid(as_uuid=False)` per the lys entity rules.

Document **type codes are generic and English** — `TERMS_OF_USE`, `SALES_TERMS`,
`PRIVACY_POLICY`. Product-facing labels (e.g. French "CGU"/"CGV") are the application's
concern (i18n), never stored here.

### `LegalDocumentType` (parametric)

Table `legal_document_type`. `ParametricEntity` with a business-meaningful string id (the
code). Discriminator for versions. lys seeds a default set via fixture; applications may add
their own codes.

| Column | Type | Notes |
|---|---|---|
| `id` | `str` (PK) | Code, e.g. `TERMS_OF_USE`, `SALES_TERMS`, `PRIVACY_POLICY` |
| `enabled` | `bool` | Inherited from `ParametricEntity` |
| `description` | `str` | Human-readable purpose of the type (inherited from `ParametricEntity`) |
| `requires_acceptance` | `bool` | Whether this type **gates access** — its current version must be actively accepted. Seeded per type. |

**`requires_acceptance` is a property of the type, not per-deployment config.** Whether a
document type must be accepted follows its **nature**: terms of use and sales terms are
contracts that gate (`True`); a privacy policy is an information notice under GDPR art. 12-14 —
it is *acknowledged*, never *accepted* (`False`). The realistic value is essentially fixed per
type: `PRIVACY_POLICY = True` would be a dark pattern (it misrepresents the legal basis as
consent), and `TERMS_OF_USE = False` is degenerate (browsewrap / offline-signed contract —
outside this provable-clickwrap mechanism). So it belongs **on the type**, seeded by the
fixture, next to `enabled`/`description` — one place fully defines a type.

lys ships the safe default (`TERMS_OF_USE`/`SALES_TERMS` → `True`, `PRIVACY_POLICY` → `False`),
which steers applications away from the anti-pattern. An application with a genuinely unusual
posture overrides it by re-registering the fixture (registry: last loaded wins). Custom gating
types (e.g. an acceptance-required `DPA`) are added by the application's own fixture.

**Why the column and not `settings`, nor a code constant.** It is *data about the type*, so it
lives in the type's row. `required_types()` (Consent flow §Services) reads it directly:
`SELECT id FROM legal_document_type WHERE requires_acceptance AND enabled`. Adding the column
does **not** sacrifice the generic node: `ParametricEntity` supports extra columns, and the
gating decision is **server-side** — the fixed-shape `parametric_node` (id/code/enabled/
description) simply does not expose `requires_acceptance`, which is an internal policy flag the
public API never needs.

Being parametric, the fixture inherits the standard **disable-on-removal** semantics
(`ParametricFixtureLoadingStrategy`): a type dropped from the fixture is set `enabled=False`,
**never deleted** — its immutable versions and acceptance proofs stay referenceable. This is
exactly the desired semantics for retiring a legal type.

### `LegalDocumentVersion`

Table `legal_document_version`. **Immutable, append-only registry** — rows are never
updated or deleted after creation. One row = one published version of one type in one
language.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `Uuid(as_uuid=False)` (PK) | no | From `Entity` |
| `type_id` | FK → `legal_document_type.id` | no | Document type |
| `language_id` | FK → `language.id` | no | Existing lys `Language` parametric entity (ISO 639-1: `fr`, `en`…); referenced like `Emailing.language_id`, with a `selectin` relationship |
| `version_number` | `int` | no | Monotonic per (`type_id`, `language`), human-readable |
| `markdown_hash` | `str(64)` | no | SHA-256 of the source Markdown (version identity / idempotency) |
| `pdf_hash` | `str(64)` | no | SHA-256 of the rendered PDF (legal integrity fingerprint), **computed by the legal service** as `sha256(pdf_bytes)` — same helper as `StoredFileService.content_hash`; the storage backend's `upload()` returns only the key, not a hash |
| `object_key` | `str` | no | Object-storage key of the immutable PDF (via the shared `core/utils/storage` backend) |
| `effective_date` | `datetime(tz)` | no | When it takes legal effect (may be ≥ `created_at`) |
| `created_at` / `updated_at` | `datetime(tz)` | — | From `Entity`. A row is created only at publication, so **`created_at` is the publication timestamp** — no separate `published_at` field. |

**Constraints & indexes**
- Unique (`type_id`, `language_id`, `markdown_hash`) — idempotent publication: identical
  source is never registered twice.
- Unique (`type_id`, `language_id`, `version_number`).
- Index (`type_id`, `language_id`, `effective_date`) — current-version lookup.

**Current version.** Derived, **not** a stored `is_current` flag. The current version for
a (`type`, `language`) is the row with the greatest `effective_date` that is `<= now()`.

*Why derived rather than a flag:* a flag is mutable state on an **append-only, immutable
registry** — publishing a new version would have to flip the previous row's flag (an
`UPDATE`), contradicting the write-once guarantee and opening a race (two rows briefly
"current"). Deriving from `effective_date` keeps the table strictly append-only, is
race-free, and naturally handles a version published with a **future** `effective_date`
(registered but not yet current — supports a notice period). The lookup is a single
indexed query.

**Storage.** The PDF bytes are stored through the **shared storage backend**
(`core/utils/storage`, the same S3/MinIO layer `file_management` uses) — **not** through
the `stored_file` entity, which is **tenant-scoped** (`client_id` NOT NULL) and therefore
cannot represent a **global, non-tenant** legal version. This table holds only the
`object_key` and the fingerprints; immutability of the object itself (bucket versioning /
Object-Lock) is an infra concern.

**Access.** Versions are non-tenant and **public** — a prospect must be able to read the
terms before signing up, and the PDFs are permanently linkable (footer, e-mails, citations).
This is materialized by the **stable public PDF routes** (Consent flow §Public PDF routes),
not by presigned URLs. `accessing_users` / `accessing_organizations` return empty (no
per-subject restriction); read exposure is controlled at the webservice access level, not by
row filtering.

### `LegalDocumentAcceptance`

Table `legal_document_acceptance`. **Append-only proof.** A row records that a subject
accepted a specific version at a specific time, with a **self-contained identity
snapshot** so the proof does not depend on the (mutable, anonymizable) user account.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `Uuid(as_uuid=False)` (PK) | no | From `Entity` |
| `version_id` | **`ForeignKey` → `legal_document_version.id`** | no | The exact version accepted. **Hard FK** — intra-app, same DB as the version registry → referential integrity is enforced at the database (contrast `user_id`, which crosses to `user_auth` and is therefore soft) |
| `user_id` | `Uuid(as_uuid=False)` | **yes** | Soft FK → user. **Operational link only.** Set to `NULL` when the account is anonymized (severs re-identification), leaving the snapshot as the sole, minimized proof |
| `accepted_by_email` | `str` | no | Identity snapshot at acceptance time — the **essential anchor** (who accepted) |
| `accepted_by_name` | `str` | yes | Identity snapshot at acceptance time, when available (`user_private_data` may have none) |
| `acceptance_context` | `JSON` | yes | Corroborating act metadata: `ip_address`, `user_agent`, and any product-specific extras. Nullable — the application decides what to populate (minimization; IP may be truncated/hashed). Mirrors the `context` / `extra_data` JSON pattern used by `emailing` / `file_import` |
| `retention_anchor_date` | `datetime(tz)` | **yes** | **Retention clock start.** `NULL` while the relationship is live (an active user's proof is never purged, regardless of `created_at`). Set to the user's **`anonymized_at`** by the reconciliation job — the same update that nulls `user_id`. The purge selects rows where `retention_anchor_date + retention < now()`. Not the acceptance date: an active customer who accepted years ago must keep a valid proof |
| `created_at` / `updated_at` | `datetime(tz)` | — | From `Entity`. A row is created at the moment of acceptance, so **`created_at` is the acceptance timestamp** — no separate `accepted_at` field |

**Immutability.** Rows are never updated **except** the single permitted operation of the
reconciliation job, which in one update sets `user_id = NULL` and stamps
`retention_anchor_date` (= the user's `anonymized_at`). That is severing an operational foreign
key and starting the retention clock, **not** mutating the evidential content (`version_id`,
`accepted_by_email` /
`accepted_by_name`, `created_at`, `acceptance_context` remain frozen). Rows are never
deleted individually; the whole row is purged only when its retention lapses (see
Retention).

**Why the snapshot.** `accepted_by_email` / `accepted_by_name` are a deliberate, minimized
copy kept under a distinct purpose and lawful basis (proof of consent) from
`user_private_data` (account operation). Same data, different retention — this separation
is what lets the account be fully anonymized while the consent proof stands. Detailed in
[Retention and anonymization](#retention-and-anonymization).

**Access.** A subject sees their own acceptances (`accessing_users` → `[user_id]` while
non-null); privileged read is governed at the webservice access level.

**Constraints & indexes**
- Unique (`user_id`, `version_id`) — one acceptance per user per version (idempotent
  `record_acceptance`). NULLs are distinct in SQL, so anonymized rows (`user_id` nulled) do
  not collide.
- Index (`user_id`) — "has this user accepted…" lookups.
- Index (`version_id`) — acceptances per version.
- Index (`accepted_by_email`) — retrieve a person's acceptances after anonymization
  (`user_id` nulled) or for a data-subject access request.
- Index (`retention_anchor_date`) — the purge task scans rows past their retention window.

---

### Module layout (indicative)

```
lys/apps/legal/
├── __init__.py                 # app registration
└── modules/
    └── legal_document/
        ├── entities.py         # the three entities above
        ├── services.py         # publication + consent proof (later steps)
        ├── fixtures.py         # default document-type codes
        ├── nodes.py            # GraphQL nodes
        ├── webservices.py      # GraphQL fields + public REST PDF routes (/legal/...)
        └── tasks.py            # Celery task callables: anonymization reconciliation, retention purge
```

## Publication lifecycle

Publishing turns an application-owned Markdown source into an immutable
`LegalDocumentVersion`. It is **idempotent**: identical source is never published twice.

### The `publish` operation

Signature (indicative): `publish(type_id, language_id, markdown, *, effective_date=None,
template=None, context=None) -> LegalDocumentVersion`.

Steps:

1. Compute `markdown_hash = sha256(markdown)`.
2. **Idempotency check** — if a row already exists for (`type_id`, `language_id`,
   `markdown_hash`), return it and stop. Nothing is rendered, uploaded, or written.
3. Render the PDF once: `render_markdown_to_pdf(markdown, template=template,
   context=context)` (see [`_core/pdf`](../_core/pdf.md)).
4. Compute `pdf_hash = sha256(pdf_bytes)` in the service (mirror `StoredFileService.content_hash`;
   the backend does not hash). Upload the bytes through the shared storage backend
   (`core/utils/storage`), obtaining the `object_key` (the only value `upload()` returns).
5. Assign `version_number = max(existing for type+language) + 1`.
6. Insert the version row (`effective_date` defaults to `created_at` if not supplied).

### Idempotency and determinism interplay

The idempotency key is the **`markdown_hash`, never the `pdf_hash`**. So a version's PDF
is rendered **exactly once** — when its Markdown hash is first seen — then frozen. This is
what neutralizes WeasyPrint's non-determinism (see [`_core/pdf` §Determinism](../_core/pdf.md#determinism)):
a re-run with unchanged source hits the idempotency check *before* rendering, so
non-identical PDF bytes can never spawn a spurious new version. Editing the Markdown (any
change) yields a new `markdown_hash` and therefore a new version.

### Concurrency

Publication may run on several booting replicas at once. Two replicas can both pass the
idempotency check and try to insert. The **unique constraint** on
(`type_id`, `language_id`, `markdown_hash`) makes this safe: one insert wins, the other
catches the integrity error, re-reads, and returns the winning row. A duplicate
render/upload is wasteful but harmless (the losing object is orphaned; the storage key
should embed the `markdown_hash` so both writes target the same key and the loser is a
no-op overwrite of identical content).

### Declaration (application config)

The Markdown is **application content**, not part of lys. The application **declares** its
legal documents in settings — a `settings.legal` namespace / `configure_legal(...)`,
mirroring how `email` and `ai` are configured.

`settings.legal.documents` declares only **content location** — it is purely `type → languages`.
Everything intrinsic to a type (`description`, `requires_acceptance`) lives on the type itself,
seeded by fixture (§`LegalDocumentType`), never here. Each type maps to a `languages` map
enumerating the languages the document **actually exists in**, each pointing to its Markdown
source:

```python
app_settings.legal.documents = {
    TERMS_OF_USE:   {"languages": {"fr": "legal/terms_of_use_fr.md",
                                   "en": "legal/terms_of_use_en.md"}},
    PRIVACY_POLICY: {"languages": {"fr": "legal/privacy_policy_fr.md"}},
}
```

The source is shipped in the application image and read at publication time. A language entry
may be a bare path (as above) or, when a language needs its own publication options, an object
`{"path": ..., "effective_date": ..., "template": ..., "context": ..., "base_url": ...}`
(`base_url`/`context` let the template resolve branding assets — logo, fonts).

**Languages are enumerated explicitly, per type.** The set of languages a legal document
*exists in* is **not** the set of enabled UI languages: an app may enable `en` as an interface
language while its `en` terms do not yet exist. Deriving publication from "all enabled
languages" would attempt a missing translation and fail — and, at signup, break acceptance
recording under the strict no-fallback rule (§Services). The declaration therefore lists
exactly the languages that exist; no convention infers paths or languages.

The set of gating types is **not** declared here — it is read from the `requires_acceptance`
column (`required_types()`, Consent flow §Services), keeping the acceptance policy on the type,
not in per-deployment content config.

This one-time **declarative** step is all the consumer does — no imperative publish calls.
The framework renders, stores, and registers the declared documents (see Trigger), and seeds
the `LegalDocumentType` parametric rows from the same declaration (§`LegalDocumentType`).

### Trigger

Publication runs **automatically at application startup**, via the legal service's
`on_initialize()` hook. `registry.initialize_services()` (defined in `core/registries.py`,
invoked from `core/managers/app.py`) calls `on_initialize()` on **every** service at startup,
**unconditionally — in all environments including prod**. The hook reads the declared documents and calls `publish` for each:
unchanged sources are cheap no-ops (hash + indexed lookup), a PDF is rendered only when a
new `markdown_hash` appears. The consumer declares; the framework publishes. No manual step.

**Fault-tolerance is a hard requirement.** `initialize_services` **re-raises** on failure,
which would abort app startup. The legal `on_initialize` MUST therefore **catch and log its
own publication errors** instead of propagating them. Required behaviour: if publishing a
*new* version fails at boot (storage down, `pdf` extra or native libs missing, malformed
source), the app **still starts and keeps serving the existing current version**; the
publish is retried on the next boot. A publication hiccup must never prevent the application
from starting.

**Why not a fixture** (rejected):
1. Fixtures are idempotent **by `id`** (upsert on the explicit `id` in `data_list`), whereas
   a version's identity is content-based — (`type`, `language`, `markdown_hash`) — with a
   random UUID `id`. The idempotency models do not align.
2. **Fixtures skip non-parametric entities in prod** (`core/fixtures.py`: `_inner_load`
   returns early when `not issubclass(entity_class, ParametricEntity)` and `env == PROD`).
   `LegalDocumentVersion` is a regular `Entity`, so a publication fixture would **never run
   in prod**. Fatal. `on_initialize` has neither limitation.

Note: `LegalDocumentType` **is** seeded via a normal fixture (a `ParametricEntity`, which
fixtures do load in prod) — codes plus `description`/`requires_acceptance` (§`LegalDocumentType`).
Only the **versions** go through `on_initialize`.

**Optional manual re-publish.** A CLI command over the same declared config MAY be provided
for on-demand publication (force a re-run without a restart); it is not the nominal path.

### Correcting a version

Versions are immutable and may already be accepted, so a mistake is **never edited**. A
corrected text is published as a **new version** with a later `effective_date`; it becomes
current per the derived rule. There is no un-publish. (Whether a change forces existing
users/subscribers to re-accept is a consent-flow / open-points concern, not publication.)

## Consent flow

`legal` provides the **mechanism** — read the current version, record an acceptance, check
whether a user is up to date. **Where and when** acceptance is required (signup checkbox,
login gate, paid-license step) is **application policy**, wired by the consuming apps.

### Services

Signatures below omit it for readability, but **every service method takes the active
`session`** as a keyword argument (`session: AsyncSession`) and performs no commit of its own —
the caller owns the transaction, per the lys service convention (as in `StoredFileService` /
the Mollie service). E.g. the real signature is
`get_current_version(type_id, language_id, *, session) -> LegalDocumentVersion`.

- **`get_current_version(type_id, language_id) -> LegalDocumentVersion`** — the derived
  current version (greatest `effective_date <= now()`) for the **exact** (`type`, `language`)
  requested. **Strict resolution — no language fallback**: if no version is effective for that
  exact pair, it **raises** (a `legal` not-found error), never serves another language. Serving
  `fr` terms to an `en` user and recording that as consent would be legally unsound; a missing
  language is a **publication gap to fix**, surfaced loudly rather than masked.
- **`record_acceptance(user, version, *, context=None) -> LegalDocumentAcceptance`** —
  creates the append-only proof row. Captures the **identity snapshot** from `user`
  (`accepted_by_email`, `accepted_by_name` — read at this instant) and, when supplied, the
  request metadata into `acceptance_context` (`ip_address`, `user_agent`). **Idempotent per
  (user, version)**: a unique (`user_id`, `version_id`) constraint means re-accepting the
  same version returns the existing row rather than inserting a duplicate.
- **`has_accepted_current(user, type_id, language_id) -> bool`** — whether the user has an
  acceptance for the current version of that type.
- **`required_types() -> list[type_id]`** — the gating set, read from the type rows:
  `SELECT id FROM legal_document_type WHERE requires_acceptance AND enabled`. The acceptance
  policy lives **on the type** (§`LegalDocumentType`), not in per-deployment config.
- **`outstanding_acceptances(user, required_types=None) -> list[type_id]`** — among the gating
  types (defaults to `required_types()`), those whose current version the user has **not**
  accepted (drives the re-consent gate). An application with an unusual posture may pass an
  explicit set to override the default. Storing `requires_acceptance` as a column does not
  sacrifice the generic node: the gating decision is **server-side**, and the fixed-shape
  `parametric_node` (id/code/enabled/description) simply does not expose the internal flag.

### GraphQL surface

| Field | Kind | Access | Purpose |
|---|---|---|---|
| `currentLegalDocument(type, language)` | query | disconnected-friendly | Read the current version + its PDF (terms must be readable **before** acceptance / at signup) |
| `outstandingLegalAcceptances` | query | connected | Types the connected user still owes acceptance for (the login gate reads this) |
| `acceptLegalDocument(versionId)` | mutation | connected | Record consent for the **specific version** the client was shown |

The PDF is exposed on the version node as a **stable, public URL** (see below), not as an
expiring presigned URL and not streamed through GraphQL.

### Public PDF routes

Legal documents are **public by nature** and must be **permanently linkable** — website
footer (`<a href>` in server-rendered HTML, not a GraphQL client), e-mails, contracts,
citations — and readable **before authentication** (a prospect reads the sales terms before
signing up). An **expiring presigned URL cannot serve any of that**. `legal` therefore exposes
**stable, public, unauthenticated REST routes** (webservices on the app):

| Route | Serves |
|---|---|
| `/legal/{type}/{language}` | the **current** version — canonical public link (footer, signup, e-mails) |
| `/legal/versions/{id}` | a **specific immutable** version — the one an acceptance points to (proof retrieval, DSAR) |

The **object storage stays private** (uniform backend, no public bucket to manage in infra):
each route resolves the `object_key` and either streams the bytes or `302`-redirects to an
internally generated presigned URL. The presigned URL becomes an implementation detail hidden
behind the stable route. `currentLegalDocument` and the version node return **this stable
URL**. Strict language resolution applies to `/legal/{type}/{language}` too (missing language
→ error, no fallback).

#### Implementation — route wiring

These are plain **FastAPI REST routes**, wired exactly like the existing Mollie webhook
(`apps/licensing/modules/mollie/webservices.py`), not GraphQL fields:

- **Declaration & auto-mount.** Declare a module-level `router = APIRouter(prefix="/legal")`
  in `legal/modules/legal_document/webservices.py`. lys auto-collects any `router` attribute
  from a `webservices` module (`core/managers/app.py` `_load_from_submodules` →
  `registry.routers`) and mounts it with `app.include_router(router)`. Nothing else to
  register.
- **Public = no auth dependency.** lys auth is enforced **per GraphQL field**
  (`lys_field(is_public=…, access_levels=…)`), **not** by a blanket JWT middleware. A REST
  route on an `APIRouter` is therefore unauthenticated by default — the same reason
  `/webhooks/mollie` is public. Add **no** auth dependency; do not whitelist anything.
- **Storage access — via a service, using the shared backend.** The route must **not** reach
  storage directly. It calls the `legal_document` service, which obtains the backend the same
  way `StoredFileService` does — `get_storage_backend(settings.get_plugin_config(FILE_STORAGE_PLUGIN_KEY))`,
  cached on the service (`core/utils/storage.get_storage_backend`). **There is no
  `app_manager.storage`.** The service exposes the presigned URL for a version's `object_key`
  (e.g. `get_presigned_url(version.object_key, expires_in=300)`).
- **Response.** `302`-redirect to the presigned URL (`fastapi.responses.RedirectResponse`,
  `status_code=302`) — no bytes proxied through the API. Content is public and immutable, so a
  long `Cache-Control` is appropriate.
- **Strict resolution → 404.** `/legal/{type}/{language}` calls `get_current_version`, which
  **raises** when no version is effective for that exact pair (Consent flow §Services); the
  route maps that to **HTTP 404** (missing language = publication gap, never a fallback).
  `/legal/versions/{id}` returns 404 when the id is unknown.

Reference skeleton (mirrors the Mollie precedent; `app_manager = LysAppManager()`,
`app_manager.get_service(...)`, `app_manager.database.get_session()`):

```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from lys.core.managers.app import LysAppManager

router = APIRouter(prefix="/legal", tags=["legal"])

@router.get("/{type_id}/{language_id}")
async def current_legal_pdf(type_id: str, language_id: str):
    app_manager = LysAppManager()
    service = app_manager.get_service("legal_document")
    async with app_manager.database.get_session() as session:
        version = await service.get_current_version(type_id, language_id, session=session)
        url = await service.get_presigned_url(version.object_key, expires_in=300)
    return RedirectResponse(url, status_code=302)

@router.get("/versions/{version_id}")
async def legal_version_pdf(version_id: str):
    app_manager = LysAppManager()
    async with app_manager.database.get_session() as session:
        version = await session.get(app_manager.get_entity("legal_document_version"), version_id)
        if version is None:
            raise HTTPException(status_code=404, detail="Legal document version not found")
        url = await app_manager.get_service("legal_document").get_presigned_url(
            version.object_key, expires_in=300
        )
    return RedirectResponse(url, status_code=302)
```

Accepting **by `versionId`** (not by type) guarantees the proof records exactly the version
the user was presented — the client fetches `currentLegalDocument`, shows it, then accepts
that `versionId`.

### Identity snapshot and context capture

At `record_acceptance` the snapshot is frozen from the user (`accepted_by_email` from the
user's email, `accepted_by_name` from `user_private_data` when present) and `ip_address` /
`user_agent` are read from the request context into `acceptance_context`. This is what makes
the proof self-contained and anonymization-proof (see
[Retention and anonymization](#retention-and-anonymization)).

### Composition — who wires acceptance, and why not `legal`

`legal`, `user_auth` and `licensing` are **independent building blocks**: none imports
another. Deciding that *signup requires TERMS_OF_USE* or that *buying a licence requires
SALES_TERMS* is **product policy**, so the **application composes** the blocks — it is
**not** wired inside any lys app.

**Dependency direction (important).** `legal` conceptually sits *above* `user_auth` (an
acceptance references a user). So `user_auth`'s signup **must not call `legal`** — that
would make the foundational auth layer depend on the higher-level legal layer. Nor should
`legal` override `user_auth`/`licensing`: that would couple the two lys apps *and* bake a
consent policy into the framework, forcing it on every consumer. Both are rejected.

**The application performs the composition, via lys's service-override** (subclass a service
and re-register it under the same name; loaded last, it wins — the standard lys service-override
pattern):

- **Signup** — acceptance is wired into the **self-signup flow(s)**, *not* the generic
  `create_user` primitive. `create_user` is too low: it also backs admin user-creation and
  invitation flows — recording an acceptance there would fabricate consent for users
  who never accepted — and it does not even carry the acceptance signal (the "I accept"
  checkbox is a signup-form input). In lys both self-signup paths funnel through the
  organization app — `create_client_with_owner` (password) and `create_client_with_sso_owner`
  (SSO) — and both already call `create_user` internally. The application overrides **these
  self-signup services** to add `record_acceptance(user, current TERMS_OF_USE version,
  context)` in the **same transaction** (user and acceptance atomic — an async event could
  not guarantee this). Server-side (the user is being created), not a client mutation.
- **Paid license** — the application overrides the subscription flow to call
  `record_acceptance(user, current SALES_TERMS version, context)`.
- **Login gate** — the application reads `outstanding_acceptances(user)` on login (the gating
  set defaults to `required_types()`, i.e. the types marked `requires_acceptance`) and, if
  non-empty, signals the front to prompt re-acceptance (the `acceptLegalDocument` mutation)
  before granting normal access. The **check** is a `legal` service; **which types gate** is
  carried by the `requires_acceptance` column (overridable per application).

`legal` stays generic throughout: it exposes the acceptance capability for **any** type and
takes the `user` **duck-typed** (`user.email`, `user.private_data`) so it need not import
`user_auth`. Which types are acceptance-required, and where, is entirely product policy —
e.g. a privacy policy may be **displayed/linked without acceptance** simply by not wiring an
acceptance step for it.

## Retention and anonymization

Two **scheduled Celery Beat tasks**, both **daily**, act on `LegalDocumentAcceptance` — no
event, no hook, no in-process trigger:

| Task | Effect on the row |
|---|---|
| **Anonymization reconciliation** | for users now anonymized: `user_id → NULL` **and** stamp `retention_anchor_date = anonymized_at` — sever the operational link, start the retention clock; evidential snapshot untouched. |
| **Retention purge** | for rows past prescription: **delete the whole row** — the proof itself expires. |

Both are **poll** jobs owned by `legal` and run in the existing worker — **no extra process**.

### Anonymization reconciliation (daily poll via GraphQL)

**Why poll, not push.** lys anonymization is **not a delete**: `anonymize_user` nulls the
user's fields and keeps the row, so **no database cascade ever fires** and there is no event to
react to. `legal` must sever its own `user_id` by code. Rather than couple `user_auth` to
`legal` (a hook/event) or let `legal` read `user_auth`'s tables, `legal` **asks** `user_auth`,
periodically, who has been anonymized.

**Mechanism.** A daily task fetches the newly anonymized users from `user_auth` **over
GraphQL** and reconciles the local proofs:

1. Query `user_auth`: `anonymizedUsers(since: <last successful run>)` → `[{ id, anonymized_at }]`.
2. For each, `UPDATE legal_document_acceptance SET user_id = NULL,
   retention_anchor_date = :anonymized_at WHERE user_id = :id AND user_id IS NOT NULL`.

Everything evidential (`version_id`, `accepted_by_email` / `accepted_by_name`, `created_at`,
`acceptance_context`) is left frozen — this is the single permitted mutation (Data model
§Immutability). The anchor is set to the **real** `anonymized_at`, not the job's run time, so
the retention clock is exact regardless of poll latency.

**Windowing.** No persisted cursor is required: because the `UPDATE` is idempotent, the task
queries a **lookback window with margin** — `since = now() − (cadence + margin)` (e.g. 25h for a
daily run). Re-processing an already-reconciled user is a no-op (the `user_id IS NOT NULL`
guard skips it), so a generous overlap is safe and removes any cursor-persistence machinery.

**Authentication.** The task calls `user_auth`'s GraphQL as an **internal service**, not as a
user: it generates a short-lived service JWT via `ServiceAuthUtils` (`core/utils/auth`) and
calls the endpoint with `Authorization: Service <token>` — the mechanism described in
[`internal_service_communication`](../internal_service_communication.md). The
`anonymizedUsers` field is gated at `INTERNAL_SERVICE_ACCESS_LEVEL`, so only a service caller
reaches it.

**Properties.**
- **Idempotent** (`user_id IS NOT NULL` guard) — safe to re-run; a user already reconciled is
  skipped.
- **Correct dependency direction** — `legal → user_auth` via its **published GraphQL contract**,
  not its schema. `user_auth` knows nothing of `legal`.
- **Topology-independent** — GraphQL crosses the API boundary, so this works whether `legal` is
  co-located or split to its own store (the reason the soft FK is kept). No SQL join to the
  `user` table.
- **Latency ≤ cadence** — up to a day between anonymization and nulling. "Without undue delay"
  (art. 17) tolerates a daily batch; tighten the cadence (e.g. hourly) if needed — same task,
  just more frequent.

**Required on `user_auth`.** An internal GraphQL query
`anonymizedUsers(since: DateTime): [AnonymizedUser!]` returning `{ id, anonymized_at }`, exposed
at **`INTERNAL_SERVICE_ACCESS_LEVEL`** (service-to-service, not a user-facing field). The
reconciliation task calls it with a service credential. This is a small, reusable addition to
`user_auth`'s surface (also useful for audits).

### Retention purge

A daily task deletes acceptance rows whose retention has lapsed — selecting rows where
**`retention_anchor_date IS NOT NULL AND retention_anchor_date + retention < now()`**. The
anchor is the relationship-end (anonymization) date, **not** `created_at`: a still-active
customer (anchor `NULL`) is never purged, however old the acceptance. `retention` is the
prescription period for defending legal claims (≈ 5 years; **configurable**). It deletes the
**whole row**, snapshot included: the moment the identity finally leaves the store. Lawful basis
for keeping it until then: GDPR art. 17.3.e (establishment, exercise or defence of legal
claims), to be recorded in the processing register. Versions and their PDFs are not purged by
this job — only the acceptance proofs. A daily cadence has no urgency here (a row purged a day
after prescription is fine); daily simply bounds the backlog.

### Mechanism vs schedule

`legal` **provides** the two task callables (idempotent, parametrized by retention duration and
the `user_auth` GraphQL endpoint); the **consuming service schedules them** in its Celery Beat
config, mirroring how the app owns templates and content while lys owns the machinery.
Retention duration is a setting, not hardcoded.

### Why this reconciles erasure and proof

- **After anonymization**, the next reconciliation pass nulls `user_id` here — the proof can no
  longer be joined back to operational data. The **minimized snapshot** (email, name) is
  retained under art. 17.3.e; the person is informed that this narrow proof is kept for a
  limited period.
- **At prescription**, the row is purged — erasure is then complete.

**Cross-dependency (must hold for the guarantee to be real).** Nulling `legal`'s `user_id`
removes only *one* bridge. For the retained proof not to re-identify the person's
operational activity, the application's **operational anonymization must also break `user_id`
elsewhere** (purge or pseudonymize the user-keyed operational data). `legal` guarantees its
own side; making the whole coherent is the application's responsibility.

## Open points

Decisions the mechanism supports but does **not** resolve — they are product/legal policy,
to be settled by the consuming application before or during implementation. All are
**application-side**; the mechanism-affecting questions raised during design are already
resolved inside the relevant sections above.

### 1. B2B signatory authority *(application-side)*

An acceptance references a **user**, but sales terms bind the **company**. Who may accept on
the organization's behalf, and is one owner's acceptance sufficient to bind it? The common
SaaS answer is a **warranty-of-authority clause** in the terms themselves ("you confirm you
are authorized to bind your organization"), with the owner's acceptance recorded as-is — no
extra modeling. If stronger evidence is wanted (role/mandate at acceptance), it goes in
`acceptance_context`. Decide whether per-user acceptance + clause is enough, or an
organization-level binding is required.

### 2. Re-acceptance on version change *(application-side)*

When a new version becomes current, what happens to users/subscribers who accepted the prior
one? Options: **hard gate** on next login (block until re-accept), **grandfather** (old
acceptance stays valid until renewal), or **implied by continued use** (weakest, often
insufficient for CGV). Also: does **every** edit force re-acceptance, or only **material**
changes — and who classifies materiality? The mechanism detects the gap
(`outstanding_acceptances`); the policy (block vs soft-prompt vs grandfather, per type) is the
application's. Note the business risk: hard-gating paying subscribers on a CGV change can
block revenue-generating accounts.

### 3. Publication governance *(application-side / process)*

Versions publish **automatically** from the Markdown shipped in the app image (Publication
§Trigger). The **process around** that — legal review and approval of the new text, choosing
the `effective_date` and any notice period before it takes effect — is undefined and
deliberately out of the mechanism. The mechanism supports a **future `effective_date`**
(registered now, current later) to implement a notice period; who approves and how the date
is chosen is a process decision.

### 4. Consent withdrawal *(application-side)*

An acceptance is a **historical fact** and is not "withdrawn" like a marketing opt-in;
declining the current terms in practice means **ceasing to use the service** (account
closure → anonymization → the retention/purge path above). No withdrawal operation is
modeled. Confirm this framing meets the privacy-policy commitments, and that the closure
path is the documented way to "revoke."

### 5. Cross-dependency with operational anonymization *(application-side)*

Restated from [Retention and anonymization](#retention-and-anonymization): nulling `legal`'s
`user_id` closes only one re-identification bridge. The application's operational
anonymization **must also break `user_id` in every other user-keyed store** for the retained
proof snapshot to be truly non-re-identifying. `legal` guarantees its own side; the
end-to-end coherence is the application's responsibility.
