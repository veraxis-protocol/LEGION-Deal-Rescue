"""CAD-025: server-side LEGION Deal Rescue ZTL engineering admission.

An intake extraction, model output, or browser-supplied flag NEVER grants authority.
The ONLY source of engineering T is an Ed25519-signed attestation from the
configured independent ZTL verifier. Signer must check the authentic source
BOM and run the complete required engineering checks, not mesh geometry alone.
This gate does not create RFQs, supplier orders or PayPal transactions.
"""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
import re
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

T, F, Z = 'T', 'F', 'Z'
HASH = re.compile(r'^[0-9a-fA-F]{64}$')
ID = re.compile(r'^[A-Za-z0-9_.-]{1,80}$')
CONTRACT = re.compile(r'^[A-Za-z0-9_-]{8,100}$')
TOKEN = re.compile(r'^[A-Za-z0-9_-]+$')
CATEGORIES = frozenset(('material', 'dimensions', 'tolerances',
                        'manufacturing_process', 'inspection', 'functional'))
PART_FIELDS = ('material', 'material_grade', 'manufacturing_process',
               'dimensional_requirements', 'dimensional_tolerances',
               'surface_finish', 'inspection_requirements', 'functional_requirements')
MAX_JWS = 50000


class GateError(ValueError):
    def __init__(self, code, status=409, evidence=Z):
        self.code, self.status, self.evidence = code, status, evidence
        super().__init__(code)


def _valid_text(value, maximum=200):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        return False
    return value.strip().lower() not in {
        'unknown', 'open', 'pending', 'tbd', 'to be determined',
        'n/a', 'na', 'not applicable', 'z', 'null', 'undefined', '?'
    }


def _hash(value):
    return isinstance(value, str) and HASH.fullmatch(value) is not None


