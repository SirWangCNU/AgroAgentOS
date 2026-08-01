import os

os.environ["DEBUG"] = "false"

from app.main import app


def test_public_routes_expose_agriculture_without_aiops_endpoints():
    paths = {route.path for route in app.routes}

    assert "/api/v1/chat/stream" in paths
    assert "/api/v1/image/analyze" in paths
    assert "/api/v1/farms" in paths

    removed_prefixes = (
        "/api/v1/aiops",
        "/api/v1/webhook",
        "/api/v1/diagnosis",
        "/api/v1/observability",
    )
    assert not any(
        path.startswith(prefix)
        for path in paths
        for prefix in removed_prefixes
    )
