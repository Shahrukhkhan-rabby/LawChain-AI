# Implementation Plan: LawChain-AI PDF Chatbot

## Overview

Implement a PDF-based conversational assistant using a Python/FastAPI backend with LangChain orchestration, FAISS vector store (per-session, in-memory), OpenAI embeddings (text-embedding-3-small) and GPT-4o, and a React frontend. The implementation follows the ingestion → retrieval → generation pipeline described in the design document.

## Tasks

- [x] 1. Project scaffolding and data models
  - Create the backend directory structure: `backend/app/{api,core,models,services,tests}/`
  - Create the frontend directory structure: `frontend/src/{components,hooks,api}/`
  - Define all Python dataclasses from the design: `UserIdentity`, `Session`, `PageText`, `Chunk`, `EmbeddedChunk`, `Citation`, `AnswerResult`, `IngestionResult`, `UploadResponse`
  - Add `requirements.txt` (pinned versions) and `pyproject.toml` with pytest + hypothesis configuration
  - Add `frontend/package.json` with React 18, axios, and testing dependencies
  - _Requirements: 1.1, 2.2, 3.1, 4.1_

- [x] 2. Authentication middleware and session management
  - [x] 2.1 Implement `AuthMiddleware` class
    - Implement `authenticate(token: str) -> UserIdentity` using `python-jose` (HS256, configurable secret from env)
    - Implement `authorize_session(user_id: str, session_id: str) -> bool`
    - Return HTTP 401 for missing, expired, or malformed JWTs
    - Load JWT secret from environment variable; never hardcode or log it
    - _Requirements: 7.1, 7.4_

  - [ ]\* 2.2 Write unit tests for `AuthMiddleware`
    - Test valid token → correct `UserIdentity` returned
    - Test expired token → HTTP 401
    - Test malformed token → HTTP 401
    - Test `authorize_session` with matching and mismatched user/session pairs
    - _Requirements: 7.1_

  - [x] 2.3 Implement `SessionManager` class
    - Implement `create_session(user_id: str) -> Session` with UUID-based `session_id`
    - Implement `get_session(session_id: str, user_id: str) -> Session` with ownership check
    - Implement `end_session(session_id: str, user_id: str) -> None` following the teardown algorithm in the design
    - Implement `active_session_count() -> int`
    - Each session holds its own `ConversationBufferMemory` instance and `DocumentStore` reference
    - _Requirements: 6.1, 6.2, 6.3, 7.2_

  - [ ]\* 2.4 Write unit tests for `SessionManager`
    - Test session creation returns unique UUIDs
    - Test `get_session` raises for wrong `user_id`
    - Test `end_session` marks session inactive and calls `DocumentStore.delete_session`
    - Test `active_session_count` increments and decrements correctly
    - _Requirements: 6.1, 6.3_

  - [x] 2.5 Implement `POST /session` endpoint
    - Wire `SessionManager.create_session` behind `AuthMiddleware`
    - Return `{ session_id, created_at }` on success
    - _Requirements: 6.1_

