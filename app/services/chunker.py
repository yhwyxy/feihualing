from __future__ import annotations

from markdown_it import MarkdownIt


DEFAULT_CHUNK_SIZE = 400
MAX_ATOMIC_SIZE = 1500

ATOMIC_OPEN_TYPES = {"blockquote_open", "table_open"}
ATOMIC_LEAF_TYPES = {"fence", "code_block"}
HEADING_OPEN = "heading_open"


def _soft_split(text: str, max_size: int) -> list[str]:
    """只在原子块或单段超过 max_size 时使用，尽量按换行或句号切。"""
    text = text.strip()
    if len(text) <= max_size:
        return [text] if text else []

    parts: list[str] = []
    remaining = text
    while len(remaining) > max_size:
        window = remaining[:max_size]
        cut = max(window.rfind("\n"), window.rfind("。"), window.rfind("."))
        if cut < max_size // 2:
            cut = max_size
        parts.append(remaining[:cut].strip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        parts.append(remaining)
    return [p for p in parts if p]


def _render_breadcrumb(heading_stack: list[tuple[int, str]]) -> str:
    if not heading_stack:
        return ""
    return " > ".join(f"《{title}》" for _, title in heading_stack)


def _extract_blocks(text: str) -> list[dict]:
    """把 markdown 解析成顶层块列表：heading / atomic / block。"""
    md = MarkdownIt("commonmark").enable("table")
    tokens = md.parse(text)
    lines = text.split("\n")

    blocks: list[dict] = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if tok.level != 0:
            i += 1
            continue

        if tok.type == HEADING_OPEN:
            inline = tokens[i + 1]
            level = int(tok.tag[1])
            title = (inline.content or "").strip()
            blocks.append({"kind": "heading", "level": level, "text": title})
            i += 3
            continue

        if tok.type in ATOMIC_LEAF_TYPES:
            raw = (tok.content or "").strip()
            if raw:
                blocks.append({"kind": "atomic", "text": raw})
            i += 1
            continue

        if tok.type in ATOMIC_OPEN_TYPES:
            start, end = tok.map or (0, 0)
            raw = "\n".join(lines[start:end]).strip()
            if raw:
                blocks.append({"kind": "atomic", "text": raw})
            close_type = tok.type.replace("_open", "_close")
            j = i + 1
            while j < n and not (tokens[j].type == close_type and tokens[j].level == 0):
                j += 1
            i = j + 1
            continue

        if tok.type.endswith("_open") and tok.map:
            start, end = tok.map
            raw = "\n".join(lines[start:end]).strip()
            if raw:
                blocks.append({"kind": "block", "text": raw})
            close_type = tok.type.replace("_open", "_close")
            j = i + 1
            while j < n and not (tokens[j].type == close_type and tokens[j].level == 0):
                j += 1
            i = j + 1
            continue

        if tok.map:
            start, end = tok.map
            raw = "\n".join(lines[start:end]).strip()
            if raw:
                blocks.append({"kind": "block", "text": raw})
        i += 1

    return blocks


def split_markdown(
    text: str,
    max_chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_atomic_size: int = MAX_ATOMIC_SIZE,
) -> list[str]:
    text = (text or "").replace("\r\n", "\n").strip()
    if not text:
        return []

    blocks = _extract_blocks(text)
    if not blocks:
        return []

    chunks: list[str] = []
    heading_stack: list[tuple[int, str]] = []
    buffer_parts: list[str] = []
    buffer_len = 0
    buffer_breadcrumb = ""

    def emit(body: str, breadcrumb: str) -> None:
        body = body.strip()
        if not body:
            return
        chunks.append(f"{breadcrumb}\n\n{body}" if breadcrumb else body)

    def flush() -> None:
        nonlocal buffer_parts, buffer_len, buffer_breadcrumb
        if not buffer_parts:
            return
        emit("\n\n".join(buffer_parts), buffer_breadcrumb)
        buffer_parts = []
        buffer_len = 0
        buffer_breadcrumb = ""

    for blk in blocks:
        kind = blk["kind"]

        if kind == "heading":
            flush()
            level = blk["level"]
            heading_stack = [h for h in heading_stack if h[0] < level]
            if blk["text"]:
                heading_stack.append((level, blk["text"]))
            continue

        if kind == "atomic":
            flush()
            breadcrumb = _render_breadcrumb(heading_stack)
            for part in _soft_split(blk["text"], max_atomic_size):
                emit(part, breadcrumb)
            continue

        t = blk["text"]
        if len(t) > max_chunk_size:
            flush()
            breadcrumb = _render_breadcrumb(heading_stack)
            for part in _soft_split(t, max_chunk_size):
                emit(part, breadcrumb)
            continue

        if not buffer_parts:
            buffer_breadcrumb = _render_breadcrumb(heading_stack)

        projected = buffer_len + len(t) + (2 if buffer_parts else 0)
        if projected <= max_chunk_size:
            buffer_parts.append(t)
            buffer_len = projected
        else:
            flush()
            buffer_breadcrumb = _render_breadcrumb(heading_stack)
            buffer_parts.append(t)
            buffer_len = len(t)

    flush()
    return chunks