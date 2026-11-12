"""CAD-025: Deal Rescue ZTL admission negative HTTP tests, zero external effects.

Synthetic signed fixtures only. Does NOT claim actual ztl-stand proof, supplier
purchase, or PayPal operation. Run: python -m unittest tests.test_cad025_ztl_gate -v
"""
import base64
import copy
import hashlib
import http.client
import json
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from deal_rescue.industrial import ztl_gate
from deal_rescue import server

DRAWING = '95BA6427A4F5E8033615810D0ABC61EA3A3EEF89ACC95AC8C348CAD5CFE2B52E'.lower()
DOC = 'b' * 64
POLICY = 'f' * 64
STAND = 'd' * 40
CONTRACT = 'contract_cad025'
EPOCH = 'test_epoch_1'
CATEGORIES = ('material', 'dimensions', 'tolerances', 'manufacturing_process', 'inspection', 'functional')


def spec():
    return {
        'drawing_sha256': DRAWING, 'drawing_revision': 'TEST-REV-A',
        'source_documents': [
            {'document_id': 'TEST_AUTHENTIC_STEP', 'kind': 'CAD_STEP', 'sha256': DRAWING},
            {'document_id': 'TEST_ADDITIONAL_MANUFACTURING_SPEC', 'kind': 'TEST_SPEC', 'sha256': DOC},
        ],
        'bom': [{'part_number': 'DEMO-BRACKET', 'quantity': 20, 'material': 'SYNTHETIC_PA12',
                 'material_grade': 'SYNTHETIC_GRADE', 'manufacturing_process': 'SLS',
                 'dimensional_requirements': 'SYNTHETIC_DIMS',
                 'dimensional_tolerances': 'SYNTHETIC_TOLS',
                 'surface_finish': 'SYNTHETIC_FINISH',
                 'inspection_requirements': 'SYNTHETIC_INSPECTION',
                 'functional_requirements': 'SYNTHETIC_LOAD',
                 'source_sha256': DOC}],
        'requirements': [{'id': 'test_' + k, 'part_number': 'DEMO-BRACKET',
                          'category': k, 'statement': 'SYNTHETIC_' + k, 'source_sha256': DOC}
                         for k in CATEGORIES],
    }


def _urlsafe(x):
    return base64.urlsafe_b64encode(x).rstrip(b'=').decode('ascii')


class SignedTestFixture:
    def __init__(self):
        self.private = Ed25519PrivateKey.generate()
        self.key_pem = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        self.env = {
            'LEGION_ZTL_VERIFY_KEY_PEM': self.key_pem,
            'LEGION_ZTL_VERIFY_KID': 'TEST_KEY_ONLY',
            'LEGION_ZTL_CURRENT_EPOCH': EPOCH,
            'LEGION_ZTL_POLICY_SHA256': POLICY,
            'LEGION_ZTL_STAND_COMMIT': STAND,
            'LEGION_ZTL_ATTESTATION_URL': 'https://verifier.example.com/engineering/v1',
            'LEGION_BACKEND_TOKEN': 'TEST_ONLY_FAKE_SECRET',
        }

    def sign(self, data, update=None):
        s = spec()
        timestamp = int(time.time())
        receipt = {
            'schema': 'LEGION_ZTL_ENGINEERING_ATTESTATION_V1',
            'audience': 'LEGION_PROCUREMENT', 'proof_scope': 'MANUFACTURING_REQUIREMENTS',
            'contract_id': CONTRACT, 'spec_digest': ztl_gate.spec_digest(s),
            'drawing_sha256': DRAWING, 'policy_sha256': POLICY, 'epoch': EPOCH,
            'issued_at': timestamp, 'expires_at': timestamp + 1200,
            'verdict': 'EARNED',
            'ztl': {'engine': 'ztl-stand', 'verdict': 'EARNED', 'commit': STAND,
                    'evidence_sha256': 'c' * 64},
            'coverage': {'all_parts_accounted': True, 'verified_parts': 1,
                         'required_checks': 6, 'part_numbers': ['DEMO-BRACKET']},
            'checks': [{'id': r['id'], 'verdict': 'EARNED', 'proof_sha256': 'c' * 64,
                        'source_sha256': DOC} for r in s['requirements']],
        }
        if data is not None: receipt['spec_digest'] = ztl_gate.spec_digest(data)
        if update: update(receipt)
        header = {'alg': 'EdDSA', 'typ': 'LEGION-ZTL-ENGINEERING-V1', 'kid': 'TEST_KEY_ONLY'}
        segment = _urlsafe(json.dumps(header).encode()) + '.' + _urlsafe(json.dumps(receipt).encode())
        return segment + '.' + _urlsafe(self.private.sign(segment.encode()))


