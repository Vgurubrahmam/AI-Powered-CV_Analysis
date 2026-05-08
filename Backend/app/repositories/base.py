"""Generic async CRUD repository base with type generics.

All domain-specific repositories inherit from this base.
DB access ONLY lives in repositories — no SQL in services or API routes.
"""

from __future__ import annotations

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic CRUD repository for SQLAlchemy async ORM models."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id: uuid.UUID | str) -> ModelT | None:
        """Fetch a single record by primary key. Returns None if not found."""
        return await self.session.get(self.model, id)

    async def get_or_raise(self, id: uuid.UUID | str, exc_class=None) -> ModelT:
        """Fetch by PK or raise ResourceNotFoundException."""
        from app.core.exceptions import ResourceNotFoundException
        record = await self.get(id)
        if record is None:
            exc = exc_class or ResourceNotFoundException(
                f"{self.model.__name__} with id '{id}' not found."
            )
            raise exc
        return record

    async def get_multi(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        order_by: Any = None,
        filters: list[Any] | None = None,
    ) -> list[ModelT]:
        """Fetch multiple records with optional filtering and ordering."""
        stmt = select(self.model)
        if filters:
            stmt = stmt.where(*filters)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, filters: list[Any] | None = None) -> int:
        """Count records with optional filtering."""
        stmt = select(func.count()).select_from(self.model)
        if filters:
            stmt = stmt.where(*filters)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def create(self, obj_in: dict[str, Any]) -> ModelT:
        """Create a new record from a dict of field values."""
        db_obj = self.model(**obj_in)
        self.session.add(db_obj)
        await self.session.flush()      # flush to get generated ID before commit
        await self.session.refresh(db_obj)
        return db_obj

    async def update(self, db_obj: ModelT, updates: dict[str, Any]) -> ModelT:
        """Update fields on an existing ORM instance."""
        for field, value in updates.items():
            setattr(db_obj, field, value)
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, db_obj: ModelT) -> None:
        """Hard-delete a record."""
        await self.session.delete(db_obj)
        await self.session.flush()
