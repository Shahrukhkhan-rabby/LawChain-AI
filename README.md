# LawChain-AI

A PDF-based conversational assistant for professional settings such as law firms. Upload one or more PDF documents, then ask natural-language questions — the system retrieves relevant passages and generates accurate, cited answers using LangChain and GPT-4o.

## Features

- Upload up to 20 PDF documents per session (max 50 MB each)
- Automatic text extraction, chunking, and vector embedding via OpenAI
- Semantic search with FAISS for fast, session-isolated retrieval
- Grounded answers with citations (filename + page number)
- Conversation history maintained throughout each session
- JWT-based authentication; all data is ephemeral and session-scoped

## Tech Stack

| Layer    | Technology                                         |
| -------- | -------------------------------------------------- |
| Backend  | Python 3.11, FastAPI, LangChain, FAISS, pdfplumber |
| LLM      | OpenAI GPT-4o + text-embedding-3-small             |
| Frontend | React 18, Vite, axios                              |
| Testing  | pytest, Hypothesis (property-based), Vitest        |

## Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- An OpenAI API key

### 1. Clone and configure environment

```bash
cp .env.example .env
# Edit .env and fill in OPENAI_API_KEY and JWT_SECRET
```

### 2. Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

The UI will be available at `http://localhost:5173`.

### 4. Run tests

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
```

## Project Structure

```
LawChain-AI/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI route handlers
│   │   ├── core/         # Auth middleware, config
│   │   ├── models/       # Data models and exceptions
│   │   ├── services/     # Ingestion, QA, session, document store
│   │   └── tests/        # pytest unit and property-based tests
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/          # axios API client
│   │   ├── components/   # React components
│   │   └── hooks/        # Custom React hooks
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── .env.example
└── README.md
```

## Security Notes

- Never commit `.env` to version control — it is listed in `.gitignore`
- JWT tokens expire after 15 minutes by default (configurable via `JWT_EXPIRY_MINUTES`)
- All API traffic should be served over TLS in production (configure at the reverse proxy layer)
- Session data is fully ephemeral: all vectors and document content are deleted when a session ends
