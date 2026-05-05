from __future__ import annotations

from app.db.connection import get_connection
from app.schemas.concept import GraphEdge, GraphNode


def parse_node_types(value: str | None) -> set[str]:
    if not value:
        return {"line", "poem", "author", "dynasty"}
    return {item.strip() for item in value.split(",") if item.strip()}


def add_node(nodes: dict[str, GraphNode], node: GraphNode) -> None:
    nodes.setdefault(node.id, node)


def add_edge(edges: dict[str, GraphEdge], edge: GraphEdge) -> None:
    edges.setdefault(edge.id, edge)


def get_concept_graph(
    concept_id: int,
    *,
    limit_poems: int,
    limit_lines: int,
    author_id: int | None = None,
    dynasty: str | None = None,
    node_types: str | None = None,
    source: str | None = None,
    min_popularity: int | None = None,
    min_matched_count: int | None = None,
) -> tuple[GraphNode | None, list[GraphNode], list[GraphEdge], bool]:
    enabled = parse_node_types(node_types)

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, type
            FROM concepts
            WHERE id = %s AND is_active = true
            """,
            (concept_id,),
        )
        center_row = cur.fetchone()
        if center_row is None:
            return None, [], [], False

        conditions = ["lc.concept_id = %s"]
        params: list[object] = [concept_id]
        if author_id is not None:
            conditions.append("p.author_id = %s")
            params.append(author_id)
        if dynasty:
            conditions.append(
                """
                EXISTS (
                    SELECT 1
                    FROM author_concepts ac
                    JOIN concepts dc ON dc.id = ac.concept_id
                    WHERE ac.author_id = p.author_id
                      AND dc.type = 'dynasty'
                      AND dc.name = %s
                )
                """
            )
            params.append(dynasty)
        if source:
            conditions.append("lc.source = %s")
            params.append(source)
        if min_popularity is not None:
            conditions.append("p.popularity_rank >= %s")
            params.append(min_popularity)
        if min_matched_count is not None:
            conditions.append(
                """
                EXISTS (
                    SELECT 1
                    FROM poem_concepts pc
                    WHERE pc.poem_id = lc.poem_id
                      AND pc.concept_id = lc.concept_id
                      AND pc.matched_count >= %s
                )
                """
            )
            params.append(min_matched_count)

        query = f"""
            SELECT
                lc.poem_id,
                lc.line_index,
                lc.line_text,
                lc.matched_text,
                lc.confidence,
                p.title,
                p.author_id,
                a.name,
                dc.id,
                dc.name
            FROM line_concepts lc
            JOIN poems p ON p.id = lc.poem_id
            LEFT JOIN authors a ON a.id = p.author_id
            LEFT JOIN author_concepts ac ON ac.author_id = p.author_id
            LEFT JOIN concepts dc ON dc.id = ac.concept_id AND dc.type = 'dynasty'
            WHERE {" AND ".join(conditions)}
            ORDER BY p.popularity_rank DESC, p.id ASC, lc.line_index ASC, lc.start_offset ASC
            LIMIT %s
        """
        cur.execute(query, [*params, limit_lines + 1])
        rows = cur.fetchall()

    truncated = len(rows) > limit_lines
    rows = rows[:limit_lines]

    center = GraphNode(
        id=f"concept:{center_row[0]}",
        type="concept",
        label=center_row[1],
        meta={"concept_id": center_row[0], "concept_type": center_row[2]},
    )
    nodes: dict[str, GraphNode] = {center.id: center}
    edges: dict[str, GraphEdge] = {}
    poem_count = 0
    seen_poems: set[int] = set()

    for row in rows:
        poem_id, line_index, line_text, matched_text, confidence, title, row_author_id, author_name, dynasty_id, dynasty_name = row
        if poem_id not in seen_poems:
            if poem_count >= limit_poems:
                truncated = True
                continue
            seen_poems.add(poem_id)
            poem_count += 1

        line_node_id = f"line:{poem_id}:{line_index}"
        poem_node_id = f"poem:{poem_id}"
        author_node_id = f"author:{row_author_id}" if row_author_id is not None else None
        dynasty_node_id = f"concept:{dynasty_id}" if dynasty_id is not None else None

        if "line" in enabled:
            add_node(
                nodes,
                GraphNode(
                    id=line_node_id,
                    type="line",
                    label=line_text,
                    meta={"poem_id": poem_id, "line_index": line_index},
                ),
            )
            add_edge(
                edges,
                GraphEdge(
                    id=f"concept:{concept_id}-{line_node_id}",
                    source=f"concept:{concept_id}",
                    target=line_node_id,
                    type="matched",
                    meta={"matched_text": matched_text, "confidence": float(confidence)},
                ),
            )

        if "poem" in enabled:
            add_node(
                nodes,
                GraphNode(
                    id=poem_node_id,
                    type="poem",
                    label=title,
                    meta={"poem_id": poem_id},
                ),
            )
            if "line" in enabled:
                add_edge(
                    edges,
                    GraphEdge(
                        id=f"{line_node_id}-{poem_node_id}",
                        source=line_node_id,
                        target=poem_node_id,
                        type="belongs_to",
                    ),
                )
            else:
                add_edge(
                    edges,
                    GraphEdge(
                        id=f"concept:{concept_id}-{poem_node_id}",
                        source=f"concept:{concept_id}",
                        target=poem_node_id,
                        type="matched",
                        meta={"matched_text": matched_text, "confidence": float(confidence)},
                    ),
                )

        if "author" in enabled and author_node_id is not None:
            add_node(
                nodes,
                GraphNode(
                    id=author_node_id,
                    type="author",
                    label=author_name or "佚名",
                    meta={"author_id": row_author_id},
                ),
            )
            if "poem" in enabled:
                add_edge(
                    edges,
                    GraphEdge(
                        id=f"{poem_node_id}-{author_node_id}",
                        source=poem_node_id,
                        target=author_node_id,
                        type="written_by",
                    ),
                )

        if "dynasty" in enabled and dynasty_node_id is not None:
            add_node(
                nodes,
                GraphNode(
                    id=dynasty_node_id,
                    type="dynasty",
                    label=dynasty_name,
                    meta={"concept_id": dynasty_id},
                ),
            )
            if author_node_id is not None and "author" in enabled:
                add_edge(
                    edges,
                    GraphEdge(
                        id=f"{author_node_id}-{dynasty_node_id}",
                        source=author_node_id,
                        target=dynasty_node_id,
                        type="dynasty",
                    ),
                )

    return center, list(nodes.values()), list(edges.values()), truncated
