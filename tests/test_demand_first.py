"""Executable mechanism & failure tests for buyer-first CAD/BOM → group → feasibility → demo intent."""
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from deal_rescue.industrial import cad_bom,core,workflow,demo_intent

SAMPLES=Path(__file__).resolve().parents[1]/'deal_rescue/industrial/samples'
SAMPLE=(SAMPLES/'DEMO-BRACKET-20.json').read_bytes()
CLAIM=json.loads((SAMPLES/'DEMO-CLAIM.json').read_text())

def dxf(n=20, other=False):
    pairs=[(0,'SECTION'),(2,'HEADER'),(0,'ENDSEC'),(0,'SECTION'),(2,'BLOCKS'),(0,'BLOCK'),(2,'SLS-BRACKET-REV-C'),(0,'INSERT'),(2,'FAKE-INSIDE-DEF'),(0,'ENDBLK'),(0,'ENDSEC'),(0,'SECTION'),(2,'ENTITIES')]
    pairs += [(k,v) for i in range(n) for k,v in ((0,'INSERT'),(2,'SLS-BRACKET-REV-C' if not other or i<10 else 'OTHER-PART'))]
    pairs += [(0,'ENDSEC'),(0,'EOF')]
    return ('\n'.join(str(v) for p in pairs for v in p)+'\n').encode()

class CADIntake(unittest.TestCase):
    def test_json_bom_20(self):
        r=cad_bom.extract('drawing.json',SAMPLE)
        self.assertEqual((r['extraction'],r['bom'][0]['quantity']),(core.T,20))
        self.assertFalse(r['raw_file_retained'])
    def test_real_dxf_insert_count(self):
        r=cad_bom.extract('assembly.dxf',dxf())
        self.assertEqual((r['extraction'],r['bom'][0]['quantity']),(core.T,20))
    def test_dxf_blocks_not_placements(self):
        r=cad_bom.extract('assembly.dxf',dxf(1))
        self.assertEqual(r['bom'],[{'part_no':'SLS-BRACKET-REV-C','quantity':1,'origin':'DXF_INSERT_ENTITY','verification':'EXTRACTED_NOT_ENGINEERING_PROVED'}])
    def test_dxf_multiple_components(self):
        r=cad_bom.extract('assembly.dxf',dxf(20,True))
        self.assertEqual(len(r['bom']),2)
        self.assertEqual(sum(x['quantity'] for x in r['bom']),20)
    def test_svg_explicit_annotations(self):
        data=b'<svg xmlns="http://www.w3.org/2000/svg"><rect data-part-number="BRACKET-01" data-qty="4"/></svg>'
        self.assertEqual(cad_bom.extract('bom.svg',data)['bom'][0]['quantity'],4)
    def test_csv_quantity_aggregation(self):
        data=b'part_no,qty\nA-123,2\nA-123,3\n'
        r=cad_bom.extract('bom.csv',data)
        self.assertEqual(r['bom'][0]['quantity'],5)
    def test_step_never_claims_bom(self):
        for ext in ('.step','.stp','.stl'):
            with self.subTest(ext=ext):self.assertEqual(cad_bom.extract('part'+ext,b'geometry')['extraction'],core.Z)
    def test_empty_dxf_never_invents_bom(self):
        self.assertEqual(cad_bom.extract('blank.dxf',b'0\nEOF\n')['extraction'],core.Z)
    def test_reject_path_traversal(self):
        with self.assertRaises(cad_bom.IntakeError):cad_bom.extract('../part.csv',SAMPLE)
    def test_reject_oversized_file(self):
        with self.assertRaises(cad_bom.IntakeError):cad_bom.extract('part.csv',b'a'*2097153)
    def test_reject_bad_quantity(self):
        for bad in (b'part_no,qty\nAA,0\n',b'part_no,qty\nAA,-1\n',b'part_no,qty\nAA,1.4\n'):
            with self.subTest(bad=bad),self.assertRaises(cad_bom.IntakeError):cad_bom.extract('bad.csv',bad)
    def test_reject_external_xml_entity_no_expansion(self):
        r=cad_bom.extract('test.svg',b'<svg><text>Use non-structured geometry only</text></svg>')
        self.assertEqual(r['extraction'],core.Z)
    def test_drawing_digest_stable(self):
        a=cad_bom.extract('x.json',SAMPLE)['file_sha256']
        self.assertEqual(a,cad_bom.extract('x.json',SAMPLE)['file_sha256'])

