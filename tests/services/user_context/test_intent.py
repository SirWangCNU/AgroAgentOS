"""农场意图识别模块单元测试。"""

from app.services.user_context.intent import detect_intent


def test_farm_keyword_is_exposed():
    intent = detect_intent("我的农场有多少亩地")
    assert intent.has_farm is True
    assert "农场" in intent.farm_keywords


def test_crop_and_growth_keywords_are_exposed():
    intent = detect_intent("水稻分蘖期需要注意什么")
    assert intent.has_farm is True
    assert "水稻" in intent.farm_keywords
    assert "分蘖期" in intent.farm_keywords


def test_unrelated_query_still_requests_farm_summary():
    intent = detect_intent("今天天气怎么样")
    assert intent.has_farm is True
    assert intent.farm_keywords == []
