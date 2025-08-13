# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Start the application:**

```bash
# Quick start (recommended)
chmod +x run.sh
./run.sh

# Manual start
cd backend && uv run uvicorn app:app --reload --port 8000
```

**Install dependencies:**

```bash
uv sync
```

**Add new dependencies:**

```bash
uv add package-name
```

**Add development dependencies:**

```bash
uv add --dev package-name
```

**Update dependencies:**

```bash
uv lock --upgrade
```

**Environment setup:**

```bash
# Copy environment template and add your API key
cp .env.example .env
# Edit .env to add: ANTHROPIC_API_KEY=your-key-here
```

**Access points:**

- Web Interface: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## Architecture Overview

This is a **Retrieval-Augmented Generation (RAG) system** for course materials with a tool-based AI approach using Claude's function calling capabilities.

### Core Architecture Pattern

**Request Flow:**
Frontend → FastAPI → RAG System → AI Generator (with tools) → Vector Search → Response

**Key Design Principles:**

- **Tool-based AI**: Claude decides when to search vs. use general knowledge
- **Session-based conversations**: Maintains context across queries
- **Semantic chunking**: Course documents split into meaningful, overlapping chunks
- **Source attribution**: Every AI response tracks which course materials were referenced

### Component Responsibilities

**RAG System (`rag_system.py`)**: Central orchestrator that coordinates all components. Processes user queries by managing conversation history, calling AI with available tools, and extracting sources.

**AI Generator (`ai_generator.py`)**: Handles Anthropic Claude API integration with tool calling. Contains system prompt that instructs Claude to search only for course-specific questions and answer general knowledge directly.

**Vector Store (`vector_store.py`)**: ChromaDB wrapper managing two collections:

- `course_catalog`: Course metadata for semantic course name resolution
- `course_content`: Actual course chunks with embeddings for content search

**Search Tools (`search_tools.py`)**: Implements tool interface for Claude. `CourseSearchTool` provides semantic search with course name matching and lesson filtering. Tracks sources for UI display.

**Document Processor (`document_processor.py`)**: Processes course documents with expected format:

```
Line 1: Course Title: [title]
Line 2: Course Link: [url]
Line 3: Course Instructor: [instructor]
Line 4+: Lesson markers ("Lesson N: Title") and content
```

**Session Manager (`session_manager.py`)**: Maintains conversation context with configurable history limits (default: 2 exchanges).

### Data Models

**Course Structure**: `Course` → `Lesson[]` → `CourseChunk[]`

- Chunks include contextual prefixes: `"Course [title] Lesson [N] content: [chunk]"`
- Each chunk maintains relationship to source course and lesson

**Search Flow**: User query → Embedding → ChromaDB semantic search → Filtered results → Formatted context → Claude synthesis

### Configuration

**Key settings in `config.py`:**

- `CHUNK_SIZE`: 800 chars (sentence-based chunking)
- `CHUNK_OVERLAP`: 100 chars (context preservation)
- `MAX_RESULTS`: 5 search results
- `MAX_HISTORY`: 2 conversation exchanges
- `ANTHROPIC_MODEL`: "claude-sonnet-4-20250514"

### Document Processing

Documents are automatically loaded from `docs/` folder on startup. Supports `.txt`, `.pdf`, `.docx`.

- Existing courses detected to avoid reprocessing
- Clear existing data with `clear_existing=True` in `add_course_folder()`

### Frontend Integration

**Static serving**: FastAPI serves frontend files with no-cache headers for development
**API endpoints**:

- `POST /api/query`: Main query processing with session management
- `GET /api/courses`: Course statistics and metadata

**Response format**: `{answer: str, sources: str[], session_id: str}`

- Sources automatically extracted from tool usage
- Markdown rendering supported in frontend

### ChromaDB Storage

Database persists in `backend/chroma_db/` (gitignored). Collections use SentenceTransformer embeddings ("all-MiniLM-L6-v2"). Course titles serve as unique identifiers across both collections.

### Development Notes

**Package Management**: Always use `uv` for all dependency management - never use `pip` directly. The project uses `pyproject.toml` for dependency specification and `uv.lock` for reproducible installs.

**No testing framework** currently implemented - consider adding pytest for future development with `uv add --dev pytest`.

**Tool execution flow**: Claude API call → Tool decision → Search execution → Results formatting → Final response generation. Only one search per query to maintain efficiency.

**Session persistence**: Sessions exist only in memory - restart clears all conversation history.
