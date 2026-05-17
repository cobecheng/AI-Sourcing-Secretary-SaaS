from fastapi.testclient import TestClient

from app.main import app


def test_planned_route_shells_are_registered() -> None:
    client = TestClient(app)

    checks = [
        ("POST", "/projects/demo-project/chat"),
        ("GET", "/projects/demo-project/milestones"),
        ("GET", "/projects/demo-project/suppliers"),
        ("GET", "/projects/demo-project/approvals"),
        ("POST", "/suppliers/demo-supplier/outreach/draft"),
        ("POST", "/inbox/sync"),
        ("POST", "/projects/demo-project/report/generate"),
    ]

    for method, path in checks:
        response = client.request(method, path)
        assert response.status_code == 200
        assert response.json()["status"] == "not_implemented"
        assert response.json()["mock_mode"] is True


def test_outbound_placeholders_include_safety_metadata() -> None:
    client = TestClient(app)

    response = client.post("/inbox/sync")

    assert response.status_code == 200
    assert "idempotent" in response.json()["metadata"]["safety"]
