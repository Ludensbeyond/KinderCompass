"""Evaluate fixed synthetic guide labels; never build or publish document vectors."""

import argparse
from copy import deepcopy
from dataclasses import replace
import json
import os
import re
from pathlib import Path
import time
import tracemalloc
from types import SimpleNamespace

import numpy as np
from dotenv import load_dotenv

from SystemCode.src.backend.agents.contracts import ConversationRequestContext, EvidenceIndexContext
from SystemCode.src.backend.agents.supervisor import _tools_for_intent
from SystemCode.src.backend.pipeline.general_knowledge_config import (
    GeneralKnowledgeRetrievalMode, REPOSITORY_ROOT, get_general_knowledge_config,
)
from SystemCode.src.backend.pipeline.parent_guide_embeddings import (
    EmbeddingSettings, OpenAIEmbeddingProvider, normalise_vectors,
)
from SystemCode.src.backend.pipeline.parent_guide_retrieval import (
    ParentGuideRetriever, VECTOR_MIN_SIMILARITY, _eligible, _evidence, _question_topic,
)
from SystemCode.src.backend.pipeline.stage1.conversation import update_conversation
from SystemCode.src.backend.pipeline.stage1.intent_router import classify_intent
from SystemCode.src.backend.repositories.parent_guide_index import json_bytes

LABELS = REPOSITORY_ROOT / 'SystemCode/src/backend/resources/parent_guide_evaluation.json'
TOOL_NAMES = ('search_general_knowledge', 'search_selected_school_evidence',
              'query_structured_school_facts', 'update_preferences', 'run_what_if_scenario')


def selected_tools(question, intent):
    context = ConversationRequestContext(
        message=question, deterministic_intent=intent,
        selected_school_evidence=EvidenceIndexContext(scope='school', available=False),
        general_knowledge_evidence=EvidenceIndexContext(scope='general', available=False),
        catalogue_version='synthetic-evaluation',
    )
    if intent == 'needs_clarification':
        # Supervisor terminates with clarification before invoking capabilities.
        return []
    return sorted(t.name for t in _tools_for_intent(
        context, [SimpleNamespace(name=name) for name in TOOL_NAMES],
    ))


def vector_search(retriever, provider, question):
    """Independent vector ranking: never credit lexical/provider fallback as a hit."""
    expected = EmbeddingSettings.from_config(retriever.config)
    if provider.settings != expected:
        raise ValueError('Incompatible query provider')
    batch = provider.embed([question], timeout_seconds=retriever.config.timeout_seconds)
    if batch.model != expected.model:
        raise ValueError('Incompatible response model')
    query = normalise_vectors(batch.vectors, 1, expected.dimensions)[0]
    years = {int(value) for value in re.findall(r'\b(20\d{2})\b', question)}
    subjects = _question_topic(question)
    rows = [i for i, chunk in enumerate(retriever.chunks)
            if _eligible(chunk, years, None) and (subjects is None or chunk.mapping_id in subjects)]
    scores = retriever.index.embeddings[rows] @ query
    ranked = sorted(zip(rows, scores), key=lambda pair: (-float(pair[1]), pair[0]))
    return [_evidence(retriever.chunks[row]) for row, score in ranked[:3]
            if score >= VECTOR_MIN_SIMILARITY]


def score_evidence(case, matches, chunks):
    by_id = {c.chunk_id: c for c in chunks}
    mappings = [by_id[m.chunk_id].mapping_id for m in matches]
    expected = set(case['expected_mapping_ids'])
    expected_matches = [m for m in matches if by_id[m.chunk_id].mapping_id in expected]
    citation_ok = all(
        m.citation.citation_id == m.chunk_id
        and m.citation.evidence_scope == 'general'
        and str(m.citation.url) == by_id[m.chunk_id].citation['url']
        and m.citation.retrieved_at.isoformat() == by_id[m.chunk_id].source_verified_at
        for m in matches
    )
    text = '\n'.join(m.text for m in expected_matches).casefold()
    return {
        'mapping_ids': mappings,
        'hit': bool(expected_matches) if expected else not matches,
        'qualifications_ok': all(term.casefold() in text for term in case['required_terms']),
        'citations_ok': citation_ok,
    }


