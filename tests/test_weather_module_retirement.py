import subprocess
import sys
import textwrap


def test_standalone_weather_routes_are_not_registered():
    check_routes = textwrap.dedent(
        """
        from app.main import app

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

        unexpected = {
            "/api/v1/weather",
            "/api/v1/weather/location",
            "/api/v1/weather/config",
        } & paths
        assert not unexpected, unexpected
        assert "/api/v1/farms/{farm_id}/weather" in paths
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", check_routes],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
