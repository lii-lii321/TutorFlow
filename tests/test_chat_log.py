from app.services.ingest import parse_chat_log

LOG = (
    "2024-10-01 10:30 王女士: 老师您好，孩子现在初二，数学大概80分，希望提高到100分左右，周末有时间，预算150一节。\n"
    "我：好的，孩子平时作业完成情况怎么样？\n"
    "王女士：计算还可以，应用题比较薄弱。\n"
    "- 2024-10-02 09:00 我：那我们先约一次试听吧。\n"
)


def test_directions_and_content():
    messages = parse_chat_log(LOG)
    assert [m["direction"] for m in messages] == ["in", "out", "in", "out"]
    assert messages[0]["content"].startswith("老师您好")
    assert "150一节" in messages[0]["content"]
    assert messages[1]["content"] == "好的，孩子平时作业完成情况怎么样？"
    assert messages[3]["content"] == "那我们先约一次试听吧。"


def test_timestamp_and_bullet_stripped():
    messages = parse_chat_log(LOG)
    assert not messages[0]["content"].startswith("2024")
    assert not messages[3]["content"].startswith("-")


def test_lines_without_speaker_default_inbound():
    messages = parse_chat_log("随便一句话")
    assert messages == [{"direction": "in", "content": "随便一句话"}]


def test_empty_lines_skipped():
    messages = parse_chat_log("你好\n\n\n老师好")
    assert len(messages) == 2
