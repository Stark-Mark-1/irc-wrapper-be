from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def find_user_by_userid(db: AsyncSession, user_id: str) -> User | None:
    """Find a user by their user_id."""
    return await db.scalar(
        select(User).where(User.user_id == user_id, User.is_active.is_(True))
    )


async def find_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Find a user by their email."""
    return await db.scalar(
        select(User).where(User.email == email, User.is_active.is_(True))
    )


async def create_user(db: AsyncSession, email: str, name: str | None = None) -> User:
    """Create a new user."""
    user = User(email=email, name=name)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