class CAD025UnitTests(unittest.TestCase):
    def setUp(self):
        self.signer = SignedTestFixture()
        self.calls = []

    def stub(self, jwt):
        def post(url, payload, token):
            self.calls.append({'url': url, 'contract_id': payload['contract_id'], 'token': token})
            return {'attestation_jws': jwt}
        return post

    def test_01_actual_cad023_missing_bom_never_contacts_verifier(self):
        missing = {'drawing_sha256': DRAWING, 'drawing_revision': 'MFCAD_060',
                   'bom': [], 'requirements': [], 'source_documents': []}
        with self.assertRaisesRegex(ztl_gate.GateError, 'BOM_EMPTY') as err:
            ztl_gate.engineering_admission(CONTRACT, missing, env=self.signer.env,
                                           http_post=self.stub('NOPE'))
        self.assertEqual(err.exception.status, 422)
        self.assertEqual(self.calls, [])

    def test_02_forged_browser_flag_not_authority(self):
        s = spec(); s['engineering_approved'] = True; s['ztl_verdict'] = 'EARNED'
        del s['bom'][0]['material']
        with self.assertRaisesRegex(ztl_gate.GateError, 'PART_FIELD_MISSING_MATERIAL'):
            ztl_gate.engineering_admission(CONTRACT, s, env=self.signer.env,
                                           http_post=self.stub('NOPE'))
        self.assertEqual(self.calls, [])

    def test_03_missing_requirement_category_denies_before_verifier(self):
        s = spec(); s['requirements'] = [r for r in s['requirements'] if r['category'] != 'inspection']
        with self.assertRaises(ztl_gate.GateError):
            ztl_gate.engineering_admission(CONTRACT, s, env=self.signer.env,
                                           http_post=self.stub('NOPE'))
        self.assertEqual(self.calls, [])

    def test_04_valid_synthetic_signed_proof_only_engineering_t(self):
        s = spec(); result = ztl_gate.engineering_admission(CONTRACT, s, env=self.signer.env,
                                                             http_post=self.stub(self.signer.sign(s)))
        self.assertEqual(result['verdict'], 'T')
        self.assertEqual(result['verified_checks'], 6)
        self.assertFalse(result['procurement_authorized'])
        self.assertFalse(result['payment_authorized'])
        self.assertEqual(len(self.calls), 1)

    def test_05_mesh_only_scope_denied(self):
        s = spec(); jwt = self.signer.sign(s, lambda p: p.update(proof_scope='CAD_MESH'))
        with self.assertRaisesRegex(ztl_gate.GateError, 'CERTIFICATE_SCOPE_NOT_MANUFACTURING'):
            ztl_gate.engineering_admission(CONTRACT, s, env=self.signer.env,
                                           http_post=self.stub(jwt))

    def test_06_invalid_signature_denied(self):
        s = spec(); jwt = self.signer.sign(s)
        jwt = jwt[:-2] + ('AA' if jwt[-2:] != 'AA' else 'BB')
        with self.assertRaises(ztl_gate.GateError):
            ztl_gate.engineering_admission(CONTRACT, s, env=self.signer.env,
                                           http_post=self.stub(jwt))

    def test_07_stale_epoch_denied(self):
        s = spec(); jwt = self.signer.sign(s, lambda p: p.update(epoch='OLD_EPOCH'))
        with self.assertRaisesRegex(ztl_gate.GateError, 'CERTIFICATE_EPOCH_INVALID'):
            ztl_gate.engineering_admission(CONTRACT, s, env=self.signer.env,
                                           http_post=self.stub(jwt))

    def test_08_policy_change_denied(self):
        s = spec(); jwt = self.signer.sign(s, lambda p: p.update(policy_sha256='e'*64))
        with self.assertRaisesRegex(ztl_gate.GateError, 'POLICY_OR_STAND_VERSION_MISMATCH'):
            ztl_gate.engineering_admission(CONTRACT, s, env=self.signer.env,
                                           http_post=self.stub(jwt))

    def test_09_attestation_for_other_contract_denied(self):
        s = spec(); jwt = self.signer.sign(s, lambda p: p.update(contract_id='wrong_contract'))
        with self.assertRaisesRegex(ztl_gate.GateError, 'CERTIFICATE_BINDING_MISMATCH'):
            ztl_gate.engineering_admission(CONTRACT, s, env=self.signer.env,
                                           http_post=self.stub(jwt))

    def test_10_attestation_for_old_spec_denied(self):
        s = spec(); jwt = self.signer.sign(s)
        s['bom'][0]['quantity'] = 21
        with self.assertRaisesRegex(ztl_gate.GateError, 'CERTIFICATE_BINDING_MISMATCH'):
            ztl_gate.engineering_admission(CONTRACT, s, env=self.signer.env,
                                           http_post=self.stub(jwt))

    def test_11_one_check_open_denied(self):
        s = spec(); jwt = self.signer.sign(s, lambda p: p['checks'][0].update(verdict='OPEN'))
        with self.assertRaisesRegex(ztl_gate.GateError, 'CERTIFICATE_CHECK_NOT_EARNED_OR_UNBOUND'):
            ztl_gate.engineering_admission(CONTRACT, s, env=self.signer.env,
                                           http_post=self.stub(jwt))

    def test_12_missing_part_coverage_denied(self):
        s = spec(); jwt = self.signer.sign(s, lambda p: p['coverage'].update(verified_parts=0))
        with self.assertRaisesRegex(ztl_gate.GateError, 'CERTIFICATE_COVERAGE_INCOMPLETE'):
            ztl_gate.engineering_admission(CONTRACT, s, env=self.signer.env,
                                           http_post=self.stub(jwt))

    def test_13_wrong_verifier_commit_denied(self):
        s = spec(); jwt = self.signer.sign(s, lambda p: p['ztl'].update(commit='a'*40))
        with self.assertRaisesRegex(ztl_gate.GateError, 'POLICY_OR_STAND_VERSION_MISMATCH'):
            ztl_gate.engineering_admission(CONTRACT, s, env=self.signer.env,
                                           http_post=self.stub(jwt))

    def test_14_expired_signature_denied(self):
        s = spec()
        def old(p): p.update(issued_at=int(time.time()) - 3000, expires_at=int(time.time()) - 1000)
        with self.assertRaisesRegex(ztl_gate.GateError, 'CERTIFICATE_EXPIRED_OR_INVALID'):
            ztl_gate.engineering_admission(CONTRACT, s, env=self.signer.env,
                                           http_post=self.stub(self.signer.sign(s, old)))

    def test_15_missing_key_config_denied_before_network(self):
        s = spec(); env = dict(self.signer.env); del env['LEGION_ZTL_VERIFY_KEY_PEM']
        with self.assertRaisesRegex(ztl_gate.GateError, 'TRUSTED_ZTL_SERVICE_NOT_CONFIGURED'):
            ztl_gate.engineering_admission(CONTRACT, s, env=env, http_post=self.stub('NOPE'))
        self.assertEqual(self.calls, [])

    def test_16_private_verifier_url_denied_before_network(self):
        s = spec(); env = dict(self.signer.env); env['LEGION_ZTL_ATTESTATION_URL'] = 'https://127.0.0.1:8080/'
        with self.assertRaisesRegex(ztl_gate.GateError, 'UNTRUSTED_VERIFIER_ENDPOINT'):
            ztl_gate.engineering_admission(CONTRACT, s, env=env, http_post=self.stub('NOPE'))
        self.assertEqual(self.calls, [])

    def test_17_verifier_unavailable_denied(self):
        def offline(*args):
            self.calls.append('attempted')
            raise OSError('test downstream offline')
        with self.assertRaisesRegex(ztl_gate.GateError, 'INDEPENDENT_ZTL_VERIFIER_UNAVAILABLE'):
            ztl_gate.engineering_admission(CONTRACT, spec(), env=self.signer.env, http_post=offline)
        self.assertEqual(self.calls, ['attempted'])

    def test_18_wrong_spec_source_sha_denied(self):
        s = spec(); s['bom'][0]['source_sha256'] = 'f'*64
        with self.assertRaisesRegex(ztl_gate.GateError, 'PART_SOURCE_UNBOUND'):
            ztl_gate.engineering_admission(CONTRACT, s, env=self.signer.env,
                                           http_post=self.stub('NOPE'))

    def test_19a_unrelated_document_does_not_bind_drawing(self):
        s = spec(); s['source_documents'] = [s['source_documents'][1]]
        with self.assertRaisesRegex(ztl_gate.GateError, 'DRAWING_SOURCE_NOT_BOUND'):
            ztl_gate.engineering_admission(CONTRACT, s, env=self.signer.env,
                                           http_post=self.stub('NOPE'))
        self.assertEqual(self.calls, [])

    def test_19_same_input_same_verdict(self):
        for _ in range(2):
            with self.assertRaisesRegex(ztl_gate.GateError, 'BOM_EMPTY'):
                ztl_gate.engineering_admission(CONTRACT, {'drawing_sha256': DRAWING,
                    'drawing_revision': 'R1', 'bom':[], 'requirements':[], 'source_documents':[]},
                    env=self.signer.env, http_post=self.stub('NOPE'))
        self.assertEqual(self.calls, [])


