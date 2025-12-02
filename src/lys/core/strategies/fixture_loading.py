"""
Fixture loading strategies for different entity types.

This module implements the Strategy pattern to handle different fixture loading
behaviors for parametric entities (reference data) vs business entities (test data).
"""
from abc import ABC, abstractmethod
from typing import Type, Dict, Any, List, Optional, Tuple

from sqlalchemy import delete, select, update, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncSession

from lys.core.consts.environments import EnvironmentEnum
from lys.core.entities import Entity, ParametricEntity
from lys.core.interfaces.services import EntityServiceInterface


class FixtureLoadingStrategy(ABC):
    """
    Abstract base class for fixture loading strategies.

    Defines the interface for loading fixtures with different behaviors
    based on entity type.
    """

    @abstractmethod
    async def load(
        self,
        fixture_class,
        session: AsyncSession,
        entity_class: Type[Entity],
        service: EntityServiceInterface
    ) -> Tuple[int, int, int, int]:
        """
        Load fixture data into the database.

        Args:
            fixture_class: The fixture class containing data and configuration
            session: Database session for queries
            entity_class: The entity class to load fixtures for
            service: Service instance for entity operations

        Returns:
            Tuple of (deleted_count, added_count, updated_count, unchanged_count)
        """
        pass


class ParametricFixtureLoadingStrategy(FixtureLoadingStrategy):
    """
    Loading strategy for parametric entities (reference data).

    Parametric entities are configuration/reference data with business-meaningful IDs.
    This strategy:
    - Disables entities not in data_list instead of deleting them
    - Updates existing entities with new data
    - Adds new entities when they don't exist
    - Tracks changes for reporting
    """

    async def load(
        self,
        fixture_class,
        session: AsyncSession,
        entity_class: Type[ParametricEntity],
        service: EntityServiceInterface
    ) -> Tuple[int, int, int, int]:
        """
        Load parametric entity data with update/disable logic.

        Returns:
            Tuple of (deleted_count, added_count, updated_count, unchanged_count)
        """
        deleted_count = 0
        added_count = 0
        updated_count = 0
        unchanged_count = 0

        # Disable entities not in data_list
        if fixture_class.delete_previous_data:
            stmt = update(entity_class).where(
                entity_class.id.notin_([data["id"] for data in fixture_class.data_list])
            ).values(enabled=False)
            result = await session.execute(stmt)
            deleted_count = result.rowcount

        # Process each data item
        for data in fixture_class.data_list:
            stmt = select(entity_class).where(entity_class.id == data["id"]).limit(1)
            result = await session.execute(stmt)
            obj: Optional[Entity] = result.scalars().one_or_none()

            attributes: Dict[str, Any] = data.get("attributes", {})

            if obj is not None:
                # Update existing entity
                if len(attributes.keys()):
                    formatted_attributes = await fixture_class._format_attributes(
                        attributes, session=session
                    )
                    obj_updated, is_updated = await service.check_and_update(
                        entity=obj, **formatted_attributes
                    )

                    if is_updated:
                        updated_count += 1
                    else:
                        unchanged_count += 1
                else:
                    unchanged_count += 1
            else:
                # Create new entity
                formatted_attributes = await fixture_class._format_attributes(
                    attributes, session=session
                )
                obj = entity_class(id=data["id"], **formatted_attributes)

                await fixture_class._do_before_add(obj)
                session.add(obj)
                added_count += 1

        return deleted_count, added_count, updated_count, unchanged_count


