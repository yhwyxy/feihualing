from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Iterator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.db.connection import get_connection
from app.schemas.feihualing import (
    SessionListResponse,
    SessionRead,
    SessionSummary,
    StartSessionRequest,
    TurnRead,
    TurnRequest,
)
from app.schemas.poem import MessageResponse
from app.services.feihualing_agent import agent_pick_line_stream
from app.services.feihualing_tools import (
    get_session_state,
    validate_user_line,
)


router = APIRouter(prefix="/agent/feihualing", tags=["feihualing"])


def _sse(event: dict) -> bytes:
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n".encode("utf-8")


def _ensure_poem_title(poem_id: int | None) -> tuple[str | None, str | None]:
    if not poem_id:
        return None, None
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.title, COALESCE(a.name, '佚名')
            FROM poems p LEFT JOIN authors a ON a.id = p.author_id
            WHERE p.id = %s
            """,
            (poem_id,),
        )
        row = cur.fetchone()
    return (row[0], row[1]) if row else (None, None)


def _insert_turn(session_id: int, turn_index: int, speaker: str, line: str,
                 poem_id: int | None, is_valid: bool,
                 reject_reason: str | None, latency_ms: int | None,
                 llm_title: str | None = None,
                 llm_author: str | None = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO feihualing_turns
                  (session_id, turn_index, speaker, line, poem_id, is_valid,
                   reject_reason, latency_ms, llm_source_title, llm_source_author)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (session_id, turn_index, speaker, line, poem_id,
                 is_valid, reject_reason, latency_ms, llm_title, llm_author),
            )
        conn.commit()


def _end_session(session_id: int, status: str, reason: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE feihualing_sessions
                SET status = %s, winner_reason = %s, ended_at = %s
                WHERE id = %s
                """,
                (status, reason, datetime.now(timezone.utc), session_id),
            )
        conn.commit()


def _to_turn_read(turn: dict) -> TurnRead:
    title, author = _ensure_poem_title(turn.get("poem_id"))
    return TurnRead(
        turn_index=turn["turn_index"],
        speaker=turn["speaker"],
        line=turn["line"],
        poem_id=turn.get("poem_id"),
        title=title,
        author=author,
        is_valid=turn["is_valid"],
        reject_reason=turn.get("reject_reason"),
        latency_ms=turn.get("latency_ms"),
        llm_title=turn.get("llm_title"),
        llm_author=turn.get("llm_author"),
    )


def _session_read(session_id: int) -> SessionRead:
    state = get_session_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionRead(
        session_id=state["session_id"],
        target_char=state["target_char"],
        difficulty=state["difficulty"],
        status=state["status"],
        winner_reason=state["winner_reason"],
        started_at=datetime.fromisoformat(state["started_at"]),
        ended_at=datetime.fromisoformat(state["ended_at"]) if state["ended_at"] else None,
        turns=[_to_turn_read(t) for t in state["turns"]],
    )


