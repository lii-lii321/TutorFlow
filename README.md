# TutorFlow

AI CRM for independent tutors: paste WeChat-style parent inquiries, get a
structured customer profile, an enforced lead pipeline, and a ranked daily
follow-up list with ready-to-send messages.

Companion to **TeacherOS** (teaching delivery) — TutorFlow covers everything
before the first lesson: acquisition, qualification, trial, closing.

Part of a personal product matrix (TeacherOS → teaching delivery, TutorFlow →
client CRM, Data Analyst Agent → data-science engine).

## Core loop

```
微信咨询文本
   ↓
Conversation Parser     中文规则引擎：年级/科目/当前&目标分数/预算/时间/需求/意向
   ↓                     （可切换任意 OpenAI 兼容 LLM，规则引擎永远兜底）
Customer Profile        预算演变时间线、需求标签、价格敏感度、决策速度
   ↓
Lead State Machine      new → contacted → qualified → trial → won / lost
   ↓                     （非法跳转返回 409，全量事件留痕）
Follow-up Engine        评分 = 阶段权重 + 意向权重 + 沉默天数 + 试听黄金期加成
   ↓                     → 每日 Top N 待跟进 + 建议动作 + 可直接发送的话术
Analytics               漏斗、阶段转化率、成交率、平均预算、渠道来源
```

## Example

Input (one WeChat message):

> 老师您好，我家孩子现在初二，数学大概80分，希望提高到100分左右，周末有时间，预算150一节。

Extracted:

```json
{
  "grade": "初二", "subject": "数学",
  "current_score": 80, "target_score": 100,
  "budget": 150, "availability": ["周末"], "needs": ["成绩提升"]
}
```

Lead auto-advances `new → contacted`, budget/intent update on every message,
and the customer profile tracks budget evolution over time (an evolving entity,
not a static CRUD row).

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn main:app --reload --port 8002
```

Seed a demo funnel (5 customers across all stages + daily follow-ups):

```bash
.venv\Scripts\python scripts\seed_demo.py
```

Optional LLM extraction (any OpenAI-compatible endpoint):

```bash
copy .env.example .env   # set TUTORFLOW_LLM_* values
```

## API overview

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/customers` | create customer |
| POST | `/customers/{id}/conversations` | ingest WeChat message → parse → update lead (`occurred_at` 可带时区，自动归一为 naive UTC) |
| POST | `/customers/{id}/conversations/bulk` | paste a whole chat log (`说话人：内容` lines, `我：` = outbound, `[图片]`/`[表情]`/`[语音]` 等占位行自动过滤) |
| GET | `/customers/{id}/conversations` | conversation history (ordered by occurred_at) |
| GET | `/customers/{id}/profile` | budget history, needs, price sensitivity, decision speed |
| GET | `/leads?stage=&intent=` | pipeline list（含 `customer_name`） |
| POST | `/leads/{id}/transition` | move stage (409 on invalid jump; won/lost 自动取消该线索的 pending 跟进，保留 cancelled 留痕) |
| POST | `/leads/{id}/handoff` | won lead → TeacherOS student payload (409 if not won / already handed off) |
| POST | `/followups/generate` | build today's ranked follow-up list |
| GET | `/followups?status=` | ranked follow-up list (`pending`/`done`/`cancelled`/`all`，含 `customer_name`/`lead_stage` 客户身份) |
| PATCH | `/followups/{id}/done` | mark follow-up done (409 if already done/cancelled，cancelled 留痕不可翻转为 done) |
| GET | `/analytics/summary` | funnel, conversion, win rate, sources |

## Design decisions

- **Entity evolution**: budget changes are appended to the conversation
  extraction log; the lead's current budget is a projection, history is kept.
- **Human-in-the-loop**: the engine suggests messages, never auto-sends.
- **State machine discipline**: every stage change is a `LeadEvent` row; the
  funnel analytics are computed from events, not from mutable state.
- **Offline-first**: rule-based Chinese parser works with zero API keys; LLM
  mode is a strict upgrade (rules fill whatever the LLM misses).
- **One clock**: all timestamps are stored as naive UTC; timezone-aware
  `occurred_at` input is normalized at the API boundary, so imported history
  and live `utcnow()` records sort on the same timeline.

## Testing

```bash
.venv\Scripts\python -m pytest -q     # 76 tests
```

## Roadmap

- [x] Parser, state machine, follow-up engine, funnel analytics
- [x] Won-lead → TeacherOS handoff endpoint (`POST /leads/{id}/handoff`)
- [x] Streamlit follow-up board (`dashboard.py`：今日待跟进 + 线索管道 + **一键交接 TeacherOS**)
- [x] Chat log bulk ingestion (`conversations/bulk`，粘贴整段微信记录)
- [x] WeChat export import (chat log bulk ingestion)
- [x] One-click handoff from the board (board button → TeacherOS API)
