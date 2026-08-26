# Changelog

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.41.2] - 2026-08-26

### Fixed
- `sso_providers` is now reachable by connected users, not just anonymous ones (`is_public` changed from `"disconnected"` to `True`), so an already-authenticated user can list configured SSO providers to link/unlink their account instead of only seeing them pre-login

## [0.41.1] - 2026-08-26

### Fixed
- Multi-tenant SSO providers now verify the ID token's issuer against that directory's own published metadata (`SSOAuthService._assert_issuer_is_its_own_directory`), scoped to the authority already trusted by the deployment's configured `issuer_url`. Optional `allowed_tenants` restricts sign-in to a pre-approved set of directories; a provider whose discovery document advertises a per-directory issuer while not configured as `multi_tenant` now fails loudly (`SSO_PROVIDER_MISCONFIGURED`) instead of on an opaque token error
- `SSOProviderQuery` no longer lists SSO providers that are declared but missing a `client_id`, avoiding a login button that fails on an unreadable provider error

## [0.41.0] - 2026-08-25

### Added
- New `client_request` module in the `organization` app: `ClientRequest` tracks a request raised by a client through to its outcome (PENDING/PROCESSED/CANCELLED/ERROR), with `ClientRequestService.mark_processed`/`mark_failed`/`mark_cancelled` recording the transition. The request type is left for the consuming application to declare; lys only owns the record and its lifecycle
- `ClientNode.open_requests` GraphQL field: a client's requests still waiting for an action, oldest first
- Anonymizing a user (`organization.UserService.anonymize_user`) now also cancels their open client requests and clears the free-text fields (`contact_phone`, `message`) in the same transaction, via `ClientRequestService.cancel_open_for_anonymized_user`. Settled requests are left untouched — they describe the client, not the person

## [0.40.0] - 2026-08-21

### Added
- `RateLimitMiddleware` now buckets authenticated requests by user (`connected_user["sub"]`) instead of falling into the shared anonymous IP bucket, via a new `user_requests_per_minute` setting (default: 300). Keeps multiple users behind the same IP (NAT, corporate proxy) from sharing — and exhausting — one quota. Requires `UserAuthMiddleware` to be declared **after** `RateLimitMiddleware` in `settings.middlewares` (Starlette runs middlewares in the reverse of their declaration order), documented directly in the class docstring; getting the order wrong fails silently to the anonymous IP bucket

## [0.39.0] - 2026-08-21

### Added
- `extract_text` now also checks the PDF's font table (via `pdffonts`) before trusting `pdftotext`'s char count. A many-page scanned PDF can accumulate enough page-break characters to clear `min_text_chars` while carrying zero real text; an empty font table catches that case and routes to OCR regardless of char count. The check is skipped when the char count already falls under the threshold, since OCR is triggered either way and a second subprocess call would be wasted

## [0.38.1] - 2026-08-21

### Fixed
- `AppManager._register_webservices_to_auth_server` no longer defaults a webservice's `is_licenced` to `False` when the attribute is absent from its registered attributes. The Auth Server gates access on this flag, so a missing value must fail closed (licenced) rather than silently grant licence-free access; the fallback now matches the `True` default used everywhere else `is_licenced` is declared

## [0.38.0] - 2026-08-21

### Added
- Sync counterparts for quota enforcement, usable from Celery task contexts holding a sync `Session` where bridging to an `AsyncSession` isn't practical: `LicenseCheckerService.check_quota_sync` / `enforce_quota_sync`, `SubscriptionService.get_client_subscription_sync`, `LicensePlanVersionRuleService.get_rules_for_version_sync`. A new `SyncValidatorRegistry` (`validators_sync`) and `register_validator_sync` decorator let rule validators be registered for this sync path alongside the existing async `validators` registry

## [0.37.0] - 2026-08-21

### Added
- `AIConversation.client_id`, an optional soft-FK tenant reference stamped on a conversation at creation time. `AIConversationService.get_or_create` and `_prepare_chat_context` accept a `client_id` and forward it through, ignoring it once a conversation already exists. lys stays agnostic about how the value is resolved: a consumer app scoping conversations to a tenant overrides `_prepare_chat_context` to resolve it from its own trust boundary

## [0.36.1] - 2026-08-19

### Fixed
- A structured response cut off by the output token limit is no longer retried. `AIResponseTruncatedError` separates that case from an ordinary schema mismatch: truncation is deterministic, so the same request on the same endpoint hits the same limit, and three attempts per endpoint burnt the tokens of a large payload for nothing. It now falls back immediately, where a model with a different limit may answer
- A schema mismatch is retried on its own endpoint before falling back. A malformed answer says nothing about the provider's health, and moving straight to the fallback took the request off the model it was written for
- Anthropic's forced tool use sometimes nests the arguments one level deeper, under a lone wrapper key holding the whole object, itself sometimes a JSON string. That wrapper carries no information, so it is unwrapped and the otherwise complete response is recovered. Only attempted after validation has already failed, so a legitimate single-field payload is never rewritten
- The error raised once the fallback chain is exhausted now carries the last provider error, both in its message and as `__cause__`. The detail existed only in the logs, and the caller received an opaque `All providers failed`

## [0.36.0] - 2026-08-18

### Added
- Discount module: `LicenseDiscount` declares a reduction the catalogue can offer, `LicenseDiscountUnit` says how its value is read and `LicenseDiscountGrant` how it is obtained. A price is immutable and shared by every subscriber, so a negotiated or promotional reduction cannot be expressed as a price of its own. What entitles a client to a discount is not checked: the conditions are commercial and agreed outside the application
- `SubscriptionDiscount` records the discount a subscription benefits from, carrying the value **as granted**. A discount revised later never rewrites what a client was granted, which is the same promise immutable prices already carry. One row per subscription at most: discounts do not stack
- `Subscription.amount_due` and `Subscription.receipt`. The price says what the catalogue asks, these say what this client pays and on what basis. The receipt repeats the plan, the price, the currency, the discount and the commitment rather than referring to rows that can be revised, so it reads on its own
- `allClaimableLicenseDiscounts` lists what a client may claim when subscribing; `allLicenseDiscounts`, `createLicenseDiscount` and `setLicenseDiscountEnabled` administer the catalogue under `LICENSE_ADMIN_ROLE`; `revokeSubscriptionDiscount` undoes a grant made by mistake
- `subscribeToPlan` and `subscribeClientManually` accept a discount. A claimed discount is taken off the payment at checkout and granted once the payment is confirmed, never before: an abandoned checkout leaves nothing behind
- `allClientLegalAcceptances` lists the acceptance proofs recorded for a client's users, under `LICENSE_ADMIN_ROLE`. Reading what a company signed belongs to the same act as granting a discount against it

### Changed
- A discount claimed by a client is refused unless it is meant to be claimed. A business code is guessable, and both the payment amount and the grant now apply that rule, so a discount reserved to operators can neither be granted nor collected at a reduced price
- A commitment reaching its term removes the discount granted against it, and the subscription renews at the catalogue price. A denounced commitment does the same when its pending change is applied — its only occasion, since clearing the term takes it out of the renewal loop for good
- Every path that changes what is owed now realigns the recurring collection: the provider knows nothing of a discount and would keep charging the reduced amount indefinitely
- A discount is refused on a subscription carrying no price. It would reduce nothing, and with no price there is no commitment to end it

