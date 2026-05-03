"""
FastAPI application entry point for LawChain-AI PDF Chatbot.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

app = FastAPI(
    title="LawChain-AI PDF Chatbot",
    description=(
        "A PDF-based conversational assistant for professional settings. "
        "Upload documents, ask questions, and receive cited answers."
    ),
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# CORS — allow the Vite dev server origin
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Returns a simple liveness probe response."""
    return {"status": "ok"}
