# Permissions (back) — chain, levels, row filtering

Stateless and claim-based: authorization decisions read the JWT (and the
webservice registry), never the database. Read before touching `access_levels`
or a tenant entity.

## The chain (settings.py order matters)

```
InternalServicePermission   → service-to-service (Authorization: Service <token>)
AnonymousPermission         → no JWT: grants only is_public webservices
JWTPermission               → JWT claims: super user / webservices claim
OrganizationPermission      → organizations claim → tenant row filtering
```

Each permission returns one of:

| Result | Meaning |
|--------|---------|
| `(True, None)` | granted — chain stops |
| `(False, error)` | denied — chain stops |
| `(None, None)` | no opinion — next |
| `({keys}, None)` | conditional — dicts merge, chain continues (row filtering) |

## Access levels (on the webservice decorator)

| Level | Constant (from) | Grants |
|-------|-----------------|--------|
| Owner | `OWNER_ACCESS_LEVEL` (`lys.core.consts.webservices`) | own rows only |
| Role | `ROLE_ACCESS_LEVEL` (`lys.apps.user_role.consts`) | webservice in the user's role list |
| Organization | `ORGANIZATION_ROLE_ACCESS_LEVEL` (`lys.apps.organization.consts`) | rows of the user's organizations |
| Internal | `INTERNAL_SERVICE_ACCESS_LEVEL` (`lys.core.consts.webservices`) | service-to-service caller |

Combined with OR: `access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL]`.

## JWT claims (shape your rules reason about)

```json
{
  "sub": "user-uuid", "is_super_user": false,
  "webservices": {"product": "owner", "all_products": "full"},
  "organizations": {"client-uuid": {"level": "client", "webservices": ["all_products"]}}
}
```

`"full"` = unconditional; `"owner"` = own rows (OWNER_ACCESS_KEY in access_type).

## Row-level filtering — how it reaches the query

- `lys_connection` / `lys_getter` pass the merged access_type dict to
  `add_statement_access_constraints()` of each permission → WHERE conditions
  (owner: `owner_id == user_id`; org: `client_id IN (…)`).
- Instance operations (`lys_edition`, `lys_delete`, instance `lys_getter`)
  call the entity's `check_permission(user_id, access_type)` after fetch.
- **The entity provides the columns**: `accessing_users()`,
  `accessing_organizations()`, `user_accessing_filters()`,
  `organization_accessing_filters()` — see `entity.md` R4.

## RULES

- **R1 — Declarative, never imperative.** Access = decorator flags + chain +
  entity filter methods. An `if` on a role inside a webservice is a bug.
- **R2 — Tenant guard is a startup error**: an entity with `client_id` (or any
  `DEFAULT_TENANT_COLUMNS` column) that doesn't implement
  `organization_accessing_filters()` crashes the boot — that guard is the
  point; never bypass it, implement the filter. Extra tenant columns →
  subclass `OrganizationPermission` with a wider set and register the subclass
  in settings.
- **R3 — is_public surfaces are rare and deliberate** (login, activate…).
  Everything else requires the chain.
- **R4 — Custom permission**: implement `PermissionInterface`
  (`lys.core.interfaces.permissions`) —
  `check_webservice_permission(webservice_id, context)` +
  `add_statement_access_constraints(access_type, entity_class, stmt, or_where,
  context)` — and add it to the settings chain (after the built-ins unless it
  must pre-empt them).
- **R5 — Service-to-service**: generate short-lived tokens with
  `ServiceAuthUtils(secret_key=settings.secret_key).generate_token(service_name=…,
  expiration_minutes=1)` and call with `Authorization: Service <token>`;
  the callee sets `info.context.service_caller`. Reserve for genuine
  service-to-service calls — the api↔worker share the database and don't need it.