### Fixed
- Plan version fixtures no longer detach the rules they do not list, and set the parent explicitly on rules and prices added to a version already stored. An application refining a version the framework ships kept losing its own rules on the next boot

## [0.35.1] - 2026-08-16

### Fixed
- A commitment already running is no longer restarted by a plan change. Moving a client to another plan raises what they owe, but it must not lock them in for longer than what they signed: a three year term entered two years ago now ends on its original date, whichever plan they move to. A term that has lapsed still opens a new one, which the previous null check never did

## [0.35.0] - 2026-08-16

### Added
- `LicenseBillingMode` parametric entity routing how a subscription is collected: through the payment provider, or outside the application by invoicing. An application usually launches before its payment integration is ready, and entitlements, commitment and renewal already work in the meantime, since they depend on the plan and its price and never on how the money is collected
- `subscribeClientManually`, placing a subscription on a priced plan without taking any payment, and `setSubscriptionBillingMode`, both restricted to `LICENSE_ADMIN_ROLE` and deliberately not opened to organization roles: granting a paid plan is a commercial act, never a client one
- `SubscriptionNode` exposes the billing mode, so a billing team can read who is still to be invoiced

### Changed
- `Subscription.is_free` is derived from the subscribed price instead of the absence of a provider subscription. A paid subscription billed by invoice has no provider subscription and is not free
- The first successful payment records the provider mode, so the mode never claims a collection that has not started. Nothing is switched beforehand: flipping it in advance would stop the invoicing of a subscription nobody is charging
- Routing a subscription as manual is refused while the provider still collects. Switching the mode does not stop the provider subscription, and every provider branch is skipped once manual, so the client would be charged and invoiced at once, and a later cancellation would no longer stop the collection

## [0.34.0] - 2026-08-15

### Added
- Catalogue administration webservices, restricted to `LICENSE_ADMIN_ROLE`: `allLicensePlans` and `allLicensePlanVersions` list disabled and client-specific entries, which the public catalogue deliberately hides; `createLicensePlanVersion` publishes a version with its prices and its rules; `setLicensePlanVersionRule` corrects a limit; `setLicensePlanVersionEnabled` withdraws a version or puts a previous one back. Together they let an application define its commercial offer in preproduction and production, where the development fixtures do not run
- `LicensePlanVersionService.set_enabled`, enforcing that a single version of a plan is offered at a time
- `LicensePlanVersionRuleService.validate_rule`, shared by the publication and the correction paths so the same mistake surfaces the same way
- Integration test building the GraphQL schema with the licensing app loaded: a malformed resolver signature only fails when Strawberry resolves the fields, at application startup, so the whole suite passed while the application could not boot

### Changed
- `create_new_version` takes the version rules and creates them in the same transaction. The new version is offered as soon as it exists, so publishing it without its rules left a live version granting unlimited quotas
- A plan version must declare at least one rule, `NO_RULE_ON_VERSION` otherwise. A quota missing from a version is read as unlimited by the checker, and unlimited has its own representation, a null limit, which must stay deliberate
- `set_rule_limit` validates the version, the rule and the limit instead of relying on foreign keys to raise

### Removed
- `MAX_PROJECTS_PER_MONTH` rule and its validator. The validator always returned valid, since counting projects depends on an entity the framework does not own, so the limit shown in the catalogue was never enforced. A quota the framework cannot count belongs to the application

## [0.33.0] - 2026-08-14

### Changed
- `LicensePlanDevFixtures` no longer disables the plans it does not list. Custom plans negotiated with a single client are created at runtime and appear in no `data_list`, so the sweep silently disabled them and removed them from the catalogue while their subscribers kept their entitlements. Retiring a plan is now an explicit `enabled: False`

### Removed
- `STARTER` and `PRO` plans and their versions. `LicensePlan` is parametric, so these demonstration tiers were loaded in every environment, production included, and competed with the plans of the applications consuming the framework. Only the free plan is shipped, because the framework depends on it: a new client is subscribed to it and a cancellation falls back to it

## [0.32.0] - 2026-08-14

### Added
- `LicenseCommitment` parametric entity carrying the initial duration, the span it is tacitly renewed for and the notice required before the term, so that a commitment is not billed as a periodicity
- `commitment_id` on plan version prices, letting the same plan be priced differently depending on how long the client commits, and `commitment_end_date` on subscriptions
- `commitmentId` argument on the `subscribeToPlan` mutation
- Tacit renewal in `apply_pending_plan_changes`: a commitment reaching its term undenounced is renewed for its own renewal span, or simply ends when it has none
- `SubscriptionNode` exposes the commitment term, the notice deadline and whether a cancellation can still be requested, so a client can know when they may leave
- `subtract_months` deriving a notice deadline from a commitment term, with the same day clamping as `calculate_period_end`

### Changed
- A downgrade or a cancellation requested under commitment is deferred to the commitment term instead of the billing period end, and the recurring collection continues until then; stopping it earlier would have handed out the remaining periods for free
- A downgrade or a cancellation is refused with `NOTICE_PERIOD_EXPIRED_ERROR` once the notice deadline has passed, the commitment being renewed at that point
- `LicensePlanVersionService.create_new_version` rejects a commitment that does not span a whole number of billing periods, which would otherwise leave a partially billed period nobody can settle

## [0.31.0] - 2026-08-13

### Added
- `MollieCheckoutService.update_subscription_amount` and `cancel_provider_subscription`, aligning or stopping a recurring collection without database access, so they can be called from services and background tasks alike
- `major_unit_value` on plan version prices, giving the decimal string payment providers expect and honouring currencies without decimals

### Changed
- `Subscription` references the exact price subscribed to through `plan_version_price_id`, which carries the periodicity, the currency and the amount agreed upon, replacing the `billing_period` column
- `SubscriptionService.change_plan` realigns the subscribed price on the new version when the change is immediate, instead of leaving a price belonging to another version
- `apply_pending_plan_changes` resolves the new price on the terms subscribed to, and skips the change with an error when a paid target carries no such price, rather than granting a plan that cannot be billed

### Fixed
- An upgrade no longer leaves the payment provider charging the previous, lower amount; the recurring collection is realigned when the plan actually changes, including when no prorata payment is needed
- A downgrade to a cheaper plan realigns the recurring collection when the change takes effect, instead of keeping the previous amount
- A downgrade to a free plan stops the recurring collection, instead of charging the client indefinitely for a plan they no longer hold
- `SubscriptionService.cancel` now goes through the downgrade path, so cancelling and downgrading to a free plan can no longer diverge, and it reports a failure when the collection could not be stopped
- Changing the periodicity or the currency of a running subscription returns `BILLING_TERMS_CHANGE_ERROR` instead of computing a prorata between two different cadences

## [0.30.0] - 2026-08-13

### Added
- `LicenseCurrency` and `LicensePricePeriod` parametric entities, with their services, nodes and fixtures
- `LicensePlanVersionPrice` entity holding one price per (plan version, period, currency)
- `currencyId` argument on the `subscribeToPlan` mutation

### Changed
- Plan version pricing moved out of `LicensePlanVersion` into `license_plan_version_price`, so a new periodicity or currency no longer requires a schema migration
- `LicensePlanVersionService.create_new_version` takes a `prices` list and creates version and prices in the same transaction, rejecting duplicate (period, currency) pairs, non-positive amounts and unknown periods or currencies
- `calculate_period_end` takes a number of months instead of a period name, computing any cadence in a single code path
- `subscription.billing_period` is now a foreign key to `license_price_period`
- `BillingPeriod` values are uppercase to match the parametric entity IDs

