"""Industrial sourcing controls, data provenance and cross-contract safety."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from deal_rescue.industrial import core

CASES=core.read_json('cases.json')

class Registry(unittest.TestCase):
    def test_87_discovery_entries_not_quoted(self):
        r=core.source_registry()
        self.assertEqual(r['total'],87)
        self.assertTrue(all(x['quote_verdict']=='Z' for x in r['records']))
        self.assertTrue(all(x['supplier_commitment_verdict']=='Z' for x in r['records']))
        self.assertEqual(len(set(x['id'] for x in r['records'])),87)
        self.assertEqual(len([x for x in r['records'] if x['kind'] in ('contract_manufacturer','manufacturing_network','manufacturing_marketplace')]),30)
    def test_hp_48_member_index_exact_and_no_double_claim(self):
        r=core.source_registry(); hp=[x for x in r['records'] if x['id'].startswith('HP')]
        self.assertEqual(len(hp),48)
        self.assertTrue(all(x['quote_verdict']=='Z' for x in hp))
        self.assertEqual(len([v for v in core.read_json('sources.json')['records'] if v.get('linked_existing_registry_id')]),3)
    def test_no_filename_traversal(self):
        for n in ('../cases.json','x/y.json','..\\.json','cases.txt'):
            with self.subTest(n=n),self.assertRaises(ValueError):core.read_json(n)
    def test_shortlist_unknown_capability(self):
        rows=core.shortlist_sources('SLS')
        self.assertGreaterEqual(len(rows),12)
        self.assertTrue(all(x['exact_process_capability']=='Z' for x in rows))

class Demand(unittest.TestCase):
    def setUp(self):self.d=copy.deepcopy(CASES['coalition']['demands'][0])
    def test_demo_opt_in_is_not_live_authority(self):
        self.assertEqual(core.valid_demand(self.d,demonstration=False)['verdict'],'Z')
        self.assertEqual(core.valid_demand(self.d,demonstration=True)['verdict'],'T')
    def test_missing_fields_hold(self):
        for field in ('buyer_id','spec_digest','qty','budget_cents','consent_scope','due_date'):
            d=dict(self.d);d.pop(field)
            with self.subTest(field=field):self.assertEqual(core.valid_demand(d,demonstration=True)['verdict'],'Z')
    def test_invalid_qty_budget_fails(self):
        for k,v in [('qty',0),('qty',-1),('qty',1.0),('budget_cents',-1),('budget_cents',False)]:
            d=dict(self.d);d[k]=v
            with self.subTest(k=k,v=v):self.assertEqual(core.valid_demand(d,demonstration=True)['verdict'],'F')
    def test_revocation_and_consent_scope(self):
        for k,v in [('revoked',True),('consent_scope','marketing'),('consent_scope',''),('consent_scope','no')]:
            d=dict(self.d);d[k]=v
            with self.subTest(k=k):self.assertEqual(core.valid_demand(d,demonstration=True)['verdict'],'F' if v else 'Z')
    def test_real_unverified_optin_unknown(self):
        d=dict(self.d,source_scope='CRM',source_ref='crm/197',consent_receipt='signed_by_me')
        self.assertEqual(core.valid_demand(d,demonstration=False)['verdict'],'Z')
    def test_self_attested_real_optin_does_not_pass(self):
        d=dict(self.d,source_scope='CRM',source_ref='crm/197',consent_receipt='abc',consent_authentication='EXTERNALLY_VERIFIED')
        self.assertEqual(core.valid_demand(d,demonstration=False)['verdict'],'Z')
    def test_duplicate_buyer_is_denied(self):
        d=copy.deepcopy(self.d); d['id']='other'
        r=core.group_demand([self.d,d],demonstration=True)
        self.assertEqual(len(r['excluded']),1)
        self.assertEqual(r['excluded'][0]['verdict'],'F')
    def test_spec_revision_prevents_superficial_merge(self):
        g=core.group_demand(CASES['mismatch']['demands'],demonstration=True)['groups']
        self.assertEqual(sorted(x['units'] for x in g),[20,80])
    def test_material_process_or_hash_prevents_merge(self):
        for k,v in [('material','ABS'),('process','MJF'),('spec_digest','0'*64)]:
            d=copy.deepcopy(self.d);d['id']='another';d['buyer_id']='another';d[k]=v
            g=core.group_demand([self.d,d],demonstration=True)['groups']
            with self.subTest(k=k):self.assertEqual(len(g),2)

class Quotations(unittest.TestCase):
    def setUp(self):
        self.g=core.group_demand(CASES['coalition']['demands'],demonstration=True)['groups'][0]
        self.q=copy.deepcopy(CASES['coalition']['offers'][-1])
    def test_fixture_only_not_actual_supplier_quote(self):
        self.assertEqual(core.evaluate_quote(self.q,self.g,demonstration=True)['verdict'],'T')
        self.assertEqual(core.evaluate_quote(self.q,self.g,demonstration=False)['verdict'],'Z')
    def test_missing_quote_fields_do_not_pass(self):
        for key in ('route','spec_digest','material','due_date','landed_cents','moq_units','capacity_units'):
            q=dict(self.q);q.pop(key)
            with self.subTest(key=key):self.assertEqual(core.evaluate_quote(q,self.g,demonstration=True)['verdict'],'Z')
    def test_wrong_revision_digest_material_rejected(self):
        for key,value in [('spec_digest','f'*64),('spec_revision','REV-X'),('material','ABS'),('process','FDM')]:
            q=dict(self.q);q[key]=value
            with self.subTest(key=key):self.assertEqual(core.evaluate_quote(q,self.g,demonstration=True)['verdict'],'F')
    def test_capacity_and_moq_negative(self):
        for key,value in [('capacity_units',99),('moq_units',101),('landed_cents',-1),('landed_cents',1.0)]:
            q=dict(self.q);q[key]=value
            with self.subTest(key=key):self.assertEqual(core.evaluate_quote(q,self.g,demonstration=True)['verdict'],'F')
    def test_due_date_critical(self):
        q=dict(self.q,due_date='2027-01-01')
        self.assertEqual(core.evaluate_quote(q,self.g,demonstration=True)['verdict'],'F')
    def test_quotes_research_only_when_unconfirmed(self):
        q=dict(self.q,source_scope='ALIBABA_PUBLIC_LISTING',landed_cents=1)
        self.assertEqual(core.evaluate_quote(q,self.g,demonstration=False)['verdict'],'Z')
    def test_self_attested_supplier_quote_does_not_pass(self):
        q=dict(self.q,source_scope='REAL_SUPPLIER',signed_quote_digest='hash',signature_validated_externally=True,
               merchant_identity_verified=True,quote_not_expired=True)
        self.assertEqual(core.evaluate_quote(q,self.g,demonstration=False)['verdict'],'Z')
    def test_nonbinding_budget_blocks(self):
        g=copy.deepcopy(self.g);g['demands'][0]['budget_cents']=0
        decision=core.choose_route(g,CASES['coalition']['offers'],demonstration=True)
        self.assertIsNone(decision['route'])

class Proofs(unittest.TestCase):
    def setUp(self):self.req={'model':'resistor','range':[1,2]}
    def test_no_ztl_receipt_is_Z(self):
        self.assertEqual(core.verify_ztl_binding(self.req)['verdict'],'Z')
    def test_claimed_proof_without_independent_verifier_is_Z(self):
        r={'request_sha256':core.digest(self.req),'verdict':'T','theorem_id':'fake'}
        self.assertEqual(core.verify_ztl_binding(self.req,r)['verdict'],'Z')
    def test_forged_request_digest_F(self):
        r={'request_sha256':'f'*64,'model_id':'resistor','theorem_id':'demo','engine_pin':'x','epoch':'1','verifier_pin':'p'}
        self.assertEqual(core.verify_ztl_binding(self.req,r,lambda a,b:True,expected_verifier_pin='p')['verdict'],'F')
    def test_wrong_verifier_pin_F(self):
        r={'request_sha256':core.digest(self.req),'model_id':'resistor','theorem_id':'demo','engine_pin':'x','epoch':'1','verifier_pin':'wrong'}
        self.assertEqual(core.verify_ztl_binding(self.req,r,lambda a,b:True,expected_verifier_pin='p')['verdict'],'F')
    def test_external_rejection_cannot_be_faked(self):
        r={'request_sha256':core.digest(self.req),'model_id':'resistor','theorem_id':'demo','engine_pin':'x','epoch':'1','verifier_pin':'p'}
        self.assertEqual(core.verify_ztl_binding(self.req,r,lambda a,b:False,expected_verifier_pin='p')['verdict'],'F')
        self.assertEqual(core.verify_ztl_binding(self.req,r,lambda a,b:None,expected_verifier_pin='p')['verdict'],'Z')
    def test_stubbed_positive_isolated_contract_only(self):
        r={'request_sha256':core.digest(self.req),'model_id':'resistor','theorem_id':'demo','engine_pin':'x','epoch':'1','verifier_pin':'TEST_VERIFIER_PIN'}
        v=core.verify_ztl_binding(self.req,r,lambda a,b:True,expected_verifier_pin='TEST_VERIFIER_PIN')
        self.assertEqual(v['verdict'],'T')  # a stub; never present as an actual ZTL result

class EndToEnd(unittest.TestCase):
    def test_coalition_route_numerical_on_demo_fixture(self):
        r=core.run_case('coalition')
        self.assertEqual(r['route_decision']['route'],'COALITION')
        self.assertEqual(r['route_decision']['landed_cents'],230000)
        self.assertEqual(sum(x['allocated_cents'] for x in r['route_decision']['allocation']),230000)
        self.assertEqual(r['demand']['group']['member_count'],5)
        self.assertEqual(r['demand']['group']['units'],100)
        self.assertEqual(r['outcome'],'SYNTHETIC_ROUTE_CHOSEN_NOT_ADMITTED')
    def test_direct_route_must_win_when_cheaper(self):
        self.assertEqual(core.run_case('direct')['route_decision']['route'],'DIRECT')
    def test_changed_revision_no_false_coalition(self):
        r=core.run_case('mismatch')
        self.assertEqual(r['demand']['group']['units'],80)
        self.assertIsNone(r['route_decision']['route'])
    def test_no_z_to_t_and_no_payment_transfer(self):
        for c in ('coalition','direct','mismatch'):
            r=core.run_case(c)
            with self.subTest(c=c):
                self.assertEqual(r['gates']['ztl_engineering'],'Z')
                self.assertEqual(r['gates']['paypal_authority'],'Z')
                self.assertEqual(r['gates']['federation_admission'],'Z')
                self.assertEqual(r['federation_proposal']['external_effects'],0)
                self.assertEqual(r['federation_proposal']['paypal_captures_on_this_new_contract'],0)
                self.assertEqual(r['federation_proposal']['reliance'],'NOT_ADMITTED_TO_EXISTING_FEDERATION')
    def test_rfq_excludes_private_buyer_identity_or_cad(self):
        r=core.supplier_rfq('coalition')
        self.assertIn('NOT SENT',r)
        for b in CASES['coalition']['demands']:
            self.assertNotIn(b['buyer_id'],r)
        self.assertNotIn('PAYPAL',r)
    def test_passport_deterministic(self):
        self.assertEqual(core.run_case('coalition')['passport_sha256'],core.run_case('coalition')['passport_sha256'])
    def test_missing_case_rejected(self):
        with self.assertRaises(ValueError):core.run_case('../secrets')

if __name__=='__main__':unittest.main()
