from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Difficulty = Literal["easy", "medium", "hard", "expert"]
SessionStatus = Literal["in_progress", "user_won", "agent_won", "abandoned"]
Speaker = Literal["user", "agent"]


class StartSessionRequest(BaseModel):
    target_char: str = Field(..., min_length=1, max_length=1)
    difficulty: Difficulty = "medium"


class TurnRequest(BaseModel):
    line: str = Field(..., min_length=1, max_length=80)


class TurnRead(BaseModel):
    turn_index: int
    speaker: Speaker
    line: str
    poem_id: int | None = None
    title: str | None = None
    author: str | None = None
    is_valid: bool = True
    reject_reason: str | None = None
    latency_ms: int | None = None
    llm_title: str | None = None
    llm_author: str | None = None


class SessionRead(BaseModel):
    session_id: int
    target_char: str
    difficulty: Difficulty
    status: SessionStatus
    winner_reason: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    turns: list[TurnRead] = []


class SessionSummary(BaseModel):
    session_id: int
    target_char: str
    difficulty: Difficulty
    status: SessionStatus
    winner_reason: str | None = None
    turn_count: int
    started_at: datetime
    ended_at: datetime | None = None


class SessionListResponse(BaseModel):
    items: list[SessionSummary]
    total: int


class PlayResponse(BaseModel):
    status: SessionStatus
    winner_reason: str | None = None
    user_turn: TurnRead | None = None
    agent_turn: TurnRead | None = None