### Fixed
- `subscribe_to_plan` rejects a paid plan version that carries no price for the requested period and currency; the request previously fell through to the downgrade branch and scheduled the plan change without any payment

### Removed
- `price_monthly`, `price_yearly`, `currency` and `provider_product_id` columns on `LicensePlanVersion`
- Payment provider synchronization hook in the plan version fixtures, which called a service that was never implemented; the Mollie API exposes no product catalog to synchronize

## [0.29.0] - 2026-08-11

### Added
- `lys.core.utils.ingest.extract_text`: stateless document-to-text extraction (bytes + MIME type -> text), with OCR used only when a free extraction path is unavailable. A PDF's embedded text layer is read locally with `pdftotext` (poppler); a text layer shorter than `min_text_chars` means a scanned document and falls back to OCR, as do images. Any other MIME type raises `UnsupportedDocumentError`. The OCR service is injected through an `OcrService` Protocol rather than resolved via `app_manager`, so the module stays usable without the `ai` app loaded. Every `pdftotext` failure mode (missing binary, timeout, non-zero exit) is non-fatal, logged at WARNING, and degrades to OCR; partial output from a failed run is discarded so it cannot skip an OCR pass the document needed. `pdftotext` output is decoded as UTF-8 explicitly, since the process locale would raise on accented text under the `C` locale. Requires the `poppler-utils` OS package in the consuming image — see `docs/FRS/_core/ingest.md`.

## [0.28.1] - 2026-08-10

### Fixed
- `check_access_to_object` raised `MissingGreenlet` when an entity's `check_permission` (or the `accessing_users` / `accessing_organizations` chain it calls) walked an unloaded relationship. The check now runs inside `session.run_sync` when the entity is still attached to a session, so implicit lazy loads resolve; detached entities keep the direct call.

## [0.28.0] - 2026-08-05

### Added
- `FileImportService.stage_document`: single-document counterpart of `stage_zip_documents`, for entry points receiving files one by one through the presigned upload flow. Creates a StoredFile plus a PENDING FileImport, or a SKIPPED FileImport pointing at the original on a content-hash duplicate — in which case the already-uploaded object is purged, since no record will ever reference it. Returns a `StagedDocument`. Extra columns can be routed per record (`stored_file_fields` / `file_import_fields`) or to both (`**entity_fields`); a field colliding with a column the method sets itself (`RESERVED_STAGING_FIELDS`) raises a readable `ValueError`.
- `FileImportService.find_active_import_async`: async counterpart of `find_active_import`, same rule and same best-effort guarantee. Both now share `_active_import_stmt`.
- `StoredFileService.create_from_uploaded` validates the stored object instead of trusting the caller: actual size read via `head_object` and checked against the declared one, optional `max_size`, and optional `validate_zip` checking the ZIP magic bytes on the stored bytes (`ZIP_MAGIC_BYTES`, local file header only — an empty or spanned archive is rejected). A rejected upload is purged. Also accepts a declarative `content_hash` and subclass `entity_fields`.
- `StoredFileService.check_object_key_ownership`: object keys travel through the client during the presigned upload flow, so they come back as untrusted input. Every operation acting on a key on a client's behalf now checks it against `client_id` first.
- `StoredFileService.purge_object`: best-effort removal of an object no record will reference (rejected upload, orphan left by a skipped staging). Failures are logged, never raised, so the caller's own error surfaces.

### Fixed
- `create_from_uploaded` reported every storage failure as "File not found", masking outages, denied calls and credential errors. A missing object is now told apart from a backend failure (`_is_not_found_error`), which is logged and propagated.

## [0.27.0] - 2026-08-05

### Added
- `StoredFile.deleted_at`: soft delete timestamp. A soft-deleted file has its S3 bytes purged but keeps its row as a tombstone, so the `content_hash` still feeds the import idempotency lookup and the audit trail survives. No global read filter is applied — callers serving or listing live files must exclude tombstones, and the schema migration belongs to the consuming application.
- `StoredFileService.soft_delete_file` / `soft_delete_file_sync`: purge the stored bytes and mark the row instead of deleting it. Idempotent on an already tombstoned row. The S3 purge deliberately runs before the commit: on a commit failure the bytes are gone while the row stays unmarked, which is preferable to a row claiming deletion while the bytes remain and the idempotency guard blocks any retry from clearing them.

### Changed
- `AbstractImportService.perform_import` soft deletes the source file after a successful import instead of hard deleting it. The hard delete destroyed the `content_hash`, so `find_active_import` could never match a COMPLETED import and re-imports of the same file were never deduplicated; it also left `FileImport.stored_file_id` dangling.
- The post-import purge no longer runs inside the import's `try` block: the import data is already committed at that point, so a purge failure is logged and swallowed instead of flipping the import to FAILED. A committed import marked FAILED would let a re-import bypass the content-hash idempotency check (FAILED imports are ignored there) and duplicate the data.

### Fixed
- `StoredFileService.delete_file_sync` skipped the S3 purge when the row was already gone, leaving orphaned bytes in the bucket. Both deletion modes now purge the bytes using the detached entity's path when the row cannot be found.

## [0.26.0] - 2026-08-04

### Added
- `AIStreamChunk.reasoning`: reasoning trace of thinking models, carried apart from `content` so it never reaches the user by accident. `MistralProvider._extract_reasoning` reads the `thinking` blocks (both the nested-list and plain-string shapes returned by the API); `_extract_text` still keeps only the `text` blocks.
- Chatbot SSE stream: `reasoning_progress` event carrying only `characters`, the running size of the reasoning trace for the current LLM call (restarts at 0 on each tool iteration). A reasoning model can spend tens of seconds before its first answer token, and the size is enough to prove liveness without publishing the trace. The trace itself is emitted as a `reasoning` event only when `chatbot.expose_reasoning` is set (default `False`): it is a draft naming internal tools and vocabulary a system prompt may forbid showing.
- `MistralProvider._normalize_usage`: maps `usage.prompt_tokens_details.cached_tokens` to the provider-neutral `cache_read_tokens` key already used by the Anthropic provider, so cached-prompt activity is recorded instead of silently reading as zero.
- Anthropic provider: `claude-opus-5`, `claude-sonnet-5` and `claude-fable-5` added to `MODELS`, and to `MODELS_REJECTING_SAMPLING` — the Claude 5 generation rejects `temperature`/`top_p`/`top_k`, which are dropped with a warning instead of forwarded.

### Fixed
- `MistralProvider._cache_key_field` derived `prompt_cache_key` from the whole system prompt, volatile segments included (focus marker, current date, conversation summary, per-turn tool context), so every turn landed in its own cache bucket. The key now hashes only the segments flagged cacheable, and is computed before `_flatten_system` (once flattened, stable and volatile segments cannot be told apart). Several segments with none flagged cacheable yield no key at all, rather than one derived from volatile content.
- `sanitize_llm_messages` preserves system segment boundaries as soon as there are several messages, cacheable or not. Flattening is lossy: a consumer could no longer tell the stable prefix from the volatile tail.
- Anthropic provider: a structured system prompt with no segment flagged cacheable received no `cache_control` breakpoint at all, dropping the system prompt out of the cache — where the single-string shape always caches it. The breakpoint now falls back to the last segment.

