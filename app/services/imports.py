from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.db.connection import get_connection
from app.schemas.imports import (
    BatchImportRequest,
    BatchImportResponse,
    BatchImportSummary,
    BatchImportWarning,
    ImportAuthorInput,
    ImportCollectionInput,
)


@dataclass
class BatchImportOutcome:
    response: BatchImportResponse
    created_author_ids: list[int]
    created_collection_ids: list[int]
    created_poem_ids: list[int]


def normalize_key(value: str) -> str:
    return " ".join(value.strip().split())


def add_warning(warnings: list[BatchImportWarning], code: str, path: str, message: str):
    warnings.append(BatchImportWarning(code=code, path=path, message=message))


def add_author_input(
    author_inputs: dict[str, tuple[ImportAuthorInput, str]],
    summary: BatchImportSummary,
    warnings: list[BatchImportWarning],
    author: ImportAuthorInput,
    path: str,
    count_duplicate: bool,
):
    key = normalize_key(author.name)
    if key in author_inputs:
        if count_duplicate:
            summary.authors.skipped += 1
            add_warning(warnings, "duplicate_author_in_payload", path, f"作者“{author.name}”重复，已跳过后续项。")
        return

    author_inputs[key] = (author, path)


def add_collection_input(
    collection_inputs: dict[str, tuple[ImportCollectionInput, str]],
    summary: BatchImportSummary,
    warnings: list[BatchImportWarning],
    collection: ImportCollectionInput,
    path: str,
    count_duplicate: bool,
):
    key = normalize_key(collection.name)
    if key in collection_inputs:
        if count_duplicate:
            summary.collections.skipped += 1
            add_warning(warnings, "duplicate_collection_in_payload", path, f"合集“{collection.name}”重复，已跳过后续项。")
        return

    collection_inputs[key] = (collection, path)


def find_author_id(cur, name: str) -> tuple[int | None, int]:
    cur.execute(
        "SELECT id FROM authors WHERE btrim(name) = %s ORDER BY id ASC",
        (name,),
    )
    rows = cur.fetchall()
    if not rows:
        return None, 0
    return rows[0][0], len(rows)


def find_collection_id(cur, name: str) -> tuple[int | None, int]:
    cur.execute(
        "SELECT id FROM collections WHERE btrim(name) = %s ORDER BY id ASC",
        (name,),
    )
    rows = cur.fetchall()
    if not rows:
        return None, 0
    return rows[0][0], len(rows)


def find_poem(cur, title: str, author_id: int) -> tuple[tuple[int, str] | None, int]:
    cur.execute(
        "SELECT id, content FROM poems WHERE btrim(title) = %s AND author_id = %s ORDER BY id ASC",
        (title, author_id),
    )
    rows = cur.fetchall()
    if not rows:
        return None, 0
    return rows[0], len(rows)


def build_import_inputs(payload: BatchImportRequest, summary: BatchImportSummary, warnings: list[BatchImportWarning]):
    author_inputs: dict[str, tuple[ImportAuthorInput, str]] = {}
    collection_inputs: dict[str, tuple[ImportCollectionInput, str]] = {}
    poem_inputs = {}

    for index, author in enumerate(payload.authors):
        add_author_input(author_inputs, summary, warnings, author, f"authors[{index}]", True)

    for index, collection in enumerate(payload.collections):
        add_collection_input(collection_inputs, summary, warnings, collection, f"collections[{index}]", True)
        for poem_index, poem in enumerate(collection.poems):
            add_author_input(
                author_inputs,
                summary,
                warnings,
                ImportAuthorInput(name=poem.author),
                f"collections[{index}].poems[{poem_index}].author",
                False,
            )

    for index, poem in enumerate(payload.poems):
        author_key = normalize_key(poem.author)
        add_author_input(author_inputs, summary, warnings, ImportAuthorInput(name=poem.author), f"poems[{index}].author", False)

        poem_key = (normalize_key(poem.title), author_key)
        if poem_key in poem_inputs:
            summary.poems.skipped += 1
            add_warning(warnings, "duplicate_poem_in_payload", f"poems[{index}]", f"诗词“{poem.title} / {poem.author}”重复，已跳过后续项。")
        else:
            poem_inputs[poem_key] = (poem, f"poems[{index}]")

        for collection_index, collection_name in enumerate(poem.collections):
            add_collection_input(
                collection_inputs,
                summary,
                warnings,
                ImportCollectionInput(name=collection_name),
                f"poems[{index}].collections[{collection_index}]",
                False,
            )

    return author_inputs, collection_inputs, poem_inputs


def iter_collection_links(payload: BatchImportRequest) -> Iterable[tuple[str, str, str, str]]:
    for poem_index, poem in enumerate(payload.poems):
        for collection_index, collection_name in enumerate(poem.collections):
            yield (
                normalize_key(collection_name),
                normalize_key(poem.title),
                normalize_key(poem.author),
                f"poems[{poem_index}].collections[{collection_index}]",
            )

    for collection_index, collection in enumerate(payload.collections):
        for poem_index, poem in enumerate(collection.poems):
            yield (
                normalize_key(collection.name),
                normalize_key(poem.title),
                normalize_key(poem.author),
                f"collections[{collection_index}].poems[{poem_index}]",
            )