class DemandFirst(unittest.TestCase):
    def run_one(self,c=None,b=SAMPLE):return workflow.run_intake('bom.json',b,c or copy.deepcopy(CLAIM))
    def test_positive_buyer_intake_to_demand_pool(self):
        r=self.run_one(); l=r['lines'][0]
        self.assertEqual(r['overall'],'DEMO_FEASIBLE_NEEDS_ACTUAL_AUTHORITY')
        self.assertEqual((l['demand_pool']['buyer_count'],l['demand_pool']['quantity'],l['demand_pool']['moq']),(5,100,100))
        self.assertEqual(l['demand_pool']['peer_buyers_from_fixture'],4)
        self.assertEqual(l['best_route'],'COALITION')
        self.assertEqual(l['allocation']['total_all_buyers_cents'],242500)
        self.assertEqual([x['all_in_cents'] for x in l['allocation']['per_buyer']],[48500]*5)
        self.assertEqual(l['allocation']['shipping_cents'],12500)
    def test_fixture_status_never_real_authority(self):
        r=self.run_one()
        self.assertEqual(r['live_execution_gate'],core.Z)
        self.assertEqual(r['new_paypal_captures'],0)
        self.assertEqual(r['lines'][0]['gates']['real_buyer_opt_in'],core.Z)
        self.assertEqual(r['lines'][0]['gates']['engineering'],core.Z)
    def test_budget_cap_prevents_confirmation(self):
        c=copy.deepcopy(CLAIM);c['budget_cents']=40000
        r=self.run_one(c)
        self.assertNotEqual(r['customer_call_to_action'],'REVIEW_AND_CONFIRM_DEMO_ONLY')
    def test_unknown_shipping_holds(self):
        c=copy.deepcopy(CLAIM);c['own_shipping_cents']=None
        r=self.run_one(c)
        self.assertEqual(r['live_execution_gate'],core.Z)
    def test_missing_taxes_holds(self):
        c=copy.deepcopy(CLAIM);c['taxes_cents']=None
        self.assertNotEqual(self.run_one(c)['overall'],'DEMO_FEASIBLE_NEEDS_ACTUAL_AUTHORITY')
    def test_missing_payment_fee_holds(self):
        c=copy.deepcopy(CLAIM);c['payment_fees_cents']=None
        self.assertNotEqual(self.run_one(c)['overall'],'DEMO_FEASIBLE_NEEDS_ACTUAL_AUTHORITY')
    def test_optin_is_explicit_and_revocable(self):
        c=copy.deepcopy(CLAIM);c['discovery_consent']=False
        self.assertNotEqual(self.run_one(c)['overall'],'DEMO_FEASIBLE_NEEDS_ACTUAL_AUTHORITY')
    def test_real_claim_cannot_use_demo_peers(self):
        c=copy.deepcopy(CLAIM);c['demo']=False
        r=self.run_one(c)
        self.assertEqual(r['overall'],'HOLD_MISSING_OBLIGATIONS')
    def test_revision_mismatch_cannot_group(self):
        c=copy.deepcopy(CLAIM);c['requirements']['spec_revision']='REV-X'
        self.assertNotEqual(self.run_one(c)['overall'],'DEMO_FEASIBLE_NEEDS_ACTUAL_AUTHORITY')
    def test_material_mismatch_cannot_group(self):
        c=copy.deepcopy(CLAIM);c['requirements']['material']='PLA'
        self.assertNotEqual(self.run_one(c)['overall'],'DEMO_FEASIBLE_NEEDS_ACTUAL_AUTHORITY')
    def test_part_number_missing_in_bom_rejected(self):
        c=copy.deepcopy(CLAIM);c['requirements']['part_no']='FAKE'
        r=self.run_one(c)
        self.assertEqual(r['lines'][0]['status'],'NEEDS_PART_REQUIREMENTS')
    def test_multi_component_bom_cannot_complete(self):
        b=json.dumps({'bom':[{'part_no':'SLS-BRACKET-REV-C','qty':20},{'part_no':'SCREW-M6','qty':40}]}).encode()
        r=self.run_one(b=b)
        self.assertEqual(len(r['lines']),2)
        self.assertEqual(r['overall'],'HOLD_MISSING_OBLIGATIONS')
    def test_unsupported_geometry_no_fabricated_bom(self):
        r=workflow.run_intake('mesh.stl',b'binary STL geometry',copy.deepcopy(CLAIM))
        self.assertEqual(r['overall'],'NEEDS_HUMAN_BOM')
    def test_amounts_are_cents_and_exact(self):
        r=self.run_one();a=r['lines'][0]['allocation']
        self.assertEqual(sum(b['all_in_cents'] for b in a['per_buyer']),a['total_all_buyers_cents'])
        self.assertEqual(sum(b['part_cost_cents'] for b in a['per_buyer']),a['production_cents'])
    def test_supplier_listing_never_accepted_quote(self):
        self.assertEqual(self.run_one()['lines'][0]['gates']['real_supplier_quote'],core.Z)
    def test_real_paypal_cannot_be_bound_to_new_contract(self):
        self.assertFalse(self.run_one()['existing_historic_paypal_payments_reused'])

