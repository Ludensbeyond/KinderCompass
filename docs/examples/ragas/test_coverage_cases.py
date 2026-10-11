"""Coverage contract checks using frozen snapshots and offline replay."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from capture_dataset import composer_evidence
from coverage_cases import capture_conversation, check_capture, validate_input
from score import prepare, read_jsonl
from SystemCode.src.backend.agents import tools as agent_tools
from SystemCode.src.backend.domain.models import FamilyDetails
from SystemCode.src.backend.repositories.school_repository import SchoolRepository
from SystemCode.src.backend.services.evaluation_service import EvaluationService
from SystemCode.src.backend.services.location_service import LocationService
from SystemCode.src.backend.services.preference_service import PreferenceService

ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = Path(__file__).with_name('expanded')


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.cases = read_jsonl(DIRECTORY / 'cases.jsonl')
        self.inputs = read_jsonl(DIRECTORY / 'inputs.jsonl')

    def test_frozen_dataset_complete_labels_and_split(self):
        manifest = json.loads((DIRECTORY / 'manifest.json').read_text())
        self.assertEqual(len(self.cases), 24)
        self.assertEqual(len({c['case_id'] for c in self.cases}), 24)
        self.assertEqual(self.inputs, [{k:c[k] for k in ['case_id','user_input','setup']} for c in self.cases])
        for name, record in manifest['files'].items():
            self.assertEqual(hashlib.sha256((DIRECTORY/name).read_bytes()).hexdigest(), record['sha256'])
        for record in [manifest['evidence_snapshot'], *manifest['supporting_snapshots']]:
            self.assertEqual(hashlib.sha256((ROOT/record['path']).read_bytes()).hexdigest(), record['sha256'])
        self.assertEqual(set(manifest['splits']['tuning']) & set(manifest['splits']['held_out']), set())
        self.assertEqual(len(manifest['splits']['held_out']), 4)
        schools = SchoolRepository(ROOT/'SystemCode/data/processed/kindercompass_master.json')
        index = json.loads((ROOT/'SystemCode/src/backend/output/web_rag_pilot_index.json').read_text())
        original_school_chunks = {chunk['chunk_id']: chunk for page in index['pages'] for chunk in page['chunks']}
        for c, i in zip(self.cases,self.inputs):
            validate_input(i)
            self.assertEqual(c['review']['status'], 'reviewed')
            self.assertTrue(c['reference'].strip())
            for text, source in zip(c['reference_contexts'], c['reference_sources']):
                if source.get('school_id'):
                    original = original_school_chunks[source['chunk_id']]
                    self.assertEqual((text, source['school_id']), (original['text'], original['school_id']))
            for sid in i['setup']['selected_school_ids']:
                self.assertEqual(schools.get(sid).school_id, sid)
            self.assertEqual(c['scored_turn'],len(i['setup']['conversation_history'])+1 if c['evaluation']=='ragas' else None)
        # Clearly synthetic format fixture only, no claim of actual execution.
        prepared, _, behaviour = prepare(self.cases,[{'case_id':c['case_id'],'response':'Synthetic format fixture.','retrieved_contexts':[]} for c in self.cases])
        self.assertEqual((len(prepared),len(behaviour)),(16,8))

    def test_replay_uses_returned_profile_and_stops_on_failure(self):
        i = next(i for i in self.inputs if i['case_id']=='language_confirmed_change')
        original = deepcopy(i); seen=[]
        def execute(service, value, model):
            seen.append(deepcopy(value))
            return {'case_id':value['case_id'],'status':'agent','response':'Answer.', 'retrieved_contexts':[], 'agent_response':{'profile':{'count':len(seen)}}}
        row=capture_conversation(None,i,lambda:None,execute)
        self.assertEqual([v['user_input'] for v in seen],['Chinese is required.','Malay is required.','Use Malay instead.'])
        self.assertEqual([v['setup']['profile'] for v in seen],[{}, {'count':1},{'count':2}])
        self.assertEqual(i,original); self.assertEqual(row['scored_turn'],3)
        failed=capture_conversation(None,i,lambda:None,lambda *a:{'case_id':i['case_id'],'execution_error':{'type':'TestFailure'},'response':'partial','retrieved_contexts':[]})
        self.assertEqual(len(failed['turns']),1);self.assertIsNone(failed['response'])

    def test_real_deterministic_preference_replay_and_fee_oracle(self):
        schools=SchoolRepository(ROOT/'SystemCode/data/processed/kindercompass_master.json')
        evaluation=EvaluationService(schools)
        service=PreferenceService(schools,evaluation,LocationService(schools,ROOT/'SystemCode/data/raw/PreSchoolsLocation.geojson'),ROOT)
        for cid in ['language_confirmed_change','language_pending_confirmation','language_change_then_general','fee_income_explanation']:
            item=next(i for i in self.inputs if i['case_id']==cid)
            row=capture_conversation(service,item,lambda:None)
            self.assertFalse(row.get('execution_error'),row)
            case=next(c for c in self.cases if c['case_id']==cid)
            checks=check_capture(case,row)
            self.assertTrue(checks.get('profile_delta',True),checks)
            if cid=='fee_income_explanation':
                self.assertTrue(checks['exact_fee_transition'],checks)
                fam=FamilyDetails.model_validate(item['setup']['family'])
                for amount,f in [(85,fam),(272,fam.model_copy(update={'gross_household_income':10000}))]:
                    self.assertEqual(evaluation.evaluate(item['setup']['selected_school_ids'],{},f,include_ineligible=True)[0].net_monthly_fee,amount)

    def test_wrong_school_control_preserves_real_provenance(self):
        i=next(i for i in self.inputs if i['case_id']=='wrong_school_transport')
        index=json.loads((ROOT/'SystemCode/src/backend/output/web_rag_pilot_index.json').read_text())
        def execute(service,value,model):
            matches=agent_tools.retrieve(index,'CENTRE:PT9148','transport')
            self.assertEqual(matches[0]['school_id'],'CENTRE:PT9116')
            self.assertIn('Two-way school bus',matches[0]['text'])
            # Exercise the existing tool's identity filter after injection.
            tool = agent_tools.create_selected_school_evidence_tool(index)
            supplied = tool.invoke({'question':'transport', 'school_id':'CENTRE:PT9148',
                                    'school_name':'Star Learners Woodlands Circle'})
            self.assertTrue(all(p.school_id == 'CENTRE:PT9148' for p in supplied))
            return {'case_id':i['case_id'],'status':'agent','response':'Evidence unavailable.','retrieved_contexts':[], 'agent_response':{'profile':{},'citations':[]}}
        row=capture_conversation(None,i,lambda:None,execute)
        case=next(c for c in self.cases if c['case_id']==i['case_id'])
        self.assertTrue(all(check_capture(case,row).values()))
        row['passages']=row['controlled_retrievals']
        self.assertFalse(check_capture(case,row)['wrong_school_filtered'])

    def test_labels_are_rejected_and_transformed_calculation_is_explicit(self):
        with self.assertRaises(ValueError): validate_input(dict(self.inputs[-1],reference='Secret'))
        payload={'tool_name':'run_what_if_scenario','grounding_facts':['{"net_monthly_fee":272}'],'evidence_category':'calculated_estimate','citations':[]}
        _,facts,passages=composer_evidence([{'messages':[{'type':'tool','content':json.dumps(payload)}]}],[])
        self.assertEqual(facts,[passages[0]['text']]);self.assertEqual(passages[0]['basis'],'transformed_tool_fact')


if __name__=='__main__': unittest.main()