def import_batch_payload(payload: BatchImportRequest) -> BatchImportOutcome:
    summary = BatchImportSummary()
    warnings: list[BatchImportWarning] = []
    author_inputs, collection_inputs, poem_inputs = build_import_inputs(payload, summary, warnings)

    author_ids: dict[str, int] = {}
    collection_ids: dict[str, int] = {}
    poem_ids: dict[tuple[str, str], int] = {}
    created_author_ids: list[int] = []
    created_collection_ids: list[int] = []
    created_poem_ids: list[int] = []

    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                for author_key, (author, path) in author_inputs.items():
                    author_id, match_count = find_author_id(cur, author.name)
                    if author_id is not None:
                        author_ids[author_key] = author_id
                        summary.authors.matched += 1
                        if match_count > 1:
                            add_warning(warnings, "ambiguous_author_match", path, f"存在多个同名作者“{author.name}”，已使用 ID 最小的记录。")
                        continue

                    cur.execute(
                        "INSERT INTO authors (name, bio) VALUES (%s, %s) RETURNING id",
                        (author.name, author.bio),
                    )
                    new_id = cur.fetchone()[0]
                    author_ids[author_key] = new_id
                    created_author_ids.append(new_id)
                    summary.authors.created += 1

                for collection_key, (collection, path) in collection_inputs.items():
                    collection_id, match_count = find_collection_id(cur, collection.name)
                    if collection_id is not None:
                        collection_ids[collection_key] = collection_id
                        summary.collections.matched += 1
                        if match_count > 1:
                            add_warning(warnings, "ambiguous_collection_match", path, f"存在多个同名合集“{collection.name}”，已使用 ID 最小的记录。")
                        continue

                    cur.execute(
                        "INSERT INTO collections (name, description) VALUES (%s, %s) RETURNING id",
                        (collection.name, collection.description),
                    )
                    new_id = cur.fetchone()[0]
                    collection_ids[collection_key] = new_id
                    created_collection_ids.append(new_id)
                    summary.collections.created += 1

                for poem_key, (poem, path) in poem_inputs.items():
                    author_id = author_ids[poem_key[1]]
                    poem_row, match_count = find_poem(cur, poem.title, author_id)
                    if poem_row is not None:
                        poem_ids[poem_key] = poem_row[0]
                        summary.poems.matched += 1
                        if match_count > 1:
                            add_warning(warnings, "ambiguous_poem_match", path, f"存在多首同标题同作者诗词“{poem.title} / {poem.author}”，已使用 ID 最小的记录。")
                        if poem_row[1].strip() != poem.content.strip():
                            add_warning(warnings, "poem_content_differs", path, f"诗词“{poem.title} / {poem.author}”已存在，导入内容与现有内容不同，未覆盖。")
                        continue

                    cur.execute(
                        "INSERT INTO poems (title, author_id, content) VALUES (%s, %s, %s) RETURNING id",
                        (poem.title, author_id, poem.content),
                    )
                    new_id = cur.fetchone()[0]
                    poem_ids[poem_key] = new_id
                    created_poem_ids.append(new_id)
                    summary.poems.created += 1

                seen_links: set[tuple[str, str, str]] = set()
                for collection_key, title_key, author_key, path in iter_collection_links(payload):
                    link_key = (collection_key, title_key, author_key)
                    if link_key in seen_links:
                        summary.collection_poems.skipped += 1
                        add_warning(warnings, "duplicate_collection_poem_in_payload", path, "收录关系重复，已跳过后续项。")
                        continue
                    seen_links.add(link_key)

                    collection_id = collection_ids[collection_key]
                    poem_id = poem_ids.get((title_key, author_key))
                    if poem_id is None:
                        author_id = author_ids[author_key]
                        poem_row, match_count = find_poem(cur, title_key, author_id)
                        if poem_row is None:
                            summary.collection_poems.skipped += 1
                            add_warning(warnings, "poem_reference_not_found", path, f"找不到诗词“{title_key} / {author_key}”，收录关系已跳过。")
                            continue

                        poem_id = poem_row[0]
                        poem_ids[(title_key, author_key)] = poem_id
                        if match_count > 1:
                            add_warning(warnings, "ambiguous_poem_match", path, f"存在多首同标题同作者诗词“{title_key} / {author_key}”，已使用 ID 最小的记录。")

                    cur.execute(
                        """
                        INSERT INTO collection_poems (collection_id, poem_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                        RETURNING collection_id
                        """,
                        (collection_id, poem_id),
                    )
                    if cur.fetchone() is None:
                        summary.collection_poems.matched += 1
                    else:
                        summary.collection_poems.created += 1
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return BatchImportOutcome(
        response=BatchImportResponse(summary=summary, warnings=warnings),
        created_author_ids=created_author_ids,
        created_collection_ids=created_collection_ids,
        created_poem_ids=created_poem_ids,
    )
