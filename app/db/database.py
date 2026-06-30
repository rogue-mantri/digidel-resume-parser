import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool

# Database URL from env var (Supabase or Neon)
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///./digidel_hiring.db"  # fallback for local dev
)

# For SQLite, need to handle connect_args differently
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    poolclass=NullPool if os.environ.get("APP_ENV") == "production" else None,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# ── Dependency for FastAPI ────────────────────────────────────────────

def get_db():
    """Yield a DB session for FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
