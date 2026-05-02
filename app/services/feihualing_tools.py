from __future__ import annotations

import json
import logging
import random
import re

from openai import OpenAI

from app.core.config import settings
from app.db.connection import get_connection


logger = logging.getLogger(__name__)


_LINE_SPLIT_RE = re.compile(r"[，。；！？、,.!?;\n\r]+")
MIN_LINE_CHARS = 3
MAX_LINE_CHARS = 40

# 难度 -> Agent 可见诗库的最低 popularity_rank（1=偏僻, 5=顶流）
DIFFICULTY_MIN_RANK: dict[str, int] = {
    "easy": 4,       # 仅顶流（约 10% 诗库）
    "medium": 3,     # 中等及以上（约 30%）
    "hard": 1,       # 全库
    "expert": 1,     # 全库 + 允许 Agent 引用库外（炼狱）
}

# expert 模式下允许 Agent 跳过工具、引用库外原句
ALLOW_OUT_OF_LIBRARY = {"expert"}


def difficulty_min_rank(difficulty: str) -> int:
    return DIFFICULTY_MIN_RANK.get(difficulty, 1)


def split_poem_lines(content: str) -> list[str]:
    lines: list[str] = []
    for chunk in _LINE_SPLIT_RE.split(content or ""):
        text = chunk.strip()
        if MIN_LINE_CHARS <= len(text) <= MAX_LINE_CHARS:
            lines.append(text)
    return lines


def search_poems_by_char(
    char: str,
    difficulty: str = "medium",
    exclude_poem_ids: list[int] | None = None,
    exclude_lines: list[str] | None = None,
    limit: int = 10,
    min_rank: int | None = None,
) -> list[dict]:
    char = char.strip()
    if len(char) != 1:
        raise ValueError("char must be a single character")
    exclude_poem_ids = exclude_poem_ids or []
    exclude_lines_set = {line.strip() for line in (exclude_lines or [])}

    if min_rank is None:
        min_rank = difficulty_min_rank(difficulty)

    sql = """
        SELECT p.id, p.title, COALESCE(a.name, '佚名'), p.content
        FROM poems p LEFT JOIN authors a ON a.id = p.author_id
        WHERE p.content LIKE %s AND p.popularity_rank >= %s
    """
    params: list = [f"%{char}%", min_rank]
    if exclude_poem_ids:
        sql += " AND p.id <> ALL(%s)"
        params.append(exclude_poem_ids)

    if difficulty == "easy":
        sql += " ORDER BY p.popularity_rank DESC, p.id ASC"
    elif difficulty == "hard":
        sql += " ORDER BY p.popularity_rank ASC, p.id DESC"
    else:
        sql += " ORDER BY random()"
    sql += " LIMIT 100"

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

    candidates: list[dict] = []
    for poem_id, title, author, content in rows:
        for line in split_poem_lines(content):
            if char not in line:
                continue
            if line in exclude_lines_set:
                continue
            candidates.append(
                {
                    "poem_id": poem_id,
                    "title": title,
                    "author": author,
                    "line": line,
                }
            )

    if difficulty == "medium":
        random.shuffle(candidates)

    seen_lines: set[str] = set()
    deduped: list[dict] = []
    for item in candidates:
        if item["line"] in seen_lines:
            continue
        seen_lines.add(item["line"])
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


_VALIDATE_PROMPT = """你是古诗词鉴别专家。请严格判断以下句子是否是中国古典诗词（诗/词/曲/赋）的**原句**：

判定标准：
- 必须是古代作品中**一字不差**出现的句子（可包含句末标点与否不影响）
- 改写、化用、近似、拼接、现代人创作、散文、对联、俗语都不通过
- 如果你不能 100% 确认是真迹，请判为不通过

只返回 JSON，不要任何其他解释文字。字段说明：
- is_valid: true 或 false
- reason: 简短判断理由
- possible_title: 若为真句，填作品名（不带书名号）；否则空字符串
- possible_author: 若为真句，填作者姓名；否则空字符串

句子："{line}"
"""


