# Entities (back)

## Base classes — choose by primary key

| Class | PK | Use for |
|-------|----|---------|
| `lys.core.entities.Entity` | auto UUID | business objects |
| `lys.core.entities.ParametricEntity` | business string (`id`/`code`), + `enabled`, `description` | reference data (statuses, types, categories) |

Both give `created_at` / `updated_at` audit columns and row-level access hooks.

## RULES

- **R1 — `__tablename__` is SINGULAR.** `user`, `stored_file` — never plural.
  The table name IS the registry name (`get_entity("client")`).
- **R2 — Soft FKs use `Uuid(as_uuid=False)`** (string form, DB-validated):
  ```python
  from sqlalchemy import Uuid
  client_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False, comment="Client reference (soft FK)")
  ```
  `ParametricEntity` references are plain strings — no Uuid.
- **R3 — Hard FK vs soft FK**: same-app relation → real `ForeignKey` +
  `relationship`; reference to another app/service's data → soft FK (no
  constraint). Cross-service data must never assume a JOINable constraint.
- **R4 — Row-level access.** If the entity carries tenant columns (e.g.
  `client_id`), implement `organization_accessing_filters()` (and keep
  `accessing_users()` coherent) — the `OrganizationPermission` raises at
  startup otherwise (tenant-leak guard).
- **R5 — Register**: `@register_entity()` from `lys.core.registries`; never
  import an entity class elsewhere (see `rules.md`).
- **R6 — Indexes** for queried soft-FK columns in `__table_args__`:
  `Index("ix_product_client", "client_id")`.
- **R7 — Sensitive data**: `_sensitive = True` on entities whose access must be
  audit-logged.

## PROCEDURE — new entity

1. Create/extend the module's `entities.py`:
   ```python
   from sqlalchemy import Uuid, Index
   from sqlalchemy.orm import Mapped, mapped_column
   from typing import Optional
   from lys.core.entities import Entity
   from lys.core.registries import register_entity


   @register_entity()
   class Product(Entity):
       __tablename__ = "product"

       name: Mapped[str] = mapped_column(nullable=False)
       client_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False, comment="Client reference (soft FK)")
       category_id: Mapped[Optional[str]] = mapped_column(nullable=True)

       __table_args__ = (Index("ix_product_client", "client_id"),)
   ```
2. Parametric variant:
   ```python
   @register_entity()
   class ProductStatus(ParametricEntity):
       __tablename__ = "product_status"
       # id = code string; enabled/description provided by the base
   ```
3. Declare the module in `modules/__init__.py` (`__submodules__`) if new.
4. **Migration**: `python main.py makemigrations -m "add product"` — review the
   generated file, then run your project's own migration command.
5. Self-check: boot the app and confirm it starts clean.

## Access at runtime — never by import

```python
entity = cls.app_manager.get_entity("product")     # in a service
entity = info.context.app_manager.get_entity("product")   # in a webservice
```
