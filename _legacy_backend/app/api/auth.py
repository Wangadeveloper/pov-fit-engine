from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserOut, Token
from app.services.fit_service import FitService
from typing import Any, Dict
from pydantic import BaseModel
import uuid

router = APIRouter()

class GoogleLoginRequest(BaseModel):
    credential: str  # Mock token representing the Google token

@router.post("/register", response_model=Dict[str, Any])
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)) -> Any:
    # Check if user already exists
    stmt = select(User).where(User.email == user_in.email)
    res = await db.execute(stmt)
    if res.scalars().first():
        return {
            "success": False,
            "data": None,
            "error": {
                "code": "EMAIL_ALREADY_EXISTS",
                "message": "A user with this email already exists."
            }
        }
    
    # Create user
    hashed_password = get_password_hash(user_in.password)
    user = User(email=user_in.email, hashed_password=hashed_password)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Create initial empty fit profile
    await FitService.get_or_create_profile(db, user.id)
    
    user_out = UserOut.model_validate(user)
    return {
        "success": True,
        "data": user_out.model_dump(),
        "error": None
    }

@router.post("/login", response_model=Token)
async def login_access_token(
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    stmt = select(User).where(User.email == form_data.username)
    res = await db.execute(stmt)
    user = res.scalars().first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )
    
    access_token = create_access_token(subject=user.id)
    return Token(access_token=access_token, token_type="bearer")

@router.post("/login-json", response_model=Dict[str, Any])
async def login_json(user_in: UserLogin, db: AsyncSession = Depends(get_db)) -> Any:
    stmt = select(User).where(User.email == user_in.email)
    res = await db.execute(stmt)
    user = res.scalars().first()
    
    if not user or not verify_password(user_in.password, user.hashed_password):
        return {
            "success": False,
            "data": None,
            "error": {
                "code": "INVALID_CREDENTIALS",
                "message": "Incorrect email or password."
            }
        }
        
    access_token = create_access_token(subject=user.id)
    return {
        "success": True,
        "data": {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "email": user.email
            }
        },
        "error": None
    }

@router.post("/google", response_model=Dict[str, Any])
async def google_login(req: GoogleLoginRequest, db: AsyncSession = Depends(get_db)) -> Any:
    # In a real app, we verify the Google JWT using google-auth library
    # Here, we simulate a successful OAuth exchange
    # E.g. we mock extract user email "googleuser@example.com"
    email = "googleuser@example.com"
    if "@" not in req.credential:
        # If the user passed some dummy credential string, just mock a nice email
        email = f"user_{req.credential[:8]}@google.com"
    else:
        email = req.credential
        
    stmt = select(User).where(User.email == email)
    res = await db.execute(stmt)
    user = res.scalars().first()
    
    if not user:
        # Create a new user with a mock password
        hashed_password = get_password_hash(f"google_oauth_fallback_{uuid.uuid4()}")
        user = User(email=email, hashed_password=hashed_password)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        # Create fit profile
        await FitService.get_or_create_profile(db, user.id)
        
    access_token = create_access_token(subject=user.id)
    return {
        "success": True,
        "data": {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "email": user.email
            }
        },
        "error": None
    }
