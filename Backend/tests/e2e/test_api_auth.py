"""E2E API tests — auth endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio


class TestAuthAPI:
    """HTTP-level tests for POST /v1/auth/login, /refresh, DELETE /logout."""

    @pytest_asyncio.fixture
    async def registered_user(self, db):
        from app.models.user import User
        from app.core.security import hash_password
        user = User(
            id=uuid.uuid4(),
            email="e2e+auth@test.local",
            password_hash=hash_password("E2ePass123!"),
            role="candidate",
            plan_tier="free",
            is_active=True,
        )
        db.add(user)
        await db.flush()
        return user

    @pytest.mark.asyncio
    async def test_login_returns_tokens(self, client, registered_user):
        response = await client.post(
            "/v1/auth/login",
            json={"email": "e2e+auth@test.local", "password": "E2ePass123!"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["access_token"]
        assert data["data"]["refresh_token"]
        assert data["data"]["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password_returns_401(self, client, registered_user):
        response = await client.post(
            "/v1/auth/login",
            json={"email": "e2e+auth@test.local", "password": "WrongPass!"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_unknown_user_returns_401(self, client):
        response = await client.post(
            "/v1/auth/login",
            json={"email": "nobody@no.com", "password": "Any123!"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_returns_new_tokens(self, client, registered_user):
        login = await client.post(
            "/v1/auth/login",
            json={"email": "e2e+auth@test.local", "password": "E2ePass123!"},
        )
        refresh_token = login.json()["data"]["refresh_token"]

        response = await client.post(
            "/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        new_tokens = response.json()["data"]
        assert new_tokens["access_token"]

    @pytest.mark.asyncio
    async def test_refresh_invalid_token_returns_401(self, client):
        response = await client.post(
            "/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )
        assert response.status_code in (401, 422)

    @pytest.mark.asyncio
    async def test_logout_succeeds(self, auth_client):
        response = await auth_client.delete("/v1/auth/logout")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_protected_endpoint_without_token_returns_401(self, client):
        response = await client.get("/v1/users/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_protected_endpoint_with_valid_token(self, auth_client):
        response = await auth_client.get("/v1/users/me")
        assert response.status_code == 200
        assert response.json()["data"]["email"]