- [ ] 3. Checkpoint — Auth and session foundation
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Ingestion pipeline — PDF parsing and chunking
  - [x] 4.1 Implement `extract_text_by_page(pdf_bytes: bytes) -> list[PageText]`
    - Use `pdfplumber` to extract text page-by-page
    - Set `extraction_failed=True` and `text=""` for any page that raises an exception; log the failure
    - Raise `OCRRequiredError` when all pages fail extraction (image-only PDF)
    - Return pages ordered by ascending `page_number` (1-indexed)
    - _Requirements: 2.1, 2.5, 5.2, 5.3_

  - [ ]\* 4.2 Write property test for `extract_text_by_page` — non-empty chunks for text-bearing PDFs (Property 2)
    - **Property 2: Non-Empty Chunks for Text-Bearing PDFs**
    - **Validates: Requirements 5.2**
    - Use `hypothesis` to generate lists of non-empty page text strings; assert `chunk_text` on those pages always returns a non-empty list
    - _Requirements: 5.2_

  - [x] 4.3 Implement `chunk_text(pages, chunk_size=1000, chunk_overlap=200) -> list[Chunk]`
    - Use LangChain `RecursiveCharacterTextSplitter` with `tiktoken` as the length function
    - Skip pages where `extraction_failed == True`
    - Attach `filename`, `page_number`, `doc_id`, `session_id` metadata to every `Chunk`
    - Assert `len(result) > 0` after processing
    - _Requirements: 2.2, 5.1, 5.2_

  - [ ]\* 4.4 Write property test for `chunk_text` — chunk size bound never exceeded (Property 3)
    - **Property 3: Chunk Size Bound**
    - **Validates: Requirements 2.2**
    - Use `hypothesis` to generate arbitrary text strings; assert every produced chunk has `token_count <= 1000`
    - _Requirements: 2.2_

  - [ ]\* 4.5 Write property test for `chunk_text` — round-trip chunking stability (Property 1)
    - **Property 1: Round-Trip Chunking Stability**
    - **Validates: Requirements 5.1**
    - Use `hypothesis` to generate text; chunk it, rejoin, re-chunk, and assert total token counts are equivalent within overlap tolerance
    - _Requirements: 5.1_

  - [ ]\* 4.6 Write unit tests for `extract_text_by_page` and `chunk_text`
    - Test `extract_text_by_page` with a valid multi-page PDF, a single failed page, and an all-image PDF
    - Test `chunk_text` at the exact 1000-token boundary and with overlap correctness
    - Test that failed pages are excluded from chunk output
    - _Requirements: 2.1, 2.2, 2.5, 5.3_

- [x] 5. Ingestion pipeline — embedding and document store
  - [x] 5.1 Implement `embed_chunks(chunks: list[Chunk]) -> list[EmbeddedChunk]`
    - Use `langchain-openai` `OpenAIEmbeddings` with model `text-embedding-3-small`
    - Batch calls (up to 2048 inputs per request per design)
    - Assert output length equals input length and each vector has dimension 1536
    - _Requirements: 2.3_

  - [ ]\* 5.2 Write unit tests for `embed_chunks`
    - Mock the OpenAI API; assert output list length matches input length
    - Assert each vector has exactly 1536 dimensions
    - Assert output order matches input order
    - _Requirements: 2.3_

  - [x] 5.3 Implement `DocumentStore` class
    - Maintain one `faiss.IndexFlatL2` per `session_id` in a dict keyed by session
    - Implement `store_chunks(session_id, embedded_chunks)` — add vectors and store chunk metadata
    - Implement `similarity_search(session_id, query_vector, k=5) -> list[Chunk]` — enforce session isolation; return chunks ordered by ascending L2 distance
    - Implement `delete_session(session_id)` — remove FAISS index and all metadata for that session
    - _Requirements: 2.3, 6.3, 7.2, 7.3_

  - [ ]\* 5.4 Write property test for `DocumentStore.similarity_search` — session isolation (Property 4)
    - **Property 4: Session Isolation**
    - **Validates: Requirements 7.2**
    - Use `hypothesis` to generate two sets of text chunks for two different sessions; assert similarity search on session A never returns chunks with `session_id` belonging to session B
    - _Requirements: 7.2_

  - [ ]\* 5.5 Write unit tests for `DocumentStore`
    - Test `store_chunks` then `similarity_search` returns correct chunks for that session
    - Test `similarity_search` on session A does not return session B chunks
    - Test `delete_session` removes the index so subsequent searches return empty
    - _Requirements: 2.3, 6.3, 7.2, 7.3_

  - [x] 5.6 Implement `IngestionPipeline.ingest_document` orchestrator
    - Wire `extract_text_by_page` → `chunk_text` → `embed_chunks` → `DocumentStore.store_chunks` following the main ingestion algorithm in the design
    - Validate PDF magic bytes (`%PDF`) at entry; return `IngestionResult(status="error")` if invalid
    - Collect `failed_pages` and include in `IngestionResult`
    - Run `pdfplumber` extraction in a `ProcessPoolExecutor` for large documents
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ]\* 5.7 Write unit tests for `IngestionPipeline.ingest_document`
    - Test full happy path: valid PDF → `IngestionResult(status="ready")`
    - Test invalid magic bytes → `IngestionResult(status="error")`
    - Test partial page failure → `failed_pages` populated, status still `"ready"`
    - Test image-only PDF → `OCRRequiredError` propagated
    - _Requirements: 2.1, 2.4, 2.5, 5.3_

