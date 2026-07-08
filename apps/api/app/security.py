from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.db import ApiKey, OrganizationMembership, RefreshSession, User, get_db

password_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "platform_admin": {"*"},
    "organization_admin": {
        "workspace:manage", "users:manage", "calls:read", "calls:transfer", "calls:takeover",
        "agents:manage", "agents:approve", "agents:activate", "quality:review", "leads:manage",
        "calendar:manage", "routing:manage", "reports:manage", "governance:manage", "security:manage",
        "providers:manage", "analytics:read",
    },
    "operations_manager": {
        "calls:read", "calls:transfer", "calls:takeover", "agents:manage", "leads:manage",
        "calendar:manage", "routing:manage", "reports:manage", "analytics:read", "quality:review",
    },
    "voice_agent_manager": {"agents:manage", "agents:submit", "calls:read", "analytics:read", "quality:review"},
    "supervisor": {"calls:read", "calls:transfer", "calls:takeover", "leads:manage", "routing:read", "quality:review"},
    "quality_reviewer": {"calls:read", "quality:review", "quality:manage", "analytics:read"},
    "sales_representative": {"calls:read", "leads:manage", "calendar:read"},
    "scheduler": {"calendar:manage", "calls:read", "leads:read"},
    "support_agent": {"calls:read", "leads:manage"},
    "compliance_reviewer": {"calls:read", "governance:manage", "quality:review", "reports:manage"},
    "viewer": {"calls:read", "leads:read", "analytics:read", "calendar:read"},
}


@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str
    organization_id: str
    role: str
    permissions: set[str]
    auth_type: str = "jwt"


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(user: User, organization_id: str, role: str) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": user.id,
        "org": organization_id,
        "role": role,
        "email": user.email,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_session(db: Session, user: User, organization_id: str) -> str:
    token = secrets.token_urlsafe(40)
    db.add(
        RefreshSession(
            id=f"refresh-{secrets.token_hex(8)}",
            user_id=user.id,
            organization_id=organization_id,
            token_hash=_hash_token(token),
            expires_at=datetime.utcnow() + timedelta(days=settings.refresh_token_days),
        )
    )
    db.commit()
    return token


def rotate_refresh_session(db: Session, raw_token: str) -> tuple[User, str, str]:
    session = (
        db.query(RefreshSession)
        .filter(RefreshSession.token_hash == _hash_token(raw_token), RefreshSession.revoked_at.is_(None))
        .first()
    )
    if not session or session.expires_at <= datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session is invalid or expired")
    session.revoked_at = datetime.utcnow()
    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is unavailable")
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == session.organization_id,
            OrganizationMembership.is_active.is_(True),
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace membership no longer exists")
    db.commit()
    return user, create_access_token(user, session.organization_id, membership.role), create_refresh_session(db, user, session.organization_id)


def revoke_refresh_session(db: Session, raw_token: str) -> None:
    session = db.query(RefreshSession).filter(RefreshSession.token_hash == _hash_token(raw_token)).first()
    if session and session.revoked_at is None:
        session.revoked_at = datetime.utcnow()
        db.commit()


def permission_set(role: str, explicit: list[str] | None = None) -> set[str]:
    return set(explicit or []) | ROLE_PERMISSIONS.get(role, set())


def has_permission(principal: Principal, required: str) -> bool:
    return "*" in principal.permissions or required in principal.permissions


def _principal_from_token(token: str, db: Session) -> Principal:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = str(payload.get("sub"))
        org_id = str(payload.get("org"))
    except (JWTError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc
    user = db.get(User, user_id)
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.is_active.is_(True),
        )
        .first()
    )
    if not user or not user.is_active or not membership:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Workspace access is unavailable")
    return Principal(
        user_id=user.id,
        email=user.email,
        organization_id=org_id,
        role=membership.role,
        permissions=permission_set(membership.role, membership.permissions),
    )


def _principal_from_api_key(raw_key: str, db: Session) -> Principal | None:
    prefix = raw_key[:12]
    candidates = db.query(ApiKey).filter(ApiKey.key_prefix == prefix, ApiKey.revoked_at.is_(None)).all()
    for api_key in candidates:
        if api_key.expires_at and api_key.expires_at <= datetime.utcnow():
            continue
        if secrets.compare_digest(api_key.key_hash, _hash_token(raw_key)):
            api_key.last_used_at = datetime.utcnow()
            db.commit()
            return Principal(
                user_id="api-key",
                email=f"{api_key.name}@api-key.local",
                organization_id=api_key.organization_id,
                role="api_key",
                permissions=set(api_key.scopes),
                auth_type="api_key",
            )
    return None


def get_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
    x_api_key: Annotated[str | None, Header()] = None,
) -> Principal:
    if x_api_key:
        principal = _principal_from_api_key(x_api_key, db)
        if principal:
            return principal
    if credentials and credentials.scheme.lower() == "bearer":
        return _principal_from_token(credentials.credentials, db)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required")


def require_permissions(*required: str):
    def dependency(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        missing = [permission for permission in required if not has_permission(principal, permission)]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"message": "Insufficient permission", "missing": missing},
            )
        return principal

    return dependency


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")
