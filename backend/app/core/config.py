"""
Application settings for LawChain-AI PDF Chatbot.

All sensitive values (API keys, secrets) are loaded from environment variables.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- External service credentials (required, loaded from env) ---
    OPENAI_API_KEY: str
    JWT_SECRET: str

    # --- JWT configuration ---
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 15

    # --- Upload limits ---
    MAX_FILE_SIZE_MB: int = 50

    # --- Session limits ---
    MAX_DOCS_PER_SESSION: int = 20

    # --- Chunking parameters ---
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # --- Retrieval parameters ---
    TOP_K_CHUNKS: int = 5

    # --- Input validation ---
    MAX_QUESTION_LENGTH: int = 2000

    class Config:
        env_file = ("../.env", ".env")  # look in project root first, then cwd
        env_file_encoding = "utf-8"


settings = Settings()
