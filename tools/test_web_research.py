"""Stdlib synthetic evidence tests; no real website claims, network, or models."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.web_research import WebResearchError, evidence_paths, main, validate_bundle


class WebEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic_web_evidence_'); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); (self.base/'source.txt').write_text('SYNTHETIC TEST FIXTURE ONLY: object 10 x 20 x 30 cm. Not a retrieved web result.', encoding='utf-8')
        self.bundle = dict(schema='real2sim.web-research/1', queries=[dict(id='q1', query='synthetic fixture query')],
            sources=[dict(id='s1',url='https://synthetic.example.invalid/item', title='SYNTHETIC fixture', publisher='SYNTHETIC fixture',
                retrieved_at='2026-09-30T00:00:00Z', snapshot_path='source.txt', snapshot_sha256=hashlib.sha256((self.base/'source.txt').read_bytes()).hexdigest(), type='manufacturer')],
            objects=[dict(object_id='fixture_box',identity_match='exact_product', unresolved=[], priors=[dict(parameter='dimensions',value=[10,20,30],unit='cm',axis_order=['width','depth','height'], source_id='s1',dimension_kind='object',status='sourced_prior',uncertainty_fraction=.1,claim_locator='Synthetic first line')])])

    def validate(self):return validate_bundle(self.bundle,self.base)
    def prior(self):return self.bundle['objects'][0]['priors'][0]
    def test_unit_and_axis_normalization(self):
        self.prior().update(value=[300,100,200],unit='mm',axis_order=['height','width','depth'])
        row=self.validate()['model_priors'][0];self.assertEqual(row['dimensions_m'],[.1,.2,.3]);self.assertEqual(row['source_status'],'prior_not_instance_measurement')
    def test_shipping_retained_not_promoted(self):
        self.prior()['dimension_kind']='shipping_package';report=self.validate()
        self.assertEqual(report['model_priors'],[]);self.assertIsNone(report['objects'][0]['priors'][0]['dimensions_m'])
    def test_shipping_cannot_supply_derived_object_dimensions(self):
        self.prior().update(dimension_kind='shipping_package',dimensions_m=[.1,.2,.3])
        with self.assertRaises(WebResearchError):self.validate()
    def test_unknown_identity_never_promoted(self):
        self.bundle['objects'][0].update(identity_match='unknown',unresolved=['Cannot identify instance'])
        report=self.validate();self.assertEqual(report['model_priors'],[]);self.assertIsNone(report['objects'][0]['priors'][0]['dimensions_m'])
    def test_unknown_requires_reason(self):
        self.bundle['objects'][0]['identity_match']='unknown'
        with self.assertRaises(WebResearchError):self.validate()
    def test_explicit_null_tolerance_requires_note_not_invented_number(self):
        self.prior()['uncertainty_fraction']=None
        with self.assertRaises(WebResearchError):self.validate()
        self.prior()['uncertainty_note']=''
        with self.assertRaises(WebResearchError):self.validate()
        self.prior()['uncertainty_note']='Synthetic source does not state manufacturing tolerance.'
        row=self.validate()['model_priors'][0]
        self.assertIsNone(row['uncertainty_fraction']);self.assertEqual(row['uncertainty_status'],'unquantified')
        self.prior().pop('uncertainty_fraction')
        with self.assertRaises(WebResearchError):self.validate()
    def detail(self):
        return dict(parameter='body_material',value='Synthetic cardboard construction statement',source_id='s1',
            status='sourced_prior',claim_locator='Synthetic text fixture',uncertainty_note='Not verified on the photographed instance')
    def test_details_transferred_with_explicit_prior_status(self):
        self.bundle['objects'][0]['details']=[self.detail()]
        report=self.validate();self.assertEqual(len(report['model_details']),1)
        row=report['model_details'][0];self.assertEqual(row['object_id'],'fixture_box');self.assertEqual(row['identity_match'],'exact_product')
        self.assertEqual(row['source_status'],'prior_not_instance_measurement');self.assertTrue(row['model_eligible'])
    def test_unknown_details_retained_but_never_promoted(self):
        self.bundle['objects'][0].update(identity_match='unknown',unresolved=['Cannot identify instance'],details=[self.detail()])
        report=self.validate();self.assertEqual(report['model_details'],[])
        row=report['objects'][0]['details'][0];self.assertFalse(row['model_eligible']);self.assertEqual(row['value'],self.detail()['value'])
    def test_conflicting_expo_dimensions_cannot_be_promoted_via_text_detail(self):
        obj=self.bundle['objects'][0];obj['object_id']='expo_marker'
        second=copy.deepcopy(self.prior());second['value']=[11,20,30];obj['priors'].append(second)
        report=self.validate()
        self.assertEqual(report['model_priors'],[])
        self.assertEqual(report['conflicts'][0]['object_id'],'expo_marker')
        for name in ['dimensions','DIMENSIONS',' Dimensions ','\tDiMeNsIoNs\n']:
            with self.subTest(parameter=name):
                obj['details']=[dict(self.detail(),parameter=name,value='Synthetic dimension claim that must remain blocked')]
                with self.assertRaisesRegex(WebResearchError,'reserved for numeric priors'):
                    self.validate()
    def test_detail_missing_source_fields_and_numeric_value_rejected(self):
        for field,value in [('source_id','missing'),('claim_locator',''),('uncertainty_note',''),('parameter',''),('value',12),('status','measured')]:
            with self.subTest(field=field):
                self.bundle['objects'][0]['details']=[dict(self.detail(),**{field:value})]
                with self.assertRaises(WebResearchError):self.validate()
    def test_category_remains_a_prior(self):
        self.bundle['objects'][0]['identity_match']='category'
        row=self.validate()['model_priors'][0];self.assertEqual(row['identity_match'],'category');self.assertEqual(row['source_status'],'prior_not_instance_measurement')
    def test_all_conflicting_values_retained_none_selected(self):
        second=copy.deepcopy(self.prior());second['value']=[10,20,40];self.bundle['objects'][0]['priors'].append(second)
        report=self.validate();self.assertEqual(report['model_priors'],[]);self.assertEqual(len(report['objects'][0]['priors']),2);self.assertEqual(len(report['conflicts']),1)
    def test_snapshot_drift(self):
        (self.base/'source.txt').write_text('Changed synthetic evidence')
        with self.assertRaises(WebResearchError):self.validate()
    def test_paths_reject_traversal_absolute_and_windows_escape(self):
        for path in ['../source.txt','/tmp/source.txt','C:/source.txt','C:source.txt','..\\source.txt']:
            with self.subTest(path=path):
                self.bundle['sources'][0]['snapshot_path']=path
                with self.assertRaises(WebResearchError):self.validate()
                with self.assertRaises(WebResearchError):evidence_paths(self.bundle,self.base)
    def test_evidence_paths_include_missing_for_fingerprint(self):
        self.bundle['sources'][0]['snapshot_path']='missing.txt'
        self.assertEqual(evidence_paths(self.bundle,self.base),[self.base/'missing.txt'])
        with self.assertRaises(WebResearchError):self.validate()
    def test_source_reference_required(self):
        self.prior()['source_id']='missing'
        with self.assertRaises(WebResearchError):self.validate()
    def test_query_and_source_limits(self):
        for limits in [dict(max_queries=0),dict(max_sources=0),dict(max_queries=True),dict(max_sources=-1),dict(max_queries=101)]:
            with self.subTest(limits=limits),self.assertRaises(WebResearchError):validate_bundle(self.bundle,self.base,**limits)
    def test_invalid_numeric_units_axes_and_status(self):
        original=copy.deepcopy(self.prior())
        for field,value in [('unit','inch'),('axis_order',['width','width','height']),('value',[1,2,float('nan')]),('value',[1,2,float('inf')]),('value',[1,0,3]),('value',[1,True,3]),('uncertainty_fraction',-.1),('uncertainty_fraction',float('inf')),('status','measured'),('dimension_kind','unspecified'),('claim_locator','')]:
            with self.subTest(field=field,value=value):
                self.bundle['objects'][0]['priors']=[dict(original,**{field:value})]
                with self.assertRaises(WebResearchError):self.validate()
    def test_invalid_source_provenance(self):
        original=copy.deepcopy(self.bundle['sources'][0])
        for field,value in [('url','http://example.invalid'),('url','https://user:secret@example.invalid'),('url','https:///missing'),('retrieved_at','2026-09-30'),('type','invented'),('publisher',''),('snapshot_sha256','bad')]:
            with self.subTest(field=field,value=value):
                self.bundle['sources']=[dict(original,**{field:value})]
                with self.assertRaises(WebResearchError):self.validate()
    def test_duplicate_source_or_object_ids(self):
        for key in ['sources','objects','queries']:
            with self.subTest(key=key):
                bad=copy.deepcopy(self.bundle);bad[key].append(copy.deepcopy(bad[key][0]))
                with self.assertRaises(WebResearchError):validate_bundle(bad,self.base)
    def test_binary_snapshot(self):
        raw=b'fixture\x00binary';(self.base/'source.txt').write_bytes(raw);self.bundle['sources'][0]['snapshot_sha256']=hashlib.sha256(raw).hexdigest()
        with self.assertRaises(WebResearchError):self.validate()
    def test_malformed_nested_fields_fail_as_validation_error(self):
        for field,value in [('unit',[]),('source_id',{}),('axis_order',None)]:
            with self.subTest(field=field):
                bad=copy.deepcopy(self.bundle);bad['objects'][0]['priors'][0][field]=value
                with self.assertRaises(WebResearchError):validate_bundle(bad,self.base)
    def test_cli_missing_invalid_and_valid(self):
        bundle_path=self.base/'web_research.json';packet_path=self.base/'packet.json';out=self.base/'out'
        packet=dict(output_directory=str(out),input_artifacts={},parameters=dict(max_queries=1,max_sources=1))
        packet_path.write_text(json.dumps(packet));self.assertEqual(main(packet_path)['status'],'needs_input')
        bundle_path.write_text(json.dumps(self.bundle));record=dict(path=str(bundle_path),sha256='0'*64)
        packet['input_artifacts']={'agent_identify':[record]};packet_path.write_text(json.dumps(packet))
        self.assertEqual(main(packet_path)['status'],'needs_input')
        record['sha256']=hashlib.sha256(bundle_path.read_bytes()).hexdigest();packet_path.write_text(json.dumps(packet))
        self.assertEqual(main(packet_path)['status'],'needs_input')  # Snapshot exists but was not delivered.
        snapshot=dict(path=str(self.base/'source.txt'),sha256=self.bundle['sources'][0]['snapshot_sha256'])
        packet['input_artifacts']['agent_identify'].append(snapshot);packet_path.write_text(json.dumps(packet))
        self.assertEqual(main(packet_path)['status'],'complete')
        report=json.loads((out/'web_research_report.json').read_text());self.assertEqual(len(report['model_priors']),1)
        snapshot['sha256']='0'*64;packet_path.write_text(json.dumps(packet))
        self.assertEqual(main(packet_path)['status'],'needs_input')  # Correct source hash in bundle is insufficient.
        snapshot['sha256']=self.bundle['sources'][0]['snapshot_sha256']
        packet['input_artifacts']['agent_identify'].pop();packet_path.write_text(json.dumps(packet))
        self.assertEqual(main(packet_path)['status'],'needs_input')  # Previously accepted snapshot artifact was lost.


if __name__=='__main__':unittest.main(verbosity=2)
