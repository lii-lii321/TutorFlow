from app.services.parser import parse_message

FULL = "老师您好，我家孩子现在初二，数学大概80分，希望提高到100分左右，周末有时间，预算150一节。"


def test_full_extraction():
    ex = parse_message(FULL)
    fields = ex.fields
    assert fields["grade"] == "初二"
    assert fields["subject"] == "数学"
    assert fields["current_score"] == 80
    assert fields["target_score"] == 100
    assert fields["budget"] == 150
    assert "周末" in fields["availability"]
    assert "成绩提升" in fields["needs"]
    assert ex.intent == "high"
    assert ex.missing == []
    assert ex.confidence >= 0.8


def test_budget_variants():
    assert parse_message("一节课150元可以吗").fields["budget"] == 150
    assert parse_message("150一节吧").fields["budget"] == 150
    assert parse_message("预算180左右").fields["budget"] == 180
    assert parse_message("每次200").fields["budget"] == 200
    assert "budget" not in parse_message("周末有时间").fields


def test_score_windows():
    ex = parse_message("孩子考了65分，我们的目标是75分")
    assert ex.fields["current_score"] == 65
    assert ex.fields["target_score"] == 75

    ex = parse_message("现在90分，想提到110分")
    assert ex.fields["current_score"] == 90
    assert ex.fields["target_score"] == 110


def test_scores_ignored_without_unit():
    assert "current_score" not in parse_message("预算150一节").fields


def test_intent_levels():
    assert parse_message("想让孩子什么时候能试听？").intent == "high"
    assert parse_message("怎么收费的？").intent == "high"
    assert parse_message("再考虑一下吧").intent == "low"
    assert parse_message("暂时不需要").intent == "low"
    assert parse_message("你好").intent == "mid"


def test_needs_extraction():
    ex = parse_message("想提高成绩，准备中考冲刺")
    assert "成绩提升" in ex.fields["needs"]
    assert "考前冲刺" in ex.fields["needs"]


def test_sparse_message():
    ex = parse_message("你好")
    assert ex.fields == {}
    assert ex.missing == ["grade", "subject", "current_score", "target_score", "budget"]
    assert ex.intent == "mid"
    assert ex.confidence == 0.0


def test_grade_variants():
    assert parse_message("孩子初三，想补数学").fields["grade"] == "初三"
    assert parse_message("孩子小五，数学跟不上").fields["grade"] == "小五"
    assert parse_message("孩子小学五年级，数学跟不上").fields["grade"] == "小学五年级"
    assert parse_message("高一英语，现在90分").fields["grade"] == "高一"
    assert parse_message("大二学生，想考研数学").fields["grade"] == "大二"
    assert parse_message("考研数学怎么收费").fields["grade"] == "考研"


def test_subject_variants():
    assert parse_message("想找英语老师").fields["subject"] == "英语"
    assert parse_message("高二物理，现在65分").fields["subject"] == "物理"
    assert parse_message("化学实验总是丢分").fields["subject"] == "化学"


def test_availability_multiple_keywords():
    ex = parse_message("周末和周中晚上都可以")
    assert ex.fields["availability"] == ["周末", "周中", "晚上"]


def test_needs_other_labels():
    ex = parse_message("孩子基础差有点跟不上，希望保持现状")
    assert "基础巩固" in ex.fields["needs"]
    assert "稳定进步" in ex.fields["needs"]


def test_interest_need_and_high_intent():
    ex = parse_message("想学钢琴，培养兴趣")
    assert ex.fields["subject"] == "钢琴"
    assert "兴趣培养" in ex.fields["needs"]
    assert ex.intent == "high"
