"""Configured retrieval across service, supervisor and deterministic fallbacks."""
from copy import deepcopy
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from SystemCode.src.backend.agents.contracts import GeneralKnowledgeEvidence
from SystemCode.src.backend.agents.supervisor import _tools_for_intent
from SystemCode.src.backend.pipeline.general_knowledge_config import DEFAULT_VECTOR_PATH, GeneralKnowledgeConfig
from SystemCode.src.backend.pipeline.parent_guide_embeddings import EmbeddingBatch, EmbeddingSettings
from SystemCode.src.backend.repositories.parent_guide_index import load_active_index
from SystemCode.src.backend.services.preference_service import PreferenceService
from SystemCode.src.backend.tests.test_conversation_supervisor import SequencedModel, route, tool_calls
from SystemCode.src.backend.tests.test_general_knowledge_rag import SCHOOL_INDEX
from stage1.intent_router import classify_intent


class ParentGuideServiceTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "GENERAL_KNOWLEDGE_RETRIEVAL_MODE": "vector",
            "CONVERSATION_AGENT_MODE": "deterministic",
            "OPENAI_INTENT_CLASSIFICATION_ENABLED": "false",
            "OPENAI_PREFERENCE_EXTRACTION_ENABLED": "false",
            "OPENAI_GROUNDED_EXPLANATIONS_ENABLED": "false",
            "OPENAI_WEB_RAG_ANSWERS_ENABLED": "false",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.index = load_active_index(DEFAULT_VECTOR_PATH)
        self.provider = Mock(settings=EmbeddingSettings.from_config(GeneralKnowledgeConfig()))
        self.provider_patch = patch(
            "SystemCode.src.backend.pipeline.parent_guide_retrieval.OpenAIEmbeddingProvider",
            return_value=self.provider,
        )
        self.provider_patch.start()
        self.addCleanup(self.provider_patch.stop)
        self.schools = Mock(catalogue_version="test")
        self.schools.facet_summary.return_value = {}
        self.schools.get_many.return_value = [{"school_id": "S1", "name": "Test School"}]
        self.service = PreferenceService(self.schools, Mock(), Mock(), Path('.'))
        self.service._resources = Mock(return_value=(SCHOOL_INDEX, None))
        self.profile = {"preferences": {"pedagogy": {"value": "Montessori"}}}

    def target(self, mapping):
        chunk = next(c for c in self.index.chunks if c.mapping_id == mapping)
        self.provider.embed.return_value = EmbeddingBatch(
            [self.index.embeddings[chunk.matrix_row]], self.provider.settings.model,
        )
        return chunk

    def handle(self, message, selected=None):
        return self.service.handle(
            message=message, profile=deepcopy(self.profile), selected_school_ids=selected or [],
            eligible_school_ids=[], excluded_school_ids=[], family=None, home_postal_code=None,
        )

    def test_deterministic_vector_guidance_reuses_loaded_index_and_preserves_state(self):
        chunk = self.target('additional-subsidy-2027-table')
        with patch('SystemCode.src.backend.pipeline.parent_guide_retrieval.load_active_index', wraps=load_active_index) as load:
            for _ in range(2):
                result = self.handle('How do subsidy thresholds change in 2027?')
                self.assertIn(chunk.text, result['question'])
                self.assertIn('Policy period: 2027', result['question'])
                self.assertEqual(result['profile']['preferences'], self.profile['preferences'])
                self.assertEqual(result['citations'][0]['url'], chunk.citation['url'])
                self.assertEqual(result['citations'][0]['retrieved_at'], chunk.source_verified_at)
                self.assertEqual(result['evidence_scope'], 'general')
            load.assert_called_once()
        self.assertEqual(self.provider.embed.call_count, 2)

    def test_registered_general_tool_retrieves_vectors_in_supervisor(self):
        from SystemCode.src.backend.agents.supervisor import create_conversation_supervisor_graph
        chunk = self.target('montessori-emphasis')
        context = self.service.build_conversation_context(
            message='What is Montessori?', profile=self.profile, selected_school_ids=[],
            eligible_school_ids=[], excluded_school_ids=[], family=None, home_postal_code=None,
            intent=classify_intent('What is Montessori?'),
        )
        tools = self.service._conversation_tools(context)
        model = SequencedModel([
            route('general_knowledge', 'ask_general_knowledge'),
            tool_calls(('search_general_knowledge', {})),
            tool_calls(('generated_conversation_answer', {
                'answer': chunk.text[:700], 'citation_ids': [chunk.chunk_id],
            })),
        ])
        result = create_conversation_supervisor_graph(context, tools, model=model).invoke({})
        self.assertEqual(result['termination_reason'], 'completed')
        self.assertEqual(result['tool_calls'], 1)
        self.assertIn(chunk.chunk_id, [c.citation_id for c in result['tool_results'][0].citations])
        self.provider.embed.assert_called_once()

    def test_agent_setup_failure_uses_same_grounded_deterministic_boundary(self):
        chunk = self.target('cda-current-benefits')
        self.service._run_conversation_agent = Mock(side_effect=RuntimeError('private'))
        with patch.dict(os.environ, {'CONVERSATION_AGENT_MODE': 'agent'}):
            result = self.handle('What is CDA used for?')
        self.assertEqual(result['answer_method'], 'deterministic_fallback')
        self.assertIn(chunk.text, result['question'])
        self.assertNotIn('private', str(result))
        self.provider.embed.assert_called_once()

    def test_timeout_fallback_and_excluded_material(self):
        self.provider.embed.side_effect = TimeoutError('private')
        result = self.handle('What is Montessori?')
        self.assertTrue(result['citations'])
        self.assertEqual(self.service._general_retriever.status.mode, 'lexical')
        for question in ['Can parents watch the CCTV livestream?', 'Does a waitlist guarantee a place?']:
            result = self.handle(question)
            self.assertEqual(result['evidence_scope'], 'unavailable')
            self.assertFalse(result['citations'])

    def test_combined_evidence_preserves_scopes(self):
        self.target('montessori-emphasis')
        result = self.handle('Does this school use play-based learning, and what is Montessori?', ['S1'])
        self.assertEqual(result['status'], 'combined_evidence')
        self.assertEqual({c['evidence_scope'] for c in result['citations']}, {'school', 'general'})
        self.assertIn('School evidence:', result['question'])
        self.assertIn('General guidance:', result['question'])

    def test_preferences_calculations_and_school_facts_make_no_vector_calls(self):
        for question in ['Change my budget to $800', 'What if my income is $4000?',
                         'What is the fee for this selected centre?']:
            intent = classify_intent(question)
            context = self.service.build_conversation_context(
                message=question, profile=self.profile, selected_school_ids=[], eligible_school_ids=[],
                excluded_school_ids=[], family=None, home_postal_code=None, intent=intent,
            )
            allowed = _tools_for_intent(context, self.service._conversation_tools(context))
            self.assertNotIn('search_general_knowledge', [tool.name for tool in allowed])
        self.handle('Change my budget to $800')
        self.provider.embed.assert_not_called()

    def test_invalid_configuration_falls_back_to_curated_without_loading_vectors(self):
        with patch.dict(os.environ, {'GENERAL_KNOWLEDGE_TIMEOUT_SECONDS': 'invalid'}):
            result = self.handle('What is Montessori?')
        self.assertFalse(result['citations'])
        self.provider.embed.assert_not_called()

    def test_deterministic_retrieval_preserves_non_authoritative_classification(self):
        from stage1.conversation import update_conversation
        chunk = self.target('montessori-emphasis')
        item = self.service._knowledge_retriever(None).search('What is Montessori?')[0]
        item = GeneralKnowledgeEvidence.model_validate({**item.model_dump(), 'evidence_category': 'unknown'})
        result = update_conversation(self.profile, 'What is Montessori?',
                                     classified_intent=classify_intent('What is Montessori?'),
                                     general_retriever=Mock(search=Mock(return_value=[item])))
        self.assertEqual(result['evidence_category'], 'unknown')
        self.assertIn(chunk.text, result['question'])

    def test_broader_guide_questions_route_without_changing_preferences(self):
        for question in ['When is preschool registration?', 'How do I enrol my child?',
                         'How does EIPIC support children?', 'What are AOP fee caps in 2026?',
                         'Can parents watch the CCTV livestream?', 'Does a waitlist guarantee a place?',
                         'What changes in 2027?', 'What is CDA used for?']:
            with self.subTest(question=question):
                self.assertEqual(classify_intent(question).intent, 'ask_general_knowledge')
        self.assertEqual(classify_intent('I prefer a preschool with CCTV').intent, 'update_preferences')