## [0.25.0] - 2026-08-01

### Added
- Mistral provider: `reasoning_effort` accepted in `VALID_OPTIONS`, so the option reaches the API instead of being filtered out of the payload. Reasoning models return `content` as a list of typed blocks mixing `thinking` and `text`; `MistralProvider._extract_text` keeps only the `text` blocks, so the reasoning trace never reaches the caller.

### Fixed
- Mistral streaming with reasoning models: a `delta.content` block list was forwarded as-is in `AIStreamChunk.content`, raising `TypeError: can only concatenate str (not "list") to str` in the SSE accumulator and leaking the reasoning trace into the stream. Deltas are now flattened to text; a thinking-only delta yields no content.
- `MistralProvider._parse_response` returns `""` instead of `None` when a response carries no text block (reasoning-only answer, or explicit `content: null`). `AIResponse.content` is typed `str`, and the `len(content)` calls in the non-stop-finish and validation-failure loggers raised a `TypeError` that masked the real `AIValidationError` on truncated reasoning responses.

## [0.24.0] - 2026-07-23

### Added
- `legal` app (`lys.apps.legal`): versioned legal documents with provable, version-bound consent.
  - `LegalDocumentType` (parametric, with a `requires_acceptance` gating flag), `LegalDocumentVersion` (immutable append-only registry, content-hash idempotent publication), `LegalDocumentAcceptance` (append-only consent proof with a self-contained identity snapshot that survives anonymization).
  - Publication at startup via the service `on_initialize` hook (fault-tolerant, per-document session), rendering Markdown to an immutable PDF through `lys.core.utils.pdf` and storing it via the shared storage backend. GDPR data minimization (IP truncation, user-agent capping) applied service-side for all callers.
  - GraphQL: `currentLegalDocument` (public), `acceptLegalDocument` (connected, `lys_creation`), `outstandingLegalAcceptances` (connected). Public REST PDF routes (`/legal/{type}/{language}`, `/legal/versions/{id}`) auto-mounted like the Mollie webhook.
  - Celery tasks: daily anonymization reconciliation (polls `user_auth` over an internal-service GraphQL feed) and retention purge (GDPR art. 17.3.e).
  - `LegalSettings` (`settings.legal`): declared documents (`type → languages → source`), `retention_days`, reconciliation endpoint.
- `user_auth`: internal `anonymizedUsers(since)` relay connection (gated `INTERNAL_SERVICE_ACCESS_LEVEL`) exposing `id` + `anonymized_at`, consumed by the legal reconciliation task.
- `Context.client_ip` / `Context.user_agent`: reusable request-metadata accessors on the GraphQL context.
- `core.utils.storage.get_configured_storage_backend`: shared, memoized backend resolver used by `file_management` and `legal` (removes per-service duplication without coupling the apps).

### Fixed
- `test_graphql_subscription_logic`: annotate the `info` parameter of the subscription test resolver (`info: Info`). Strawberry >= 0.3xx requires the reserved `info` context parameter to be annotated; the unannotated fixture raised `MissingArgumentsAnnotationsError`, breaking the suite on the declared strawberry floor (`>=0.287.0`, used in preprod).

## [0.23.0] - 2026-07-20

### Added
- `lys.core.utils.pdf`: stateless PDF rendering utility. `markdown_to_html` (Python-Markdown with `extra`/`toc`/`sane_lists`), `render_html_to_pdf` (WeasyPrint, optional `base_url` and extra `stylesheets`), `render_markdown_to_pdf` (Markdown → HTML body → Jinja2 layout → PDF), plus the `render_markdown_to_pdf_async` worker-thread wrapper for async callers. Raises `PdfRenderError` (a plain domain exception, not `LysError`) when the optional `pdf` extra is missing or rendering fails.
- `PdfSettings` (`settings.pdf`) with `template_path` (default `/templates/pdf`), resolved like `EmailSettings.template_path`. PDF layout templates load via a Jinja2 `ChoiceLoader`: application templates first, then the lys built-in fallback (`pdf_templates/default.html` + `default.css`, a minimal A4 layout with a `{{ body }}` slot).
- `pdf` optional-dependency extra (`weasyprint>=62`, `markdown>=3.6`), added to the `all` and `test` extras; built-in templates shipped via package data.

## [0.22.0] - 2026-06-26

### Added
- `NotificationService.mark_all_as_read(session, user_id)`: clears every unread notification of a user in a single `UPDATE`, scoped to the user at the database level (independent of frontend pagination). Returns the remaining unread count.
- `mark_all_notifications_as_read` GraphQL mutation (`NotificationMutation`): marks all of the connected user's unread notifications as read. Connected access level, scoped to `connected_user["sub"]`; returns the remaining unread count.

## [0.21.0] - 2026-06-19

### Added
- `AIConversationService._get_focus_context`: overridable hook (returns `None` in the base framework) for a per-turn focus marker — a small, volatile layer-C anchor describing what the user is currently looking at. Injected as the first volatile system segment (after the cacheable layers, before the summary and per-turn context) so it frames the rest without busting the cache.

### Changed
- `ToolExecutor._inject_page_params` now takes `force_ids` (default `True`). `*_id` params are pinned to the page focus only on the service-auth path (no per-user gateway filtering); with a user bearer token (`force_ids=False`) the LLM may override ids to roam across entities, access then being enforced by the user token at the gateway and writes by the confirmation guardrail. `GraphQLToolExecutor` records `_user_authed` at construction and pins ids only when it has no user bearer. Non-id params remain page-focus defaults filled in only when omitted.

### Fixed
- `GraphQLToolExecutor.execute` docstring corrected: it authenticates with the user's bearer token when built with one (gateway applies per-user access filtering), falling back to the service JWT otherwise.

## [0.20.0] - 2026-06-19

### Added
- `AIConversationService._get_stable_context`: overridable hook (returns `None` in the base framework) for a session-stable, cacheable context layer injected as the first system segment, before the page prompt. Consumers override it to push a byte-deterministic per-session map; ordered most-stable-first so a page change does not bust its cache.

### Changed
- `AnthropicProvider` now places one prompt-cache breakpoint per cacheable system layer instead of a single breakpoint on the last cacheable segment. Breakpoints are budgeted under Anthropic's 4-per-request cap (the tools block and the rolling last-message breakpoint each reserve one); when the cacheable layers exceed the remaining budget, the most-stable (earliest) layers keep their breakpoints, since the rolling last-message breakpoint already caches the longest fully-stable prefix.

## [0.19.0] - 2026-06-19

