import os
import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Import Sync DB components (for the REST API tables)
from backend.models.database import engine, Base, DATABASE_URL

# Import API Routes
from backend.api.routes import router

# Import the Alert Service
from backend.services.alerting import AlertService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 1. Auto-create Database Tables (Sync)
# This runs once on startup to ensure tables exist
Base.metadata.create_all(bind=engine)

# 2. Initialize FastAPI
app = FastAPI(title="Sentiment Analysis Platform")

# 3. Configure CORS (Allow Frontend to connect)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Include API Routes
app.include_router(router, prefix="/api")

# --- Async Database Setup for Background Tasks ---
# The AlertService requires an ASYNC session, but our main DATABASE_URL is usually sync.
# We create a specific async engine here for the background loop.

# Ensure URL uses the async driver (postgresql+asyncpg)
ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

async_engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

@app.on_event("startup")
async def startup_event():
    """
    Initialize background services on app startup.
    """
    logger.info("🚀 Starting Alert Monitoring Service...")
    
    # Initialize AlertService with the ASYNC session maker
    alert_service = AlertService(db_session_maker=AsyncSessionLocal)
    
    # Run the monitoring loop in the background (non-blocking)
    asyncio.create_task(alert_service.run_monitoring_loop())

@app.get("/")
def root():
    return {
        "message": "Sentiment Analysis API is running",
        "health_check": "/api/health",
        "docs": "/docs"
    }