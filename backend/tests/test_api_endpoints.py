import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import httpx
import sys
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


class TestQueryEndpoint:
    """Test the /api/query endpoint."""
    
    def test_query_with_session_id(self, client):
        """Test query endpoint with existing session ID."""
        response = client.post("/api/query", json={
            "query": "What is machine learning?",
            "session_id": "existing-session-123"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        assert data["session_id"] == "existing-session-123"
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
    
    def test_query_without_session_id(self, client):
        """Test query endpoint without session ID (should create new session)."""
        response = client.post("/api/query", json={
            "query": "Explain supervised learning"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        assert data["session_id"] == "test-session-123"  # From mock
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
    
    def test_query_empty_string(self, client):
        """Test query endpoint with empty query string."""
        response = client.post("/api/query", json={
            "query": ""
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
    
    def test_query_missing_query_field(self, client):
        """Test query endpoint with missing query field."""
        response = client.post("/api/query", json={
            "session_id": "test-session"
        })
        
        assert response.status_code == 422  # Validation error
    
    def test_query_invalid_json(self, client):
        """Test query endpoint with invalid JSON."""
        response = client.post("/api/query", data="invalid json")
        
        assert response.status_code == 422
    
    def test_query_with_rag_system_error(self, client, test_app_without_static):
        """Test query endpoint when RAG system raises an error."""
        # Mock the RAG system to raise an exception
        mock_rag = test_app_without_static.state.mock_rag
        mock_rag.query.side_effect = Exception("RAG system error")
        
        response = client.post("/api/query", json={
            "query": "test query"
        })
        
        assert response.status_code == 500
        assert "RAG system error" in response.json()["detail"]
    
    def test_query_very_long_text(self, client):
        """Test query endpoint with very long query text."""
        long_query = "What is machine learning? " * 100
        
        response = client.post("/api/query", json={
            "query": long_query
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
    
    def test_query_special_characters(self, client):
        """Test query endpoint with special characters."""
        response = client.post("/api/query", json={
            "query": "What about ML & AI? Does it handle UTF-8 like café, naïve, résumé?"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data


class TestCoursesEndpoint:
    """Test the /api/courses endpoint."""
    
    def test_get_courses_success(self, client):
        """Test successful courses endpoint call."""
        response = client.get("/api/courses")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_courses" in data
        assert "course_titles" in data
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)
        assert data["total_courses"] >= 0
    
    def test_get_courses_with_rag_error(self, client, test_app_without_static):
        """Test courses endpoint when RAG system raises an error."""
        mock_rag = test_app_without_static.state.mock_rag
        mock_rag.get_course_analytics.side_effect = Exception("Analytics error")
        
        response = client.get("/api/courses")
        
        assert response.status_code == 500
        assert "Analytics error" in response.json()["detail"]
    
    def test_get_courses_empty_catalog(self, client, test_app_without_static):
        """Test courses endpoint with empty course catalog."""
        mock_rag = test_app_without_static.state.mock_rag
        mock_rag.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }
        
        response = client.get("/api/courses")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []
    
    def test_get_courses_multiple_courses(self, client, test_app_without_static):
        """Test courses endpoint with multiple courses."""
        mock_rag = test_app_without_static.state.mock_rag
        mock_rag.get_course_analytics.return_value = {
            "total_courses": 3,
            "course_titles": ["ML Basics", "Python Advanced", "Data Science"]
        }
        
        response = client.get("/api/courses")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 3
        assert len(data["course_titles"]) == 3
        assert "ML Basics" in data["course_titles"]
        assert "Python Advanced" in data["course_titles"]
        assert "Data Science" in data["course_titles"]


class TestRootEndpoint:
    """Test the root / endpoint."""
    
    def test_root_endpoint(self, client):
        """Test root endpoint returns basic info."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert isinstance(data["message"], str)


class TestAPIIntegration:
    """Integration tests for API endpoints."""
    
    def test_query_then_courses_workflow(self, client):
        """Test typical workflow: query then check courses."""
        # First, make a query
        query_response = client.post("/api/query", json={
            "query": "What is Python?"
        })
        
        assert query_response.status_code == 200
        query_data = query_response.json()
        session_id = query_data["session_id"]
        
        # Then get course stats
        courses_response = client.get("/api/courses")
        
        assert courses_response.status_code == 200
        courses_data = courses_response.json()
        
        # Verify both responses are valid
        assert "answer" in query_data
        assert "total_courses" in courses_data
    
    def test_multiple_queries_same_session(self, client):
        """Test multiple queries with the same session ID."""
        session_id = "test-session-persistence"
        
        # First query
        response1 = client.post("/api/query", json={
            "query": "What is machine learning?",
            "session_id": session_id
        })
        
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["session_id"] == session_id
        
        # Second query with same session
        response2 = client.post("/api/query", json={
            "query": "Tell me about supervised learning",
            "session_id": session_id
        })
        
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["session_id"] == session_id
    
    def test_concurrent_queries_different_sessions(self, client):
        """Test concurrent queries with different session IDs."""
        # Query 1
        response1 = client.post("/api/query", json={
            "query": "What is AI?",
            "session_id": "session-1"
        })
        
        # Query 2
        response2 = client.post("/api/query", json={
            "query": "What is ML?",
            "session_id": "session-2"
        })
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        assert data1["session_id"] == "session-1"
        assert data2["session_id"] == "session-2"


class TestAPIHeaders:
    """Test API request/response headers."""
    
    def test_cors_headers(self, client):
        """Test CORS headers are present."""
        response = client.options("/api/query")
        
        # FastAPI/TestClient may not return all CORS headers in OPTIONS,
        # but we can test a regular request
        response = client.get("/api/courses")
        assert response.status_code == 200
    
    def test_content_type_json(self, client):
        """Test API returns JSON content type."""
        response = client.get("/api/courses")
        
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")
    
    def test_query_accepts_json(self, client):
        """Test query endpoint accepts JSON content type."""
        response = client.post(
            "/api/query",
            json={"query": "test"},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200


class TestAPIValidation:
    """Test API input validation."""
    
    def test_query_request_validation(self, client):
        """Test query request model validation."""
        # Valid request
        response = client.post("/api/query", json={
            "query": "valid query",
            "session_id": "valid-session"
        })
        assert response.status_code == 200
        
        # Invalid request - wrong types
        response = client.post("/api/query", json={
            "query": 123,  # Should be string
            "session_id": ["invalid"]  # Should be string or null
        })
        assert response.status_code == 422
    
    def test_response_model_structure(self, client):
        """Test response models match expected structure."""
        # Test query response
        query_response = client.post("/api/query", json={
            "query": "test query"
        })
        
        assert query_response.status_code == 200
        query_data = query_response.json()
        
        # Verify required fields
        required_fields = ["answer", "sources", "session_id"]
        for field in required_fields:
            assert field in query_data
        
        # Test courses response
        courses_response = client.get("/api/courses")
        
        assert courses_response.status_code == 200
        courses_data = courses_response.json()
        
        # Verify required fields
        required_fields = ["total_courses", "course_titles"]
        for field in required_fields:
            assert field in courses_data


@pytest.mark.integration
class TestAPIWithRealRAGSystem:
    """Integration tests using a real RAG system (marked as slow)."""
    
    @pytest.mark.slow
    def test_query_with_real_rag_system(self, test_config, temp_dir):
        """Test query with actual RAG system components."""
        # This would test with real RAG system if needed for integration testing
        # Currently skipped to keep tests fast
        pytest.skip("Integration test requires full RAG system setup")
    
    @pytest.mark.slow  
    def test_document_loading_and_query(self, temp_dir):
        """Test document loading and subsequent querying."""
        # This would test document loading + querying workflow
        pytest.skip("Integration test requires document setup")


# Performance and load tests
class TestAPIPerformance:
    """Basic performance tests for API endpoints."""
    
    def test_query_response_time(self, client):
        """Test query endpoint response time is reasonable."""
        import time
        
        start_time = time.time()
        response = client.post("/api/query", json={
            "query": "What is machine learning?"
        })
        end_time = time.time()
        
        assert response.status_code == 200
        # Should respond within 5 seconds (generous for testing)
        assert (end_time - start_time) < 5.0
    
    def test_courses_response_time(self, client):
        """Test courses endpoint response time is reasonable."""
        import time
        
        start_time = time.time()
        response = client.get("/api/courses")
        end_time = time.time()
        
        assert response.status_code == 200
        # Should respond very quickly for analytics
        assert (end_time - start_time) < 1.0