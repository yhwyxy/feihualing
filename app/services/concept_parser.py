from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from app.db.connection import get_connection
from app.services.feihualing_tools import split_poem_lines


EXACT_CONFIDENCE = Decimal("1.0000")
ALIAS_CONFIDENCE = Decimal("0.9500")
PARSER_SOURCE = "parser"
DEFAULT_STOPWORDS: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ConceptTerm:
    concept_id: int
    concept_name: str
    concept_type: str
    term: str
    normalized_term: str
    is_alias: bool = False


@dataclass(frozen=True)
class LineConceptMatch:
    poem_id: int
    concept_id: int
    line_index: int
    line_text: str
    matched_text: str
    start_offset: int
    confidence: Decimal
    source: str = PARSER_SOURCE


@dataclass(frozen=True)
class PoemConceptAggregate:
    poem_id: int
    concept_id: int
    confidence: Decimal
    matched_count: int
    matched_texts: list[str]


@dataclass(frozen=True)
class ParseResult:
    poem_id: int
    line_match_count: int
    concept_count: int
    conflicts: list[dict[str, object]]


def normalize_term(value: str) -> str:
    return "".join((value or "").strip().split()).casefold()


def load_active_concept_terms() -> list[ConceptTerm]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, type, name, normalized_name, false
            FROM concepts
            WHERE is_active = true
            UNION ALL
            SELECT c.id, c.name, c.type, a.alias, a.normalized_alias, true
            FROM concept_aliases a
            JOIN concepts c ON c.id = a.concept_id
            WHERE c.is_active = true
            """
        )
        rows = cur.fetchall()

    terms = [
        ConceptTerm(
            concept_id=row[0],
            concept_name=row[1],
            concept_type=row[2],
            term=row[3],
            normalized_term=row[4],
            is_alias=row[5],
        )
        for row in rows
        if (row[3] or "").strip()
    ]
    return sorted(terms, key=lambda item: (len(item.term), not item.is_alias), reverse=True)


def find_term_occurrences(line: str, term: str) -> list[int]:
    if not line or not term:
        return []

    positions: list[int] = []
    start = 0
    while True:
        index = line.find(term, start)
        if index < 0:
            return positions
        positions.append(index)
        start = index + 1


def detect_match_conflicts(matches: list[LineConceptMatch]) -> list[dict[str, object]]:
    conflicts: list[dict[str, object]] = []
    by_line: dict[int, list[LineConceptMatch]] = defaultdict(list)
    for match in matches:
        by_line[match.line_index].append(match)

    for line_index, line_matches in by_line.items():
        ordered = sorted(line_matches, key=lambda item: (item.start_offset, len(item.matched_text)))
        for index, current in enumerate(ordered):
            current_end = current.start_offset + len(current.matched_text)
            for other in ordered[index + 1 :]:
                other_end = other.start_offset + len(other.matched_text)
                overlaps = current.start_offset < other_end and other.start_offset < current_end
                if not overlaps or current.concept_id == other.concept_id:
                    continue
                conflicts.append(
                    {
                        "line_index": line_index,
                        "line_text": current.line_text,
                        "left": current.matched_text,
                        "right": other.matched_text,
                    }
                )
    return conflicts


def match_line_concepts(
    poem_id: int,
    lines: list[str],
    terms: list[ConceptTerm],
    *,
    stopwords: set[str] | None = None,
    prefer_longest: bool = False,
) -> list[LineConceptMatch]:
    stopword_set = {normalize_term(item) for item in (stopwords or DEFAULT_STOPWORDS)}
    raw_matches: list[LineConceptMatch] = []
    best_by_position: dict[tuple[int, int, int, str], LineConceptMatch] = {}

    for line_index, line in enumerate(lines):
        for term in terms:
            if term.normalized_term in stopword_set:
                continue
            for start_offset in find_term_occurrences(line, term.term):
                key = (line_index, term.concept_id, start_offset, term.normalized_term)
                candidate = LineConceptMatch(
                    poem_id=poem_id,
                    concept_id=term.concept_id,
                    line_index=line_index,
                    line_text=line,
                    matched_text=term.term,
                    start_offset=start_offset,
                    confidence=ALIAS_CONFIDENCE if term.is_alias else EXACT_CONFIDENCE,
                )
                existing = best_by_position.get(key)
                if existing is None or candidate.confidence > existing.confidence:
                    best_by_position[key] = candidate

    raw_matches.extend(best_by_position.values())
    matches = sorted(
        raw_matches,
        key=lambda item: (item.line_index, item.start_offset, -len(item.matched_text), item.concept_id, item.matched_text),
    )
    if prefer_longest:
        filtered: list[LineConceptMatch] = []
        occupied_by_line: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for match in matches:
            span = (match.start_offset, match.start_offset + len(match.matched_text))
            occupied = occupied_by_line[match.line_index]
            if any(span[0] < other_end and other_start < span[1] for other_start, other_end in occupied):
                continue
            occupied.append(span)
            filtered.append(match)
        matches = filtered

    return sorted(
        matches,
        key=lambda item: (item.line_index, item.start_offset, item.concept_id, item.matched_text),
    )


def aggregate_poem_concepts(
    line_matches: list[LineConceptMatch],
) -> list[PoemConceptAggregate]:
    grouped: dict[int, list[LineConceptMatch]] = defaultdict(list)
    for match in line_matches:
        grouped[match.concept_id].append(match)

    aggregates: list[PoemConceptAggregate] = []
    for concept_id, matches in grouped.items():
        aggregates.append(
            PoemConceptAggregate(
                poem_id=matches[0].poem_id,
                concept_id=concept_id,
                confidence=max(match.confidence for match in matches),
                matched_count=len(matches),
                matched_texts=sorted({match.matched_text for match in matches}),
            )
        )
    return sorted(aggregates, key=lambda item: item.concept_id)


def parse_poem_concepts(poem_id: int) -> ParseResult:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT content FROM poems WHERE id = %s", (poem_id,))
        poem_row = cur.fetchone()
        if poem_row is None:
            raise ValueError(f"Poem not found: {poem_id}")

        lines = split_poem_lines(poem_row[0])
        terms = load_active_concept_terms()
        line_matches = match_line_concepts(poem_id=poem_id, lines=lines, terms=terms)
        aggregates = aggregate_poem_concepts(line_matches)
        conflicts = detect_match_conflicts(line_matches)

        cur.execute(
            "DELETE FROM line_concepts WHERE poem_id = %s AND source = %s",
            (poem_id, PARSER_SOURCE),
        )
        cur.execute(
            "DELETE FROM poem_concepts WHERE poem_id = %s AND source = %s",
            (poem_id, PARSER_SOURCE),
        )

        for match in line_matches:
            cur.execute(
                """
                INSERT INTO line_concepts (
                    poem_id,
                    concept_id,
                    line_index,
                    line_text,
                    matched_text,
                    start_offset,
                    confidence,
                    source
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (poem_id, line_index, concept_id, matched_text, start_offset, source)
                DO UPDATE SET
                    line_text = EXCLUDED.line_text,
                    confidence = GREATEST(line_concepts.confidence, EXCLUDED.confidence),
                    updated_at = now()
                """,
                (
                    match.poem_id,
                    match.concept_id,
                    match.line_index,
                    match.line_text,
                    match.matched_text,
                    match.start_offset,
                    match.confidence,
                    match.source,
                ),
            )

        for aggregate in aggregates:
            cur.execute(
                """
                INSERT INTO poem_concepts (
                    poem_id,
                    concept_id,
                    confidence,
                    source,
                    matched_count,
                    matched_texts
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (poem_id, concept_id)
                DO UPDATE SET
                    confidence = GREATEST(poem_concepts.confidence, EXCLUDED.confidence),
                    matched_count = EXCLUDED.matched_count,
                    matched_texts = EXCLUDED.matched_texts,
                    source = CASE
                        WHEN poem_concepts.source = 'manual' THEN poem_concepts.source
                        ELSE EXCLUDED.source
                    END,
                    updated_at = now()
                WHERE poem_concepts.source <> 'manual'
                """,
                (
                    aggregate.poem_id,
                    aggregate.concept_id,
                    aggregate.confidence,
                    PARSER_SOURCE,
                    aggregate.matched_count,
                    aggregate.matched_texts,
                ),
            )

        conn.commit()

    return ParseResult(
        poem_id=poem_id,
        line_match_count=len(line_matches),
        concept_count=len(aggregates),
        conflicts=conflicts,
    )