- [ ] 6. Checkpoint — Ingestion pipeline complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Upload endpoint
  - [x] 7.1 Implement `POST /upload` endpoint
    - Accept `UploadFile` + `session_id` form fields; require `AuthMiddleware` dependency
    - Validate file size ≤ 50 MB before reading content; return HTTP 413 if exceeded
    - Validate PDF magic bytes; return HTTP 400 if not a valid PDF
    - Enforce 20-document-per-session cap; return HTTP 422 if exceeded
    - Delegate to `IngestionPipeline.ingest_document`; return `UploadResponse`
    - Stream large uploads to avoid loading full 50 MB into memory at once
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]\* 7.2 Write unit tests for `POST /upload`
    - Test valid PDF upload → HTTP 200 with `UploadResponse`
    - Test non-PDF file → HTTP 400 with `InvalidFileType` error body
    - Test file > 50 MB → HTTP 413 with `FileTooLarge` error body
    - Test 21st document in session → HTTP 422 with `SessionCapExceeded` error body
    - Test unauthenticated request → HTTP 401
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 7.1_

- [x] 8. QA pipeline
  - [x] 8.1 Implement `QAPipeline.answer` method
    - Embed the question using `OpenAIEmbeddings`
    - Call `DocumentStore.similarity_search(session_id, query_vector, k=5)`
    - Return a "no relevant information" response when the chunk list is empty
    - Build a `RetrievalQAWithSourcesChain` prompt that demands citations and instructs the LLM to answer only from provided context (prompt injection mitigation)
    - Inject conversation history via `ConversationBufferMemory.load_memory_variables()`
    - Call GPT-4o via `langchain-openai` `ChatOpenAI`
    - Save context to memory after a successful answer
    - Cap question length at 2,000 characters before processing
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 8.2 Implement `QAPipeline.validate_citations` method
    - Parse chunk IDs referenced in `answer_text`
    - Return `True` iff every referenced chunk ID exists in `source_chunks`
    - Return `False` (and do not mutate inputs) if any referenced ID is absent
    - _Requirements: 4.1, 4.4_

  - [ ]\* 8.3 Write unit tests for `QAPipeline`
    - Mock LLM and retriever; test happy path returns `AnswerResult` with citations
    - Test empty chunk list → "no relevant information" response
    - Test `validate_citations` with all valid IDs → `True`
    - Test `validate_citations` with one invalid ID → `False`
    - Test conversation history is injected into subsequent prompts
    - _Requirements: 3.1, 3.2, 3.4, 3.5, 4.1, 4.4_

  - [x] 8.4 Implement `POST /query` endpoint
    - Accept `{ question, session_id }` JSON body; require `AuthMiddleware` dependency
    - Validate session ownership via `SessionManager.get_session`
    - Delegate to `QAPipeline.answer`; return `AnswerResult` as JSON
    - Return HTTP 200 with citation-error body when `validate_citations` returns `False`
    - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.4, 7.1, 7.2_

  - [ ]\* 8.5 Write unit tests for `POST /query`
    - Test valid question → HTTP 200 with answer and citations
    - Test unverifiable citation → HTTP 200 with `CitationUnverifiable` error body
    - Test no relevant chunks → HTTP 200 with "no relevant information" body
    - Test unauthenticated request → HTTP 401
    - Test question > 2,000 characters → HTTP 422
    - _Requirements: 3.3, 3.5, 4.4, 7.1_

