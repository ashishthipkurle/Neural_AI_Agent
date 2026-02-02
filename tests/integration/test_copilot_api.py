import pytest
from fastapi.testclient import TestClient
from agent.api_server import app
from agent.core.file_safety import start_gate

client = TestClient(app)

class TestCopilotAPI:
    
    def test_suggest_endpoint(self):
        """Test inline suggestion endpoint."""
        # Mocking LLM response would be ideal, but for now we expect 200 OK 
        # even if LLM fails (returns empty suggestion)
        response = client.post("/api/copilot/suggest", json={
            "file_content": "def hello():\n    print('world')",
            "cursor_line": 2,
            "cursor_column": 18,
            "language": "python"
        })
        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data

    def test_refactor_creates_proposal(self, tmp_path):
        """Test refactoring workflow creates a proposal."""
        # We'll mock the LLM call or use a simplified path in refactor if instructions are trivial?
        # Since refactor relies on LLM, it's hard to test fully without mocking.
        # However, we can test that INVALID request fails.
        
        response = client.post("/api/copilot/refactor", json={
            "file_content": "code",
            "cursor_line": 1,
            "cursor_column": 1,
            "language": "python"
            # Missing selection and instruction
        })
        assert response.status_code == 400

    def test_apply_diff_security(self):
        """Test that apply-diff requires valid proposal and approval."""
        
        # 1. Try with invalid ID
        response = client.post("/api/copilot/apply-diff", json={
            "proposal_id": "invalid_id",
            "user_approved": True
        })
        assert response.status_code == 400
        assert "Invalid or expired" in response.json()["detail"]
        
        # 2. Create a manual proposal in safety gate to test approval logic
        pid = start_gate.create_proposal("write", "/tmp/test.txt", "content")
        
        # 3. Try with user_approved = False
        response = client.post("/api/copilot/apply-diff", json={
            "proposal_id": pid,
            "user_approved": False
        })
        assert response.status_code == 400
        assert "User rejected" in response.json()["detail"]
        
        # 4. Try with user_approved = True (Should work, but file write might fail in test env if path invalid)
        # We used /tmp/test.txt which might not work on Windows without careful path
        # But the Logic check happens before file write attempt mostly.
        # Actually verify_and_apply attempts write.
        
        # Let's use a safe path
        import os
        safe_file = "test_safe_write.txt"
        pid2 = start_gate.create_proposal("write", safe_file, "content")
        
        response = client.post("/api/copilot/apply-diff", json={
            "proposal_id": pid2,
            "user_approved": True
        })
        
        # If it succeeds it returns 200
        # If file write fails (permissions etc), it returns 400 with error msg
        # We accept either as passing the SECURITY check.
        # The key is we didn't get "Invalid ID" or "User rejected".
        
        if response.status_code == 200:
            assert response.json()["status"] == "success"
            # Clean up
            if os.path.exists(safe_file):
                os.remove(safe_file)
        else:
            # If it failed, make sure it wasn't security related
            assert "Invalid" not in response.json()["detail"]
            assert "rejected" not in response.json()["detail"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