### Added
- Conversation compaction: `AIConversationSummary` entity (`ai_conversation_summary`) holding a rolling summary of older messages, the boundary message it covers (`through_message_id`), the summarization call's cost (model + token/cache fields), and a `completed` flag that doubles as a concurrency guard. `AIConversation.summaries` relationship added.
- `AIConversationService.maybe_enqueue_compaction`: best-effort, off-request-path trigger. When the last turn's real billed prompt size (input + cache read + cache write tokens) exceeds `chatbot.compaction.token_threshold`, a pending summary row is created and a Celery task enqueued. A recent pending row (within `compaction_pending_ttl`) blocks a second enqueue; it never raises so a failure cannot break the turn.
- `AIConversationService.fill_summary` (+ `_load_current_summary`, `_compute_compaction_boundary`, `_render_summary_input`, `discard_pending_summary` / `_sync`): incremental summarization of the slice between the previous and current boundary, merged with the prior summary. `_build_messages` returns only the verbatim window after the current summary boundary; the summary is injected as a volatile (uncached) system segment.
- `summarize_conversation` Celery task: fills a pending summary row off the request path and discards it on failure so the next turn re-enqueues.
- Compaction configuration defaults (locale-neutral, overridable via the ai plugin config): `conversation_summary` endpoint, `chatbot.compaction.{token_threshold, window_messages}`, pending TTL, and a default summary prompt that preserves per-subject facts and writes in the conversation's language.

### Changed
- `AnthropicProvider` rolling cache breakpoint is now gated on the presence of conversation history (a prior assistant turn) rather than on the system-prompt shape, so any multi-turn consumer benefits while one-shot calls pay for no unused cache write.

### Removed
- `cleanup_old_ai_conversations` Celery task and `AIConversationService.delete_old_conversations`: conversation history is now bounded by compaction (summarization) instead of deletion.

## [0.18.0] - 2026-06-18

### Added
- Segmented system prompt with provider prompt-cache breakpoints. `AIConversationService._build_system_prompt` now returns an ordered list of `{"content", "cache"}` segments: the page-specific prompt is stable per page (cacheable) and the dynamic per-request context (company / year / turn) is volatile (uncached), so the volatile tail no longer busts the cache of the stable prefix.
- `sanitize_llm_messages` preserves system-segment boundaries when any segment carries a truthy `cache` flag (content becomes an ordered list of `{"text", "cache"}` blocks); without a cacheable segment it flattens to the historical single string.
- `AnthropicProvider` places cache breakpoints for a structured system: one at the last cacheable system segment, one on the last tool, and a rolling breakpoint on the last message (multi-turn prefix caching). A one-shot string system keeps its single-breakpoint shape.
- `MistralProvider._flatten_system`: flattens a segmented system message back to a single string (Mistral takes a plain string), applied across all chat entry points.

### Removed
- `AIConversationService._get_user_details` / `_get_user_roles_info`: the system prompt no longer injects the user's identity and roles. This removes two DB queries per message and keeps user PII out of cached prompt prefixes (intentional behaviour change).

### Fixed
- `AnthropicProvider.chat_stream` now carries the response model forward from `message_start` to the final chunk, so streamed assistant messages are persisted with their `model` (previously `None` for Anthropic streaming, unlike non-streaming and Mistral).

## [0.17.0] - 2026-06-18

### Added
- `AIMessage.cache_read_tokens` / `AIMessage.cache_write_tokens`: nullable `Integer` columns recording provider prompt-cache usage (Anthropic `cache_read_input_tokens` / `cache_creation_input_tokens`), enabling measurement of cache effectiveness. Provider-agnostic: providers that do not report cache usage leave them `None`.
- `AnthropicProvider` now surfaces prompt-cache token counts in normalized usage (`cache_read_tokens` / `cache_write_tokens`) for both streaming (carried forward from `message_start`) and non-streaming responses. `total_tokens` continues to exclude cache tokens.

### Changed
- `AIConversationService` persists `cache_read_tokens` / `cache_write_tokens` on every assistant message across all chat paths (sync, tool-loop, streaming). Token-column mapping is centralized in the new `AIConversationService._usage_fields(usage)` helper, removing the previously duplicated extraction at each `AIMessage` creation site.

## [0.16.0] - 2026-06-11

### Added
- `StoredFile.content_hash`: nullable, indexed `String(64)` column holding the SHA-256 hex digest of the file content (basis for import idempotency). Null when the content is not available server-side at creation (e.g. presigned-URL upload).
- `StoredFileService.content_hash(data)`: returns the SHA-256 hex digest for in-memory bytes, and `None` for a file-like stream (which is not consumed, to avoid breaking the upload). `upload` / `upload_sync` now populate `content_hash` automatically.
- `StoredFileService.upload` / `upload_sync` accept arbitrary `**entity_fields`, forwarded unchanged to the StoredFile entity (supports subclass-defined columns).
- `FileImportService.find_active_import(session, client_id, content_hash)`: returns the most recent non-failed (PROCESSING/COMPLETED) FileImport for a client whose StoredFile shares the given content hash; returns `None` for a falsy hash. FAILED/SKIPPED/CANCELLED imports are ignored, so a re-import after a failure is always allowed.
- `FileImportService.stage_zip_documents(...)`: generic ZIP import staging engine. Downloads and safely extracts a ZIP (path-traversal / zip-bomb protected), then creates one StoredFile + PENDING FileImport per document. Optional content-hash idempotency (`check_idempotency`) records a SKIPPED FileImport for duplicates (existing in DB or earlier in the same ZIP, the in-batch original taking precedence) instead of re-importing. `max_files` is enforced during extraction (early rejection, bounded memory); per-document errors are isolated so one bad document does not abort the batch; the source ZIP is deleted only on a fully clean run. Idempotency is best-effort (check + insert is not atomic and there is no unique constraint).
- `FILE_IMPORT_STATUS_SKIPPED` file import status constant and fixture.

## [0.15.0] - 2026-06-09

### Added
- Document OCR capability on the AI provider layer. `AIProvider.ocr` / `ocr_sync` are optional methods that default to raising `NotImplementedError`, and `AIService.ocr` / `ocr_sync` walk the endpoint fallback chain — skipping providers that don't support OCR (`NotImplementedError`) or error (`AIError`) — and raise `AIError` only when no provider in the chain succeeds. Takes raw document bytes + MIME type, returns concatenated per-page markdown.
- `MistralProvider.ocr` / `ocr_sync`: OCR via Mistral's dedicated `/ocr` endpoint (model from config, e.g. `mistral-ocr-latest`). Builds a base64 data-URI `document_url` (or `image_url` for `image/*` MIME types) and concatenates the per-page markdown; `include_image_base64` is disabled to keep responses lean.
- `MistralProvider` now sends a stable `prompt_cache_key` (derived from a SHA-1 of the system prompt) on every chat/stream/JSON request. Requests sharing the same system prompt reuse Mistral's prompt cache, lowering cost (cached input billed at ~10%). Omitted when there is no string system message.

## [0.14.0] - 2026-06-09

### Added
- `AnthropicProvider` now sends the system prompt as a `cache_control: {"type": "ephemeral"}` text block, enabling Anthropic prompt caching. When the system block (instructions / catalog / context) is identical across a batch of requests within the 5-minute TTL, cached input tokens are billed at ~10% of the base rate. Sub-minimum prompts simply aren't cached (no error).

### Changed
- `AnthropicProvider` request payload sends `system` as a list of content blocks instead of a bare string (required to attach `cache_control`). No change for callers — the translation is internal.

## [0.13.0] - 2026-06-09

### Added
- `lys.apps.ai.utils.providers.anthropic.AnthropicProvider`: full `AIProvider` implementation for Anthropic's Messages API (chat, chat_sync, streaming, structured JSON). Registered under `provider="anthropic"` in `AIService._providers`; the API key resolves automatically from `_keys["anthropic"]`. Translates the OpenAI/Mistral-shaped flat message list to Anthropic's `system` field + `tool_use`/`tool_result` content blocks in both directions, so no calling code changes when an endpoint switches providers. Structured output uses forced `tool_choice` (Anthropic has no native `response_format`). Known models: `claude-opus-4-8`, `claude-sonnet-4-6`, `claude-haiku-4-5`.

