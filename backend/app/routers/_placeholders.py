from typing import Any


def placeholder_response(
    *,
    area: str,
    action: str,
    mock_mode: bool,
    detail: str = "Endpoint shell only. Implementation belongs to a future roadmap issue.",
    **metadata: Any,
) -> dict[str, Any]:
    return {
        "area": area,
        "action": action,
        "status": "not_implemented",
        "mock_mode": mock_mode,
        "detail": detail,
        "metadata": metadata,
    }

