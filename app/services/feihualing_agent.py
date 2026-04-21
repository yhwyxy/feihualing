from __future__ import annotations

import json
import logging
from typing import Any, Iterator

from openai import OpenAI

from app.core.config import settings
from app.services.feihualing_tools import search_poems_by_char


logger = logging.getLogger(__name__)


AGENT_SYSTEM_PROMPT = """你是飞花令游戏的 AI 对手。

规则：
1. 你要出一句**包含指定字**的古诗词原句。
2. 必须通过 search_poems_by_char 工具获取候选诗句，然后从中挑一句。
3. 不得编造工具未返回的句子，不得改写原文。
4. 避开「已用诗句」列表里的所有句子（字面完全一致视为重复）。同一首诗的不同句子可以继续使用。
5. 调用工具时，将已用诗句列表通过 exclude_lines 参数传入。
6. 难度策略：easy=选最常见的；medium=任选一句；hard=选较偏门的一句。

输出格式（仅返回 JSON，不要任何额外文字）：
- 正常出句：{"line": "诗句原文", "poem_id": 整数, "title": "作品名", "author": "作者"}
- 工具返回空或所有候选都已用过：{"line": null, "reason": "认输原因"}
"""


TOOL_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "search_poems_by_char",
            "description": "从诗词数据库中搜索包含指定字的候选诗句，返回 [{poem_id, title, author, line}]",
            "parameters": {
                "type": "object",
                "properties": {
                    "char": {
                        "type": "string",
                        "description": "目标字（单字）",
                    },
                    "difficulty": {
                        "type": "string",
                        "enum": ["easy", "medium", "hard"],
                        "description": "难度，影响候选排序",
                    },
                    "exclude_lines": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要排除的已用诗句字面列表（按字面完全一致匹配）",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回候选数量上限，默认 10",
                    },
                },
                "required": ["char", "difficulty"],
            },
        },
    }
]


def _build_user_prompt(target_char: str, difficulty: str,
                       used_lines: list[str]) -> str:
    lines_str = "\n".join(f"- {line}" for line in used_lines) if used_lines else "（无）"
    return (
        f"目标字：{target_char}\n"
        f"难度：{difficulty}\n"
        f"已用诗句：\n{lines_str}\n\n"
        f"请调用 search_poems_by_char 工具搜索候选（记得把已用诗句通过 exclude_lines 传进去），"
        f"然后从返回的候选里挑一句作为你的回答。"
    )


def _execute_tool(name: str, arguments: dict) -> Any:
    if name == "search_poems_by_char":
        return search_poems_by_char(
            char=arguments["char"],
            difficulty=arguments.get("difficulty", "medium"),
            exclude_poem_ids=[],
            exclude_lines=arguments.get("exclude_lines") or [],
            limit=arguments.get("limit", 10),
        )
    return {"error": f"unknown tool: {name}"}


def agent_pick_line(
    target_char: str,
    difficulty: str,
    used_lines: list[str],
    used_poem_ids: list[int],
    max_iters: int = 4,
) -> dict:
    if not settings.dashscope_api_key:
        raise RuntimeError("未配置 DashScope API Key")

    client = OpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )
    messages: list[dict] = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(
            target_char, difficulty, used_lines,
        )},
    ]

    for _ in range(max_iters):
        resp = client.chat.completions.create(
            model=settings.dashscope_chat_model,
            messages=messages,
            tools=TOOL_SPEC,
            tool_choice="auto",
            temperature=0.3,
        )
        msg = resp.choices[0].message

        if msg.tool_calls:
            assistant_msg: dict = {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
            messages.append(assistant_msg)

            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                try:
                    result = _execute_tool(tc.function.name, args)
                except Exception as exc:  # noqa: BLE001
                    result = {"error": str(exc)}
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })
            continue

        content = (msg.content or "").strip()
        if not content:
            raise RuntimeError("Agent 返回为空")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            cleaned = content.strip("`").lstrip("json").strip()
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Agent 返回非 JSON: {content[:200]}") from exc

        return parsed

    raise RuntimeError(f"Agent 超过 {max_iters} 轮仍未给出答案")


def agent_pick_line_stream(
    target_char: str,
    difficulty: str,
    used_lines: list[str],
    max_iters: int = 4,
) -> Iterator[dict]:
    """Yield step events: agent_thinking / agent_tool_call / agent_tool_result /
    agent_final / agent_error. Caller forwards all events as SSE and captures
    agent_final.data as the final answer."""
    if not settings.dashscope_api_key:
        yield {"type": "agent_error", "message": "未配置 DashScope API Key"}
        return

    client = OpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )
    messages: list[dict] = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(
            target_char, difficulty, used_lines,
        )},
    ]

    yield {"type": "agent_thinking"}

    for _ in range(max_iters):
        try:
            resp = client.chat.completions.create(
                model=settings.dashscope_chat_model,
                messages=messages,
                tools=TOOL_SPEC,
                tool_choice="auto",
                temperature=0.3,
            )
        except Exception as exc:  # noqa: BLE001
            yield {"type": "agent_error", "message": f"LLM 调用失败: {exc}"}
            return

        msg = resp.choices[0].message

        if msg.tool_calls:
            assistant_msg: dict = {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
            messages.append(assistant_msg)

            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                yield {
                    "type": "agent_tool_call",
                    "name": tc.function.name,
                    "args": args,
                }

                try:
                    result = _execute_tool(tc.function.name, args)
                except Exception as exc:  # noqa: BLE001
                    result = {"error": str(exc)}

                result_count = len(result) if isinstance(result, list) else 0
                sample_lines = (
                    [r.get("line") for r in result[:3]]
                    if isinstance(result, list)
                    else []
                )
                yield {
                    "type": "agent_tool_result",
                    "count": result_count,
                    "sample_lines": sample_lines,
                }

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })
            continue

        content = (msg.content or "").strip()
        if not content:
            yield {"type": "agent_error", "message": "Agent 返回为空"}
            return

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            cleaned = content.strip("`").lstrip("json").strip()
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError:
                yield {"type": "agent_error", "message": f"Agent 返回非 JSON: {content[:200]}"}
                return

        yield {"type": "agent_final", "data": parsed}
        return

    yield {"type": "agent_error", "message": f"超过 {max_iters} 轮迭代"}
