"""Typed guide retrieval shared by standalone queries and backend guidance."""

from dataclasses import dataclass
import logging
import re
import time
from uuid import uuid4

import numpy as np

from SystemCode.src.backend.agents.contracts import GeneralKnowledgeEvidence, PublicCitation
from SystemCode.src.backend.agents.tools import CuratedGeneralKnowledgeRetriever, GeneralKnowledgeRetriever
from SystemCode.src.backend.pipeline.general_knowledge_config import (
    GeneralKnowledgeConfig, GeneralKnowledgeRetrievalMode,
)
from SystemCode.src.backend.pipeline.parent_guide_chunking import load_parent_guide_chunks
from SystemCode.src.backend.pipeline.parent_guide_embeddings import (
    EmbeddingSettings, OpenAIEmbeddingProvider, normalise_vectors,
)
from SystemCode.src.backend.pipeline.stage1.web_rag import _rank_chunks
from SystemCode.src.backend.repositories.parent_guide_index import load_active_index


# Calibrated on the labelled standalone questions; these are ranking cutoffs,
# not probabilities. See doc/file-vector-retrieval.md for limits and results.
VECTOR_MIN_SIMILARITY = 0.40
LEXICAL_MIN_RELEVANCE = 0.45
LOGGER = logging.getLogger("kindercompass.retrieval")


@dataclass(frozen=True)
class RetrievalStatus:
    build_id: str | None
    mode: str
    elapsed_ms: float
    result_count: int
    failure_category: str | None


def _periods(chunk):
    dates = chunk.policy_dates
    years = {dates[key] for key in ("fee_year", "policy_year", "intake_year") if key in dates}
    start, end = dates.get("effective_from"), dates.get("effective_until")
    if start:
        years.update(range(int(start[:4]), int(end[:4]) + 1) if end else [int(start[:4])])
    if not years and "2027" in chunk.topic:
        years.add(2027)
    return sorted(years)


def _question_topic(question):
    """Use explicit subject words to constrain reviewed section metadata."""
    value = question.casefold()
    # Excluded subjects must not borrow support from adjacent reviewed topics.
    if re.search(r"\b(?:primary\s*(?:1|one)|p1|cctv|livestream|waitlist)\b", value):
        return set()
    if re.search(r"\bkifas\b", value) and "kcare" not in value:
        return {"kifas-2026-scope"}
    if re.search(r"\banchor operators?\b", value):
        return {"anchor-operators"}
    if re.search(r"\bmk\b|moe kindergarten", value) and re.search(
        r"submit|submitting|submission|priority|ballot|guarantee", value
    ) and not re.search(r"\beyc\b|early years|partnership", value):
        return {"mk-priority"}
    if "subsid" in value and not any(term in value for term in ("kcare", "kifas", "kindergarten")):
        return {"subsidy-scope", "basic-subsidy-and-exception", "subsidy-income-ceiling",
                "additional-subsidy-2026-table", "additional-subsidy-2027-table"}
    if re.search(r"\bcda\b|child development account", value):
        return {"cda-current-benefits", "sg-child-support-2027"}
    return None


def _retrieval_question(question):
    """Separate an explicit general explanation from a combined school query.

    Expand domain abbreviations/eligibility wording without altering the corpus
    or dropping exceptions and dates from a single-subject question.
    """
    parts = re.split(r"\band\s+(?=(?:what is|what are|explain)\b)", question, flags=re.I)
    if len(parts) > 1 and re.search(r"\b(?:this|selected)\s+(?:school|centre|center|preschool)\b", parts[0], re.I):
        question = parts[-1].strip()
    question = re.sub(r"\bqualif(?:y|ies)\b", "eligible", question, flags=re.I)
    question = re.sub(r"\bAnchor Operators\b", "Anchor Operators AOP", question, flags=re.I)
    if re.search(r"\bMK\b", question, re.I) and re.search(r"submit|submitting|submission", question, re.I):
        question += " MOE Kindergarten admission priority submission order submit"
    return question


def _eligible(chunk, years, topic):
    if topic and topic.casefold() not in {
        chunk.topic.casefold(), chunk.mapping_id.casefold(), chunk.section_heading.casefold(),
    }:
        return False
    dates = chunk.policy_dates
    periods = _periods(chunk)
    if years and periods:
        if "effective_from" in dates and "effective_until" not in dates:
            return any(year >= int(dates["effective_from"][:4]) for year in years)
        return bool(set(years) & set(periods))
    return True


def _evidence(chunk):
    # Keep the selected passage intact, including tables and qualifications.
    periods = _periods(chunk)
    label = "Policy period: " + ", ".join(map(str, periods)) + ".\n" if periods else ""
    return GeneralKnowledgeEvidence(
        chunk_id=chunk.chunk_id, text=(label + chunk.text) if len(label + chunk.text) <= 5000 else chunk.embedding_text,
        evidence_category=chunk.evidence_category,
        citation=PublicCitation(
            citation_id=chunk.chunk_id, evidence_scope="general",
            url=chunk.citation["url"],
            title=chunk.section_heading,
            retrieved_at=chunk.source_verified_at,
        ),
    )


