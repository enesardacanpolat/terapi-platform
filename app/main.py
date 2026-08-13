from fastapi import Depends, FastAPI, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db

app = FastAPI(title="Terapi Platform", debug=settings.debug)
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