def evaluate(config, labels, *, provider=None):
    tracemalloc.start()
    started = time.perf_counter()
    retriever = ParentGuideRetriever(replace(config, mode=GeneralKnowledgeRetrievalMode.LEXICAL))
    load_ms = (time.perf_counter() - started) * 1000
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if retriever.index is None:
        raise ValueError('Evaluation requires a validated persisted index')
    results = []
    # A fixed synthetic state, never real family/chat data.
    profile = {'preferences': {'pedagogy': {'value': 'Montessori'}}}
    for case in labels['cases']:
        question = case['question']
        intent = classify_intent(question)
        tools = selected_tools(question, intent.intent)
        result = {'case_id': case['case_id'], 'kind': case['kind'],
                  'intent': intent.intent, 'tools': tools,
                  'routing_ok': intent.intent == case['expected_intent']
                  and tools == sorted(case['expected_tools'])}
        if case['kind'] in {'answerable', 'combined', 'excluded', 'unrelated'}:
            started = time.perf_counter()
            matches = retriever.search(question)
            result['lexical'] = {**score_evidence(case, matches, retriever.chunks),
                                 'elapsed_ms': round((time.perf_counter() - started) * 1000, 3)}
            if provider is not None:
                started = time.perf_counter()
                try:
                    matches = vector_search(retriever, provider, question)
                    result['vector'] = score_evidence(case, matches, retriever.chunks)
                except Exception as error:
                    result['vector'] = {'mapping_ids': [], 'hit': False, 'qualifications_ok': False,
                                        'citations_ok': False, 'failure_category': type(error).__name__}
                result['vector']['elapsed_ms'] = round((time.perf_counter() - started) * 1000, 3)
            # Check actual deterministic general-answer wiring, with no forced intent.
            # Other capabilities have dedicated integration tests and do not use this corpus.
            if intent.intent == 'ask_general_knowledge':
                turn = update_conversation(deepcopy(profile), question, classified_intent=intent,
                                           general_retriever=retriever)
                result['state_preserved'] = turn['profile']['preferences'] == profile['preferences']
                result['answer_has_citations'] = bool(turn.get('citations'))
                expected_ids = {c.chunk_id for c in retriever.chunks
                                if c.mapping_id in case['expected_mapping_ids']}
                result['answer_expected_passage'] = any(
                    c.get('chunk_id') in expected_ids for c in turn.get('citations', []))
                result['answer_qualifications_ok'] = all(
                    term.casefold() in turn['question'].casefold() for term in case['required_terms'])
                result['answer_safe'] = (result['answer_expected_passage']
                                         and result['answer_qualifications_ok']
                                         if case['expected_mapping_ids']
                                         else not result['answer_has_citations'])
        results.append(result)
    summaries = {}
    for mode in ('lexical', 'vector'):
        if mode == 'vector' and provider is None:
            continue
        evaluated = [r for r in results if mode in r]
        positives = [r for r in evaluated if r['kind'] in {'answerable', 'combined'}]
        negatives = [r for r in evaluated if r['kind'] in {'excluded', 'unrelated'}]
        hits = sum(r[mode]['hit'] for r in positives)
        latencies = [r[mode]['elapsed_ms'] for r in evaluated]
        summaries[mode] = {
            'answerable_count': len(positives), 'top_three_hits': hits,
            'recall_at_three': round(hits / len(positives), 4),
            'negative_count': len(negatives), 'negative_rejections': sum(r[mode]['hit'] for r in negatives),
            'qualifications_ok': all(r[mode]['qualifications_ok'] for r in evaluated),
            'citations_ok': all(r[mode]['citations_ok'] for r in evaluated),
            'latency_p50_ms': round(float(np.percentile(latencies, 50)), 3),
            'latency_p95_ms': round(float(np.percentile(latencies, 95)), 3),
            'provider_failures': sum('failure_category' in r[mode] for r in evaluated),
        }
        summaries[mode]['gates_passed'] = (
            summaries[mode]['recall_at_three'] >= .9
            and summaries[mode]['negative_rejections'] == len(negatives)
            and summaries[mode]['qualifications_ok'] and summaries[mode]['citations_ok'])
    provenance = json.loads((config.vector_path / 'sources.json').read_text())
    routing_ok = all(r['routing_ok'] for r in results)
    answer_ok = all(r.get('state_preserved', True) and r.get('answer_safe', True)
                    and r.get('answer_qualifications_ok', True) for r in results)
    return {
        'schema_version': 1, 'build_id': retriever.index.build_id,
        'label_basis': labels['label_basis'], 'vector_evaluated': provider is not None,
        'embedding': retriever.index.manifest['embedding'],
        'measurement': {'index_load_ms': round(load_ms, 3), 'load_peak_traced_bytes': peak_bytes,
                        'matrix_bytes': retriever.index.embeddings.nbytes,
                        'note': 'Warm Python process; traced allocations include index validation. Latency includes query API time for vectors.'},
        'corpus_exclusions': [{ 'section': s['section'], 'notes': s['exclusions_and_review_notes']}
                              for s in provenance['sections']],
        'summary': summaries, 'routing_ok': routing_ok, 'deterministic_answers_ok': answer_ok,
        'acceptance_passed': provider is not None and routing_ok and answer_ok
                             and all(s['gates_passed'] for s in summaries.values()),
        'cases': results,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--real-provider', action='store_true', help='Embed synthetic questions using configured API; incurs usage')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    load_dotenv(REPOSITORY_ROOT / '.env', override=False)
    # Disable optional answer/intent providers; only --real-provider makes API calls.
    for name in ('OPENAI_INTENT_CLASSIFICATION_ENABLED', 'OPENAI_PREFERENCE_EXTRACTION_ENABLED',
                 'OPENAI_GROUNDED_EXPLANATIONS_ENABLED', 'OPENAI_WEB_RAG_ANSWERS_ENABLED'):
        os.environ[name] = 'false'
    try:
        config = get_general_knowledge_config()
        labels = json.loads(LABELS.read_text())
        provider = OpenAIEmbeddingProvider(config) if args.real_provider else None
        report = evaluate(config, labels, provider=provider)
        if args.output:
            args.output.write_bytes(json_bytes(report))
        print(json_bytes({key: report[key] for key in ('summary', 'routing_ok', 'deterministic_answers_ok', 'acceptance_passed')}).decode())
        return 0 if report['acceptance_passed'] else 1
    except Exception as error:
        print('Parent-guide evaluation failed: ' + type(error).__name__)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