def _canonical(obj):
    """Stable JSON with integer-only numbers; the verifier must use this spec."""
    def walk(x):
        if isinstance(x, dict):
            if any(not isinstance(k, str) for k in x):
                raise GateError('NONSTRING_JSON_KEY', 422)
            return {k: walk(v) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v) for v in x]
        if isinstance(x, float):
            raise GateError('FLOAT_IN_SIGNED_SPEC', 422)
        if isinstance(x, int) and not isinstance(x, bool) and abs(x) > (2 ** 53 - 1):
            raise GateError('UNSAFE_INTEGER_IN_SPEC', 422)
        if x is None or isinstance(x, (str, bool, int)):
            return x
        raise GateError('NONJSON_SPEC_FIELD', 422)
    return json.dumps(walk(obj), sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def spec_digest(spec):
    return hashlib.sha256(_canonical(spec)).hexdigest()


def validate_spec(spec):
    if not isinstance(spec, dict):
        raise GateError('SPEC_MISSING', 422)
    if not _hash(spec.get('drawing_sha256')):
        raise GateError('DRAWING_DIGEST_MISSING', 422)
    if not _valid_text(spec.get('drawing_revision'), 80):
        raise GateError('DRAWING_REVISION_MISSING', 422)
    bom = spec.get('bom')
    if not isinstance(bom, list) or not bom:
        raise GateError('BOM_EMPTY', 422)
    if len(bom) > 200:
        raise GateError('BOM_TOO_LARGE', 422)
    docs = spec.get('source_documents')
    if not isinstance(docs, list) or not (0 < len(docs) <= 200):
        raise GateError('SOURCE_DOCUMENTS_MISSING', 422)
    sources = set()
    for doc in docs:
        if not isinstance(doc, dict) or not _hash(doc.get('sha256')) or not \
                _valid_text(doc.get('document_id'), 160) or not _valid_text(doc.get('kind'), 50):
            raise GateError('INVALID_SOURCE_DOCUMENT', 422)
        digest = doc['sha256'].lower()
        if digest in sources:
            raise GateError('DUPLICATE_SOURCE_DOCUMENT', 422)
        sources.add(digest)
    # The declared STEP/drawing must itself be present among hash-bound source
    # documents; unrelated attachments do not establish drawing provenance.
    if spec['drawing_sha256'].lower() not in sources:
        raise GateError('DRAWING_SOURCE_NOT_BOUND', 422)
    parts = set()
    for part in bom:
        if not isinstance(part, dict) or not isinstance(part.get('part_number'), str) or \
                not ID.fullmatch(part['part_number']):
            raise GateError('PART_NUMBER_MISSING', 422)
        pid = part['part_number']
        if pid in parts:
            raise GateError('DUPLICATE_PART', 422)
        parts.add(pid)
        qty = part.get('quantity')
        if type(qty) is not int or not 1 <= qty <= 100000:
            raise GateError('INVALID_QUANTITY', 422)
        for field in PART_FIELDS:
            if not _valid_text(part.get(field), 1200):
                raise GateError('PART_FIELD_MISSING_' + field.upper(), 422)
        if not _hash(part.get('source_sha256')) or part['source_sha256'].lower() not in sources:
            raise GateError('PART_SOURCE_UNBOUND', 422)
    requirements = spec.get('requirements')
    if not isinstance(requirements, list) or not 6 * len(parts) <= len(requirements) <= 2000:
        raise GateError('REQUIREMENT_COVERAGE_INCOMPLETE', 422)
    by_part = {p: set() for p in parts}
    requirement_ids = set()
    for req in requirements:
        if not isinstance(req, dict) or not isinstance(req.get('id'), str) or not ID.fullmatch(req['id']) or \
                req.get('part_number') not in parts or not _valid_text(req.get('category'), 70) or \
                not _valid_text(req.get('statement'), 2000) or not _hash(req.get('source_sha256')) or \
                req['source_sha256'].lower() not in sources:
            raise GateError('INVALID_REQUIREMENT_SOURCE', 422)
        if req['id'] in requirement_ids:
            raise GateError('DUPLICATE_REQUIREMENT', 422)
        requirement_ids.add(req['id'])
        by_part[req['part_number']].add(req['category'])
    for categories in by_part.values():
        if not CATEGORIES.issubset(categories):
            raise GateError('REQUIREMENT_CATEGORIES_INCOMPLETE', 422)
    return {'spec_digest': spec_digest(spec), 'part_numbers': sorted(parts),
            'required_checks': sorted(requirement_ids), 'sources': sources}


def _b64dec(s):
    if not isinstance(s, str) or not s or not TOKEN.fullmatch(s):
        raise GateError('CERTIFICATE_ENCODING_INVALID')
    try:
        return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))
    except Exception as exc:
        raise GateError('CERTIFICATE_ENCODING_INVALID') from exc


def _parse_jws(jws, env):
    if not isinstance(jws, str) or not 0 < len(jws) <= MAX_JWS:
        raise GateError('CERTIFICATE_MISSING')
    segments = jws.split('.')
    if len(segments) != 3:
        raise GateError('CERTIFICATE_FORMAT_INVALID')
    try:
        header = json.loads(_b64dec(segments[0]))
        payload = json.loads(_b64dec(segments[1]))
    except (ValueError, UnicodeError, TypeError) as exc:
        raise GateError('CERTIFICATE_UNREADABLE') from exc
    if not isinstance(header, dict) or not isinstance(payload, dict) or \
            header.get('alg') != 'EdDSA' or header.get('typ') != 'LEGION-ZTL-ENGINEERING-V1' or \
            not env.get('LEGION_ZTL_VERIFY_KID') or header.get('kid') != env['LEGION_ZTL_VERIFY_KID']:
        raise GateError('CERTIFICATE_HEADER_UNTRUSTED')
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        key = serialization.load_pem_public_key(env['LEGION_ZTL_VERIFY_KEY_PEM'].encode())
        if not isinstance(key, Ed25519PublicKey):
            raise GateError('CERTIFICATE_KEY_NOT_ED25519')
        key.verify(_b64dec(segments[2]), (segments[0] + '.' + segments[1]).encode('ascii'))
    except GateError:
        raise
    except (ImportError, KeyError, ValueError, TypeError, InvalidSignature) as exc:
        raise GateError('CERTIFICATE_SIGNATURE_INVALID') from exc
    return payload


