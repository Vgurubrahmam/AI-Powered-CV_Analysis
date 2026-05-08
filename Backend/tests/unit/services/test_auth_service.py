"""Unit tests for AuthService."""

from __future__ import annotations

import pytest
import pytest_asyncio

from app.core.security import hash_password, verify_password
from app.core.exceptions import AuthException, ConflictException
from app.services.auth_service import AuthService


class TestAuthService:

    @pytest_asyncio.fixture
    async def seeded_user(self, db):
        """Create a test user in the DB."""
        from app.models.user import User
        import uuid
        user = User(
            id=uuid.uuid4(),
            email="authtest@example.com",
            password_hash=hash_password("ValidPass123!"),
            role="candidate",
            plan_tier="free",
            is_active=True,
        )
        db.add(user)
        await db.flush()
        return user

    @pytest.mark.asyncio
    async def test_login_valid_credentials(self, db, mock_redis, seeded_user):
        svc = AuthService(db=db, redis=mock_redis)
        token_pair = await svc.login("authtest@example.com", "ValidPass123!")
        assert token_pair.access_token
        assert token_pair.refresh_token
        assert token_pair.token_type == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password_raises(self, db, mock_redis, seeded_user):
        svc = AuthService(db=db, redis=mock_redis)
        with pytest.raises(AuthException):
            await svc.login("authtest@example.com", "WrongPass!")

    @pytest.mark.asyncio
    async def test_login_nonexistent_user_raises(self, db, mock_redis):
        svc = AuthService(db=db, redis=mock_redis)
        with pytest.raises(AuthException):
            await svc.login("nobody@nowhere.com", "AnyPass123!")

    @pytest.mark.asyncio
    async def test_login_inactive_user_raises(self, db, mock_redis):
        from app.models.user import User
        import uuid
        inactive = User(
            id=uuid.uuid4(),
            email="inactive@example.com",
            password_hash=hash_password("Pass123!"),
            role="candidate",
            plan_tier="free",
            is_active=False,
        )
        db.add(inactive)
        await db.flush()
        svc = AuthService(db=db, redis=mock_redis)
        with pytest.raises(AuthException):
            await svc.login("inactive@example.com", "Pass123!")

    @pytest.mark.asyncio
    async def test_refresh_valid_token(self, db, mock_redis, seeded_user):
        svc = AuthService(db=db, redis=mock_redis)
        tokens = await svc.login("authtest@example.com", "ValidPass123!")
        new_tokens = await svc.refresh(tokens.refresh_token)
        assert new_tokens.access_token != tokens.access_token

    @pytest.mark.asyncio
    async def test_logout_blacklists_token(self, db, mock_redis, seeded_user):
        svc = AuthService(db=db, redis=mock_redis)
        tokens = await svc.login("authtest@example.com", "ValidPass123!")
        from app.core.security import decode_access_token
        payload = decode_access_token(tokens.access_token)
        await svc.logout(payload)
        # Second logout / any action with same jti should be blacklisted
        from app.core.security import is_token_blacklisted
        jti = payload.get("jti")
        assert await is_token_blacklisted(mock_redis, jti)