### Fixed
- `AnthropicProvider` drops `temperature`/`top_p`/`top_k` (with a warning) for models that reject them (Opus 4.7+), instead of forwarding them and triggering an HTTP 400; they are still forwarded for models that accept them (e.g. Sonnet 4.6).
- `AnthropicProvider` streaming now carries `input_tokens` from the `message_start` event into the final usage chunk, so streamed responses report complete `prompt_tokens`/`completion_tokens`/`total_tokens` instead of only completion tokens.
- `AnthropicProvider` concatenates multiple `system` messages (blank-line separated, input order preserved) rather than keeping only the last one, matching `sanitize_llm_messages` behavior.

## [0.12.3] - 2026-06-02

### Fixed
- `sanitize_llm_messages` now merges multiple `system` messages into a single index-0 message (contents concatenated with a blank-line separator, input order preserved) instead of keeping the first and silently dropping the rest. This preserves the conversation-level system prompt when an endpoint-level base prompt is prepended on top of it. Empty/falsy system contents are skipped.
- `AIConversationService._build_system_prompt` no longer re-injects `chatbot_config.system_prompt`: it is the same value as `endpoint.system_prompt`, which `AIService` entry points already prepend. With the sanitizer now merging system messages, re-injecting it here would duplicate the base prompt in the final merged system message.

## [0.12.2] - 2026-05-26

### Fixed
- `Entity.created_at` / `updated_at` previously used `server_default=func.now()`, which Postgres resolves to `transaction_timestamp()` (frozen at transaction start). Multiple rows inserted in the same transaction shared the same value, making `ORDER BY created_at` non-deterministic. Replaced with Python-side `default=lambda: datetime.now(UTC)`, evaluated per row at INSERT/UPDATE time. Cross-DB (works on Postgres and SQLite, the latter used by the test suite).
- `AIConversationService._build_messages` now orders by `(created_at, id)` instead of `created_at` alone, providing a stable tiebreaker for rows with identical timestamps. Together with the per-row timestamp fix, this resolves the Mistral "Unexpected role 'tool' after role 'system'" error that surfaced when conversation history rows were replayed in a non-deterministic order.

### Added
- `lys.apps.ai.utils.message_sanitizer.sanitize_llm_messages`: provider-agnostic enforcer of the LLM message-ordering contract (Mistral/OpenAI/Anthropic). Keeps at most one `system` at index 0, reattaches each `tool` message immediately after the `assistant` whose `tool_calls[].id` matches, drops orphan `tool` messages, and injects a synthetic placeholder for any `assistant.tool_calls[]` entry left without a response. Applied as a defense-in-depth boundary in all `AIService.chat*` entry points.

## [0.12.1] - 2026-05-21

### Fixed
- `GraphQLToolExecutor._handle_navigate` stored `created_at` / `expires_at` with the deprecated naive `datetime.utcnow()`, while `AIGuardrailService.confirm_action` compares `expires_at` against `datetime.now(UTC)`. Confirming a pending navigation raised `TypeError: can't compare offset-naive and offset-aware datetimes`. Both fields are now stored as timezone-aware (`datetime.now(UTC)`), matching `guardrails.py`.

## [0.12.0] - 2026-05-21

### Changed
- `UserService.get_by_email` and `AuthService.get_user_from_login` now perform case-insensitive lookups (`func.lower()` on the column compared against a lowercased, stripped input). Recovers legacy mixed-case rows and matches the RFC 5321 convention. Both accept `None` and resolve to no user instead of raising.
- `UserService._validate_and_prepare_user_data` and `UserService.update_email` normalize the address (`strip().lower()`) before persisting, so newly written rows always match the case-insensitive lookup.
- `LoginInputModel.validate_login` lowercases the login at the Pydantic boundary (was strip-only), keeping input normalization consistent with `CreateUserInputModel.validate_email` and `UpdateUserEmailInputModel.validate_email`.
- `UserFixtures.format_email_address` normalizes the seeded address so fixture-loaded rows always match the case-insensitive lookup.
- BREAKING (API): the `requestPasswordReset` GraphQL mutation now takes `inputs: RequestPasswordResetInput!` (with a normalized `EmailStr` field) instead of a bare `email: String!`. Clients must update their queries from `requestPasswordReset(email: $email)` to `requestPasswordReset(inputs: {email: $email})`.

### Added
- `RequestPasswordResetInputModel` (Pydantic) and `RequestPasswordResetInput` (Strawberry): validate the email as `EmailStr` and normalize it at the boundary so the service-layer lookup matches existing rows regardless of input casing.

## [0.11.0] - 2026-05-05

### Changed
- BREAKING (operational): user `access_token` cookie is now an opaque UUID resolved server-side via Redis (`AccessTokenStore`) instead of a JWT carrying claims inline. Fixes silent cookie drop for users whose claims push the JWT past the RFC 6265 4096-byte browser limit. Existing access cookies become invalid on deploy; the refresh flow re-issues a new opaque cookie transparently.
- `UserAuthMiddleware` resolves tokens through `AccessTokenStore` instead of decoding a JWT; XSRF semantics unchanged.
- `AuthService.login` accepts an optional `request` and revokes any stale access token from the previous session before issuing a new one (symmetry with `refresh_access_token`).
- SSO link flow resolves the connected user via `AuthService.resolve_access_token` instead of decoding the cookie inline.

### Added
- `AccessTokenStore` (`lys/apps/user_auth/modules/auth/store.py`): server-side opaque token store keyed under `lys:access_token:` with TTL aligned on `access_token_expire_minutes`.
- `AuthService.resolve_access_token(token_id)` and `AuthService.revoke_access_token(token_id)` public hooks for callers outside the auth module.
- Server-side revocation on logout and refresh: a leaked access cookie cannot be replayed until TTL — it is deleted immediately.

## [0.10.0] - 2026-05-05

### Added
- Add `NotificationSeverity` parametric entity (`INFO` / `SUCCESS` / `WARNING` / `ERROR`) with fixtures, GraphQL node and `allNotificationSeverities` query
- Add `severity_id` FK on `NotificationType` (server_default `INFO`, indexed) and expose `severity` resolver on `NotificationTypeNode`
- Add `is_read` and `severity_id` filters on the `allNotifications` query

### Changed
- BREAKING: `NotificationBatchNode.type_id` scalar replaced by a `type` resolver returning `NotificationTypeNode` (read severity via `type.severity` and id via `type.id`)
- Set licensing notification fixtures' severity (`LICENSE_GRANTED`/`SUBSCRIPTION_PAYMENT_SUCCESS` → SUCCESS, `LICENSE_REVOKED`/`SUBSCRIPTION_CANCELED` → WARNING, `SUBSCRIPTION_PAYMENT_FAILED` → ERROR)

### Fixed
- Relay connection pagination: truncate Strawberry overfetch when its size exceeds `expected + 1` (observed overfetch=21 for expected=10) instead of only handling the `+1` case

## [0.9.1] - 2026-04-27

