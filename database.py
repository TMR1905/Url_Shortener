from sqlalchemy import create_engine
from config import settings
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from models.url import Base

engine = create_engine(settings.DATABASE_URL,
                       echo=settings.DB_ECHO,
                       pool_pre_ping=True,
                       pool_size=5,
                       max_overflow=10
                       )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for getting database session
    Usage: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database - create all tables
    """
    Base.metadata.create_all(bind=engine)