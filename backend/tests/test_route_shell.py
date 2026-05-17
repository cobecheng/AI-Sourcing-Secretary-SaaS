from fastapi.testclient import TestClient

from app.main import app


def test_planned_route_shells_are_registered() -> None:
    client = TestClient(app)

    checks = [
        ("POST", "/projects/demo-project/chat"),
        ("GET", "/projects/demo-project/milestones"),
    ]

    for method, path in checks:
        response = client.request(method, path)
        assert response.status_code == 200
        assert response.json()["status"] == "not_implemented"
        assert response.json()["mock_mode"] is True


def test_placeholders_include_metadata() -> None:
    client = TestClient(app)

    response = client.post("/projects/demo-project/chat")

    assert response.status_code == 200
    assert response.json()["metadata"]["project_id"] == "demo-project"
