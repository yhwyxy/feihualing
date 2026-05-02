from __future__ import annotations

import json
import logging

from openai import OpenAI
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.imports import BatchImportRequest, BatchImportWarning
from app.services.chunker import split_markdown


logger = logging.getLogger(__name__)

MAX_EXTRACTION_CHARS = 30000
MAX_EXTRACTION_CHUNKS = 24


_EXTRACTION_PROMPT = """你是中文古典诗词资料整理助手。请从用户提供的文本中抽取明确出现的诗词/词/曲/赋作品。

只返回 JSON 对象，不要输出 Markdown，不要解释。

JSON 格式：
{
  "authors": [
    {"name": "作者名", "bio": null}
  ],
  "poems": [
    {
      "title": "诗词标题",
      "author": "作者名",
      "content": "完整诗词正文，保留换行",
      "collections": ["来源合集或文档标题"]
    }
  ],
  "collections": [
    {
      "name": "合集名",
      "description": null,
      "poems": [{"title": "诗词标题", "author": "作者名"}]
    }
  ]
}

规则：
1. 只抽取文本中明确给出的作品，不要凭记忆补全，不要改写。
2. 词也算诗词作品，按整阕保存；上下阕合并为同一个 content。
3. 没有明确标题时可用文本中出现的首句作为标题。
4. 没有明确作者时使用“佚名”。
5. content 只包含正文，不要包含赏析、注释、译文、页码、目录、提要。
6. collections 至少包含当前文档标题。
7. 最多返回 {max_poems} 首。
8. 如果无法可靠抽取，返回空数组。

文档标题：{title}
源文件：{source_filename}

文本：
{text}
"""


def _build_extraction_text(content: str) -> tuple[str, bool]:
    chunks = split_markdown(content)
    selected = chunks[:MAX_EXTRACTION_CHUNKS]
    text = "\n\n---\n\n".join(selected) if selected else content.strip()
    truncated = len(text) > MAX_EXTRACTION_CHARS or len(chunks) > len(selected)
    if len(text) > MAX_EXTRACTION_CHARS:
        text = text[:MAX_EXTRACTION_CHARS]
    return text, truncated


def extract_poems_from_text(
    title: str,
    content: str,
    source_filename: str | None,
    max_poems: int = 80,
) -> tuple[BatchImportRequest, list[BatchImportWarning]]:
    warnings: list[BatchImportWarning] = []
    text, truncated = _build_extraction_text(content)
    if truncated:
        warnings.append(BatchImportWarning(
            code="extraction_truncated",
            path="content",
            message="文档较长，本次仅抽取前部内容；完整逐段抽取将在后续版本支持。",
        ))

    client = OpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )
    try:
        resp = client.chat.completions.create(
            model=settings.dashscope_chat_model,
            messages=[{
                "role": "user",
                "content": _EXTRACTION_PROMPT.format(
                    title=title,
                    source_filename=source_filename or "无",
                    max_poems=max_poems,
                    text=text,
                ),
            }],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("poem extraction JSON decode failed: %s", exc)
        warnings.append(BatchImportWarning(
            code="extraction_json_invalid",
            path="llm_response",
            message="LLM 抽取结果不是有效 JSON，已跳过诗词入库。",
        ))
        return BatchImportRequest(), warnings
    except Exception as exc:  # noqa: BLE001
        logger.warning("poem extraction failed: %s", exc)
        warnings.append(BatchImportWarning(
            code="extraction_failed",
            path="llm_request",
            message=f"LLM 抽取失败：{exc}",
        ))
        return BatchImportRequest(), warnings

    try:
        payload = BatchImportRequest.model_validate(data)
    except ValidationError as exc:
        logger.warning("poem extraction schema invalid: %s", exc)
        warnings.append(BatchImportWarning(
            code="extraction_schema_invalid",
            path="llm_response",
            message="LLM 抽取 JSON 不符合导入格式，已跳过诗词入库。",
        ))
        return BatchImportRequest(), warnings

    if len(payload.poems) > max_poems:
        payload = BatchImportRequest(
            authors=payload.authors,
            poems=payload.poems[:max_poems],
            collections=payload.collections,
        )
        warnings.append(BatchImportWarning(
            code="extraction_poems_limited",
            path="poems",
            message=f"LLM 返回诗词超过 {max_poems} 首，已截断。",
        ))

    return payload, warnings
