"""
Setting up the database table for url shortener.
Data we need:
- ID for every URL
- The Long URL
- the Short URL (result)
- Date creation
- Click count
- Expiration date
- User/Owner ID
- Is Active status
- Custom alias
- Last accessed date
- Title/description
- IP address of creator
- Updated date
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timezone

Base = declarative_base()


class URL(Base):
    __tablename__ = "urls"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)

    # Core URL fields
    long_url = Column(String(2048), nullable=False)
    short_code = Column(String(10), unique=True, nullable=False, index=True)
    custom_alias = Column(String(50), unique=True, nullable=True, index=True)

    # Metadata
    title = Column(String(255), nullable=True)
    description = Column(String(500), nullable=True)

    # User tracking
    user_id = Column(Integer, nullable=True, index=True)
    creator_ip = Column(String(45), nullable=True)

    # Status and activity
    is_active = Column(Boolean, default=True, nullable=False)
    click_count = Column(BigInteger, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    last_accessed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    # Optional features
    password_hash = Column(String(255), nullable=True)
    max_clicks = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<URL(id={self.id}, short_code='{self.short_code}', long_url='{self.long_url[:50]}...')>"

    def is_expired(self):
        """Check if the URL has expired"""
        if self.expires_at is not None:
            now = datetime.now(timezone.utc)
            # Handle both timezone-aware and naive datetimes from database
            if self.expires_at.tzinfo is None:
                # Naive datetime - assume it's UTC
                return now.replace(tzinfo=None) > self.expires_at
            return now > self.expires_at
        return False

    def has_reached_max_clicks(self):
        """Check if the URL has reached its maximum click limit"""
        if self.max_clicks is not None:
            return self.click_count >= self.max_clicks
        return False

    def is_accessible(self):
        """Check if the URL can be accessed"""
        return self.is_active and not self.is_expired() and not self.has_reached_max_clicks()
