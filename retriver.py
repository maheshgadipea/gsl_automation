"""Hybrid retrieval over existing LangChain PGVector tables.

The lexical side of this module deliberately works with the tables that
LangChain PGVector already creates:

* ``public.langchain_pg_embedding``
* ``public.langchain_pg_collection``

It performs PostgreSQL full-text search at query time and does not create
tables, columns, extensions, or indexes.  This makes it suitable when the
database schema is managed by another team.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol, TypeAlias

from sqlalchemy import text
from sqlalchemy.engine import Engine


MetadataFilterBuilder: TypeAlias = Callable[
    [Mapping[str, Any]], tuple[str, Mapping[str, Any]]
]
DocumentIdResolver: TypeAlias = Callable[[Any], Any | None]


_IDENTIFIER_PATTERNS = (
    # Examples: AML-004, CDD-001, and PS21/3.
    re.compile(
        r"(?<![A-Za-z0-9])"
        r"(?=[A-Za-z0-9._/-]*[A-Za-z])"
        r"(?=[A-Za-z0-9._/-]*\d)"
        r"[A-Za-z0-9]+(?:[-_/.][A-Za-z0-9]+)+(?![A-Za-z0-9])"
    ),
    # Examples: 4.2 and 4.2.7.
    re.compile(r"(?<!\d)\d+(?:\.\d+){1,}(?!\d)"),
)


class SimilaritySearchVectorStore(Protocol):
    """The LangChain vector-store capability used by :class:`HybridRetriever`."""

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: Mapping[str, Any] | None = None,
    ) -> Sequence[tuple[Any, float]]:
        """Return LangChain documents paired with their vector-store scores."""


def _validate_query(query: str) -> str:
    if not isinstance(query, str):
        raise TypeError("query must be a string")

    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("query must not be empty")

    return normalized_query


def _validate_limit(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")

    return value


def _escape_ilike_phrase(value: str) -> str:
    """Escape PostgreSQL ILIKE wildcards while preserving a literal phrase."""

    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def _extract_identifier_literals(query: str) -> tuple[str, ...]:
    """Return identifier-like query terms that deserve literal matching."""

    matched_literals = [
        (match.start(), match.group(0))
        for pattern in _IDENTIFIER_PATTERNS
        for match in pattern.finditer(query)
    ]
    matched_literals.sort(key=lambda item: item[0])

    unique_literals: list[str] = []
    seen_literals: set[str] = set()
    for _, literal in matched_literals:
        normalized_literal = literal.casefold()
        if normalized_literal not in seen_literals:
            unique_literals.append(literal)
            seen_literals.add(normalized_literal)

    return tuple(unique_literals)


class LexicalRetriever:
    """Retrieve existing PGVector chunks with PostgreSQL full-text search.

    ``metadata_filters`` defaults to JSONB-containment semantics, which is a
    good fit for simple equality filters such as ``{"country": "UK"}``.
    When the application's LangChain filters use custom operators, provide a
    ``metadata_filter_builder`` that returns a trusted SQL predicate (using
    the ``e`` table alias) and its bound parameters.
    """

    def __init__(
        self,
        engine: Engine,
        *,
        default_collection_name: str | None = None,
        metadata_filter_builder: MetadataFilterBuilder | None = None,
    ) -> None:
        self.engine = engine
        self.default_collection_name = default_collection_name
        self._metadata_filter_builder = (
            metadata_filter_builder or self._build_jsonb_containment_filter
        )

    def lexical_search(
        self,
        query: str,
        k: int = 20,
        collection_name: str | None = None,
        metadata_filters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return lexical candidates from the existing PGVector embeddings.

        Full-text search finds normal language terms.  Literal ILIKE branches
        supplement it for the full query and identifier-like terms such as
        ``AML-004`` or ``4.2.7`` that may not tokenize well for FTS.
        """

        normalized_query = _validate_query(query)
        limit = _validate_limit(k, "k")
        selected_collection = (
            collection_name
            if collection_name is not None
            else self.default_collection_name
        )

        params: dict[str, Any] = {
            "query": normalized_query,
            "phrase_pattern": f"%{_escape_ilike_phrase(normalized_query)}%",
            "like_escape": "\\",
            "k": limit,
        }
        literal_predicates = [
            "COALESCE(e.document, '') ILIKE :phrase_pattern ESCAPE :like_escape"
        ]
        for identifier_index, identifier in enumerate(
            _extract_identifier_literals(normalized_query),
            start=1,
        ):
            parameter_name = f"identifier_pattern_{identifier_index}"
            literal_predicates.append(
                f"COALESCE(e.document, '') ILIKE :{parameter_name} ESCAPE :like_escape"
            )
            params[parameter_name] = f"%{_escape_ilike_phrase(identifier)}%"

        literal_match_predicate = "\n                    OR ".join(literal_predicates)
        sql = f"""
            WITH search_query AS (
                SELECT websearch_to_tsquery('english', :query) AS tsquery
            )
            SELECT
                e.id,
                e.document,
                e.cmetadata,
                COALESCE(
                    ts_rank_cd(
                        to_tsvector('english', COALESCE(e.document, '')),
                        search_query.tsquery
                    ),
                    0.0
                ) AS lexical_score,
                CASE
                    WHEN (
                        {literal_match_predicate}
                    )
                    THEN TRUE
                    ELSE FALSE
                END AS exact_match
            FROM public.langchain_pg_embedding AS e
            CROSS JOIN search_query
            WHERE (
                to_tsvector('english', COALESCE(e.document, ''))
                    @@ search_query.tsquery
                OR (
                    {literal_match_predicate}
                )
            )
        """

        if selected_collection is not None:
            sql += """
                AND EXISTS (
                    SELECT 1
                    FROM public.langchain_pg_collection AS c
                    WHERE c.uuid = e.collection_id
                      AND c.name = :collection_name
                )
            """
            params["collection_name"] = selected_collection

        if metadata_filters is not None and not isinstance(metadata_filters, Mapping):
            raise TypeError("metadata_filters must be a mapping")

        if metadata_filters:
            filter_sql, filter_params = self._metadata_filter_builder(metadata_filters)
            parameter_conflicts = set(params).intersection(filter_params)
            if parameter_conflicts:
                conflicts = ", ".join(sorted(parameter_conflicts))
                raise ValueError(
                    "metadata_filter_builder reused reserved parameter names: "
                    f"{conflicts}"
                )

            sql += f"\n                AND ({filter_sql})\n"
            params.update(filter_params)

        sql += """
            ORDER BY
                exact_match DESC,
                lexical_score DESC,
                e.id
            LIMIT :k
        """

        with self.engine.connect() as connection:
            rows = connection.execute(text(sql), params).mappings().all()

        results: list[dict[str, Any]] = []
        for rank, row in enumerate(rows, start=1):
            results.append(
                {
                    "id": row["id"],
                    "document": row["document"] or "",
                    "metadata": row["cmetadata"] or {},
                    "rank": rank,
                    "lexical_score": float(row["lexical_score"] or 0.0),
                    "exact_match": bool(row["exact_match"]),
                }
            )

        return results

    @staticmethod
    def _build_jsonb_containment_filter(
        metadata_filters: Mapping[str, Any],
    ) -> tuple[str, Mapping[str, Any]]:
        """Build the default equality-style filter for ``cmetadata``.

        Casting the column keeps the predicate compatible with installations
        where LangChain created ``cmetadata`` as JSON instead of JSONB.
        """

        try:
            serialized_filter = json.dumps(
                dict(metadata_filters),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as error:
            raise ValueError(
                "metadata_filters must contain JSON-serializable values"
            ) from error

        return (
            "COALESCE(CAST(e.cmetadata AS jsonb), '{}'::jsonb) "
            "@> CAST(:lexical_metadata_filter AS jsonb)",
            {"lexical_metadata_filter": serialized_filter},
        )


class HybridRetriever:
    """Fuse independently retrieved semantic and lexical candidates with RRF.

    The supplied vector store is expected to be the application's existing
    LangChain PGVector store.  For best fusion, the LangChain document ID must
    be the same value as ``langchain_pg_embedding.id``.  If a LangChain version
    drops that ID, pass ``document_id_resolver`` to recover it from the
    document or its metadata.  ``default_collection_name`` must name the
    collection to which that vector store is already scoped; the generic
    LangChain search interface cannot switch collections per request.
    """

    def __init__(
        self,
        vectorstore: SimilaritySearchVectorStore,
        engine: Engine,
        *,
        default_collection_name: str | None = None,
        rrf_k: int = 60,
        metadata_filter_builder: MetadataFilterBuilder | None = None,
        document_id_resolver: DocumentIdResolver | None = None,
    ) -> None:
        self.vectorstore = vectorstore
        self._semantic_collection_name = default_collection_name
        self.lexical_retriever = LexicalRetriever(
            engine,
            default_collection_name=default_collection_name,
            metadata_filter_builder=metadata_filter_builder,
        )
        self.rrf_k = _validate_limit(rrf_k, "rrf_k")
        self._document_id_resolver = document_id_resolver

    def retrieve(
        self,
        query: str,
        k: int = 10,
        query_filters: Mapping[str, Any] | None = None,
        collection_name: str | None = None,
        semantic_k: int | None = None,
        lexical_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Run semantic and lexical retrieval, then return fused top results.

        ``query_filters`` is intentionally sent to both retrieval branches so
        a semantic result and a lexical result are constrained to the same
        corpus.  The default lexical filter supports equality-style JSON
        metadata filters; use ``metadata_filter_builder`` for other syntax.
        A per-call ``collection_name`` is accepted only when it matches the
        collection already configured for the supplied vector store.
        """

        normalized_query = _validate_query(query)
        result_limit = _validate_limit(k, "k")
        semantic_limit = (
            _validate_limit(semantic_k, "semantic_k")
            if semantic_k is not None
            else max(result_limit, 20)
        )
        lexical_limit = (
            _validate_limit(lexical_k, "lexical_k")
            if lexical_k is not None
            else max(result_limit, 20)
        )
        if collection_name is not None:
            self._validate_collection_scope(collection_name)

        semantic_results = self.semantic_search(
            query=normalized_query,
            k=semantic_limit,
            query_filters=query_filters,
        )
        lexical_results = self.lexical_retriever.lexical_search(
            query=normalized_query,
            k=lexical_limit,
            collection_name=collection_name,
            metadata_filters=query_filters,
        )

        return self.reciprocal_rank_fusion(
            semantic_results,
            lexical_results,
            limit=result_limit,
        )

    def semantic_search(
        self,
        query: str,
        k: int = 20,
        query_filters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve semantic candidates without replacing existing PGVector use."""

        normalized_query = _validate_query(query)
        limit = _validate_limit(k, "k")
        raw_results = self.vectorstore.similarity_search_with_score(
            query=normalized_query,
            k=limit,
            filter=query_filters,
        )

        results: list[dict[str, Any]] = []
        for rank, raw_result in enumerate(raw_results, start=1):
            try:
                document, score = raw_result
            except (TypeError, ValueError) as error:
                raise TypeError(
                    "similarity_search_with_score must return "
                    "(document, score) pairs"
                ) from error

            page_content = getattr(document, "page_content", None)
            if not isinstance(page_content, str):
                raise TypeError(
                    "semantic search returned a document without string page_content"
                )

            metadata = getattr(document, "metadata", None) or {}
            results.append(
                {
                    "id": self._resolve_document_id(document),
                    "document": page_content,
                    "metadata": dict(metadata)
                    if isinstance(metadata, Mapping)
                    else metadata,
                    "rank": rank,
                    "semantic_score": float(score),
                }
            )

        return results

    def reciprocal_rank_fusion(
        self,
        semantic_results: Sequence[Mapping[str, Any]],
        lexical_results: Sequence[Mapping[str, Any]],
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Combine rank lists using reciprocal-rank fusion (RRF)."""

        if limit is not None:
            _validate_limit(limit, "limit")

        fused: dict[str, dict[str, Any]] = {}
        for source, candidates in (
            ("semantic", semantic_results),
            ("lexical", lexical_results),
        ):
            for source_rank, candidate in enumerate(candidates, start=1):
                candidate_key = self._candidate_key(candidate)
                merged = fused.get(candidate_key)
                if merged is None:
                    merged = {
                        "id": candidate.get("id"),
                        "document": candidate.get("document", ""),
                        "metadata": candidate.get("metadata") or {},
                        "rank": 0,
                        "semantic_score": None,
                        "lexical_score": None,
                        "exact_match": False,
                        "rrf_score": 0.0,
                        "sources": [],
                        "semantic_rank": None,
                        "lexical_rank": None,
                        "_best_source_rank": source_rank,
                    }
                    fused[candidate_key] = merged

                merged["rrf_score"] += 1.0 / (self.rrf_k + source_rank)
                merged["_best_source_rank"] = min(
                    merged["_best_source_rank"], source_rank
                )
                merged[f"{source}_rank"] = source_rank
                if source not in merged["sources"]:
                    merged["sources"].append(source)

                if source == "semantic":
                    merged["semantic_score"] = candidate.get("semantic_score")
                else:
                    merged["lexical_score"] = candidate.get("lexical_score")
                    merged["exact_match"] = bool(candidate.get("exact_match"))

        ordered_results = sorted(
            fused.values(),
            key=lambda result: (
                -result["rrf_score"],
                -len(result["sources"]),
                not result["exact_match"],
                result["_best_source_rank"],
                str(result["id"]),
            ),
        )

        if limit is not None:
            ordered_results = ordered_results[:limit]

        for rank, result in enumerate(ordered_results, start=1):
            result["rank"] = rank
            del result["_best_source_rank"]

        return ordered_results

    def _resolve_document_id(self, document: Any) -> Any:
        if self._document_id_resolver is not None:
            resolved_id = self._document_id_resolver(document)
            if resolved_id is not None:
                return resolved_id

        document_id = getattr(document, "id", None)
        if document_id is not None:
            return document_id

        raise ValueError(
            "semantic documents must expose the PGVector embedding ID through "
            "document.id or document_id_resolver for reciprocal-rank fusion"
        )

    def _validate_collection_scope(self, collection_name: str) -> None:
        if self._semantic_collection_name is None:
            raise ValueError(
                "collection_name cannot be applied safely to the supplied "
                "vectorstore. Construct HybridRetriever with "
                "default_collection_name set to that vectorstore's collection."
            )

        if collection_name != self._semantic_collection_name:
            raise ValueError(
                "collection_name differs from the collection configured for "
                "the supplied vectorstore; use a vectorstore scoped to the "
                "requested collection."
            )

    @staticmethod
    def _candidate_key(candidate: Mapping[str, Any]) -> str:
        candidate_id = candidate.get("id")
        if candidate_id is not None:
            return f"id:{candidate_id}"

        document = candidate.get("document", "")
        digest = hashlib.sha256(str(document).encode("utf-8")).hexdigest()
        return f"content:{digest}"