class BusinessFixtureLoadingStrategy(FixtureLoadingStrategy):
    """
    Loading strategy for business entities (test/demo data).

    Business entities are operational data used for testing/demo purposes.
    This strategy:
    - Deletes all existing data (clean slate) when delete_previous_data=True
    - Uses upsert logic when delete_previous_data=False (based on unique constraints)
    - Only runs in non-PROD environments
    """

    def _get_unique_key_fields(self, entity_class: Type[Entity]) -> Optional[List[str]]:
        """
        Extract unique key fields from entity's __table_args__.

        Args:
            entity_class: The entity class to inspect

        Returns:
            List of column names from the first UniqueConstraint found, or None
        """
        table_args = getattr(entity_class, "__table_args__", None)
        if not table_args:
            return None

        # table_args can be a tuple or a dict
        if isinstance(table_args, dict):
            return None

        for arg in table_args:
            if isinstance(arg, UniqueConstraint):
                # Extract column names from the constraint
                return [col.name if hasattr(col, "name") else str(col) for col in arg.columns]

        return None

    async def load(
        self,
        fixture_class,
        session: AsyncSession,
        entity_class: Type[Entity],
        service: EntityServiceInterface
    ) -> Tuple[int, int, int, int]:
        """
        Load business entity data (non-PROD only).

        Returns:
            Tuple of (deleted_count, added_count, updated_count, unchanged_count)
        """
        import logging

        deleted_count = 0
        added_count = 0
        updated_count = 0
        unchanged_count = 0

        if fixture_class.delete_previous_data:
            # Delete all existing rows
            stmt = delete(entity_class)
            result = await session.execute(stmt)
            deleted_count = result.rowcount

        # Check if we should use upsert logic
        unique_key_fields = self._get_unique_key_fields(entity_class)
        use_upsert = not fixture_class.delete_previous_data and unique_key_fields is not None

        # Insert or upsert data from data_list
        created_objects = []
        for i, data in enumerate(fixture_class.data_list):
            try:
                raw_attributes = data.get("attributes", {})
                existing_obj = None
                extra_data = None

                if use_upsert:
                    # First format without extra_data to get unique key values
                    temp_attributes = await fixture_class._format_attributes(
                        raw_attributes, session=session
                    )

                    # Build filter for unique key lookup
                    filters = [
                        getattr(entity_class, field) == temp_attributes.get(field)
                        for field in unique_key_fields
                    ]
                    stmt = select(entity_class).where(*filters).limit(1)
                    result = await session.execute(stmt)
                    existing_obj = result.scalars().one_or_none()

                    if existing_obj is not None:
                        # Re-format with extra_data containing parent_id
                        extra_data = {"parent_id": existing_obj.id}
                        attributes = await fixture_class._format_attributes(
                            raw_attributes, session=session, extra_data=extra_data
                        )

                        # Update existing entity
                        obj_updated, is_updated = await service.check_and_update(
                            entity=existing_obj, **attributes
                        )
                        if is_updated:
                            updated_count += 1
                        else:
                            unchanged_count += 1
                        continue

                # Try custom service creation first
                obj = await fixture_class.create_from_service(raw_attributes, session)

                if obj is None:
                    # Standard entity creation
                    attributes = await fixture_class._format_attributes(
                        raw_attributes, session=session
                    )
                    obj = entity_class(**attributes)
                    await fixture_class._do_before_add(obj)

                session.add(obj)
                created_objects.append(obj)
            except Exception as e:
                logging.error(
                    f"Failed to create/update object {i+1}/{len(fixture_class.data_list)} "
                    f"for {entity_class.__tablename__}: {str(e)}"
                )
                logging.error(f"Problematic attributes: {raw_attributes}")
                raise

        # Flush to persist objects and generate IDs
        if created_objects:
            try:
                await session.flush()
            except Exception as e:
                logging.error(
                    f"Failed to flush fixtures for {entity_class.__tablename__}: {str(e)}"
                )
                logging.error(f"Session state: {len(session.new)} new, {len(session.dirty)} dirty, "
                             f"{len(session.deleted)} deleted")
                raise

            # Count objects that were successfully persisted (have an ID)
            added_count = sum(1 for obj in created_objects if hasattr(obj, "id") and obj.id is not None)

            # Log warning if some objects failed to persist
            failed_count = len(created_objects) - added_count
            if failed_count > 0:
                logging.warning(
                    f"{failed_count} objects were added to session but failed to persist "
                    f"for {entity_class.__tablename__}"
                )

        return deleted_count, added_count, updated_count, unchanged_count


class FixtureLoadingStrategyFactory:
    """
    Factory to create appropriate loading strategy based on entity type.
    """

    @staticmethod
    def create_strategy(entity_class: Type[Entity]) -> FixtureLoadingStrategy:
        """
        Create the appropriate loading strategy for the given entity class.

        Args:
            entity_class: The entity class to create a strategy for

        Returns:
            ParametricFixtureLoadingStrategy for ParametricEntity subclasses,
            BusinessFixtureLoadingStrategy for other Entity subclasses
        """
        if issubclass(entity_class, ParametricEntity):
            return ParametricFixtureLoadingStrategy()
        else:
            return BusinessFixtureLoadingStrategy()