def _verify_attestation(jws, contract_id, spec, checked, env, now_sec):
    p = _parse_jws(jws, env)
    if p.get('schema') != 'LEGION_ZTL_ENGINEERING_ATTESTATION_V1' or \
            p.get('audience') != 'LEGION_PROCUREMENT' or \
            p.get('proof_scope') != 'MANUFACTURING_REQUIREMENTS':
        raise GateError('CERTIFICATE_SCOPE_NOT_MANUFACTURING')
    if p.get('contract_id') != contract_id or not _hash(p.get('spec_digest')) or \
            p['spec_digest'].lower() != checked['spec_digest'] or \
            not _hash(p.get('drawing_sha256')) or \
            p['drawing_sha256'].lower() != spec['drawing_sha256'].lower():
        raise GateError('CERTIFICATE_BINDING_MISMATCH')
    if not env.get('LEGION_ZTL_CURRENT_EPOCH') or p.get('epoch') != env['LEGION_ZTL_CURRENT_EPOCH']:
        raise GateError('CERTIFICATE_EPOCH_INVALID')
    issued, expiry = p.get('issued_at'), p.get('expires_at')
    if type(issued) is not int or type(expiry) is not int or issued > now_sec + 90 or \
            expiry <= now_sec or expiry <= issued or expiry - issued > 3600:
        raise GateError('CERTIFICATE_EXPIRED_OR_INVALID')
    ztl = p.get('ztl')
    if not isinstance(ztl, dict) or p.get('policy_sha256', '').lower() != env.get('LEGION_ZTL_POLICY_SHA256', '').lower() or \
            ztl.get('commit', '').lower() != env.get('LEGION_ZTL_STAND_COMMIT', '').lower():
        raise GateError('POLICY_OR_STAND_VERSION_MISMATCH')
    if not _hash(p.get('policy_sha256')) or p.get('verdict') != 'EARNED' or \
            ztl.get('engine') != 'ztl-stand' or ztl.get('verdict') != 'EARNED' or \
            not re.fullmatch('[0-9a-fA-F]{40}', ztl.get('commit', '')) or \
            not _hash(ztl.get('evidence_sha256')):
        raise GateError('FULL_ZTL_PROOF_NOT_EARNED')
    coverage = p.get('coverage')
    if not isinstance(coverage, dict) or coverage.get('all_parts_accounted') is not True or \
            coverage.get('verified_parts') != len(checked['part_numbers']) or \
            coverage.get('required_checks') != len(checked['required_checks']) or \
            coverage.get('part_numbers') != checked['part_numbers']:
        raise GateError('CERTIFICATE_COVERAGE_INCOMPLETE')
    checks = p.get('checks')
    if not isinstance(checks, list) or len(checks) != len(checked['required_checks']):
        raise GateError('CERTIFICATE_CHECKS_INCOMPLETE')
    spec_checks = {r['id']: r for r in spec['requirements']}
    seen = set()
    for c in checks:
        if not isinstance(c, dict) or c.get('id') in seen or c.get('id') not in spec_checks or \
                c.get('verdict') != 'EARNED' or not _hash(c.get('proof_sha256')) or \
                not _hash(c.get('source_sha256')) or \
                c['source_sha256'].lower() != spec_checks[c['id']]['source_sha256'].lower():
            raise GateError('CERTIFICATE_CHECK_NOT_EARNED_OR_UNBOUND')
        seen.add(c['id'])
    if seen != set(checked['required_checks']):
        raise GateError('CERTIFICATE_REQUIREMENTS_MISMATCH')
    return {
        'verdict': T, 'engineering_scope': 'MANUFACTURING_REQUIREMENTS',
        'spec_digest': checked['spec_digest'], 'certificate_sha256': hashlib.sha256(jws.encode()).hexdigest(),
        'verified_parts': len(checked['part_numbers']), 'verified_checks': len(checked['required_checks']),
        'ztl_commit': ztl['commit'], 'epoch': p['epoch'], 'expires_at': expiry,
        'procurement_authorized': False, 'payment_authorized': False,
    }


