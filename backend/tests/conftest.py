import pytest
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List
import asyncio

from fastapi.testclient import TestClient
import httpx

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from config import Config
from rag_system import RAGSystem
from session_manager import SessionManager
from vector_store import VectorStore
from ai_generator import AIGenerator
from search_tools import CourseSearchTool


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def test_config(temp_dir):
    """Create a test configuration with temporary directories."""
    config = Config()
    config.CHROMA_DB_PATH = os.path.join(temp_dir, "test_chroma_db")
    config.CHUNK_SIZE = 200  # Smaller chunks for faster tests
    config.MAX_RESULTS = 3
    config.MAX_HISTORY = 1
    return config


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for AI generator tests."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.content = [
        Mock(text="Test AI response", type="text")
    ]
    mock_response.stop_reason = "end_turn"
    
    # Mock tool use response
    mock_tool_response = Mock()
    mock_tool_response.content = [
        Mock(
            type="tool_use",
            id="test_tool_id",
            name="course_search",
            input={"query": "test query", "course_name": None, "lesson_number": None}
        )
    ]
    
    mock_client.messages.create.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_vector_store():
    """Mock vector store for testing."""
    mock_store = Mock(spec=VectorStore)
    mock_store.search_courses.return_value = ["Test Course"]
    mock_store.search_content.return_value = [
        {
            "content": "Test course content chunk",
            "course_title": "Test Course",
            "lesson_number": 1,
            "lesson_title": "Test Lesson"
        }
    ]
    mock_store.get_course_analytics.return_value = {
        "total_courses": 1,
        "course_titles": ["Test Course"]
    }
    return mock_store


@pytest.fixture
def mock_session_manager():
    """Mock session manager for testing."""
    mock_manager = Mock(spec=SessionManager)
    mock_manager.create_session.return_value = "test-session-123"
    mock_manager.get_conversation_history.return_value = []
    mock_manager.add_exchange = Mock()
    return mock_manager


@pytest.fixture
def mock_ai_generator(mock_anthropic_client):
    """Mock AI generator for testing."""
    mock_generator = Mock(spec=AIGenerator)
    mock_generator.generate_response.return_value = (
        "Test AI response based on search results",
        ["Test Course"]
    )
    return mock_generator


@pytest.fixture
def mock_search_tool():
    """Mock search tool for testing."""
    mock_tool = Mock(spec=CourseSearchTool)
    mock_tool.search.return_value = {
        "results": [
            {
                "content": "Test search result content",
                "course_title": "Test Course",
                "lesson_number": 1,
                "lesson_title": "Test Lesson"
            }
        ],
        "sources": ["Test Course - Lesson 1: Test Lesson"]
    }
    return mock_tool


@pytest.fixture
def mock_rag_system(mock_vector_store, mock_session_manager, mock_ai_generator, mock_search_tool):
    """Mock RAG system with all dependencies mocked."""
    mock_system = Mock(spec=RAGSystem)
    mock_system.vector_store = mock_vector_store
    mock_system.session_manager = mock_session_manager
    mock_system.ai_generator = mock_ai_generator
    mock_system.search_tool = mock_search_tool
    
    mock_system.query.return_value = (
        "Test response with search results",
        ["Test Course - Lesson 1: Test Lesson"]
    )
    mock_system.get_course_analytics.return_value = {
        "total_courses": 1,
        "course_titles": ["Test Course"]
    }
    mock_system.add_course_folder.return_value = (1, 5)
    
    return mock_system


@pytest.fixture
def sample_query_request():
    """Sample query request data for testing."""
    return {
        "query": "What is machine learning?",
        "session_id": "test-session-123"
    }


@pytest.fixture
def sample_query_response():
    """Sample query response data for testing."""
    return {
        "answer": "Machine learning is a subset of artificial intelligence...",
        "sources": ["Test Course - Lesson 1: Introduction to ML"],
        "session_id": "test-session-123"
    }


@pytest.fixture
def sample_course_stats():
    """Sample course statistics for testing."""
    return {
        "total_courses": 2,
        "course_titles": ["Machine Learning Basics", "Advanced Python"]
    }


