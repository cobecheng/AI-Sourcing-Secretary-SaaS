from fastapi.testclient import TestClient

from app.main import app


def test_mock_workspace_has_chat_first_structure() -> None:
    client = TestClient(app)

    response = client.get("/mock/workspace")
    payload = response.json()

    assert response.status_code == 200
    assert payload["project"]["pending_approvals"] == 2
    assert payload["messages"][0]["sender"] == "user"
    assert payload["suppliers"]
    assert payload["approvals"]