class Dispatch(unittest.TestCase):
    def test_100_metadata_preflight_tasks(self):
        plan=workflow.mock_work_plan()
        self.assertEqual(len(plan),100);self.assertEqual(len(set(x['task_id'] for x in plan)),100)
    def test_actual_100_preflight_receipts_no_agents(self):
        r=workflow.execute_preflight_plan()
        self.assertEqual((r['completed_prechecks'],r['agents_launched'],r['provider_requests_sent']),(100,0,0))
        self.assertTrue(all(x['external_effects']==0 for x in r['receipts']))

class DemoIntent(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.ledger=Path(self.tmp.name)/'demo_intents.jsonl'
        self.r=workflow.run_intake('bom.json',SAMPLE,CLAIM)
        self.s={'response':self.r}
        self.req={'agree':True,'evidence_sha256':self.r['evidence_sha256'],
                  'buyer_id':self.r['buyer_id'],'total_cents':48500,
                  'idempotency_key':'TEST_SAFE_KEY_123456789'}
    def tearDown(self):self.tmp.cleanup()
    def test_customer_can_confirm_demo_review(self):
        r=demo_intent.record(self.s,self.req,self.ledger)
        self.assertEqual(r['receipt']['state'],'DEMO_REVIEW_CONFIRMED_NO_ORDER_NO_PAYMENT')
        self.assertEqual(r['financial_effects'],0)
        self.assertTrue(self.ledger.exists())
    def test_idempotent_retry(self):
        demo_intent.record(self.s,self.req,self.ledger)
        r=demo_intent.record(self.s,self.req,self.ledger)
        self.assertTrue(r['duplicate'])
        self.assertEqual(len(self.ledger.read_text().splitlines()),1)
    def test_wrong_buyer_fails(self):
        a=dict(self.req,buyer_id='OTHERS')
        with self.assertRaises(ValueError):demo_intent.record(self.s,a,self.ledger)
    def test_price_changed_fails(self):
        a=dict(self.req,total_cents=48501)
        with self.assertRaises(ValueError):demo_intent.record(self.s,a,self.ledger)
    def test_hash_mutant_fails(self):
        a=dict(self.req,evidence_sha256='0'*64)
        with self.assertRaises(ValueError):demo_intent.record(self.s,a,self.ledger)
    def test_requires_click(self):
        a=dict(self.req,agree=False)
        with self.assertRaises(ValueError):demo_intent.record(self.s,a,self.ledger)
    def test_cross_contract_idempotency_fails(self):
        demo_intent.record(self.s,self.req,self.ledger)
        altered=copy.deepcopy(self.r);altered['evidence_sha256']='f'*64
        with self.assertRaises(ValueError):
            demo_intent.record({'response':altered},dict(self.req,evidence_sha256='f'*64),self.ledger)

if __name__=='__main__':unittest.main()

class RealAdmissionContract(unittest.TestCase):
    def setUp(self):
        from deal_rescue.industrial import admission
        self.admission=admission
        self.ctx={'contract_hash':'a'*64,'epoch':7,'buyer_id':'buyer-1','price_cents':48500,
                  'spec_digest':'b'*64,'rev':'REV-C','evidence_sha256':'c'*64}
        self.receipts={k:{'receipt_id':'external-'+k,'verifier_pin':'test-only-independent-fixture',
                          'contract_hash':self.ctx['contract_hash'],'epoch':7,
                          'buyer_id':'buyer-1','evidence_sha256':self.ctx['evidence_sha256'],'spec_digest':self.ctx['spec_digest'],
                          'rev':self.ctx['rev'],'price_cents':self.ctx['price_cents']}
                       for k in admission.OBLIGATIONS}
    def test_earns_T_only_with_all_ten_independently_accepted_receipts(self):
        r=self.admission.decide(self.ctx,self.receipts,lambda name,receipt,ctx:True)
        self.assertEqual((r['verdict'],r['eligible_for_buyer_action'],r['next']),('T',True,'REQUEST_BUYER_ACTION'))
    def test_no_verifier_never_T(self):
        self.assertEqual(self.admission.decide(self.ctx,self.receipts)['verdict'],'Z')
    def test_1_missing_Z(self):
        r=copy.deepcopy(self.receipts);r.pop('supplier_quote')
        self.assertEqual(self.admission.decide(self.ctx,r,lambda *args:True)['verdict'],'Z')
    def test_one_independently_denied_F(self):
        self.assertEqual(self.admission.decide(self.ctx,self.receipts,lambda k,*args:k!='engineering_proof')['verdict'],'F')
    def test_changed_epoch_F(self):
        r=copy.deepcopy(self.receipts);r['supplier_capacity']['epoch']=6
        self.assertEqual(self.admission.decide(self.ctx,r,lambda *args:True)['verdict'],'F')
    def test_wrong_buyer_F(self):
        r=copy.deepcopy(self.receipts);r['all_buyer_consent']['buyer_id']='other'
        self.assertEqual(self.admission.decide(self.ctx,r,lambda *args:True)['verdict'],'F')
    def test_wrong_evidence_F(self):
        r=copy.deepcopy(self.receipts);r['dfm_proof']['evidence_sha256']='0'*64
        self.assertEqual(self.admission.decide(self.ctx,r,lambda *args:True)['verdict'],'F')
    def test_revoked_F(self):
        r=copy.deepcopy(self.receipts);r['operator_payment_permit']['revoked']=True
        self.assertEqual(self.admission.decide(self.ctx,r,lambda *args:True)['verdict'],'F')
    def test_verifier_unavailable_Z(self):
        self.assertEqual(self.admission.decide(self.ctx,self.receipts,lambda *args:None)['verdict'],'Z')
    def test_price_receipt_mismatch_F(self):
        r=copy.deepcopy(self.receipts);r['supplier_quote']['price_cents']=48501
        self.assertEqual(self.admission.decide(self.ctx,r,lambda *args:True)['verdict'],'F')
    def test_no_paypal_call_for_even_T(self):
        self.assertTrue(self.admission.decide(self.ctx,self.receipts,lambda *args:True)['no_paypal_call_performed'])

class ProviderContracts(unittest.TestCase):
    def setUp(self):
        from deal_rescue.industrial import provider_contracts
        self.p=provider_contracts
        self.q=provider_contracts.Inquiry(CLAIM['requirements']['spec_digest'],'REV-C','SLS','PA12',100,'US','2026-12-10')
        self.offer={'provider_id':'shop-1','quote_id':'q-1','spec_digest':self.q.spec_digest,
            'spec_revision':'REV-C','process':'SLS','material':'PA12','quantity':100,'moq_units':100,
            'capacity_units':100,'base_amount_cents':230000,'currency':'USD','valid_through':'2028-01-01',
            'ship_country':'US','delivery_by':'2026-12-08','source_url':'https://example.org/quote',
            'own_shipping_per_buyer_cents':2500,'seller_identity_receipt':'verified-separately'}
    def test_external_quote_rejected_on_self_attestation(self):
        self.assertEqual(self.p.preflight_quote(dict(self.offer,signature_verified=True),self.q)['verdict'],'Z')
    def test_quote_can_earn_T_from_independent_verifier(self):
        self.assertEqual(self.p.preflight_quote(self.offer,self.q,verifier=lambda *args:True)['verdict'],'T')
    def test_bad_spec_F(self):
        self.assertEqual(self.p.preflight_quote(dict(self.offer,spec_digest='x'*64),self.q)['verdict'],'F')
    def test_moq_F(self):
        self.assertEqual(self.p.preflight_quote(dict(self.offer,moq_units=101),self.q)['verdict'],'F')
    def test_capacity_F(self):
        self.assertEqual(self.p.preflight_quote(dict(self.offer,capacity_units=99),self.q)['verdict'],'F')
    def test_unknown_shipping_Z(self):
        self.assertEqual(self.p.preflight_quote(dict(self.offer,own_shipping_per_buyer_cents=None),self.q)['verdict'],'Z')
    def test_wrong_destination_F(self):
        self.assertEqual(self.p.preflight_quote(dict(self.offer,ship_country='DE'),self.q)['verdict'],'F')
    def test_unusable_expiry_F(self):
        self.assertEqual(self.p.preflight_quote(dict(self.offer,valid_through='2020-01-01'),self.q)['verdict'],'F')

class BuyerEntryAlternatives(unittest.TestCase):
    def test_existing_supplier_batch_80_plus_20(self):
        c=copy.deepcopy(CLAIM);c['fixture_case']='existing_batch'
        r=workflow.run_intake('b.json',SAMPLE,c)
        self.assertEqual(r['overall'],'DEMO_FEASIBLE_NEEDS_ACTUAL_AUTHORITY')
        self.assertEqual(r['lines'][0]['best_route'],'JOIN_EXISTING_BATCH')
        self.assertEqual(r['lines'][0]['demand_pool']['quantity'],100)
        self.assertEqual(r['lines'][0]['allocation']['per_buyer'][0]['all_in_cents'],48500)
        self.assertEqual(r['lines'][0]['gates']['supplier_existing_batch_authority'],core.Z)
    def test_direct_retail_without_discovery_consent(self):
        c=copy.deepcopy(CLAIM);c['fixture_case']='direct';c['discovery_consent']=False
        r=workflow.run_intake('b.json',SAMPLE,c)
        self.assertEqual(r['lines'][0]['best_route'],'DIRECT_RETAIL')
        self.assertEqual(r['overall'],'DEMO_FEASIBLE_NEEDS_ACTUAL_AUTHORITY')
        self.assertEqual(r['lines'][0]['allocation']['per_buyer'][0]['all_in_cents'],42500)
    def test_retail_more_expensive_than_coalition(self):
        c=copy.deepcopy(CLAIM);c['fixture_case']='coalition'
        r=workflow.run_intake('b.json',SAMPLE,c)
        self.assertEqual(r['lines'][0]['best_route'],'COALITION')
    def test_no_live_direct_unauthorized_quote(self):
        c=copy.deepcopy(CLAIM);c['demo']=False;c['discovery_consent']=False
        r=workflow.run_intake('b.json',SAMPLE,c)
        self.assertNotEqual(r['overall'],'DEMO_FEASIBLE_NEEDS_ACTUAL_AUTHORITY')
