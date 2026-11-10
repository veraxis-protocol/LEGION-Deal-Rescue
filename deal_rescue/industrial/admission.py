"""Strict independent-proof admission contract for future LEGION Commerce handoff.

The *verifier* is an independent trusted process; NOT an LLM field, a payload
that asserts its own signature, or this merchant UI. This module executes no
payment. Local tests use a clearly labelled non-production verifier stub.
"""
import hashlib
import json
from datetime import datetime,timezone

T,F,Z='T','F','Z'
OBLIGATIONS=('bom_complete','engineering_proof','dfm_proof','supplier_identity',
             'supplier_quote','supplier_capacity','all_buyer_consent',
             'budget_and_shipping','federation_admission','operator_payment_permit')

def canonical(o):return json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def fingerprint(o):return hashlib.sha256(canonical(o)).hexdigest()

def decide(context,receipts,independent_verifier=None):
    """T is earned only from independent proof for each obligation in current epoch.

    Independent verification function `(obligation, receipt, context) -> True/False/None`
    is deliberately NOT supplied here for real runtime. No tool/supplier can
    self-attest. Caller must bind a separately vetted verifier and pin policy.
    """
    fields=('contract_hash','epoch','buyer_id','price_cents','spec_digest','rev','evidence_sha256')
    if not isinstance(context,dict) or any(x not in context for x in fields):
        return {'verdict':Z,'why':'CONTEXT_MISSING','gates':{x:Z for x in OBLIGATIONS},
                'eligible_for_buyer_action':False,'execute_supplier_order':False,'execute_paypal':False}
    if type(context['price_cents']) is not int or context['price_cents']<0 or type(context['epoch']) is not int:
        return {'verdict':F,'why':'INVALID_CONTEXT','gates':{x:F for x in OBLIGATIONS},'eligible_for_buyer_action':False,'execute_supplier_order':False,'execute_paypal':False}
    if not isinstance(receipts,dict):receipts={}
    gates={}
    missing=[]
    for obligation in OBLIGATIONS:
        rec=receipts.get(obligation)
        if not rec:
            gates[obligation]=Z;missing.append(obligation);continue
        if (rec.get('contract_hash')!=context['contract_hash'] or
            rec.get('epoch')!=context['epoch'] or
            rec.get('buyer_id')!=context['buyer_id'] or
            rec.get('evidence_sha256')!=context['evidence_sha256'] or
            rec.get('spec_digest')!=context['spec_digest'] or
            rec.get('rev')!=context['rev'] or
            rec.get('price_cents')!=context['price_cents']):
            gates[obligation]=F;continue
        if not rec.get('receipt_id') or not rec.get('verifier_pin') or rec.get('revoked') is True:
            gates[obligation]=F;continue
        if independent_verifier is None:
            gates[obligation]=Z;missing.append(obligation);continue
        try:verdict=independent_verifier(obligation,rec,context)
        except Exception:verdict=None
        gates[obligation]=T if verdict is True else F if verdict is False else Z
        if gates[obligation]==Z:missing.append(obligation)
    status=F if F in gates.values() else Z if missing else T
    return {'schema':'legion.industrial.admission.v1','verdict':status,
            'eligible_for_buyer_action':status==T,'execute_supplier_order':False,'execute_paypal':False,'next':'REQUEST_BUYER_ACTION' if status==T else 'DENY' if status==F else 'OBSERVE_OR_COLLECT_PROOF',
            'gates':gates,'missing':missing,
            'context_sha256':fingerprint(context),
            'authority':'EXTERNAL_SIGNED_RECEIPTS_ONLY',
            'no_paypal_call_performed':True}
