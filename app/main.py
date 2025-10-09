from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import logging
logging.basicConfig(level=logging.INFO)

from dotenv import load_dotenv
from colorlog import ColoredFormatter

class HighlightAtFormatter(ColoredFormatter):
    """Colored formatter with INFO message body highlighting."""
    def format(self, record):
        # Defer to ColoredFormatter; coloring handled via secondary_log_colors
        return super().format(record)

# Load environment variables ASAP (before importing modules that read env)
load_dotenv()

# Configure colored logging early
handler = logging.StreamHandler()
formatter = HighlightAtFormatter(
    "%(log_color)s%(levelname)s%(reset)s:     %(name)s:%(message_log_color)s%(message)s%(reset)s",
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'blue',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bold_red'
    },
    secondary_log_colors={
        'message': {
            'INFO': 'bold_blue'
        }
    }
)
handler.setFormatter(formatter)
root_logger = logging.getLogger()
root_logger.handlers = []
root_logger.addHandler(handler)
root_logger.setLevel(logging.INFO)

from app.api import chat, products, recommendations
from app.database.database import init_db

app = FastAPI(
    title="AI Commerce Assistant API",
    description="An AI-powered shopping assistant API similar to Amazon Rufus",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
@app.on_event("startup")
async def startup_event():
    await init_db()

# Include routers
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(products.router, prefix="/api", tags=["products"])
app.include_router(recommendations.router, prefix="/api", tags=["recommendations"])

@app.get("/")
async def root():
    return {
        "message": "AI Commerce Assistant API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}