@pytest.fixture
def sample_course_documents():
    """Sample course documents for testing."""
    return [
        {
            "title": "Machine Learning Basics",
            "content": "Course Title: Machine Learning Basics\nCourse Link: https://example.com/ml\nCourse Instructor: John Doe\nLesson 1: Introduction to ML\nMachine learning is a subset of artificial intelligence that focuses on algorithms.",
            "filename": "ml_basics.txt"
        },
        {
            "title": "Advanced Python",
            "content": "Course Title: Advanced Python\nCourse Link: https://example.com/python\nCourse Instructor: Jane Smith\nLesson 1: Advanced Functions\nPython functions can be powerful tools for code organization.",
            "filename": "python_advanced.txt"
        }
    ]


@pytest.fixture
async def async_client():
    """Async HTTP client for testing."""
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def test_app_without_static():
    """Create test FastAPI app without static file mounting to avoid test issues."""
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    from typing import List, Optional, Union, Dict
    
    # Create test app
    app = FastAPI(title="Test Course Materials RAG System")
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Pydantic models
    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[Union[str, Dict[str, Optional[str]]]]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]
    
    # Mock RAG system for tests
    mock_rag = Mock()
    mock_rag.session_manager.create_session.return_value = "test-session-123"
    mock_rag.query.return_value = (
        "Test response",
        ["Test Source"]
    )
    mock_rag.get_course_analytics.return_value = {
        "total_courses": 1,
        "course_titles": ["Test Course"]
    }
    
    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag.session_manager.create_session()
            
            answer, sources = mock_rag.query(request.query, session_id)
            
            return QueryResponse(
                answer=answer,
                sources=sources,
                session_id=session_id
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/")
    async def root():
        return {"message": "Course Materials RAG System API"}
    
    # Store mock for access in tests
    app.state.mock_rag = mock_rag
    
    return app


@pytest.fixture
def client(test_app_without_static):
    """Test client for FastAPI app."""
    return TestClient(test_app_without_static)


# Utility functions for tests

def create_temp_course_file(temp_dir: str, filename: str, content: str) -> str:
    """Create a temporary course file for testing."""
    filepath = os.path.join(temp_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return filepath


def assert_valid_session_id(session_id: str) -> None:
    """Assert that a session ID is valid format."""
    assert isinstance(session_id, str)
    assert len(session_id) > 0
    assert session_id != ""


def assert_valid_sources(sources: List) -> None:
    """Assert that sources list is valid."""
    assert isinstance(sources, list)
    for source in sources:
        assert isinstance(source, (str, dict))
        if isinstance(source, str):
            assert len(source) > 0


# Mock data for consistent testing

SAMPLE_COURSE_CONTENT = """Course Title: Machine Learning Fundamentals
Course Link: https://example.com/ml-fundamentals
Course Instructor: Dr. Sarah Johnson

Lesson 1: Introduction to Machine Learning
Machine learning is a method of data analysis that automates analytical model building. It is a branch of artificial intelligence (AI) based on the idea that systems can learn from data, identify patterns and make decisions with minimal human intervention.

Lesson 2: Supervised Learning
Supervised learning is the machine learning task of learning a function that maps an input to an output based on example input-output pairs. It infers a function from labeled training data consisting of a set of training examples.

Lesson 3: Unsupervised Learning
Unsupervised learning is a type of machine learning that looks for previously undetected patterns in a data set with no pre-existing labels and with a minimum of human supervision.
"""

SAMPLE_PYTHON_CONTENT = """Course Title: Advanced Python Programming
Course Link: https://example.com/advanced-python
Course Instructor: Prof. Mike Chen

Lesson 1: Decorators and Context Managers
Decorators provide a simple syntax for calling higher-order functions. Context managers allow you to allocate and release resources precisely when you want to.

Lesson 2: Metaclasses and Descriptors
Metaclasses are classes whose instances are classes. They allow you to control the creation of classes. Descriptors are objects that define how attribute access is handled.
"""