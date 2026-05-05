from decimal import Decimal

from app.services.concept_parser import (
    ALIAS_CONFIDENCE,
    EXACT_CONFIDENCE,
    ConceptTerm,
    aggregate_poem_concepts,
    detect_match_conflicts,
    find_term_occurrences,
    match_line_concepts,
    normalize_term,
)


def term(
    concept_id: int,
    name: str,
    concept_type: str,
    value: str,
    *,
    is_alias: bool = False,
) -> ConceptTerm:
    return ConceptTerm(
        concept_id=concept_id,
        concept_name=name,
        concept_type=concept_type,
        term=value,
        normalized_term=normalize_term(value),
        is_alias=is_alias,
    )


def test_normalize_term_strips_spaces_and_casefolds():
    assert normalize_term("  Moon Light ") == "moonlight"
    assert normalize_term(" 明 月 ") == "明月"
    assert normalize_term("") == ""


def test_find_term_occurrences_returns_repeated_positions():
    assert find_term_occurrences("明月明月", "明月") == [0, 2]
    assert find_term_occurrences("月月月", "月") == [0, 1, 2]
    assert find_term_occurrences("春风不度", "秋") == []


def test_match_line_concepts_matches_chars_phrases_places_and_images():
    terms = [
        term(1, "月", "char", "月"),
        term(2, "明月", "phrase", "明月"),
        term(3, "长安", "place", "长安"),
        term(4, "孤舟", "image", "孤舟"),
    ]

    matches = match_line_concepts(
        poem_id=12,
        lines=["举头望明月", "孤舟泊长安"],
        terms=terms,
    )

    assert [(m.concept_id, m.line_index, m.matched_text, m.start_offset) for m in matches] == [
        (2, 0, "明月", 3),
        (1, 0, "月", 4),
        (4, 1, "孤舟", 0),
        (3, 1, "长安", 3),
    ]
    assert all(match.confidence == EXACT_CONFIDENCE for match in matches)


def test_alias_match_uses_lower_confidence():
    terms = [term(1, "月", "char", "月亮", is_alias=True)]

    matches = match_line_concepts(poem_id=1, lines=["月亮照故乡"], terms=terms)

    assert len(matches) == 1
    assert matches[0].matched_text == "月亮"
    assert matches[0].confidence == ALIAS_CONFIDENCE


def test_duplicate_terms_keep_best_confidence_for_same_concept_position():
    terms = [
        term(1, "月", "char", "月", is_alias=True),
        term(1, "月", "char", "月", is_alias=False),
    ]

    matches = match_line_concepts(poem_id=1, lines=["明月"], terms=terms)

    assert len(matches) == 1
    assert matches[0].confidence == Decimal("1.0000")


def test_aggregate_poem_concepts_counts_and_deduplicates_texts():
    terms = [
        term(1, "月", "char", "月"),
        term(2, "明月", "phrase", "明月"),
    ]
    matches = match_line_concepts(
        poem_id=12,
        lines=["明月明月", "月下独酌"],
        terms=terms,
    )

    aggregates = aggregate_poem_concepts(matches)

    assert [(item.concept_id, item.matched_count, item.matched_texts) for item in aggregates] == [
        (1, 3, ["月"]),
        (2, 2, ["明月"]),
    ]


def test_empty_dictionary_returns_no_matches():
    assert match_line_concepts(poem_id=1, lines=["床前明月光"], terms=[]) == []
    assert aggregate_poem_concepts([]) == []


def test_match_line_concepts_supports_stopwords():
    terms = [
      term(1, "月", "char", "月"),
      term(2, "明月", "phrase", "明月"),
    ]

    matches = match_line_concepts(
        poem_id=1,
        lines=["床前明月光"],
        terms=terms,
        stopwords={"月"},
    )

    assert [(item.concept_id, item.matched_text) for item in matches] == [(2, "明月")]


def test_match_line_concepts_supports_prefer_longest():
    terms = [
        term(1, "月", "char", "月"),
        term(2, "明月", "phrase", "明月"),
    ]

    matches = match_line_concepts(
        poem_id=1,
        lines=["床前明月光"],
        terms=terms,
        prefer_longest=True,
    )

    assert [(item.concept_id, item.matched_text) for item in matches] == [(2, "明月")]


def test_detect_match_conflicts_reports_overlaps():
    terms = [
        term(1, "月", "char", "月"),
        term(2, "明月", "phrase", "明月"),
    ]
    matches = match_line_concepts(poem_id=1, lines=["床前明月光"], terms=terms)

    conflicts = detect_match_conflicts(matches)

    assert conflicts
    assert conflicts[0]["line_index"] == 0
