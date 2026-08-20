from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import settings
from app.db import get_db
from app.security import (create_access_token, decode_access_token,
                          hash_password, verify_password)

app = FastAPI(title="Terapi Platform", debug=settings.debug)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
templates = Jinja2Templates(directory="app/templates")


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "connected"}


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        "home.html",
        {"request": request, "baslik": "Bugün nasıl hissediyorsun?"},
    )

@app.post("/register", response_model=schemas.UserOut, status_code=201)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.execute(
        select(models.User).where(models.User.email == payload.email)
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=409, detail="Bu e-posta zaten kayıtlı")

    user = models.User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/login", response_model=schemas.Token)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(
        select(models.User).where(models.User.email == payload.email)
    ).scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="E-posta veya şifre hatalı")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Hesap devre dışı")

    return schemas.Token(access_token=create_access_token(str(user.id)))


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Geçersiz veya süresi dolmuş oturum",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(models.User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı")

    return user


@app.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user