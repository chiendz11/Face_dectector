from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.config import settings


class AuthService:
    def authenticate_user(self, username: str, password: str) -> bool:
        return (
            username == settings.admin_username
            and password == settings.admin_password
        )

    def create_access_token(
        self,
        subject: str,
        expires_delta: timedelta | None = None,
    ) -> str:
        expire = datetime.now(timezone.utc) + (
            expires_delta
            if expires_delta is not None
            else timedelta(minutes=settings.access_token_expire_minutes)
        )
        payload = {
            "sub": subject,
            "exp": expire,
        }
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    def verify_token(self, token: str) -> str:
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            subject = payload.get("sub")
            if not subject:
                raise ValueError("Invalid token payload")
            return subject
        except JWTError as exc:
            raise ValueError("Invalid authentication token") from exc