def validate_user_line(line: str, char: str) -> dict:
    stripped = (line or "").strip()
    if not stripped:
        return {"is_valid": False, "reason": "句子为空"}
    if char not in stripped:
        return {"is_valid": False, "reason": f"句子不含指定字「{char}」"}
    if len(stripped) < MIN_LINE_CHARS:
        return {"is_valid": False, "reason": "句子过短"}

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.id, p.title, COALESCE(a.name, '佚名')
            FROM poems p LEFT JOIN authors a ON a.id = p.author_id
            WHERE p.content ILIKE %s
            LIMIT 1
            """,
            (f"%{stripped}%",),
        )
        row = cur.fetchone()

    if row:
        return {
            "is_valid": True,
            "reason": f"库内匹配：《{row[1]}》({row[2]})",
            "matched_poem_id": row[0],
            "llm_title": None,
            "llm_author": None,
            "source": "db",
        }

    if not settings.dashscope_api_key:
        return {
            "is_valid": False,
            "reason": "未配置 LLM 服务，无法校验库外诗句",
            "source": "llm_unavailable",
        }

    client = OpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )
    try:
        resp = client.chat.completions.create(
            model=settings.dashscope_chat_model,
            messages=[{"role": "user", "content": _VALIDATE_PROMPT.format(line=stripped)}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        logger.warning("validate_user_line JSON decode failed: %s", exc)
        return {"is_valid": False, "reason": "LLM 返回不是有效 JSON", "source": "llm_error"}
    except Exception as exc:
        logger.warning("validate_user_line LLM failed: %s", exc)
        return {"is_valid": False, "reason": f"LLM 调用失败: {exc}", "source": "llm_error"}

    is_valid = bool(data.get("is_valid"))
    reason = data.get("reason") or ("LLM 判定为真" if is_valid else "LLM 判定非原句")
    llm_title = (data.get("possible_title") or "").strip() or None
    llm_author = (data.get("possible_author") or "").strip() or None
    return {
        "is_valid": is_valid,
        "reason": reason,
        "matched_poem_id": None,
        "llm_title": llm_title if is_valid else None,
        "llm_author": llm_author if is_valid else None,
        "source": "llm",
    }


def fallback_pick_line(
    target_char: str,
    used_lines: list[str],
    difficulty: str = "medium",
) -> dict | None:
    """Agent 彻底失败时的降级：直接 SQL 查含目标字的诗句，随机挑一条。
    不经 LLM，保证 < 200ms 返回。无候选时返回 None。"""
    try:
        candidates = search_poems_by_char(
            char=target_char,
            difficulty=difficulty,
            exclude_lines=used_lines,
            limit=50,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("fallback_pick_line search failed: %s", exc)
        return None
    if not candidates:
        return None
    pick = random.choice(candidates)
    return {
        "line": pick["line"],
        "poem_id": pick["poem_id"],
        "title": pick["title"],
        "author": pick["author"],
    }


def get_session_state(session_id: int) -> dict | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, target_char, difficulty, status, started_at, ended_at, winner_reason
            FROM feihualing_sessions WHERE id = %s
            """,
            (session_id,),
        )
        session_row = cur.fetchone()
        if not session_row:
            return None

        cur.execute(
            """
            SELECT turn_index, speaker, line, poem_id, is_valid, reject_reason, latency_ms,
                   llm_source_title, llm_source_author, created_at
            FROM feihualing_turns
            WHERE session_id = %s
            ORDER BY turn_index
            """,
            (session_id,),
        )
        turns = [
            {
                "turn_index": r[0],
                "speaker": r[1],
                "line": r[2],
                "poem_id": r[3],
                "is_valid": r[4],
                "reject_reason": r[5],
                "latency_ms": r[6],
                "llm_title": r[7],
                "llm_author": r[8],
                "created_at": r[9].isoformat() if r[9] else None,
            }
            for r in cur.fetchall()
        ]

    used_lines = [t["line"] for t in turns if t["is_valid"]]
    used_poem_ids = [t["poem_id"] for t in turns if t["poem_id"]]

    return {
        "session_id": session_row[0],
        "target_char": session_row[1],
        "difficulty": session_row[2],
        "status": session_row[3],
        "started_at": session_row[4].isoformat() if session_row[4] else None,
        "ended_at": session_row[5].isoformat() if session_row[5] else None,
        "winner_reason": session_row[6],
        "turns": turns,
        "used_lines": used_lines,
        "used_poem_ids": used_poem_ids,
    }
