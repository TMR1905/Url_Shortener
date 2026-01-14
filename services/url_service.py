from sqlalchemy.orm import Session
from hashids import Hashids
import bcrypt
from fastapi import HTTPException, status
from typing import Optional
from datetime import datetime, timezone

from models.url import URL
from schemas.url import URLCreate, URLUpdate, URLStats
from config import settings


# Initialize Hashids
hashids = Hashids(
    salt=settings.HASHIDS_SALT,
    min_length=settings.HASHIDS_MIN_LENGTH,
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
)


def generate_short_code(url_id: int) -> str:
    """
    Generate a short code from URL ID using hashids

    Args:
        url_id: The database ID of the URL

    Returns:
        str: The generated short code
    """
    return hashids.encode(url_id)


def decode_short_code(short_code: str) -> Optional[int]:
    """
    Decode a short code back to URL ID

    Args:
        short_code: The short code to decode

    Returns:
        Optional[int]: The URL ID, or None if invalid
    """
    try:
        decoded = hashids.decode(short_code)
        return decoded[0] if decoded else None
    except Exception:
        return None


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt

    Args:
        password: Plain text password

    Returns:
        str: Hashed password
    """
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(url: URL, password: str) -> bool:
    """
    Verify a password against the stored hash

    Args:
        url: The URL object
        password: Plain text password to verify

    Returns:
        bool: True if password matches, False otherwise
    """
    if not url.password_hash:
        return True
    return bcrypt.checkpw(password.encode('utf-8'), url.password_hash.encode('utf-8'))


def create_short_url(db: Session, url_data: URLCreate, creator_ip: Optional[str] = None) -> URL:
    """
    Create a new shortened URL

    Args:
        db: Database session
        url_data: URL creation data
        creator_ip: IP address of the creator

    Returns:
        URL: The created URL object

    Raises:
        HTTPException: If custom alias already exists
    """
    # Check if custom alias already exists
    if url_data.custom_alias:
        existing = db.query(URL).filter(
            (URL.custom_alias == url_data.custom_alias) | (URL.short_code == url_data.custom_alias)
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Custom alias '{url_data.custom_alias}' is already taken"
            )

    # Hash password if provided
    password_hash = None
    if url_data.password:
        password_hash = hash_password(url_data.password)

    # Create URL without short_code first (we need the ID)
    new_url = URL(
        long_url=str(url_data.long_url),
        short_code="temporary",  # Will be updated after we get the ID
        custom_alias=url_data.custom_alias,
        title=url_data.title,
        description=url_data.description,
        expires_at=url_data.expires_at,
        max_clicks=url_data.max_clicks,
        password_hash=password_hash,
        creator_ip=creator_ip,
        is_active=True,
        click_count=0
    )

    db.add(new_url)
    db.flush()  # Get the ID without committing

    # Generate short code from ID
    new_url.short_code = generate_short_code(new_url.id)

    db.commit()
    db.refresh(new_url)

    return new_url


def get_url_by_code(db: Session, code: str) -> Optional[URL]:
    """
    Get URL by short code or custom alias

    Args:
        db: Database session
        code: Short code or custom alias

    Returns:
        Optional[URL]: The URL object if found, None otherwise
    """
    return db.query(URL).filter(
        (URL.short_code == code) | (URL.custom_alias == code)
    ).first()


def get_url_by_id(db: Session, url_id: int) -> Optional[URL]:
    """
    Get URL by database ID

    Args:
        db: Database session
        url_id: The database ID

    Returns:
        Optional[URL]: The URL object if found, None otherwise
    """
    return db.query(URL).filter(URL.id == url_id).first()


def increment_click_count(db: Session, url: URL) -> None:
    """
    Increment click count and update last accessed timestamp

    Args:
        db: Database session
        url: The URL object to update
    """
    url.click_count += 1
    url.last_accessed_at = datetime.now(timezone.utc)
    db.commit()


def get_url_stats(db: Session, code: str) -> Optional[URLStats]:
    """
    Get statistics for a URL

    Args:
        db: Database session
        code: Short code or custom alias

    Returns:
        Optional[URLStats]: URL statistics if found, None otherwise
    """
    url = get_url_by_code(db, code)
    if not url:
        return None

    return URLStats(
        id=url.id,
        short_code=url.short_code,
        long_url=url.long_url,
        click_count=url.click_count,
        is_active=url.is_active,
        created_at=url.created_at,
        last_accessed_at=url.last_accessed_at,
        expires_at=url.expires_at,
        is_expired=url.is_expired(),
        has_reached_max_clicks=url.has_reached_max_clicks(),
        is_accessible=url.is_accessible()
    )


def update_url(db: Session, url_id: int, url_update: URLUpdate) -> Optional[URL]:
    """
    Update URL properties

    Args:
        db: Database session
        url_id: The database ID of the URL
        url_update: Update data

    Returns:
        Optional[URL]: Updated URL object if found, None otherwise
    """
    url = get_url_by_id(db, url_id)
    if not url:
        return None

    # Update only provided fields
    update_data = url_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(url, field, value)

    db.commit()
    db.refresh(url)

    return url


def delete_url(db: Session, url_id: int, soft_delete: bool = True) -> bool:
    """
    Delete a URL (soft or hard delete)

    Args:
        db: Database session
        url_id: The database ID of the URL
        soft_delete: If True, set is_active=False; if False, delete from database

    Returns:
        bool: True if successful, False if URL not found
    """
    url = get_url_by_id(db, url_id)
    if not url:
        return False

    if soft_delete:
        url.is_active = False
        db.commit()
    else:
        db.delete(url)
        db.commit()

    return True


def get_all_urls(db: Session, skip: int = 0, limit: int = 100, active_only: bool = False) -> list[URL]:
    """
    Get all URLs with pagination

    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        active_only: If True, only return active URLs

    Returns:
        list[URL]: List of URL objects
    """
    query = db.query(URL)

    if active_only:
        query = query.filter(URL.is_active == True)

    return query.offset(skip).limit(limit).all()