### Changed
- Expose `finish_reason` field on `AIResponse` and propagate it from `MistralProvider._parse_response` (covers `chat`, `chat_sync`, `chat_json`, `chat_json_sync`)
- Add Mistral structured-output observability: warn when `finish_reason` is non-stop (e.g. `length`, `content_filter`) and log Pydantic validation failures with finish_reason / completion_tokens / content length context

## [0.9.0] - 2026-04-27

### Changed
- Switch `MistralProvider.chat_json` / `chat_json_sync` to Mistral's native `response_format: json_schema` (strict) mode; remove obsolete schema-injection helper `AIProvider._inject_schema_in_messages`

## [0.8.2] - 2026-04-04

### Fixed
- Filter disabled webservices from `accessible_webservices` query, preventing `enabled=False` webservices from appearing in user-accessible lists

## [0.8.1] - 2026-04-03

### Fixed
- Add `id` tiebreaker to Relay connection pagination to guarantee stable ordering across pages

## [0.8.0] - 2026-04-03

### Added
- Add `StoredFileNode` GraphQL node for stored file entity
- Add `FileImportNode`, `FileImportTypeNode`, `FileImportStatusNode`, and `ActiveFileImportsCountNode` GraphQL nodes for file import module
- Add `FileImportQuery` with `all_file_imports` connection and `active_file_imports_count` field
- Add unit tests for file import nodes and webservices

### Changed
- Fix `ActiveFileImportsCountNode` to use `ServiceNode[FileImportService]` instead of `ServiceNode[Service]`

## [0.7.2] - 2026-04-03

### Changed
- Rename `ai_conversations` table to `ai_conversation` and `ai_messages` table to `ai_message` to follow singular naming convention
- Document singular table naming convention as mandatory in Architecture Rules

## [0.7.1] - 2026-04-01

### Fixed
- Re-raise exceptions in `AbstractImportService.perform_import` after setting FAILED status, so Celery correctly detects task failures and can retry

## [0.7.0] - 2026-03-31

### Added
- Add `head_object` and `download_range` methods to `StorageBackend` abstract class and `S3StorageBackend` implementation (async + sync variants)
- Add input validation on byte range parameters in `download_range`
- Add unit tests for all new storage methods (16 tests)

## [0.6.5] - 2026-03-28

### Changed
- Move notification user filtering from webservice query to `Notification.user_accessing_filters` classmethod, leveraging framework OWNER_ACCESS_LEVEL

### Added
- Unit tests for notification entities (NotificationType, NotificationBatch, Notification)

## [0.6.4] - 2026-03-16

### Fixed
- Protect `add_tool_result` DB calls in agent loop with try/except to prevent cascade failures when saving tool errors

## [0.6.3] - 2026-03-13

### Fixed
- Pass `access_token` to context tool functions for authenticated GraphQL calls
- Fix orphaned user message on streaming provider error (delete with error handling)
- Fix Mistral provider streaming error handling (read response body before raising)
- Fix `logger.debug` indentation for context tools when `access_token` is absent

## [0.6.2] - 2026-02-25

### Added
- `ai` and `all` optional dependency groups in pyproject.toml

## [0.6.1] - 2026-02-25

### Fixed
- Fix `AttributeError` in `_ensure_super_user`: call `database.get_session()` instead of non-existent `database.session()`
- Add `spec=DatabaseManager` to database mock in tests to prevent silent attribute errors on MagicMock

## [0.6.0] - 2026-02-24

### Added
- Auto-creation of initial super user at startup via `_ensure_super_user()` in AppManager
- `super_user_email` and `super_user_language` settings in AppSettings for configurable super user provisioning
- Password is randomly generated with `secrets.token_urlsafe`; user must reset via forgot-password flow
- Production-grade code standards section in CLAUDE.md

### Changed
- Removed hardcoded super user from `UserDevFixtures` dev fixture
- Super user creation is now idempotent: skips if user already exists, never updates or deletes

## [0.5.0] - 2026-02-23

### Added
- AI streaming support via `chat_with_tools_streaming` with SSE (Server-Sent Events)
- `AIStreamChunk` dataclass for structured streaming responses from providers
- `MistralProvider.chat_stream()` for async streaming via httpx
- `GraphQLToolExecutor.register_special_tool()` for extensible special tool dispatch
- Guard clauses in `chat_with_tools_streaming` for JWT claim validation
- Unit tests for streaming helpers, providers, special tools, and conversation services

### Changed
- Extracted `_prepare_chat_context()` to eliminate setup duplication between streaming and non-streaming paths
- Refactored `GraphQLToolExecutor` special tools from if/elif chain to dictionary dispatch
- Refactored `MistralProvider._handle_error_status()` out of `_parse_response()`
- Sanitized error messages in `chat_with_tools` and `chat_with_tools_streaming` to prevent internal details leaking to clients
- Downgraded debug-level tool/stream logs from INFO to DEBUG
- Replaced hardcoded `provider="mistral"` with dynamic provider tracking from stream chunks
- Updated coverage badge from 79% to 80%

## [0.4.1] - 2026-02-22

### Changed
- Refactored `lys_delete` to use `create_strawberry_field_config` directly instead of `lys_typed_field`
- Materialized `stream`/`stream_scalars` results in `ThreadSafeSessionProxy` to prevent asyncpg concurrent operation errors
- Exposed `create_strawberry_field_config` as public API in `fields.py`
- Added coverage calculation step (unit + integration + e2e) with README badge update to commit workflow in CLAUDE.md
- `refactor:` commits now trigger a patch version bump

## [0.4.0] - 2026-02-13

### Added
- Alembic migration helper (`lys.core.migrations`) with `configure_alembic_env()` for standardized migration setup
- Alembic CLI wrappers: `run_migrate`, `run_makemigrations`, `run_db_status`, `run_db_stamp` with auto-discovery of `alembic.ini`
- Secure ZIP extraction utility (`lys.core.utils.zip`) with ZIP Slip, ZIP bomb, and per-file size protections
- Configurable `relay_max_results` on `AppSettings` (default 100), passed to `StrawberryConfig`
- `alembic>=1.15.0` dependency
- Unit tests for migrations, Alembic CLI wrappers, ZIP utilities, and relay_max_results
- `create_all_tables()` test helper in `tests/fixtures/database.py`

### Changed
- Removed `initialize_database()` from `DatabaseManager` (Alembic now handles schema migrations)
- Removed database initialization phase from `_app_lifespan`
- XSRF mismatch log no longer exposes token values
- Test fixtures use `create_all_tables()` helper instead of `initialize_database()`
- Updated coverage badge from 77% to 79%
- Updated README testing section with E2E tests and combined coverage commands

## [0.3.0] - 2026-02-12

### Added
- SSO authentication app (`sso`) with Google/Microsoft provider support
- `UserSSOLink` entity linking users to external SSO providers
- `SSOAuthService` with OAuth2 flow, session management via Redis key-value store
- SSO callback REST endpoints (link mode + signup mode)
- `create_client_with_sso_owner` in organization and licensing `ClientService`
- `CreateClientWithSSOInput` / `CreateClientWithSSOInputModel` for SSO signup
- `create_client_with_sso` GraphQL mutation (public, unlicenced)
- PubSubManager key-value operations: `set_key`, `get_key`, `delete_key`, `get_and_delete_key`
- `authlib` and `httpx` dependencies for OAuth2 flows
- Licensing `notification` module registered in `__submodules__`
- Unit tests for SSO endpoints, auth service, models, nodes, and pub/sub KV operations
- Integration tests for SSO link service
- Additional unit tests improving combined coverage to 77%

