"""TutorFlow follow-up board — today's ranked follow-ups + pipeline overview.

Run:
    uvicorn main:app --port 8002        # terminal 1
    streamlit run dashboard.py          # terminal 2
"""

import httpx
import streamlit as st

st.set_page_config(page_title="TutorFlow", page_icon="📋", layout="wide")

NAVY = "#1a365d"
SLATE = "#334155"
LIGHT = "#f7fafc"
TIMEOUT = 8.0
STAGE_LABELS = {
    "new": "新线索",
    "contacted": "已联系",
    "qualified": "已确认需求",
    "trial": "已试听",
    "won": "已成交",
    "lost": "已流失",
}

st.markdown(
    f"""
    <style>
        .stApp {{ background: {LIGHT}; color: {SLATE}; }}
        h1, h2, h3 {{ color: {NAVY}; }}
        div[data-testid="stMetricValue"] {{ color: {SLATE}; }}
        div[data-testid="stMetricLabel"] {{ color: {SLATE}; }}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.title("TutorFlow")
    st.caption("家教老师的客户经营系统")
    page = st.radio("页面", ["今日待跟进", "线索管道"], label_visibility="collapsed")


def _error(context: str, exc: Exception):
    st.error(f"{context} 失败（确认已启动 `uvicorn main:app --port 8002`）：{exc}")


def fetch_summary():
    try:
        resp = httpx.get(
            "http://127.0.0.1:8002/analytics/summary",
            timeout=TIMEOUT,
            follow_redirects=False,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        _error("读取漏斗", exc)
        return None


def fetch_followups(status: str):
    params = {"status": status} if status != "all" else None
    try:
        resp = httpx.get(
            "http://127.0.0.1:8002/followups",
            params=params,
            timeout=TIMEOUT,
            follow_redirects=False,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        _error("读取跟进列表", exc)
        return None


def fetch_leads():
    try:
        resp = httpx.get(
            "http://127.0.0.1:8002/leads",
            timeout=TIMEOUT,
            follow_redirects=False,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        _error("读取线索", exc)
        return None


def generate_followups():
    try:
        resp = httpx.post(
            "http://127.0.0.1:8002/followups/generate",
            params={"top_n": 5},
            timeout=30.0,
            follow_redirects=False,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        _error("生成跟进", exc)
        return None


def mark_done(followup_id: int):
    try:
        resp = httpx.patch(
            f"http://127.0.0.1:8002/followups/{followup_id}/done",
            timeout=TIMEOUT,
            follow_redirects=False,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        _error("标记完成", exc)
        return None


def handoff_to_teacheros(lead_id: int):
    """Fetch the TeacherOS payload from TutorFlow, then create the student in TeacherOS."""
    try:
        resp = httpx.post(
            f"http://127.0.0.1:8002/leads/{lead_id}/handoff",
            timeout=30.0,
            follow_redirects=False,
        )
        resp.raise_for_status()
        payload = resp.json()["teacheros_student"]
    except Exception as exc:
        _error("生成交接档案", exc)
        return None
    try:
        created = httpx.post(
            "http://127.0.0.1:8000/students",
            json=payload,
            timeout=30.0,
            follow_redirects=False,
        )
        created.raise_for_status()
        return created.json()
    except Exception as exc:
        st.warning(f"TeacherOS 建档失败（确认 8000 端口已启动），档案已生成可手动创建：{payload}")
        _error("TeacherOS 建档", exc)
        return None


def pipeline_metrics(summary):
    if not summary:
        return
    counts = summary["stage_counts"]
    cols = st.columns(6)
    for col, (stage, label) in zip(cols, STAGE_LABELS.items()):
        with col:
            st.metric(label, counts.get(stage, 0))
    win_rate = summary.get("win_rate")
    budget = summary.get("avg_budget")
    st.caption(
        f"成交率 {win_rate * 100:.0f}% ｜ 平均预算 ¥{budget:.0f}"
        if win_rate is not None and budget
        else "暂无成交数据"
    )
    rates = summary.get("conversion_rates") or {}
    rate_parts = [
        f"{label} {rates[key] * 100:.0f}%"
        for key, label in (
            ("contacted_to_qualified", "确认需求"),
            ("qualified_to_trial", "约试听"),
            ("trial_to_won", "成交"),
        )
        if rates.get(key) is not None
    ]
    if rate_parts:
        st.caption("阶段转化率 ｜ " + " ｜ ".join(rate_parts))


if page == "今日待跟进":
    st.header("今日待跟进")
    summary = fetch_summary()
    pipeline_metrics(summary)

    if st.button("生成今日跟进清单", type="primary"):
        created = generate_followups()
        if created is not None:
            st.success(f"已生成 {len(created)} 条跟进建议")
            st.rerun()

    followups = fetch_followups("pending") or []
    if not followups:
        st.info("暂无待跟进，点击上方按钮生成。")
    for item in followups:
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                customer = item.get("customer_name") or "未知客户"
                stage_label = STAGE_LABELS.get(item.get("lead_stage") or "", "")
                title = f"{customer} · {stage_label}" if stage_label else customer
                st.markdown(f"**{title}** — {item['reason']}（跟进 #{item['id']}）")
                st.caption(f"建议动作：{item['suggested_action']}")
            with col2:
                st.metric("优先分", f"{item['score']:.2f}")
            st.text_area("建议话术（可直接复制）", value=item["suggested_message"], key=f"msg_{item['id']}", height=90)
            if st.button("标记完成", key=f"done_{item['id']}"):
                if mark_done(item["id"]):
                    st.rerun()

elif page == "线索管道":
    st.header("线索管道")
    summary = fetch_summary()
    pipeline_metrics(summary)

    leads = fetch_leads() or []
    if leads:
        st.dataframe(
            [{
                "ID": lead["id"],
                "客户": lead.get("customer_name") or "未知客户",
                "阶段": STAGE_LABELS.get(lead["stage"], lead["stage"]),
                "意向": lead["intent"],
                "预算": lead["budget"],
                "下一步": lead["next_action"],
            } for lead in leads],
            use_container_width=True,
        )
    else:
        st.info("暂无线索，先在 API 里录入一条微信咨询（POST /customers/{id}/conversations）。")

    won_leads = [lead for lead in leads if lead["stage"] == "won"] if leads else []
    if won_leads:
        st.subheader("待交接（已成交）")
        for lead in won_leads:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"线索 #{lead['id']} · {lead.get('customer_name') or '未知客户'} — 意向 {lead['intent']}，预算 {lead['budget']}")
            with col2:
                if st.button("交接至 TeacherOS", key=f"handoff_{lead['id']}"):
                    created = handoff_to_teacheros(lead["id"])
                    if created:
                        st.success(f"已在 TeacherOS 建档：{created['name']}（学生 ID {created['id']}）")
