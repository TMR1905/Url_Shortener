from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from schemas.url import URLCreate, URLResponse, URLShortResponse, URLStats, URLUpdate
from services.url_service import (
    create_short_url,
    get_url_by_code,
    get_url_stats,
    increment_click_count,
    verify_password,
    update_url,
    delete_url,
    get_all_urls,
)
from config import settings


router = APIRouter(prefix="/api/urls", tags=["urls"])


@router.post("/shorten", response_model=URLShortResponse, status_code=status.HTTP_201_CREATED)
def shorten_url(url_data: URLCreate, request: Request, db: Session = Depends(get_db)):
    """
    Create a shortened URL.

    - **long_url**: The original URL to shorten (required)
    - **custom_alias**: Optional custom alias (3-50 chars, alphanumeric with _ and -)
    - **title**: Optional title for the URL
    - **description**: Optional description
    - **expires_at**: Optional expiration datetime
    - **max_clicks**: Optional maximum number of clicks allowed
    - **password**: Optional password protection
    """
    creator_ip = request.client.host if request.client else None
    new_url = create_short_url(db, url_data, creator_ip)

    short_url = f"{settings.BASE_URL}/{new_url.custom_alias or new_url.short_code}"

    return URLShortResponse(
        short_code=new_url.short_code,
        short_url=short_url,
        long_url=new_url.long_url,
        created_at=new_url.created_at,
        expires_at=new_url.expires_at
    )


@router.get("/", response_model=list[URLResponse])
def list_urls(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    active_only: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    List all URLs with pagination.

    - **skip**: Number of records to skip (default: 0)
    - **limit**: Maximum number of records to return (default: 100, max: 500)
    - **active_only**: If true, only return active URLs
    """
    urls = get_all_urls(db, skip=skip, limit=limit, active_only=active_only)
    return urls


@router.get("/{code}/stats", response_model=URLStats)
def get_statistics(code: str, db: Session = Depends(get_db)):
    """
    Get statistics for a shortened URL.

    - **code**: The short code or custom alias
    """
    stats = get_url_stats(db, code)
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"URL with code '{code}' not found"
        )
    return stats


@router.get("/{code}", response_model=URLResponse)
def get_url_info(code: str, db: Session = Depends(get_db)):
    """
    Get information about a shortened URL (without redirecting).

    - **code**: The short code or custom alias
    """
    url = get_url_by_code(db, code)
    if not url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"URL with code '{code}' not found"
        )
    return url


@router.patch("/{url_id}", response_model=URLResponse)
def update_url_info(url_id: int, url_update: URLUpdate, db: Session = Depends(get_db)):
    """
    Update URL properties.

    - **url_id**: The database ID of the URL
    - **title**: New title (optional)
    - **description**: New description (optional)
    - **is_active**: Active status (optional)
    - **expires_at**: New expiration datetime (optional)
    - **max_clicks**: New max clicks limit (optional)
    """
    updated = update_url(db, url_id, url_update)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"URL with ID '{url_id}' not found"
        )
    return updated


@router.delete("/{url_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_url(
    url_id: int,
    hard_delete: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Delete a URL.

    - **url_id**: The database ID of the URL
    - **hard_delete**: If true, permanently delete; otherwise soft delete (set is_active=False)
    """
    success = delete_url(db, url_id, soft_delete=not hard_delete)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"URL with ID '{url_id}' not found"
        )
    return None


# Redirect router - separate prefix for clean short URLs
redirect_router = APIRouter(tags=["redirect"])


@redirect_router.get("/{code}")
def redirect_to_url(
    code: str,
    password: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Redirect to the original URL.

    - **code**: The short code or custom alias
    - **password**: Password if the URL is password-protected
    """
    url = get_url_by_code(db, code)

    if not url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Short URL not found"
        )

    if not url.is_accessible():
        if not url.is_active:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="This URL has been deactivated"
            )
        if url.is_expired():
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="This URL has expired"
            )
        if url.has_reached_max_clicks():
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="This URL has reached its maximum click limit"
            )

    if url.password_hash:
        if not password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="This URL is password protected. Provide password as query parameter."
            )
        if not verify_password(url, password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password"
            )

    increment_click_count(db, url)

    return RedirectResponse(url=url.long_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
