from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from enum import Enum
import os
from . import models
from .database import get_db
from sqlalchemy.future import select

class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"
    API_USER = "api_user"

class ComplianceLevel(str, Enum):
    BASIC = "basic"
    SOC2 = "soc2"
    HIPAA = "hipaa"
    GDPR = "gdpr"

security = HTTPBearer()

class AuthService:
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.SECRET_KEY = os.environ.get("SECRET_KEY", "a_very_secret_key")
        self.ALGORITHM = "HS256"
        self.ACCESS_TOKEN_EXPIRE_MINUTES = 30
        self.REFRESH_TOKEN_EXPIRE_DAYS = 30

    async def authenticate_user(self, credentials: HTTPAuthorizationCredentials = Depends(security), db = Depends(get_db)):
        try:
            payload = jwt.decode(credentials.credentials, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                raise HTTPException(status_code=401, detail="Invalid authentication")

            # Get user from database
            user = await db.get(models.User, user_id)
            if not user or not user.is_active:
                raise HTTPException(status_code=401, detail="User not found or inactive")

            return user
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

    def check_permissions(self, required_role: UserRole, required_compliance: ComplianceLevel = None):
        def permission_checker(current_user: models.User = Depends(self.authenticate_user)):
            # Role hierarchy check
            role_hierarchy = {
                UserRole.ADMIN: 4,
                UserRole.MANAGER: 3,
                UserRole.USER: 2,
                UserRole.API_USER: 1
            }

            if role_hierarchy.get(current_user.role, 0) < role_hierarchy.get(required_role, 0):
                raise HTTPException(status_code=403, detail="Insufficient permissions")

            # Compliance level check
            if required_compliance and current_user.organization:
                if current_user.organization.compliance_level != required_compliance.value:
                    raise HTTPException(status_code=403, detail="Insufficient compliance level")

            return current_user
        return permission_checker

auth_service = AuthService()
