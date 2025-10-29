"""
Fixture loading strategies for different entity types.

This module implements the Strategy pattern to handle different fixture loading
behaviors for parametric entities (reference data) vs business entities (test data).
"""
from abc import ABC, abstractmethod
from typing import Type, Dict, Any, List, Optional, Tuple

from sqlalchemy import delete, select, update
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
    - Deletes all existing data (clean slate)
    - Inserts all data from data_list
    - Only runs in non-PROD environments
    """

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
            Tuple of (deleted_count, added_count, 0, 0)
            Note: updated_count and unchanged_count are always 0 for business data
        """
        deleted_count = 0

        if fixture_class.delete_previous_data:
            # Delete all existing rows
            stmt = delete(entity_class)
            result = await session.execute(stmt)
            deleted_count = result.rowcount

        # Prepare formatted attributes
        formatted_attributes_list = []
        for data in fixture_class.data_list:
            formatted_attributes_list.append(
                await fixture_class._format_attributes(
                    data.get("attributes", {}), session=session
                )
            )

        # Insert all data from data_list
        for attributes in formatted_attributes_list:
            obj = entity_class(**attributes)
            await fixture_class._do_before_add(obj)
            session.add(obj)

        added_count = len(fixture_class.data_list)

        # Business fixtures don't track updates/unchanged
        return deleted_count, added_count, 0, 0


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