import pytest
from unittest.mock import Mock, MagicMock, call
from typing import List, Dict, Any

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ai_generator import AIGenerator


class TestAIGenerator:
    """Test sequential tool calling behavior in AIGenerator"""
    
    @pytest.fixture
    def ai_generator(self):
        """Create AIGenerator instance with mocked client"""
        generator = AIGenerator("fake_key", "claude-sonnet-4")
        generator.client = Mock()
        return generator
    
    @pytest.fixture
    def mock_tool_manager(self):
        """Create mock tool manager"""
        tool_manager = Mock()
        tool_manager.execute_tool.return_value = "Tool execution result"
        return tool_manager
    
    @pytest.fixture
    def sample_tools(self):
        """Sample tool definitions"""
        return [
            {
                "name": "course_outline",
                "description": "Get course structure and lesson list",
                "input_schema": {"type": "object", "properties": {"course_name": {"type": "string"}}}
            },
            {
                "name": "search_course_content", 
                "description": "Search course content",
                "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}}
            }
        ]
    
    def create_mock_response(self, stop_reason: str, content_blocks: List[Dict[str, Any]]):
        """Helper to create mock API response"""
        response = Mock()
        response.stop_reason = stop_reason
        response.content = []
        
        for block in content_blocks:
            content = Mock()
            content.type = block["type"]
            if block["type"] == "tool_use":
                content.name = block["name"]
                content.input = block["input"]
                content.id = block["id"]
            elif block["type"] == "text":
                content.text = block["text"]
                
            response.content.append(content)
        
        return response

    def test_single_round_tool_execution(self, ai_generator, mock_tool_manager, sample_tools):
        """Test normal single round tool execution"""
        # Mock initial response with tool use
        initial_response = self.create_mock_response(
            stop_reason="tool_use",
            content_blocks=[{
                "type": "tool_use",
                "name": "course_outline",
                "input": {"course_name": "Python Basics"},
                "id": "tool_123"
            }]
        )
        
        # Mock second response without tool use (final)
        final_response = self.create_mock_response(
            stop_reason="end_turn",
            content_blocks=[{
                "type": "text", 
                "text": "Here's the course outline for Python Basics..."
            }]
        )
        
        # Configure mock client
        ai_generator.client.messages.create.side_effect = [initial_response, final_response]
        
        # Call generate_response
        result = ai_generator.generate_response(
            query="Get the outline for Python Basics course",
            tools=sample_tools,
            tool_manager=mock_tool_manager
        )
        
        # Verify API calls made
        assert ai_generator.client.messages.create.call_count == 2
        
        # Verify tool was executed
        mock_tool_manager.execute_tool.assert_called_once_with(
            "course_outline", 
            course_name="Python Basics"
        )
        
        # Verify result
        assert result == "Here's the course outline for Python Basics..."

    def test_sequential_two_round_tool_execution(self, ai_generator, mock_tool_manager, sample_tools):
        """Test sequential tool calling across 2 rounds"""
        # Mock initial response with tool use
        round1_response = self.create_mock_response(
            stop_reason="tool_use",
            content_blocks=[{
                "type": "tool_use",
                "name": "course_outline", 
                "input": {"course_name": "Python Basics"},
                "id": "tool_123"
            }]
        )
        
        # Mock second round response with another tool use
        round2_response = self.create_mock_response(
            stop_reason="tool_use",
            content_blocks=[{
                "type": "tool_use",
                "name": "search_course_content",
                "input": {"query": "lesson 4 topic"},
                "id": "tool_456"  
            }]
        )
        
        # Mock final response without tools
        final_response = self.create_mock_response(
            stop_reason="end_turn",
            content_blocks=[{
                "type": "text",
                "text": "Based on both searches, lesson 4 covers advanced functions."
            }]
        )
        
        # Configure mock client - initial call + 2 rounds + final
        ai_generator.client.messages.create.side_effect = [
            round1_response,  # Initial call
            round2_response,  # Round 2 
            final_response    # Final synthesis
        ]
        
        # Configure tool manager to return different results
        mock_tool_manager.execute_tool.side_effect = [
            "Course has 10 lessons including lesson 4: Advanced Functions",
            "Lesson 4 content: Functions, closures, decorators"
        ]
        
        # Call generate_response
        result = ai_generator.generate_response(
            query="Search for course that discusses same topic as lesson 4 of Python Basics",
            tools=sample_tools,
            tool_manager=mock_tool_manager
        )
        
        # Verify 3 API calls were made (initial + round 2 + final)
        assert ai_generator.client.messages.create.call_count == 3
        
        # Verify both tools were executed
        assert mock_tool_manager.execute_tool.call_count == 2
        mock_tool_manager.execute_tool.assert_any_call("course_outline", course_name="Python Basics")
        mock_tool_manager.execute_tool.assert_any_call("search_course_content", query="lesson 4 topic")
        
        # Verify result
        assert result == "Based on both searches, lesson 4 covers advanced functions."

    def test_max_rounds_limit_enforcement(self, ai_generator, mock_tool_manager, sample_tools):
        """Test that maximum 2 rounds are enforced"""
        # Create 3 tool use responses to test limit
        tool_response = self.create_mock_response(
            stop_reason="tool_use",
            content_blocks=[{
                "type": "tool_use", 
                "name": "course_outline",
                "input": {"course_name": "test"},
                "id": "tool_123"
            }]
        )
        
        final_response = self.create_mock_response(
            stop_reason="end_turn", 
            content_blocks=[{
                "type": "text",
                "text": "Final response after max rounds reached"
            }]
        )
        
        # Set up client to always return tool_use (would cause infinite loop without limit)
        ai_generator.client.messages.create.side_effect = [
            tool_response,  # Initial
            tool_response,  # Round 2 
            final_response  # Final (forced after max rounds)
        ]
        
        result = ai_generator.generate_response(
            query="Test query",
            tools=sample_tools, 
            tool_manager=mock_tool_manager
        )
        
        # Should make exactly 3 calls: initial + 1 more round + final
        assert ai_generator.client.messages.create.call_count == 3
        
        # Should execute tool exactly 2 times (once per round)
        assert mock_tool_manager.execute_tool.call_count == 2

    def test_tool_execution_error_handling(self, ai_generator, mock_tool_manager, sample_tools):
        """Test graceful handling of tool execution errors"""
        tool_response = self.create_mock_response(
            stop_reason="tool_use",
            content_blocks=[{
                "type": "tool_use",
                "name": "course_outline", 
                "input": {"course_name": "test"},
                "id": "tool_123"
            }]
        )
        
        final_response = self.create_mock_response(
            stop_reason="end_turn",
            content_blocks=[{
                "type": "text",
                "text": "Handled error gracefully"
            }]
        )
        
        ai_generator.client.messages.create.side_effect = [
            tool_response,
            final_response
        ]
        
        # Make tool execution fail
        mock_tool_manager.execute_tool.side_effect = Exception("Tool failed")
        
        result = ai_generator.generate_response(
            query="Test query",
            tools=sample_tools,
            tool_manager=mock_tool_manager
        )
        
        # Should still complete successfully
        assert result == "Handled error gracefully"
        
        # Should have attempted tool execution
        mock_tool_manager.execute_tool.assert_called_once()

    def test_api_error_during_rounds(self, ai_generator, mock_tool_manager, sample_tools):
        """Test handling of API errors during sequential rounds"""
        tool_response = self.create_mock_response(
            stop_reason="tool_use", 
            content_blocks=[{
                "type": "tool_use",
                "name": "course_outline",
                "input": {"course_name": "test"},
                "id": "tool_123"
            }]
        )
        
        final_response = self.create_mock_response(
            stop_reason="end_turn",
            content_blocks=[{
                "type": "text", 
                "text": "Recovery response"
            }]
        )
        
        # First call succeeds, second fails, third succeeds
        ai_generator.client.messages.create.side_effect = [
            tool_response,        # Initial success
            Exception("API Error"), # Round 2 fails
            final_response        # Final recovery
        ]
        
        result = ai_generator.generate_response(
            query="Test query",
            tools=sample_tools,
            tool_manager=mock_tool_manager
        )
        
        # Should recover and provide final response
        assert result == "Recovery response"

    def test_claude_stops_using_tools_naturally(self, ai_generator, mock_tool_manager, sample_tools):
        """Test when Claude decides not to use more tools after first round"""
        tool_response = self.create_mock_response(
            stop_reason="tool_use",
            content_blocks=[{
                "type": "tool_use",
                "name": "course_outline",
                "input": {"course_name": "test"}, 
                "id": "tool_123"
            }]
        )
        
        # Claude responds without tools in round 2
        natural_end_response = self.create_mock_response(
            stop_reason="end_turn",
            content_blocks=[{
                "type": "text",
                "text": "I have all the information I need from the first search."
            }]
        )
        
        ai_generator.client.messages.create.side_effect = [
            tool_response,
            natural_end_response
        ]
        
        result = ai_generator.generate_response(
            query="Test query", 
            tools=sample_tools,
            tool_manager=mock_tool_manager
        )
        
        # Should make only 2 calls (initial + round 2 with natural end)
        assert ai_generator.client.messages.create.call_count == 2
        
        # Should execute tool once
        assert mock_tool_manager.execute_tool.call_count == 1
        
        # Should return Claude's natural response
        assert result == "I have all the information I need from the first search."

    def test_round_system_prompt_building(self, ai_generator):
        """Test the _build_round_system_prompt helper method"""
        base_prompt = "You are an AI assistant."
        
        # Test round 2 prompt
        round2_prompt = ai_generator._build_round_system_prompt(base_prompt, 2, 2)
        assert "Current round: 2/2" in round2_prompt
        assert "You can use tools" in round2_prompt
        
        # Test final prompt  
        final_prompt = ai_generator._build_round_system_prompt(base_prompt, "final", 2)
        assert "completed all tool calling rounds" in final_prompt
        assert "Synthesize all the information" in final_prompt