class ParentGuideRetriever:
    """Construct once per worker; queries never reload or re-embed documents.

    Index failure loads freshly validated reviewed Markdown for lexical search.
    A provider is created lazily and query calls have no retries. The optional
    topic/year parameters constrain reviewed metadata before either ranking.
    """

    def __init__(self, config: GeneralKnowledgeConfig, *, provider=None,
                 curated: GeneralKnowledgeRetriever | None = None):
        self.config = config
        self.provider = provider
        self.curated = curated or CuratedGeneralKnowledgeRetriever({"chunks": []})
        self.index = None
        self.load_failure = None
        self.status = RetrievalStatus(None, "unavailable", 0, 0, None)
        if config.mode == GeneralKnowledgeRetrievalMode.CURATED:
            self.chunks = ()
            return
        try:
            self.index = load_active_index(
                config.vector_path, expected_embedding=EmbeddingSettings.from_config(config),
            )
            self.chunks = self.index.chunks
        except (OSError, ValueError):
            self.load_failure = "index_unavailable"
            try:
                self.chunks = load_parent_guide_chunks(config.vector_path / "sources.json")
            except (OSError, ValueError, KeyError, TypeError):
                self.chunks = ()

    def search(self, question: str, *, limit: int = 3, topic: str | None = None,
               year: int | None = None) -> list[GeneralKnowledgeEvidence]:
        started = time.monotonic()
        execution_id = uuid4().hex
        try:
            LOGGER.info(
                "guide_retrieval event=started execution_id=%s configured_mode=%s",
                execution_id, GeneralKnowledgeRetrievalMode(self.config.mode).value,
            )
        except Exception:
            pass
        failure = self.load_failure
        mode = "unavailable"
        results = []
        limit = max(0, min(limit, 3))
        valid = (isinstance(question, str) and bool(question.strip())
                 and len(question) <= self.config.max_query_characters and limit > 0)
        if valid:
            question = _retrieval_question(question)
            years = {int(value) for value in re.findall(r"\b(20\d{2})\b", question)}
            if year is not None:
                years = {year}
            subjects = _question_topic(question)
            rows = [i for i, chunk in enumerate(self.chunks)
                    if _eligible(chunk, years, topic)
                    and (subjects is None or chunk.mapping_id in subjects)]
            if self.config.mode == GeneralKnowledgeRetrievalMode.VECTOR and self.index and rows:
                try:
                    if self.provider is None:
                        self.provider = OpenAIEmbeddingProvider(self.config)
                    expected = EmbeddingSettings.from_config(self.config)
                    if self.provider.settings != expected:
                        raise ValueError("Query provider does not match index.")
                    batch = self.provider.embed([question], timeout_seconds=self.config.timeout_seconds)
                    if batch.model != expected.model:
                        raise ValueError("Query embedding model mismatch.")
                    query = normalise_vectors(batch.vectors, 1, expected.dimensions)[0]
                    scores = self.index.embeddings[rows] @ query
                    ranked = sorted(zip(rows, scores), key=lambda pair: (-float(pair[1]), pair[0]))
                    results = [_evidence(self.chunks[row]) for row, score in ranked[:limit]
                               if score >= VECTOR_MIN_SIMILARITY]
                    mode = "vector"
                    if not results:
                        failure = "low_relevance"
                except Exception:
                    # Never expose provider errors, questions or family data.
                    failure = "embedding_unavailable"
            if not results and rows:
                records = [{"chunk_id": self.chunks[row].chunk_id,
                            "text": self.chunks[row].text} for row in rows]
                lexical_question = re.sub(r"\b20\d{2}\b", "", question)
                if subjects == {"mk-priority"}:
                    lexical_question = re.sub(r"\b(?:MK|registration|submitting|submission|order)\b", "", lexical_question, flags=re.I)
                matches = _rank_chunks(records, re.sub(r"\bthresholds?\b", "HHI", lexical_question, flags=re.I), limit=limit,
                                       min_relevance=LEXICAL_MIN_RELEVANCE)
                by_id = {chunk.chunk_id: chunk for chunk in self.chunks}
                results = [_evidence(by_id[match["chunk_id"]]) for match in matches]
                if results:
                    mode = "lexical"
            if not results:
                # Curated metadata cannot enforce guide topic/year constraints.
                # Do not let this fallback undo an explicit dated restriction.
                if not years and topic is None and subjects is None:
                    results = self.curated.search(question, limit=limit)[:limit]
                    if results:
                        mode = "curated"
        else:
            failure = "invalid_query"
        status = RetrievalStatus(
            self.index.build_id if self.index else None, mode,
            round((time.monotonic() - started) * 1000, 3), len(results), failure,
        )
        self.status = status
        try:
            LOGGER.info(
                "guide_retrieval event=completed execution_id=%s mode=%s "
                "result_count=%s elapsed_ms=%.3f failure_category=%s",
                execution_id, status.mode, status.result_count,
                status.elapsed_ms, status.failure_category,
            )
        except Exception:
            pass
        return results
