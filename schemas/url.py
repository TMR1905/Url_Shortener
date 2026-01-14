from pydantic import BaseModel, HttpUrl, Field, ConfigDict
from datetime import datetime
from typing import Optional


class URLCreate(BaseModel):
    """Schema for creating a new short URL"""
    long_url: HttpUrl
    custom_alias: Optional[str] = Field(None, min_length=3, max_length=50, pattern="^[a-zA-Z0-9_-]+$")
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    expires_at: Optional[datetime] = None
    max_clicks: Optional[int] = Field(None, gt=0)
    password: Optional[str] = Field(None, min_length=4)


class URLResponse(BaseModel):
    """Schema for URL response"""
    id: int
    long_url: str
    short_code: str
    custom_alias: Optional[str]
    title: Optional[str]
    description: Optional[str]
    is_active: bool
    click_count: int
    created_at: datetime
    expires_at: Optional[datetime]
    max_clicks: Optional[int]

    model_config = ConfigDict(from_attributes=True)


class URLShortResponse(BaseModel):
    """Minimal response after creating a short URL"""
    short_code: str
    short_url: str
    long_url: str
    created_at: datetime
    expires_at: Optional[datetime]


class URLStats(BaseModel):
    """Schema for URL statistics"""
    id: int
    short_code: str
    long_url: str
    click_count: int
    is_active: bool
    created_at: datetime
    last_accessed_at: Optional[datetime]
    expires_at: Optional[datetime]
    is_expired: bool
    has_reached_max_clicks: bool
    is_accessible: bool

    model_config = ConfigDict(from_attributes=True)


class URLUpdate(BaseModel):
    """Schema for updating URL properties"""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None
    max_clicks: Optional[int] = Field(None, gt=0)