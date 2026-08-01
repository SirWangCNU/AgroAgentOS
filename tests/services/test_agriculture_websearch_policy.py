import os

os.environ["DEBUG"] = "false"

from mcp_servers.websearch_server import _check_blocklist


def test_agriculture_weather_query_is_allowed():
    assert _check_blocklist("今天北京天气适合给水稻喷药吗") == ""


def test_unrelated_entertainment_query_remains_blocked():
    assert _check_blocklist("推荐一部动漫")
