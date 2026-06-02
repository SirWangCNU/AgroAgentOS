"""意图识别模块单元测试."""

from app.services.user_context.intent import QueryIntent, detect_intent


class TestDetectIntentFarm:
    """农场相关意图识别."""

    def test_farm_keyword(self):
        intent = detect_intent("我的农场有多少亩地")
        assert intent.has_farm is True
        assert "农场" in intent.farm_keywords

    def test_crop_keyword(self):
        intent = detect_intent("小麦现在处于什么生长阶段")
        assert intent.has_farm is True
        assert "小麦" in intent.farm_keywords

    def test_soil_keyword(self):
        intent = detect_intent("这块地的土壤是什么类型")
        assert intent.has_farm is True
        assert "土壤" in intent.farm_keywords

    def test_growth_stage_keyword(self):
        intent = detect_intent("水稻分蘖期需要注意什么")
        assert intent.has_farm is True
        assert "水稻" in intent.farm_keywords
        assert "分蘖期" in intent.farm_keywords


class TestDetectIntentTrajectory:
    """轨迹作业相关意图识别."""

    def test_trajectory_keyword(self):
        intent = detect_intent("最近作业质量怎么样")
        assert intent.has_trajectory is True

    def test_depth_keyword(self):
        intent = detect_intent("A1地块的耕深数据")
        assert intent.has_trajectory is True

    def test_machine_keyword(self):
        intent = detect_intent("农机的作业效率如何")
        assert intent.has_trajectory is True

    def test_upload_keyword(self):
        intent = detect_intent("我上传的excel数据")
        assert intent.has_trajectory is True


class TestDetectIntentDefault:
    """默认行为."""

    def test_unrelated_query_defaults_to_farm(self):
        intent = detect_intent("今天天气怎么样")
        assert intent.has_farm is True  # 默认注入农场概况
        assert intent.has_trajectory is False

    def test_empty_query(self):
        intent = detect_intent("")
        assert intent.has_farm is True  # 默认注入


class TestDetectIntentTimeRange:
    """时间范围识别."""

    def test_recent(self):
        intent = detect_intent("最近的作业数据")
        assert intent.time_range == "recent"

    def test_month(self):
        intent = detect_intent("这个月的作业记录")
        assert intent.time_range == "month"

    def test_no_time(self):
        intent = detect_intent("作业数据")
        assert intent.time_range == ""


class TestDetectIntentCombined:
    """组合意图."""

    def test_farm_and_trajectory(self):
        intent = detect_intent("A1地块最近旋耕深度合适吗")
        assert intent.has_farm is True
        assert intent.has_trajectory is True
        assert intent.time_range == "recent"

    def test_field_and_work(self):
        intent = detect_intent("我A1地块的作业质量怎么样")
        assert intent.has_farm is True
        assert intent.has_trajectory is True
