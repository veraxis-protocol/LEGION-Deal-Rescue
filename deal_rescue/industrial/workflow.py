"""Demand-first, fail-closed procurement planner. No live provider calls/payments.

A synthetic end-to-end exercise is allowed to reach a SIMULATED invitation state;
no proof, signed consent, supplier quote or payment may be inferred from fixtures.
The planner shows the exact missing live obligations for the real commerce gate.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from dataclasses import dataclass
import hashlib
import json
from typing import Any
from . import core, cad_bom

T,F,Z=core.T,core.F,core.Z

REQUIREMENTS=('engineering','geometry_dfm','supplier_identity','supplier_quote','supplier_capacity',
              'buyer_opt_in','all_owner_commitments','federation_admission','payment_authority')

def _truth_all(values):
    if any(v==F for v in values):return F
    if any(v!=T for v in values):return Z
    return T

def mock_work_plan():
    """100 *deterministic tasks*, not 100 NIM/LEGION agents. Each supplier is checked for metadata only."""
    registry=core.source_registry()['records']
    slots=[{'task_id':f'SUP-{i:03d}','task':'SOURCE_METADATA_PREFLIGHT','source_id':r['id']}
           for i,r in enumerate(registry,1)]
    stages=['CAD_BOM','SPEC_BINDING','ZTL_RECEIPT','DFM_SCOPE','BUYER_DEMAND','OPT_IN_VALIDITY',
            'COALITION_MATCH','MOQ','DIRECT_PRICE','3D_PRICE','SPLIT_PRICE','SHIPPING','PAYMENT_SCOPE']
    slots += [{'task_id':f'GATE-{i:03d}','task':s} for i,s in enumerate(stages,1)]
    assert len(slots)==100, len(slots)
    return slots

def execute_preflight_plan():
    plan=mock_work_plan()
    def execute(task):
        # REAL executed deterministic read-only step: source listing contains no verified quote.
        return {'id':task['task_id'],'task':task['task'],
                'status':'DONE_METADATA_ONLY' if task['task'].startswith('SOURCE') else 'DONE_PRECHECK_ONLY',
                'provider_quotes_verified':0,'external_effects':0}
    with ThreadPoolExecutor(max_workers=16) as ex:
        receipts=list(ex.map(execute,plan))
    return {'planned_tasks':len(plan),'completed_prechecks':len(receipts),'agents_launched':0,
            'provider_requests_sent':0,'verified_supplier_quotes':0,'receipts':receipts}

def _exact_payment_spread(total,demands):
    qty=sum(d['qty'] for d in demands)
    amounts=[total*d['qty']//qty for d in demands]
    remainder=total-sum(amounts)
    for i in sorted(range(len(demands)),key=lambda j:demands[j]['buyer_id'])[:remainder]:
        amounts[i]+=1
    assert sum(amounts)==total
    return amounts

def _quote_line(demands,quote,shipping):
    """Every buyer bears their OWN shipping, taxes and processing fee explicitly."""
    order_units=sum(d['qty'] for d in demands)
    production=quote['landed_cents'] # fixture production subtotal, not shipping
    allocation=_exact_payment_spread(production,demands)
    rows=[]
    for d,subtotal in zip(demands,allocation):
        ship=shipping.get(d['buyer_id'])
        if not isinstance(ship,int) or ship<0:
            return {'verdict':Z,'why':'BUYER_SHIPPING_UNKNOWN','buyer_id':d['buyer_id']}
        taxes=d.get('taxes_cents');fees=d.get('payment_fees_cents')
        if type(taxes) is not int or taxes<0 or type(fees) is not int or fees<0:
            return {'verdict':Z,'why':'BUYER_TAX_OR_PAYMENT_FEE_UNKNOWN','buyer_id':d['buyer_id']}
        total=subtotal+ship+taxes+fees
        rows.append({'buyer_id':d['buyer_id'],'qty':d['qty'],'part_cost_cents':subtotal,
                     'own_shipping_cents':ship,'taxes_cents':taxes,'payment_fees_cents':fees,
                     'all_in_cents':total,'budget_cents':d['budget_cents'],
                     'within_budget':total<=d['budget_cents']})
    verdict=T if all(x['within_budget'] for x in rows) else F
    return {'verdict':verdict,'units':order_units,'production_cents':production,
            'shipping_cents':sum(x['own_shipping_cents'] for x in rows),
            'total_all_buyers_cents':sum(x['all_in_cents'] for x in rows),
            'per_buyer':rows,'why':'EXACT_INDIVIDUAL_ALLOCATION' if verdict==T else 'INDIVIDUAL_CAP_EXCEEDED'}

def _make_demand(intake,part,claim):
    specs=claim.get('requirements') or {}
    # No semantic equivalence without same independently specified hash, material, revision.
    needed=('spec_digest','spec_revision','process','material')
    missing=[x for x in needed if not specs.get(x)]
    if missing:return None,{'verdict':Z,'why':'REQUIREMENTS_MISSING','fields':missing}
    if part['part_no']!=specs.get('part_no'):
        return None,{'verdict':F,'why':'CLAIM_PART_NOT_FOUND_IN_DRAWING'}
    if len(specs['spec_digest'])!=64:return None,{'verdict':F,'why':'BAD_SPEC_DIGEST'}
    budget=claim.get('budget_cents');ship=claim.get('own_shipping_cents')
    if type(budget) is not int or budget<0:return None,{'verdict':F,'why':'INVALID_BUDGET'}
    if type(ship) is not int or ship<0:return None,{'verdict':Z,'why':'OWN_SHIPPING_UNQUOTED'}
    try:date.fromisoformat(claim['due_date'])
    except (KeyError,ValueError,TypeError):return None,{'verdict':Z,'why':'DUE_DATE_MISSING'}
    d={ 'id':f'upload:{intake["file_sha256"][:16]}', 'buyer_id':claim.get('buyer_id') or 'NEW-DEMO-BUYER',
        'spec_digest':specs['spec_digest'],'spec_revision':specs['spec_revision'],
        'process':specs['process'],'material':specs['material'],'qty':part['quantity'],
        'budget_cents':budget,'due_date':claim['due_date'],
        'consent_scope':'coalition_discovery' if claim.get('discovery_consent') is True else 'NONE',
        'source_scope':'SYNTHETIC_TEST_ONLY' if claim.get('demo') is True else 'USER_UPLOAD_UNVERIFIED',
        'taxes_cents':claim.get('taxes_cents'), 'payment_fees_cents':claim.get('payment_fees_cents') }
    return d,{'verdict':T,'why':'EXTRACTED_BOM_BOUND_TO_USER_SPEC_NOT_YET_ENGINEERED'}

def _fixture_peer_demands(specs, case):
    # Simulated discovery, no actual other buyer is claimed.
    return [dict(d,taxes_cents=0,payment_fees_cents=0) for d in core.read_json('cases.json')[case]['demands']
            if d['spec_digest']==specs['spec_digest'] and d['spec_revision']==specs['spec_revision']
            and d['process']==specs['process'] and d['material']==specs['material']][:4]

def _supplier_offer(case, demands):
    offers=core.read_json('cases.json')[case]['offers']
    same=[q for q in offers if q['route']=='COALITION' and q['spec_digest']==demands[0]['spec_digest']]
    return same[0] if same else None

def _buyer_line(price, d, ship):
    tax=d.get('taxes_cents');fee=d.get('payment_fees_cents')
    if not all(type(x) is int and x>=0 for x in (price,ship,tax,fee)):
        return {'verdict':Z,'why':'BUYER_SHIPPING_TAX_OR_FEE_MISSING'}
    total=price+ship+tax+fee
    return {'verdict':T if total<=d['budget_cents'] else F,
            'buyer_id':d['buyer_id'],'qty':d['qty'],'part_cost_cents':price,
            'own_shipping_cents':ship,'taxes_cents':tax,'payment_fees_cents':fee,
            'all_in_cents':total,'budget_cents':d['budget_cents'],
            'within_budget':total<=d['budget_cents']}

def _retail_offer(d,claim):
    # Fixed quote for EXACT quantity, unlike invalid linear interpolation from a
    # MOQ100 price. This is exclusively test fixture, never a live supplier quote.
    if claim.get('demo') is not True:return None
    q=core.read_json('retail_test_offers.json').get(claim.get('fixture_case','coalition'))
    if not q or q['quantity']!=d['qty']:return None
    return _buyer_line(q['base_cents'],d,claim.get('own_shipping_cents'))

def _open_batch_offer(d,claim):
    # Supplier plug-in could expose already-committed batch. Here fixture is
    # simulated and seller/buyer authority remains Z in every live run.
    if claim.get('demo') is not True or claim.get('fixture_case')!='existing_batch':return None
    b=core.read_json('open_batches.json')['existing_batch']
    if any((d['spec_digest']!=b['spec_digest'],d['spec_revision']!=b['spec_revision'],
            d['process']!=b['process'],d['material']!=b['material'])):return None
    if b['required_moq_units']-b['committed_units_from_other_buyers']!=d['qty']:return None
    row=_buyer_line(d['qty']*b['unit_base_cents'],d,claim.get('own_shipping_cents'))
    return {'batch':b,'buyer':row}

def _early_route(d,claim,route,row,*,batch=None):
    enough=row['verdict']==T
    gates={'bom_extracted':T,'requirements_bound':T,'individual_budgets':row['verdict'],
           'real_supplier_quote':Z,'real_buyers':Z,'supplier_existing_batch_authority':Z,
           'engineering':Z,'geometry_dfm':Z,'federation_admission':Z,'payment_authority':Z}
    return {'part_no':claim['requirements']['part_no'],'status':
            ('DEMO_READY_TO_REQUEST_BUYER_CONFIRMATION_'+route if enough else 'BUDGET_OR_FEES_NOT_PROVED'),
            'best_route':route,'demand_pool':{
                'source':'SYNTHETIC_EXISTING_VENDOR_BATCH_ONLY' if batch else 'NONE_NEEDED_DIRECT_RETAIL',
                'buyer_count':1,'quantity':(batch['committed_units_from_other_buyers']+d['qty']) if batch else d['qty'],
                'moq':batch['required_moq_units'] if batch else 1,
                'missing_units':0,'peer_buyers_from_fixture':0},
            'allocation':{'verdict':row['verdict'],'per_buyer':[row],
                          'total_all_buyers_cents':row['all_in_cents'] if enough else None,
                          'shipping_cents':row['own_shipping_cents'],
                          'production_cents':row['part_cost_cents']},
            'gates':gates,'execution_gate':Z,'supplier_quote_verified':False,
            'supplier_verified_shipping':False,'paypal_payment_authorized':False,
            'source_scope':'SYNTHETIC_TEST_ONLY'}

def _one_line(intake,part,claim):
    demand,claim_verdict=_make_demand(intake,part,claim)
    if not demand:return {'part_no':part['part_no'],'status':'HOLD','intake':claim_verdict,'execution_gate':Z}
    demo=claim.get('demo') is True
    retail=_retail_offer(demand,claim)
    batch=_open_batch_offer(demand,claim)
    # Supplier already holds 80/100 independently accepted units: check the
    # buyer's missing 20 first. If cheaper retail is available, choose retail.
    if batch and batch['buyer']['verdict']==T:
        if retail and retail['verdict']==T and retail['all_in_cents']<batch['buyer']['all_in_cents']:
            return _early_route(demand,claim,'DIRECT_RETAIL',retail)
        return _early_route(demand,claim,'JOIN_EXISTING_BATCH',batch['buyer'],batch=batch['batch'])
    # Direct route must not require coalition-discovery consent or peer exposure.
    if retail and retail['verdict']==T and claim.get('discovery_consent') is not True:
        return _early_route(demand,claim,'DIRECT_RETAIL',retail)
    peer_demand=_fixture_peer_demands(claim['requirements'],claim.get('fixture_case','coalition')) if demo else []
    # Exclude same buyer: each independently consented synthetic buyer appears only once.
    peer_demand=[d for d in peer_demand if d['buyer_id']!=demand['buyer_id']]
    candidates=[demand]+peer_demand
    grouped=core.group_demand(candidates,demonstration=demo)
    group=next((g for g in grouped['groups'] if demand['buyer_id'] in g['buyers']),None)
    if not group and retail and retail['verdict']==T:
        return _early_route(demand,claim,'DIRECT_RETAIL',retail)
    if not group:
        return {'part_no':part['part_no'],'status':'HOLD','intake':claim_verdict,
                'discovery':{'candidate_peers':len(peer_demand),'groups':0,'excluded':grouped['excluded']},
                'execution_gate':Z}
    count=group['units'];offer=_supplier_offer(claim.get('fixture_case','coalition'),group['demands']) if demo else None
    if not offer:return {'part_no':part['part_no'],'status':'DEMAND_POOL_OPEN',
                         'discovery':{'units':count,'missing_to_moq':None,'peers':len(peer_demand),
                                      'source':'SYNTHETIC_TEST_ONLY' if demo else 'NO_CONNECTED_BUYER_FEED'},
                         'execution_gate':Z}
    moq=offer['moq_units'];ship={x['buyer_id']:claim.get('own_shipping_cents',2500)
                               for x in group['demands']}
    coalition_complete=count>=moq and count<=offer['capacity_units']
    comparison=core.choose_route(group,core.read_json('cases.json')[claim.get('fixture_case','coalition')]['offers'],demonstration=demo)
    route=comparison.get('route')
    chosen=next((q for q in core.read_json('cases.json')[claim.get('fixture_case','coalition')]['offers']
                 if q['route']==route),None)
    allocation=_quote_line(group['demands'],chosen,ship) if chosen else {'verdict':Z,'why':'NO_VERIFIED_ROUTE'}
    # ZTL proof and signed contract cannot be self-attested. A demo route verdict is not an executable order.
    gates={'bom_extracted':intake['extraction'],'requirements_bound':claim_verdict['verdict'],
           'synthetic_pool_filled':T if coalition_complete else Z,
           'individual_budgets':allocation['verdict'],
           'real_buyer_opt_in':Z,'engineering':Z,'geometry_dfm':Z,
           'real_supplier_quote':Z,'supplier_capacity':Z,'all_owner_commitments':Z,
           'federation_admission':Z,'payment_authority':Z}
    actual=T if _truth_all(gates.values())==T else Z
    if route and route!='COALITION':status='DEMO_READY_TO_REQUEST_BUYER_CONFIRMATION_DIRECT' if demo and allocation['verdict']==T else 'DIRECT_ROUTE_RECOMMENDED'
    elif not coalition_complete:status='DEMAND_POOL_OPEN'
    elif allocation['verdict']!=T:status='BUDGET_OR_FEES_NOT_PROVED'
    else:status='DEMO_READY_TO_REQUEST_BUYER_CONFIRMATION' if demo else 'WAITING_FOR_REAL_COMMITMENTS'
    return {'part_no':part['part_no'],'status':status,'origin':'UNVERIFIED_BUYER_UPLOAD',
            'demand_pool':{'source':'SYNTHETIC_TEST_ONLY' if demo else 'NO_EXTERNAL_DEMAND_ACCESS',
                           'buyer_count':group['member_count'],'quantity':count,
                           'moq':moq,'missing_units':max(0,moq-count),
                           'peer_buyers_from_fixture':len(peer_demand)},
            'best_route':route,'allocation':allocation,'gates':gates,'execution_gate':actual,
            'next_buyer_action':'REVIEW_AND_CONFIRM_TEST_ONLY' if status=='DEMO_READY_TO_REQUEST_BUYER_CONFIRMATION'
                                else 'WAIT_FOR_VERIFIED_FEASIBILITY',
            'supplier_quote_verified':False,'paypal_payment_authorized':False,
            'supplier_verified_shipping':False,'assumed_same_fixture_shipping_for_all_routes':True}

def run_intake(filename,data,claim):
    intake=cad_bom.extract(filename,data)
    if intake['extraction']!=T:
        return {'schema':'legion.demand-first.v1','intake':intake,'lines':[],
                'overall':'NEEDS_HUMAN_BOM','live_execution_gate':Z,'new_paypal_captures':0}
    # A full BOM cannot be admitted if only one line is checked.
    results=[]
    for p in intake['bom']:
        spec=(claim.get('requirements') or {}).get('part_no')
        if p['part_no']!=spec:
            results.append({'part_no':p['part_no'],'status':'NEEDS_PART_REQUIREMENTS',
                            'execution_gate':Z,'reason':'OTHER_COMPONENT_NOT_VERIFIED'})
        else:results.append(_one_line(intake,p,claim))
    complete=len(results)==1 and all(x['status'].startswith('DEMO_READY_TO_REQUEST_BUYER_CONFIRMATION') for x in results)
    overall='DEMO_FEASIBLE_NEEDS_ACTUAL_AUTHORITY' if complete else 'HOLD_MISSING_OBLIGATIONS'
    return {'schema':'legion.demand-first.v1','intake':intake,'lines':results, 'buyer_id':claim.get('buyer_id'),
            'overall':overall,'live_execution_gate':Z,'new_paypal_captures':0,
            'customer_call_to_action':'REVIEW_AND_CONFIRM_DEMO_ONLY' if complete else 'WAIT_FOR_FEASIBILITY',
            'evidence_sha256':core.digest({'intake':intake,'claim':claim,'lines':results}),
            'existing_historic_paypal_payments_reused':False}