- [x] 9. Session teardown endpoint
  - [x] 9.1 Implement `DELETE /session/{session_id}` endpoint
    - Require `AuthMiddleware`; call `SessionManager.end_session`
    - Verify `DocumentStore.delete_session` is called and memory is cleared
    - Return HTTP 204 on success; HTTP 404 if session not found; HTTP 403 if wrong user
    - _Requirements: 6.3, 7.3_

  - [ ]\* 9.2 Write unit tests for session teardown
    - Test `end_session` → FAISS index deleted, memory cleared, session marked inactive
    - Test subsequent query on ended session → HTTP 401/404
    - Test wrong user attempting to end another user's session → HTTP 403
    - _Requirements: 6.3, 7.3_

- [ ] 10. Checkpoint — Backend API complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. React frontend — Upload panel
  - [x] 11.1 Implement `UploadPanel` component
    - Drag-and-drop file input accepting `.pdf` files only
    - Per-file upload progress indicator using `axios` with `onUploadProgress`
    - Per-file status display: pending / uploading / ready / error
    - Send `POST /upload` with `Authorization: Bearer <token>` header over HTTPS
    - Display descriptive error messages returned by the API (invalid type, too large, cap exceeded)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]\* 11.2 Write unit tests for `UploadPanel`
    - Test drag-and-drop triggers file selection
    - Test progress indicator renders during upload
    - Test error message renders on API error response
    - _Requirements: 1.2, 1.3, 1.4_

- [x] 12. React frontend — Chat interface
  - [x] 12.1 Implement `ChatThread` component
    - Render conversation history as alternating user/assistant message bubbles
    - Display inline citation badges (filename + page number) alongside each answer
    - Clicking a citation badge expands to show the source `chunk_text`
    - _Requirements: 3.3, 4.2, 4.3_

  - [x] 12.2 Implement `QuestionInput` component and `useChat` hook
    - Text input with submit button; send `POST /query` with `Authorization: Bearer <token>` header
    - Disable input while awaiting response; show loading indicator
    - Append question and answer to `ChatThread` on response
    - _Requirements: 3.1, 3.3_

  - [x] 12.3 Wire `UploadPanel`, `ChatThread`, and `QuestionInput` into the main `App` component
    - Manage `session_id` in app state; pass to all API calls
    - Handle session creation on app load (`POST /session`)
    - Handle session end on page unload or explicit "End Session" action
    - _Requirements: 6.1, 6.2, 6.3_

  - [ ]\* 12.4 Write unit tests for `ChatThread` and `QuestionInput`
    - Test citation badge renders with correct filename and page number
    - Test citation expansion shows chunk text on click
    - Test loading state disables input during in-flight request
    - _Requirements: 4.2, 4.3_

- [ ] 13. Integration wiring and end-to-end validation
  - [x] 13.1 Write integration test: upload → query → citation verification
    - Upload a real PDF fixture; submit a question whose answer is on a known page; assert the citation in the response points to the correct filename and page number
    - _Requirements: 1.2, 2.4, 3.3, 4.1, 4.2_

  - [ ]\* 13.2 Write integration test: concurrent sessions
    - Spin up 10 parallel sessions using `asyncio`; submit simultaneous queries; assert all respond within 20 seconds and no cross-session data leaks
    - _Requirements: 6.4, 7.2_

  - [ ]\* 13.3 Write integration test: session teardown
    - Create a session, upload a document, end the session, then attempt a query; assert HTTP 401 or 404 is returned
    - _Requirements: 6.3, 7.3_

- [ ] 14. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Property tests (Properties 1–4) validate universal correctness properties defined in the design document
- Unit tests validate specific examples and edge cases
- Checkpoints ensure incremental validation at each major milestone
- OpenAI API key and JWT secret must be loaded from environment variables — never hardcoded
- All API endpoints must be served over TLS (enforced at the reverse proxy layer)