### Changed
- Email dispatch decoupled from batch creation: `_create_and_send_emails` renamed to `_create_emails`, sending delegated to `send_pending_email` Celery task
- `trigger_event` dispatches `send_pending_email.delay()` per email after session commit
- `send_pending_email` upgraded to `bind=True` with retry logic (`max_retries=3`)
- `UserService.create_user` accepts `password=None` for SSO-only users
- `AuthService.login` handles SSO-only users (no password) with constant-time rejection
- Notification dispatch failures in `trigger_event` now log and continue instead of retrying

## [0.2.0] - 2026-02-11

### Added
- Role-based and organization-scoped email dispatch via `EmailingBatchService` override chain
- `RecipientResolutionMixin` (base), `RoleRecipientResolutionMixin` (user_role), `OrganizationRecipientResolutionMixin` (organization)
- `emailing_type_role` association table linking `EmailingType` to `Role` (many-to-many)
- Extended `EmailingType` entity with `roles` relationship in user_role app
- `EmailingTypeFixtures` base class with `format_roles` for role-aware fixture loading
- `EmailingTypeFixturesModel` Pydantic model for fixture validation with optional `roles`
- Organization-scoped `EmailingBatchService` with `organization_data` parameter
- Per-recipient `private_data` enrichment in `_create_and_send_emails` / `_create_and_send_emails_sync`
- `trigger_event` Celery task: unified event handler for emails and notifications
- Jinja2 base template (`_base.html`) with blocks for consistent email layout
- Licensing emailing fixtures with `context_description` and role assignments
- 5 licensing email templates (EN/FR): license_granted, license_revoked, subscription_payment_success/failed, subscription_canceled
- Minimum 75% combined coverage threshold rule in CLAUDE.md
- Integration tests for role-based and organization-scoped batch dispatch
- Unit tests for all mixins, batch service, emailing entities, templates, fixtures, email context, and trigger_event task (220+ new tests)

### Changed
- Refactored all 16 email templates to extend `_base.html` with block inheritance
- `email_context` in licensing services now includes all template variables (front_url, client_name, plan_name, etc.)
- Registered `emailing` module in `user_role` and `organization` app `__submodules__`
- Updated coverage badge in README.md from 75% to 77%

### Fixed
- `RoleRecipientResolutionMixin` fallback to `Base.metadata.tables` when `user_role` is a raw Table (not a registered entity)
- `EmailingTypeFixturesModel.roles` now optional (default `[]`) to support emailing types without role dispatch
- Missing `await` on `session.execute()` for association table inserts in async context

## [0.1.0] - 2026-02-10

Initial release of the Lys framework.

### Added

**Core Framework**
- Component-based architecture with automatic registration (`@register_entity`, `@register_service`, `@register_fixture`, `@register_node`, `@register_query`, `@register_mutation`)
- `Entity` base class with auto-generated UUID primary keys and audit timestamps
- `ParametricEntity` base class for reference data with string IDs
- `EntityService` with built-in CRUD operations, field validation, and mass-assignment protection
- `EntityFixtures` with parametric (disable strategy) and business (delete strategy) fixture loading
- Component loading order: entities → services → fixtures → nodes → webservices
- Registry locking after each component phase for deterministic behavior
- Last-registered-wins override pattern for app composition
- `override_webservice()` and `disable_webservice()` for metadata modification
- `configure_component_types()` for selective loading (API server vs Celery worker)
- Parallel query execution via `EntityService.execute_parallel()`

**GraphQL API**
- Strawberry GraphQL integration with Relay support (Global IDs, cursor pagination)
- Five operation decorators: `@lys_getter`, `@lys_connection`, `@lys_creation`, `@lys_edition`, `@lys_delete`
- `@parametric_node` for auto-generated ParametricEntity nodes
- `EntityNode` and `ServiceNode` base classes with lazy relationship loading
- Pydantic input validation via Strawberry integration
- Order-by support with `order_by_attribute_map`
- Multiple schema support with automatic routing
- GraphQL federation schema support
- Schema export functionality
- Query depth limiting, alias limiting, schema introspection disabled in production

**Authentication (`user_auth` app)**
- JWT-based authentication with access and refresh tokens
- Cookie-based token transmission (HttpOnly, Secure, SameSite)
- XSRF token validation (enabled by default)
- Refresh token rotation (enabled by default)
- Progressive rate limiting on login attempts
- Login attempt tracking and audit trail
- User status management (enable/disable)
- Password reset with one-time tokens
- Email verification system
- JWT secret key strength validation at startup
- Constant-time password comparison and user enumeration prevention

**Role-Based Access Control (`user_role` app)**
- Role entity with webservice assignments
- Role-based permission checking via JWT claims
- `ROLE_ACCESS_LEVEL` for webservice access control

**Organization & Multi-Tenancy (`organization` app)**
- Client (tenant) entity with owner access
- `ClientUser` and `ClientUserRole` for organization membership
- `OrganizationPermission` with JWT-based organization-scoped access
- Row-level filtering by `client_id` for multi-tenant data isolation
- Tenant column safety check preventing accidental data leaks
- `ORGANIZATION_ROLE_ACCESS_LEVEL` for organization-scoped webservices

**Licensing (`licensing` app)**
- License plans and versioned plan rules
- Subscription management with user quotas
- License verification integrated into JWT claims
- Mollie payment integration
- `LicensingAuthService` filtering webservices by license status

**File Management (`file_management` app)**
- S3 storage integration with presigned URLs
- File import system with status tracking
- Thread-safe GraphQL sessions for file operations

**AI Integration (`ai` app)**
- AI conversation and message management
- GraphQL tool generation from webservices
- AI guardrails with confirmation workflow for risky operations
- Text improvement service
- Frontend navigation and actions support

**Notification System**
- Redis pub/sub for real-time notifications
- GraphQL subscriptions support
- Notification batching

**Service-to-Service Communication**
- `ServiceAuthMiddleware` and `InternalServicePermission`
- `ServiceAuthUtils` for short-lived service JWT tokens with instance identity
- Webservice registration flow at startup
- `INTERNAL_SERVICE_ACCESS_LEVEL` for internal-only endpoints

**Security**
- Pluggable permission chain (Anonymous → JWT → Organization)
- Row-level filtering (OWNER and ORGANIZATION_ROLE access)
- `SecurityHeadersMiddleware` for HTTP security headers
- Global API rate limiting middleware with Redis support
- Secure cookie defaults (HttpOnly, Secure, SameSite=Lax)
- HMAC-based XSRF token comparison
- Debug mode restricted to DEV environment
- SSL/TLS enforcement for PostgreSQL connections
- Audit logging on sensitive entity access and super user bypass
- Search input sanitization before ILIKE queries
- Open redirect and SSRF prevention on success URLs
- Random generation for dev fixture passwords

**Testing**
- 75% combined test coverage (unit + integration)
- pytest-forked integration for SQLAlchemy registry isolation
- Forked coverage collection via monkey-patched `forked_run_report`

**Documentation**
- Developer guides: creating an app, entities and services, GraphQL API, permissions
- FRS documentation: authentication, JWT permissions, internal service communication, webservice management