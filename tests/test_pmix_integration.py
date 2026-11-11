"""Real pinned binary integration + adversarial gate and HTTP tests; no skips.

Set LEGION_CAD_EXPERIMENT to the verified WO-CAD-001 extraction directory.
Tests fail if required reference inputs/binary/sandbox are unavailable.
"""
import base64
import copy
import hashlib
import http.client
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from deal_rescue.industrial import pmix_adapter as pmix, cad_bom, workflow
from deal_rescue import server

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = Path(os.environ.get('LEGION_CAD_EXPERIMENT', ROOT/'external/cad-experiment')).resolve()
FIXTURES = EXPERIMENT/'tools/pmix-0.16.1/tests/fixtures'


def raw(name, family='synthetic'):
    return (FIXTURES/family/name).read_bytes()


class PmixIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = raw('assembly_properties.stp')
        cls.extraction = pmix.extract(cls.raw)

    def test_pinned_binary_checksum(self):
        self.assertEqual(hashlib.sha256(pmix._binary().read_bytes()).hexdigest(), pmix.BINARY_SHA256)

    def test_successful_extraction_and_bom_reconciliation(self):
        self.assertEqual({p['part_no']:p['quantity'] for p in self.extraction['bom']},
                         {'SYN-BRACKET':1,'SYN-PIN':2})
        self.assertEqual(sum(p['quantity'] for p in self.extraction['bom']),3)

    def test_explicit_material_by_occurrence(self):
        self.assertEqual({p['part_no']:p['material'] for p in self.extraction['bom']},
                         {'SYN-BRACKET':'SYN-ALLOY-17','SYN-PIN':'SYN-STEEL-4'})

    def test_all_26_reference_steps_parse_in_sandbox(self):
        benchmark=json.loads((EXPERIMENT/'BENCHMARK_RESULTS.json').read_text())
        self.assertEqual(len(benchmark['cases']),26)
        for case in benchmark['cases']:
            with self.subTest(case=case['case']):
                data=(EXPERIMENT/case['source_path']).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(),case['sha256'])
                result=pmix.extract(data)
                self.assertTrue(result['bom'])
                self.assertEqual(result['engineering_verdict'],'Z')
                self.assertFalse(result['checkout_enabled'])

    def test_gdt_dimension_units_source_refs(self):
        x=pmix.extract(raw('nist_ctc_01_asme1_ap242-e1.stp','nist'))
        dims=x['engineering']['semantic']['dimensions']
        dim=next(d for d in dims if '#120' in d['source_refs'])
        self.assertEqual(dim['value'],{'value':35.0,'unit':'mm'})
        self.assertEqual(dim['file_sha256'],x['file_sha256'])
        tol=next(t for t in x['engineering']['semantic']['tolerances'] if '#21' in t['source_refs'])
        self.assertEqual(tol['value']['value'],0.75)

    def test_units_preserved_without_geometry_inference(self):
        x=pmix.extract(raw('plate_one_hole_inches.stp'))
        self.assertTrue(x['units'])
        self.assertEqual(x['assembly']['units']['declared_length'],'in')
        self.assertFalse(x['procurement_eligible'])

    def test_missing_fields_remain_z(self):
        for p in self.extraction['bom']:
            for name in ('revision','process'):
                self.assertIsNone(p[name])
                self.assertEqual(p['fields'][name]['extraction'],'Z')
            self.assertFalse(p['procurement_eligible'])

    def test_critical_field_provenance(self):
        for p in self.extraction['bom']:
            for f in p['fields'].values():
                self.assertEqual(f['file_sha256'],self.extraction['file_sha256'])
                self.assertEqual(f['engineering_verdict'],'Z')
                if f['value'] is not None:self.assertTrue(f['source_refs'])

    def test_revision_difference_preserved(self):
        # Controlled STEP mutation is parsed by pmix, not by adapter string logic.
        data=raw('assembly_two_parts.stp')
        self.assertIn(b"PRODUCT_DEFINITION_FORMATION('A',",data)
        a=pmix.extract(data.replace(b"PRODUCT_DEFINITION_FORMATION('A',",b"PRODUCT_DEFINITION_FORMATION('REV-A',"))
        b=pmix.extract(data.replace(b"PRODUCT_DEFINITION_FORMATION('A',",b"PRODUCT_DEFINITION_FORMATION('REV-B',"))
        self.assertEqual({p['revision'] for p in a['bom']},{'REV-A'})
        self.assertEqual({p['revision'] for p in b['bom']},{'REV-B'})
        self.assertNotEqual(a['file_sha256'],b['file_sha256'])

    def test_malformed_rejected_and_visible(self):
        r=cad_bom.extract('bad.step',b'not a STEP document')
        self.assertEqual(r['extraction'],'Z');self.assertEqual(r['bom'],[])
        self.assertTrue(r['diagnostics'])

    def test_missing_assembly_reference(self):
        product=copy.deepcopy(self.extraction['assembly'])
        product['relations'][0]['child']='part:missing'
        with self.assertRaisesRegex(pmix.PmixError,'ASSEMBLY_PART_NOT_DECLARED'):
            pmix.adapt(self.raw,self.extraction['engineering'],product)

    def test_cycle_rejected(self):
        product=copy.deepcopy(self.extraction['assembly'])
        product['relations'].append(dict(product['relations'][0],parent=product['relations'][0]['child'],child=product['roots'][0]))
        with self.assertRaises(pmix.PmixError):pmix.adapt(self.raw,self.extraction['engineering'],product)

    def test_fabricated_entity_reference_rejected(self):
        product=copy.deepcopy(self.extraction['assembly'])
        product['parts'][0]['source_refs']=['#999999999']
        with self.assertRaisesRegex(pmix.PmixError,'SOURCE_ENTITY_NOT_DECLARED'):
            pmix.adapt(self.raw,self.extraction['engineering'],product)

    def test_diagnostics_and_unsupported_retained(self):
        x=pmix.extract(raw('nist_stc_09_asme1_ap242-e4.stp','nist'))
        self.assertEqual(len(x['engineering']['unknown']),17)
        self.assertEqual(x['engineering_verdict'],'Z')

    def test_missing_binary_fail_closed(self):
        with patch.dict(os.environ,{'LEGION_PMIX_BINARY':'/nonexistent/pmix'}):
            r=cad_bom.extract('x.step',self.raw)
        self.assertEqual(r['extraction'],'Z');self.assertIn('PMIX_BINARY_MISSING',r['diagnostics'][0])

    def test_wrong_checksum_never_executes(self):
        with tempfile.NamedTemporaryFile() as f:
            f.write(b'wrong binary');f.flush()
            with patch.dict(os.environ,{'LEGION_PMIX_BINARY':f.name}),patch.object(subprocess,'Popen') as call:
                r=cad_bom.extract('x.step',self.raw)
                call.assert_not_called()
        self.assertIn('CHECKSUM_MISMATCH',r['diagnostics'][0])

    def test_sandbox_missing_no_fallback(self):
        with patch.object(pmix.shutil,'which',return_value=None):
            r=cad_bom.extract('x.step',self.raw)
        self.assertEqual(r['extraction'],'Z');self.assertIn('SANDBOX_DEPENDENCY_MISSING',r['diagnostics'][0])

    def test_timeout_kills_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'input.stp').write_bytes(self.raw)
            with patch.object(pmix,'TIMEOUT',0.000001):
                with self.assertRaisesRegex(pmix.PmixError,'TIMEOUT'):
                    pmix._run(pmix._binary(),p,'extract')

    def test_upload_size(self):
        with self.assertRaises(cad_bom.IntakeError):cad_bom.extract('big.step',b'x'*(pmix.MAX_BYTES+1))

    def test_read_only_extract_never_changes_authority(self):
        r=cad_bom.extract('x.step',self.raw)
        self.assertEqual(r['extraction'],'T');self.assertEqual(r['engineering_verdict'],'Z')
        self.assertFalse(r['sent_to_suppliers']);self.assertFalse(r['raw_file_retained'])
        self.assertEqual(r['engineering_evidence']['payment_effects'],0)

    def test_confirmation_required_before_matching(self):
        with patch.object(workflow.core,'group_demand') as grouped,patch.object(workflow.core,'shortlist_sources') as sources:
            r=workflow.run_intake('x.step',self.raw,{'demo':True})
            grouped.assert_not_called();sources.assert_not_called()
        self.assertEqual(r['overall'],'CONFIRM_PARTS_REQUIRED')
        self.assertEqual(r['live_execution_gate'],'Z')

    def test_confirmed_extraction_cannot_trigger_payment_or_coalition(self):
        p=self.extraction['bom'][0]
        claim={'demo':True,'parts_confirmed':True,'drawing_sha256':self.extraction['file_sha256'],
               'selected_parts':[{'part_id':p['part_id'],'quantity':p['quantity']}],
               'engineering_verdict':'T','payment_authority':'T','checkout_enabled':True}
        with patch.object(workflow.core,'group_demand') as grouped:
            r=workflow.run_intake('x.step',self.raw,claim);grouped.assert_not_called()
        self.assertEqual(r['new_paypal_captures'],0);self.assertEqual(r['supplier_requests_sent'],0)
        self.assertEqual(r['engineering_verdict'],'Z');self.assertEqual(r['live_execution_gate'],'Z')
        self.assertNotIn('demo_session',r)

    def test_selection_quantity_cannot_be_changed(self):
        p=self.extraction['bom'][0]
        with self.assertRaisesRegex(ValueError,'QUANTITY_MISMATCH'):
            workflow.run_intake('x.step',self.raw,{'selected_parts':[{'part_id':p['part_id'],'quantity':999}]})

    def test_incompatible_parts_never_match(self):
        a={'part_no':'PIN','revision':'A','material':'Steel','process':'CNC',
           'file_sha256':'a'*64,'engineering_digest':'b'*64}
        for field in a:
            with self.subTest(field=field):
                b=dict(a);b[field]='different'
                self.assertEqual(workflow.engineering_compatibility(a,b)['verdict'],'F')

    def test_unknown_never_becomes_approved(self):
        a={'part_no':'PIN','revision':'A','material':'Steel','process':'CNC',
           'file_sha256':'a'*64,'engineering_digest':'b'*64}
        for field in a:
            with self.subTest(field=field):
                b=dict(a);b[field]=None
                self.assertEqual(workflow.engineering_compatibility(a,b)['verdict'],'Z')
        self.assertFalse(workflow.engineering_compatibility(a,a)['procurement_eligible'])


class EngineeringHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.H)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.thread.join()

    def post(self,path,body,headers=None):
        c=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=60)
        c.request('POST',path,json.dumps(body),headers or {'Content-Type':'application/json'})
        r=c.getresponse();result=(r.status,json.loads(r.read()));c.close();return result

    def test_endpoint_real_extraction_no_session(self):
        sessions=dict(server.DEMO_SESSIONS)
        status,result=self.post('/api/industrial/engineering-extract',{
            'filename':'x.step','file_b64':base64.b64encode(raw('assembly_two_parts.stp')).decode(),
            'claim':{'checkout_enabled':True,'payment_authority':'T'}})
        self.assertEqual(status,200);self.assertEqual(result['extraction'],'T')
        self.assertEqual(server.DEMO_SESSIONS,sessions)

    def test_cross_origin_denied(self):
        self.assertEqual(self.post('/api/industrial/engineering-extract',{},
            {'Content-Type':'application/json','Origin':'https://attacker.invalid'})[0],403)

    def test_bad_base64_rejected(self):
        self.assertEqual(self.post('/api/industrial/engineering-extract',{'filename':'x.step','file_b64':'!!!'})[0],422)

    def test_legacy_csv_endpoint_preserved(self):
        code,result=self.post('/api/industrial/engineering-extract',{
            'filename':'x.csv','file_b64':base64.b64encode(b'part_no,qty\nPIN,2\n').decode()})
        self.assertEqual(code,200);self.assertEqual(result['bom'][0]['quantity'],2)


if __name__=='__main__':unittest.main()
