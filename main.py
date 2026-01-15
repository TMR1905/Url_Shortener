from fastapi import FastAPI
from database import init_db
from api.url_endpoints import router, redirect_router


app = FastAPI(
    title="URL Shortener API",
    description="A simple and efficient URL shortening service",
    version="1.0.0"
)


@app.on_event("startup")  # change in production
def startup():
    init_db()


@app.get("/health")
def health_check():
    return {"status": "ok"}


# Include routers AFTER specific routes like /health
# Order matters: redirect_router has /{code} which catches everything
app.include_router(router)
app.include_router(redirect_router)