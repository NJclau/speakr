from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional
from models import User
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
import bcrypt

class UserRole:
    USER = "user"
    ADMIN = "admin"

class AuthService:
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

    async def get_current_user(self, token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
        # In a real application, you would decode the token and get the user from the database
        user = await db.execute(User).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return user

    def check_permissions(self, role: str):
        async def _check_permissions(current_user: User = Depends(self.get_current_user)):
            if role == UserRole.ADMIN and not current_user.is_admin:
                raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")
            return current_user
        return _check_permissions

    async def authenticate_user(self, db: AsyncSession, username: str, password: str) -> Optional[User]:
        user = await db.execute(User).filter(User.username == username).first()
        if not user:
            return None
        if not bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
            return None
        return user

auth_service = AuthService()