class CAD025HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = ThreadingHTTPServer(('127.0.0.1', 0), server.H)
        cls.port = cls.http.server_address[1]
        cls.worker = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown(); cls.http.server_close(); cls.worker.join(timeout=2)

    def request(self, endpoint, body):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        payload = json.dumps(body)
        c.request('POST', endpoint, body=payload, headers={'Content-Type': 'application/json'})
        response = c.getresponse()
        status = response.status
        body = json.loads(response.read())
        c.close()
        return status, body

    def test_20_real_cad023_incomplete_bom_http_422_no_network(self):
        body = {'contract_id':CONTRACT, 'spec': {'drawing_sha256':DRAWING,
                'drawing_revision':'CAD023', 'bom':[], 'source_documents':[], 'requirements':[]},
                'engineering_admission':'T', 'ztl_verdict':'EARNED', 'procurement_authorized':True}
        with patch.object(ztl_gate, '_private_post', side_effect=AssertionError('network attempted')) as upstream:
            status, result = self.request('/api/industrial/procurement-request', body)
        self.assertEqual((status, result['code']), (422, 'BOM_EMPTY'))
        self.assertFalse(result['procurement_authorized'])
        self.assertFalse(result['payment_authorized'])
        self.assertEqual(result['supplier_requests_sent'], 0)
        self.assertEqual(result['paypal_captures'], 0)
        upstream.assert_not_called()

    def test_21_http_ztl_admission_denies_empty_bom(self):
        status, result = self.request('/api/industrial/ztl-admission',
                                      {'contract_id': CONTRACT, 'spec': {'drawing_sha256': DRAWING,
                                        'drawing_revision':'CAD023','bom':[], 'requirements':[], 'source_documents':[]}})
        self.assertEqual(status, 422)
        self.assertEqual(result['code'], 'BOM_EMPTY')

    def test_22_http_forged_claim_does_not_authorize(self):
        status, result = self.request('/api/industrial/procurement-request',
                                      {'contract_id':CONTRACT, 'engineering_approved':True,
                                       'ztl_verdict':'EARNED', 'procurement_authorized':True})
        self.assertEqual(status, 422)
        self.assertFalse(result['procurement_authorized'])

    def test_23_http_status_no_live_authority(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.port)
        conn.request('GET', '/api/industrial/ztl-gate/status')
        r = conn.getresponse(); body = json.loads(r.read()); conn.close()
        self.assertEqual(r.status, 200)
        self.assertEqual(body['operational_proof'], 'Z')
        self.assertFalse(body['procurement_authorized'])

    def test_24_http_signed_synthetic_eng_t_but_commerce_still_denied(self):
        signer=SignedTestFixture(); s=spec()
        with patch.dict('os.environ', signer.env, clear=True), \
             patch.object(ztl_gate, '_private_post', return_value={'attestation_jws':signer.sign(s)}) as upstream:
            status, result=self.request('/api/industrial/procurement-request',
                {'contract_id':CONTRACT, 'spec':s,'commercial_context':{},'commercial_receipts':{},
                 'engineering_approved':True})
        self.assertEqual(status,409)
        self.assertEqual(result['engineering_admission'], 'T')
        self.assertEqual(result['code'],'COMMERCIAL_EXECUTION_NOT_AUTHORIZED')
        self.assertFalse(result['procurement_authorized'])
        self.assertFalse(result['payment_authorized'])
        upstream.assert_called_once()

    def test_25_post_unrecognized_payment_route_405(self):
        status, result=self.request('/api/industrial/paypal-capture', {'id':'not_allowed'})
        self.assertEqual(status, 405)
        self.assertEqual(result['error'],'METHOD_NOT_ALLOWED')


if __name__ == '__main__': unittest.main()
