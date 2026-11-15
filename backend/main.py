import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from .config import get_settings
from .database import get_db
from .logging_config import configure_logging
from .models import Mention, User
from .schemas import MentionCreate, MentionRead, Token, UserCreate

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting %s", get_settings().app_name)
    yield


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> Token:
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Email is already registered"
        ) from error
    return Token(access_token=create_access_token(user.id))


@app.post("/auth/login", response_model=Token)
def login(
    form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> Token:
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return Token(access_token=create_access_token(user.id))


@app.post("/mentions", response_model=MentionRead, status_code=status.HTTP_201_CREATED)
def create_mention(
    payload: MentionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Mention:
    mention = Mention(**payload.model_dump(), owner_id=current_user.id)
    db.add(mention)
    try:
        db.commit()
        db.refresh(mention)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Mention URL already exists"
        ) from error
    return mention


@app.get("/mentions", response_model=list[MentionRead])
def list_mentions(
    brand: str | None = Query(default=None, max_length=255),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Mention]:
    query = select(Mention).where(Mention.owner_id == current_user.id)
    if brand:
        query = query.where(Mention.brand == brand)
    return list(db.scalars(query.order_by(Mention.timestamp.desc())))


@app.patch("/mentions/{mention_id}", response_model=MentionRead)
def update_mention(
    mention_id: int,
    sentiment: str | None = None,
    topic: str | None = None,
    urgency: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Mention:
    mention = db.scalar(
        select(Mention).where(
            Mention.id == mention_id, Mention.owner_id == current_user.id
        )
    )
    if mention is None:
        raise HTTPException(status_code=404, detail="Mention not found")
    if sentiment is not None:
        mention.sentiment = sentiment
    if topic is not None:
        mention.topic = topic
    if urgency is not None:
        mention.urgency = urgency
    db.commit()
    db.refresh(mention)
    return mention
