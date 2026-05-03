"""Integration tests — AuthService token lifecycle.

Validates correct/incorrect credentials, JWT sign/verify round-trip,
expired token rejection, and tampered token rejection — without any
external dependency (no DB, no HTTP).
"""

from datetime import timedelta

import pytest

from app.services.auth_service import AuthService


@pytest.fixture()
def auth():
    return AuthService()


# ---------------------------------------------------------------------------
# authenticate_user
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestAuthenticateUser:
    def test_valid_credentials_return_true(self, auth):
        from app.core.config import settings
        assert auth.authenticate_user(settings.admin_username, settings.admin_password) is True

    def test_wrong_password_returns_false(self, auth):
        from app.core.config import settings
        assert auth.authenticate_user(settings.admin_username, "wrong-password") is False

    def test_wrong_username_returns_false(self, auth):
        from app.core.config import settings
        assert auth.authenticate_user("not-admin", settings.admin_password) is False

    def test_empty_credentials_return_false(self, auth):
        assert auth.authenticate_user("", "") is False


# ---------------------------------------------------------------------------
# create_access_token + verify_token
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestTokenRoundTrip:
    def test_create_and_verify_returns_subject(self, auth):
        token = auth.create_access_token(subject="admin")
        subject = auth.verify_token(token)
        assert subject == "admin"

    def test_token_with_custom_expiry_is_valid(self, auth):
        token = auth.create_access_token(subject="admin", expires_delta=timedelta(minutes=5))
        assert auth.verify_token(token) == "admin"

    def test_expired_token_raises_value_error(self, auth):
        token = auth.create_access_token(
            subject="admin",
            expires_delta=timedelta(seconds=-1),  # already expired
        )
        with pytest.raises(ValueError, match="[Ii]nvalid"):
            auth.verify_token(token)

    def test_tampered_token_raises_value_error(self, auth):
        token = auth.create_access_token(subject="admin")
        # Flip the last character of the signature
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        with pytest.raises(ValueError, match="[Ii]nvalid"):
            auth.verify_token(tampered)

    def test_garbage_string_raises_value_error(self, auth):
        with pytest.raises(ValueError, match="[Ii]nvalid"):
            auth.verify_token("not.a.jwt")
