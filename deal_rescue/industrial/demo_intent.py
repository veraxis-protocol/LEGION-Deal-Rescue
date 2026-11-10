"""Durable DEMO-ONLY review intent, not a contract, PayPal order or signed commitment.
Isolated journal; never writes to legacy run/dossier/payments.
"""
import hashlib
import json
import os
import re
import threading
from datetime import datetime,timezone
from pathlib import Path

LOCK=threading.Lock()
KEY=re.compile(r'^[A-Za-z0-9_-]{16,100}$')

def record(session, request, ledger_path):
    if not session or session['response']['overall']!='DEMO_FEASIBLE_NEEDS_ACTUAL_AUTHORITY':
        raise ValueError('NOT_DEMO_FEASIBLE')
    if not isinstance(request,dict) or request.get('agree') is not True:
        raise ValueError('EXPLICIT_BUYER_REVIEW_REQUIRED')
    if request.get('evidence_sha256')!=session['response']['evidence_sha256']:
        raise ValueError('CONTRACT_EVIDENCE_CHANGED')
    if request.get('buyer_id')!=session['response']['buyer_id']:
        raise ValueError('WRONG_BUYER')
    key=request.get('idempotency_key')
    if not isinstance(key,str) or not KEY.fullmatch(key):raise ValueError('INVALID_IDEMPOTENCY_KEY')
    cost=session['response']['lines'][0]['allocation']['per_buyer'][0]
    if request.get('total_cents')!=cost['all_in_cents']:
        raise ValueError('PRICE_CHANGED')
    event={'schema':'legion.demo-intent.v1','scope':'SYNTHETIC_TEST_ONLY',
           'buyer_id':request['buyer_id'],'idempotency_key':key,
           'evidence_sha256':request['evidence_sha256'],'reviewed_total_cents':cost['all_in_cents'],
           'state':'DEMO_REVIEW_CONFIRMED_NO_ORDER_NO_PAYMENT','paypal_captures':0,
           'timestamp_utc':datetime.now(timezone.utc).isoformat()}
    p=Path(ledger_path)
    if p.exists() and not p.is_file():raise ValueError('INVALID_LEDGER_PATH')
    with LOCK:
        existing=[]
        if p.exists():
            existing=[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
        for old in existing:
            if old['idempotency_key']==key:
                if old['evidence_sha256']!=event['evidence_sha256'] or old['buyer_id']!=event['buyer_id']:
                    raise ValueError('IDEMPOTENCY_REUSE_DIFFERENT_CONTRACT')
                return {'receipt':old,'duplicate':True,'financial_effects':0}
        p.parent.mkdir(parents=True,exist_ok=True)
        previous=existing[-1].get('event_hash','0'*64) if existing else '0'*64
        event['previous_hash']=previous
        event['event_hash']=hashlib.sha256(json.dumps(event,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        # One journal per local test host. File contains no credentials and no PII.
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        try:
            with os.fdopen(fd,'a',encoding='utf-8') as f:
                f.write(json.dumps(event,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
        except:raise
    return {'receipt':event,'duplicate':False,'financial_effects':0}
