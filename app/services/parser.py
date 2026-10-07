import json
import re
from dataclasses import dataclass

from app.services.llm.provider import get_provider

CORE_FIELDS = ["grade", "subject", "current_score", "target_score", "budget"]

GRADE_PATTERNS = [
    r"小学?[一二三四五六](?:年级)?",
    r"初[一二三]",
    r"高[一二三]",
    r"大一|大二|大三|大四",
    r"考研",
]

SUBJECTS = ["奥数", "数学", "英语", "物理", "化学", "语文", "生物", "历史", "地理", "政治", "编程", "钢琴", "美术"]

TARGET_KEYWORDS = ("希望", "想提高", "想达到", "想考", "目标", "提到", "冲到", "达到", "提升到", "考到")
CURRENT_KEYWORDS = ("现在", "目前", "大概", "大约", "左右", "只有", "考了", "才")

AVAILABILITY_KEYWORDS = ["周末", "周六", "周日", "周中", "工作日", "晚上", "下午", "上午", "寒暑假", "寒假", "暑假", "平时"]

HIGH_SIGNAL = ("想学", "想找", "想开始", "想提高")
STRONG_HIGH_SIGNAL = ("什么时候", "怎么收费", "如何收费", "可以试", "试听", "约课", "报名")
LOW_SIGNAL = ("再考虑", "暂时不", "以后再说", "先不", "不需要", "再看看", "再议", "先算了")

NEEDS = {
    "成绩提升": ("提高", "提升", "提分", "上去"),
    "考前冲刺": ("冲刺", "考前", "中考", "高考", "期末"),
    "基础巩固": ("基础", "补差", "跟不上"),
    "稳定进步": ("稳定", "保持"),
    "兴趣培养": ("兴趣", "启蒙"),
}

LLM_SYSTEM = (
    "从中文微信咨询文本中提取家教需求字段。只返回一个 JSON 对象，"
    '形如 {"grade": "初二", "subject": "数学", "current_score": 80, "target_score": 100, '
    '"budget": 150, "availability": ["周末"], "intent": "high", "needs": ["成绩提升"]}。'
    "缺失的字段不要编造，直接省略。intent 取值 high/mid/low。"
)


@dataclass
class Extraction:
    fields: dict
    missing: list
    intent: str
    confidence: float
    parser: str = "rules"


def extract_grade(text: str) -> str | None:
    for pattern in GRADE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None


def extract_subject(text: str) -> str | None:
    for subject in SUBJECTS:
        if subject in text:
            return subject
    return None


def extract_scores(text: str) -> tuple:
    current = target = None
    for match in re.finditer(r"(\d{2,3})\s*分", text):
        window = text[max(0, match.start() - 10):match.start()]
        if any(k in window for k in TARGET_KEYWORDS):
            if target is None:
                target = int(match.group(1))
        elif any(k in window for k in CURRENT_KEYWORDS):
            if current is None:
                current = int(match.group(1))
    return current, target


def extract_budget(text: str):
    patterns = [
        r"(?:一节|每次|每小时)\s*(\d{2,4})\s*(?:元|块)?",
        r"(\d{2,4})\s*(?:元|块)\s*(?:一节|/节|每次|一小时|每小时)?",
        r"(\d{2,4})\s*(?:一节|每次|/节)",
        r"预算[^0-9]{0,6}(\d{2,4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))
    return None


def extract_availability(text: str) -> list:
    return [k for k in AVAILABILITY_KEYWORDS if k in text]


def extract_needs(text: str) -> list:
    return [label for label, keywords in NEEDS.items() if any(k in text for k in keywords)]


def detect_intent(text: str, found_fields: int) -> str:
    if any(k in text for k in LOW_SIGNAL):
        return "low"
    if any(k in text for k in STRONG_HIGH_SIGNAL):
        return "high"
    if any(k in text for k in HIGH_SIGNAL) and found_fields >= 1:
        return "high"
    if found_fields >= 3:
        return "high"
    if found_fields >= 1:
        return "mid"
    return "mid"


def parse_message(text: str) -> Extraction:
    fields: dict = {}
    grade = extract_grade(text)
    if grade:
        fields["grade"] = grade
    subject = extract_subject(text)
    if subject:
        fields["subject"] = subject
    current, target = extract_scores(text)
    if current is not None:
        fields["current_score"] = current
    if target is not None:
        fields["target_score"] = target
    budget = extract_budget(text)
    if budget is not None:
        fields["budget"] = budget
    availability = extract_availability(text)
    if availability:
        fields["availability"] = availability
    needs = extract_needs(text)
    if needs:
        fields["needs"] = needs

    missing = [k for k in CORE_FIELDS if k not in fields]
    found = len(CORE_FIELDS) - len(missing)
    intent = detect_intent(text, found)
    confidence = round(min(1.0, found * 0.18 + (0.15 if availability else 0) + (0.1 if needs else 0)), 2)
    return Extraction(fields=fields, missing=missing, intent=intent, confidence=confidence)


async def parse_message_smart(text: str, provider=None) -> Extraction:
    base = parse_message(text)
    provider = provider or get_provider()
    if provider.name == "mock":
        return base
    try:
        raw = await provider.complete(LLM_SYSTEM, text)
        data = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
        fields = dict(base.fields)
        for key in ("grade", "subject", "budget"):
            if data.get(key) and key not in fields:
                fields[key] = data[key]
        for key in ("current_score", "target_score"):
            if isinstance(data.get(key), int) and key not in fields:
                fields[key] = data[key]
        if isinstance(data.get("availability"), list) and data["availability"]:
            fields["availability"] = data["availability"]
        if isinstance(data.get("needs"), list) and data["needs"]:
            fields["needs"] = data["needs"]
        intent = data.get("intent")
        return Extraction(
            fields=fields,
            missing=[k for k in CORE_FIELDS if k not in fields],
            intent=intent if intent in ("high", "mid", "low") else base.intent,
            confidence=max(base.confidence, 0.85),
            parser="llm",
        )
    except Exception:
        return base