def _trusted_url(url):
    try:
        p = urlsplit(url)
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.fragment:
            return False
        if p.hostname.lower() in ('localhost', 'localhost.localdomain') or p.hostname.endswith('.local'):
            return False
        try:
            ip = ipaddress.ip_address(p.hostname.strip('[]'))
            if not ip.is_global: return False
        except ValueError:
            pass
        return True
    except Exception:
        return False


def _private_post(url, body, token):
    data = _canonical(body)
    request = Request(url, data=data, method='POST', headers={
        'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token,
        'Accept': 'application/json',
    })
    # Size cap limits response parsing; HTTPS and the pinned key authenticate the verdict.
    with urlopen(request, timeout=10) as response:
        data = response.read(60001)
        if len(data) > 60000:
            raise GateError('CERTIFICATE_TOO_LARGE')
        return json.loads(data)


def engineering_admission(contract_id, spec, *, env=None, http_post=None, now_sec=None):
    """Fail-closed engineering gate. Verifier callback only injected in isolated tests."""
    if not isinstance(contract_id, str) or not CONTRACT.fullmatch(contract_id):
        raise GateError('CONTRACT_ID_INVALID', 422)
    checked = validate_spec(spec)  # reject incomplete BOM before any external request
    env = dict(os.environ if env is None else env)
    needed = ('LEGION_ZTL_ATTESTATION_URL', 'LEGION_BACKEND_TOKEN', 'LEGION_ZTL_VERIFY_KEY_PEM',
              'LEGION_ZTL_VERIFY_KID', 'LEGION_ZTL_CURRENT_EPOCH',
              'LEGION_ZTL_POLICY_SHA256', 'LEGION_ZTL_STAND_COMMIT')
    if any(not env.get(k) for k in needed):
        raise GateError('TRUSTED_ZTL_SERVICE_NOT_CONFIGURED', 503)
    if not _trusted_url(env['LEGION_ZTL_ATTESTATION_URL']):
        raise GateError('UNTRUSTED_VERIFIER_ENDPOINT', 503)
    if not _hash(env['LEGION_ZTL_POLICY_SHA256']) or not re.fullmatch('[a-fA-F0-9]{40}', env['LEGION_ZTL_STAND_COMMIT']):
        raise GateError('VERIFIER_PINS_INVALID', 503)
    post = http_post or _private_post
    try:
        response = post(env['LEGION_ZTL_ATTESTATION_URL'], {
            'contract_id': contract_id, 'spec_digest': checked['spec_digest'],
            'spec': spec, 'epoch': env['LEGION_ZTL_CURRENT_EPOCH']}, env['LEGION_BACKEND_TOKEN'])
    except GateError:
        raise
    except Exception as exc:
        raise GateError('INDEPENDENT_ZTL_VERIFIER_UNAVAILABLE', 503) from exc
    if not isinstance(response, dict):
        raise GateError('INDEPENDENT_ZTL_VERIFIER_BAD_RECEIPT', 503)
    return _verify_attestation(response.get('attestation_jws'), contract_id, spec, checked,
                               env, int(time.time()) if now_sec is None else int(now_sec))


def denial(error):
    return {'engineering_admission': F, 'evidence_status': error.evidence if isinstance(error, GateError) else Z,
            'code': error.code if isinstance(error, GateError) else 'ENGINEERING_GATE_INTERNAL_ERROR',
            'procurement_authorized': False, 'payment_authorized': False,
            'supplier_requests_sent': 0, 'paypal_captures': 0}


def status(env=None):
    env = os.environ if env is None else env
    required = ('LEGION_ZTL_ATTESTATION_URL', 'LEGION_ZTL_VERIFY_KEY_PEM',
                'LEGION_ZTL_VERIFY_KID', 'LEGION_ZTL_CURRENT_EPOCH',
                'LEGION_ZTL_POLICY_SHA256', 'LEGION_ZTL_STAND_COMMIT', 'LEGION_BACKEND_TOKEN')
    return {'service': 'LEGION Deal Rescue ZTL engineering gate',
            'configured': all(bool(env.get(k)) for k in required),
            'operational_proof': Z, 'verdict': Z, 'scope': 'Configuration is not engineering EARNED',
            'procurement_authorized': False, 'payment_authorized': False}
