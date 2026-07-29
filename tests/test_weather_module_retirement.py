from app.main import app


def test_standalone_weather_routes_are_not_registered():
    paths = set()
    for route in app.routes:
        if hasattr(route, "path"):
            paths.add(route.path)
            continue

        include_context = route.include_context
        paths.update(
            f"{include_context.prefix}{nested_route.path}"
            for nested_route in route.original_router.routes
        )

    assert "/api/v1/weather" not in paths
    assert "/api/v1/weather/location" not in paths
    assert "/api/v1/weather/config" not in paths
    assert "/api/v1/farms/{farm_id}/weather" in paths
