"""Native opt-in DAG/acceptance/cache tests with explicitly synthetic evidence."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.core import Workflow,atomic_json
from r2s.contracts import ContractError
from r2s.profiles import LEGACY,stages_for
from r2s.web_integration import check_consumption
import cv2
import numpy as np

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

class NativeWebTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='synthetic_native_web_');self.addCleanup(self.temp.cleanup)
        self.case=Path(self.temp.name);self.source=self.case/'synthetic.png'
        cv2.imwrite(str(self.source),np.zeros((48,64,3),np.uint8))
        cfg={'id':'SYNTHETIC-native-web','mode':'single','formal_test':False,'workflow_profile':'quality_v2',
             'inputs':[{'path':str(self.source)}],'web_research':{'max_queries':2,'max_sources':2}}
        atomic_json(self.case/'case.json',cfg);self.w=Workflow(self.case)
    def accept(self,name,artifacts,parameters=None):
        directory=Path(self.w.state['stages'][name]['directory'])
        for name_,value in artifacts.items():
            path=directory/name_;path.parent.mkdir(parents=True,exist_ok=True)
            if isinstance(value,str):path.write_text(value,encoding='utf-8')
            else:atomic_json(path,value)
        response={'status':'complete','artifacts':list(artifacts),'evidence':['SYNTHETIC fixture only'],
                  'reasoning_summary':'SYNTHETIC contract test; not research evidence','parameters':parameters or {}}
        path=directory/'submitted.json';atomic_json(path,response);return self.w.accept(name,path)
    def gate(self):
        self.assertEqual(self.w.run()['stage'],'agent_observe')
        self.accept('agent_observe',{'observation.json':{'fixture':'SYNTHETIC'},'furniture_observation.json':{
            'source_sha256':sha(self.source),'acceptance_before_fit':True,'targets':[],
            'no_applicable_furniture_reason':'Synthetic gate fixture has no furniture'}})
        self.assertEqual(self.w.run()['stage'],'agent_identify')
        text='SYNTHETIC TEST SOURCE: cardboard box 10 x 20 x 30 mm.'
        bundle={'schema':'real2sim.web-research/1','queries':[{'id':'q1','query':'synthetic test query'}],
          'sources':[{'id':'s1','url':'https://synthetic.example.invalid/box','title':'SYNTHETIC',
             'publisher':'SYNTHETIC','type':'manufacturer','retrieved_at':'2026-09-30T00:00:00Z',
             'snapshot_path':'source.txt','snapshot_sha256':hashlib.sha256(text.encode()).hexdigest()}],
          'objects':[{'object_id':'synthetic_box','identity_match':'family','unresolved':['Synthetic instance'],
             'priors':[{'parameter':'dimensions','value':[10,20,30],'unit':'mm','axis_order':['width','depth','height'],
               'source_id':'s1','dimension_kind':'object','status':'sourced_prior','claim_locator':'Synthetic first line',
               'uncertainty_fraction':None,'uncertainty_note':'No real-world tolerance in test fixture'}]}]}
        self.accept('agent_identify',{'web_research.json':bundle,'source.txt':text})
        self.assertEqual(self.w.run(until='validate_web_research')['status'],'completed_until')
        artifact=self.w.state['stages']['validate_web_research']['outputs'][0]
        return artifact
    def test_unconfigured_and_disabled_dags_unchanged(self):
        self.assertEqual(stages_for({}),list(LEGACY))
        base={'workflow_profile':'quality_v2'}
        self.assertEqual(stages_for(base),stages_for(dict(base,web_research={'enabled':False})))
        self.assertNotIn('validate_web_research',{n for n,_,_ in stages_for(base)})
    def test_optin_dependency_order(self):
        graph={n:d for n,d,_ in self.w.stages};names=[n for n,_,_ in self.w.stages]
        self.assertLess(names.index('agent_identify'),names.index('validate_web_research'))
        for n in ['agent_calibrate','agent_calibrate_room','agent_model','agent_materials']:
            self.assertIn('validate_web_research',graph[n])
        self.assertFalse(self.w.stage_map['validate_web_research'][1])
    def test_invalid_profile_and_budget(self):
        for cfg in [{'web_research':{}},{'workflow_profile':'quality_v2','web_research':True},
                    {'workflow_profile':'quality_v2','web_research':{'max_queries':101}},
                    {'workflow_profile':'quality_v2','web_research':{'enabled':1}}]:
            with self.subTest(cfg=cfg),self.assertRaises(ValueError):stages_for(cfg)
    def test_web_and_generation_dags_compose_without_cycle(self):
        root=self.case/'synthetic_skills'
        for name in ['blender-roomkit','pi3x-scene-reference','real2sim-local-refine']:
            path=root/name/'SKILL.md';path.parent.mkdir(parents=True);path.write_text('SYNTHETIC inventory fixture for DAG validation only')
        cfg=copy.deepcopy(self.w.config);cfg['generation_skills']={'skills_root':str(root),'reference':{'mode':'disabled'}}
        stages=stages_for(cfg);seen=set()
        for name,deps,agent in stages:
            self.assertTrue(set(deps)<=seen,(name,deps,seen));seen.add(name)
        graph={name:deps for name,deps,_ in stages}
        self.assertIn('scene_reference',graph['agent_calibrate'])
        self.assertIn('validate_web_research',graph['agent_calibrate'])
        self.assertIn('local_geometry_feedback',graph['agent_review_geometry'])
    def test_actual_executable_stage_and_accepted_consumption(self):
        artifact=self.gate();self.assertTrue(self.w.valid('validate_web_research'))
        self.assertEqual(self.w.execute('validate_web_research'),'cached')
        self.assertEqual(self.w.execute('agent_calibrate'),'awaiting_agent')
        parameter={'web_research_consumption':{'report_sha256':artifact['sha256'],
            'used_priors':[{'object_id':'synthetic_box','parameter':'dimensions','application':'Synthetic camera scale prior'}]}}
        self.accept('agent_calibrate',{'calibration.json':{'scope':'SYNTHETIC fixture'}},parameter)
        self.assertTrue(self.w.valid('agent_calibrate'))
    def test_missing_and_wrong_consumption_rejected(self):
        artifact=self.gate()
        for response in [{},{'parameters':{'web_research_consumption':{'report_sha256':'0'*64,'used_priors':[],'unconsumed_reason':'test'}}},
             {'parameters':{'web_research_consumption':{'report_sha256':artifact['sha256'],'used_priors':[{'object_id':'unknown','parameter':'dimensions','application':'test'}]}}}]:
            with self.subTest(response=response),self.assertRaises(ContractError):check_consumption(self.w,'agent_model',response)
        check_consumption(self.w,'agent_materials',{'parameters':{'web_research_consumption':{
            'report_sha256':artifact['sha256'],'used_priors':[],'unconsumed_reason':'Synthetic source does not justify material optics'}}})
    def test_tampered_detail_namespace_cannot_enable_conflicting_dimensions(self):
        artifact=self.gate();path=Path(artifact['path']);report=json.loads(path.read_text())
        report['model_priors']=[]
        report['model_details']=[{'object_id':'synthetic_box','parameter':'dimensions','value':'unverified text'}]
        atomic_json(path,report);artifact['sha256']=sha(path)
        response={'parameters':{'web_research_consumption':{'report_sha256':artifact['sha256'],
            'used_priors':[{'object_id':'synthetic_box','parameter':'dimensions','application':'Synthetic attack fixture'}]}}}
        with self.assertRaises(ContractError):check_consumption(self.w,'agent_model',response)
    def test_snapshot_mutation_invalidates_gate_and_downstream(self):
        self.gate();before=self.w.fingerprint('validate_web_research')
        path=Path(self.w.state['stages']['agent_identify']['directory'])/'source.txt'
        path.write_text('MUTATED SYNTHETIC SOURCE',encoding='utf-8')
        self.assertNotEqual(before,self.w.fingerprint('validate_web_research'))
        self.assertFalse(self.w.valid('agent_identify'));self.assertFalse(self.w.valid('validate_web_research'))
        with self.assertRaises(ContractError):self.w.execute('agent_calibrate')
    def test_budget_change_invalidates_research_not_ingest(self):
        self.gate();before=self.w.fingerprint('agent_identify');ingest_before=self.w.fingerprint('ingest')
        self.w.config['web_research']['max_queries']=3
        self.assertNotEqual(before,self.w.fingerprint('agent_identify'))
        self.assertEqual(ingest_before,self.w.fingerprint('ingest'));self.assertTrue(self.w.valid('ingest'))
    def test_executable_stage_cannot_be_accepted_manually(self):
        self.gate()
        with self.assertRaises(ContractError):self.w.accept('validate_web_research',self.case/'unused.json')
    def test_missing_bundle_halts_calibration(self):
        self.gate();directory=Path(self.w.state['stages']['agent_identify']['directory'])
        self.w.state['stages']['agent_identify']['outputs']=[a for a in self.w.state['stages']['agent_identify']['outputs'] if Path(a['path']).name!='web_research.json']
        self.assertEqual(self.w.execute('validate_web_research',retry=True),'needs_input')
        self.assertFalse(self.w.valid('validate_web_research'))
        with self.assertRaises(ContractError):self.w.execute('agent_calibrate')

if __name__=='__main__':unittest.main()
