"""Evaluation gates must expose failures rather than credit a fallback or wrong passage."""

from copy import deepcopy
from dataclasses import replace
import json
import os
import unittest
from unittest.mock import Mock, patch


from SystemCode.src.backend.pipeline.general_knowledge_config import GeneralKnowledgeConfig
from SystemCode.src.backend.pipeline.parent_guide_embeddings import EmbeddingBatch, EmbeddingSettings
from SystemCode.src.backend.pipeline.parent_guide_retrieval import ParentGuideRetriever
from SystemCode.src.backend.scripts.evaluate_parent_guide import (
    LABELS, evaluate, score_evidence, selected_tools, vector_search,
)


class ParentGuideEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'OPENAI_INTENT_CLASSIFICATION_ENABLED': 'false',
                                         'OPENAI_PREFERENCE_EXTRACTION_ENABLED': 'false',
                                         'OPENAI_WEB_RAG_ANSWERS_ENABLED': 'false'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.config = GeneralKnowledgeConfig()
        self.labels = json.loads(LABELS.read_text())
        self.retriever = ParentGuideRetriever(replace(self.config, mode='lexical'))
        self.provider = Mock(settings=EmbeddingSettings.from_config(self.config))

    def test_all_sections_and_approved_mappings_have_fixed_labels(self):
        cases = self.labels['cases']
        self.assertEqual({c['section'] for c in cases if c['section']}, set(range(1, 12)))
        self.assertEqual(len({c['case_id'] for c in cases}), len(cases))
        self.assertEqual({m for c in cases for m in c['expected_mapping_ids']},
                         {c.mapping_id for c in self.retriever.chunks})
        self.assertTrue(all(c['acceptable_answer'] for c in cases))

    def test_vector_evaluation_does_not_credit_lexical_fallback(self):
        # Deterministic double tests the scorer, not semantic retrieval quality.
        chunk = next(c for c in self.retriever.chunks if c.mapping_id == 'montessori-emphasis')
        self.provider.embed.return_value = EmbeddingBatch(
            [self.retriever.index.embeddings[chunk.matrix_row]], self.provider.settings.model)
        case = next(c for c in self.labels['cases'] if c['case_id'] == 'montessori')
        matches = vector_search(self.retriever, self.provider, case['question'])
        self.assertTrue(score_evidence(case, matches, self.retriever.chunks)['hit'])
        self.provider.embed.return_value = EmbeddingBatch([[0] * 1536], self.provider.settings.model)
        with self.assertRaises(ValueError):
            vector_search(self.retriever, self.provider, case['question'])
        # Lexical retrieval could answer, but invalid vectors remain failed evaluations.
        self.assertTrue(self.retriever.search(case['question']))
        report = evaluate(self.config, {**self.labels, 'cases': [case]}, provider=self.provider)
        self.assertEqual(report['summary']['vector']['provider_failures'], 1)
        self.assertEqual(report['summary']['vector']['top_three_hits'], 0)
        self.assertFalse(report['acceptance_passed'])

    def test_wrong_source_missing_qualification_and_citation_mutation_fail(self):
        case = next(c for c in self.labels['cases'] if c['case_id'] == 'work-exception')
        matches = self.retriever.search(case['question'])
        self.assertTrue(score_evidence(case, matches, self.retriever.chunks)['qualifications_ok'])
        changed = [m.model_copy(update={'text': 'All parents qualify.'}) for m in matches]
        self.assertFalse(score_evidence(case, changed, self.retriever.chunks)['qualifications_ok'])
        altered = deepcopy(matches)
        altered[0].citation.url = 'https://example.org/unsupported'
        self.assertFalse(score_evidence(case, altered, self.retriever.chunks)['citations_ok'])
        wrong = self.retriever.search('What is Montessori?')
        self.assertFalse(score_evidence(case, wrong, self.retriever.chunks)['hit'])

    def test_routing_contracts_keep_non_guidance_away_from_general_tool(self):
        self.assertEqual(selected_tools('What is the fee for this selected centre?',
                                        'ask_selected_school_evidence'), ['query_structured_school_facts'])
        self.assertEqual(selected_tools('Change my budget to $800', 'update_preferences'), ['update_preferences'])
        self.assertEqual(selected_tools('Does this centre use Montessori?', 'ask_selected_school_evidence'),
                         ['search_selected_school_evidence'])

    def test_broader_routing_variants_preserve_preference_and_school_scope(self):
        from SystemCode.src.backend.pipeline.stage1.intent_router import classify_intent
        for question in ('Explain ECDA services', 'Who runs the Anchor Operators?',
                         'What does DS-LS mean?', 'What is P1 admission priority?'):
            self.assertEqual(classify_intent(question).intent, 'ask_general_knowledge')
        for question in ('How can I fix a leaking tap?', 'Write a travel itinerary'):
            self.assertEqual(classify_intent(question).intent, 'needs_clarification')
        self.assertEqual(classify_intent('I prefer SPARK centres').intent, 'update_preferences')
        self.assertEqual(classify_intent('Does this centre have SPARK accreditation?').intent,
                         'ask_selected_school_evidence')

    def test_report_exposes_actual_failures_and_offline_is_incomplete(self):
        report = evaluate(self.config, self.labels)
        self.assertFalse(report['vector_evaluated'])
        self.assertFalse(report['acceptance_passed'])
        self.assertFalse(report['automated_evaluation_passed'])
        self.assertFalse(report['independent_answer_review_completed'])
        self.assertEqual(len(report['corpus_exclusions']), 11)
        self.assertGreater(report['measurement']['matrix_bytes'], 0)
        self.assertEqual(report['summary']['lexical']['negative_rejections'], 7)
        self.assertTrue(report['routing_ok'])
        self.assertTrue(report['deterministic_answers_ok'])
        self.assertTrue(report['summary']['lexical']['gates_passed'])