def _stream_start(char: str, difficulty: str) -> Iterator[bytes]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO feihualing_sessions (target_char, difficulty)
                VALUES (%s, %s)
                RETURNING id
                """,
                (char, difficulty),
            )
            session_id = cur.fetchone()[0]
        conn.commit()

    yield _sse({
        "type": "session_created",
        "session_id": session_id,
        "target_char": char,
        "difficulty": difficulty,
    })

    started = time.perf_counter()
    final: dict | None = None
    for event in agent_pick_line_stream(char, difficulty, used_lines=[]):
        if event.get("type") == "agent_final":
            final = event.get("data")
            continue
        if event.get("type") == "agent_error":
            _end_session(session_id, "abandoned", event.get("message", "Agent 失败"))
            yield _sse(event)
            yield _sse({
                "type": "done",
                "session_id": session_id,
                "status": "abandoned",
                "winner_reason": event.get("message"),
            })
            return
        yield _sse(event)

    latency_ms = int((time.perf_counter() - started) * 1000)

    if not final or not final.get("line"):
        reason = (final or {}).get("reason") or "Agent 开局认输"
        _end_session(session_id, "user_won", reason)
        yield _sse({"type": "agent_surrender", "reason": reason})
        yield _sse({
            "type": "done",
            "session_id": session_id,
            "status": "user_won",
            "winner_reason": reason,
        })
        return

    _insert_turn(
        session_id=session_id,
        turn_index=0,
        speaker="agent",
        line=final["line"],
        poem_id=final.get("poem_id"),
        is_valid=True,
        reject_reason=None,
        latency_ms=latency_ms,
    )
    turn = _to_turn_read({
        "turn_index": 0,
        "speaker": "agent",
        "line": final["line"],
        "poem_id": final.get("poem_id"),
        "is_valid": True,
        "latency_ms": latency_ms,
    })
    yield _sse({"type": "agent_result", "turn": turn.model_dump(mode="json")})
    yield _sse({
        "type": "done",
        "session_id": session_id,
        "status": "in_progress",
        "winner_reason": None,
    })


def _stream_turn(session_id: int, line: str) -> Iterator[bytes]:
    state = get_session_state(session_id)
    if state is None:
        yield _sse({"type": "error", "message": "Session not found"})
        yield _sse({"type": "done", "session_id": session_id,
                    "status": "abandoned", "winner_reason": "Session not found"})
        return
    if state["status"] != "in_progress":
        yield _sse({"type": "error", "message": f"对局已结束：{state['status']}"})
        yield _sse({
            "type": "done",
            "session_id": session_id,
            "status": state["status"],
            "winner_reason": state["winner_reason"],
        })
        return

    target_char = state["target_char"]
    difficulty = state["difficulty"]
    used_lines = list(state["used_lines"])
    next_turn_index = (state["turns"][-1]["turn_index"] + 1) if state["turns"] else 0

    user_line = line.strip()

    if user_line in used_lines:
        reject_reason = "诗句与先前重复"
        _insert_turn(session_id, next_turn_index, "user", user_line,
                     None, False, reject_reason, None)
        _end_session(session_id, "agent_won", reject_reason)
        user_turn = _to_turn_read({
            "turn_index": next_turn_index, "speaker": "user",
            "line": user_line, "poem_id": None, "is_valid": False,
            "reject_reason": reject_reason,
        })
        yield _sse({"type": "user_result", "turn": user_turn.model_dump(mode="json")})
        yield _sse({
            "type": "done",
            "session_id": session_id,
            "status": "agent_won",
            "winner_reason": reject_reason,
        })
        return

    yield _sse({"type": "user_validating"})

    started = time.perf_counter()
    result = validate_user_line(user_line, target_char)
    latency_ms = int((time.perf_counter() - started) * 1000)

    if not result["is_valid"]:
        reason = result["reason"]
        _insert_turn(session_id, next_turn_index, "user", user_line,
                     None, False, reason, latency_ms)
        _end_session(session_id, "agent_won", reason)
        user_turn = _to_turn_read({
            "turn_index": next_turn_index, "speaker": "user",
            "line": user_line, "poem_id": None, "is_valid": False,
            "reject_reason": reason, "latency_ms": latency_ms,
        })
        yield _sse({"type": "user_result", "turn": user_turn.model_dump(mode="json")})
        yield _sse({
            "type": "done",
            "session_id": session_id,
            "status": "agent_won",
            "winner_reason": reason,
        })
        return

    matched_poem_id = result.get("matched_poem_id")
    llm_title = result.get("llm_title")
    llm_author = result.get("llm_author")
    _insert_turn(session_id, next_turn_index, "user", user_line,
                 matched_poem_id, True, None, latency_ms,
                 llm_title=llm_title, llm_author=llm_author)

    user_turn_read = _to_turn_read({
        "turn_index": next_turn_index, "speaker": "user",
        "line": user_line, "poem_id": matched_poem_id, "is_valid": True,
        "latency_ms": latency_ms,
        "llm_title": llm_title, "llm_author": llm_author,
    })
    yield _sse({"type": "user_result", "turn": user_turn_read.model_dump(mode="json")})

    used_lines.append(user_line)
    agent_turn_index = next_turn_index + 1

    started = time.perf_counter()
    final: dict | None = None
    for event in agent_pick_line_stream(target_char, difficulty, used_lines):
        if event.get("type") == "agent_final":
            final = event.get("data")
            continue
        if event.get("type") == "agent_error":
            _end_session(session_id, "user_won", event.get("message", "Agent 失败"))
            yield _sse(event)
            yield _sse({
                "type": "done",
                "session_id": session_id,
                "status": "user_won",
                "winner_reason": event.get("message"),
            })
            return
        yield _sse(event)

    agent_latency = int((time.perf_counter() - started) * 1000)

    if not final or not final.get("line"):
        reason = (final or {}).get("reason") or "Agent 找不到合适诗句，认输"
        _end_session(session_id, "user_won", reason)
        yield _sse({"type": "agent_surrender", "reason": reason})
        yield _sse({
            "type": "done",
            "session_id": session_id,
            "status": "user_won",
            "winner_reason": reason,
        })
        return

    agent_line = final["line"]
    if agent_line in used_lines:
        reason = f"Agent 选了重复句「{agent_line}」，自动认输"
        _end_session(session_id, "user_won", reason)
        yield _sse({"type": "agent_surrender", "reason": reason})
        yield _sse({
            "type": "done",
            "session_id": session_id,
            "status": "user_won",
            "winner_reason": reason,
        })
        return

    _insert_turn(
        session_id=session_id,
        turn_index=agent_turn_index,
        speaker="agent",
        line=agent_line,
        poem_id=final.get("poem_id"),
        is_valid=True,
        reject_reason=None,
        latency_ms=agent_latency,
    )
    agent_turn_read = _to_turn_read({
        "turn_index": agent_turn_index, "speaker": "agent",
        "line": agent_line, "poem_id": final.get("poem_id"),
        "is_valid": True, "latency_ms": agent_latency,
    })
    yield _sse({"type": "agent_result", "turn": agent_turn_read.model_dump(mode="json")})
    yield _sse({
        "type": "done",
        "session_id": session_id,
        "status": "in_progress",
        "winner_reason": None,
    })


@router.post("/start", summary="开始一局（SSE 流式）")
def start_session(payload: StartSessionRequest):
    char = payload.target_char.strip()
    if len(char) != 1:
        raise HTTPException(status_code=400, detail="target_char 必须是一个字")

    return StreamingResponse(
        _stream_start(char, payload.difficulty),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{session_id}/turn", summary="用户出句 + Agent 应答（SSE 流式）")
def play_turn(session_id: int, payload: TurnRequest):
    return StreamingResponse(
        _stream_turn(session_id, payload.line),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{session_id}/surrender", response_model=MessageResponse, summary="用户认输")
def surrender(session_id: int) -> MessageResponse:
    state = get_session_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if state["status"] != "in_progress":
        raise HTTPException(status_code=409, detail=f"对局已结束：{state['status']}")

    _end_session(session_id, "agent_won", "用户认输")
    return MessageResponse(message="已认输，对局结束")


@router.get("/{session_id}", response_model=SessionRead, summary="获取对局详情")
def get_session(session_id: int) -> SessionRead:
    return _session_read(session_id)


@router.get("", response_model=SessionListResponse, summary="获取最近对局列表")
def list_sessions(limit: int = Query(20, ge=1, le=100),
                  offset: int = Query(0, ge=0)) -> SessionListResponse:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM feihualing_sessions")
        total = cur.fetchone()[0]
        cur.execute(
            """
            SELECT s.id, s.target_char, s.difficulty, s.status, s.winner_reason,
                   s.started_at, s.ended_at,
                   (SELECT COUNT(*) FROM feihualing_turns t WHERE t.session_id = s.id) AS turn_count
            FROM feihualing_sessions s
            ORDER BY s.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        items = [
            SessionSummary(
                session_id=r[0],
                target_char=r[1],
                difficulty=r[2],
                status=r[3],
                winner_reason=r[4],
                started_at=r[5],
                ended_at=r[6],
                turn_count=r[7],
            )
            for r in cur.fetchall()
        ]
    return SessionListResponse(items=items, total=total)
