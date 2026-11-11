import hashlib,json,re
from pathlib import Path
from deal_rescue.industrial.pmix_adapter import extract
experiment=Path('external/cad-experiment')
cases=json.loads((experiment/'BENCHMARK_RESULTS.json').read_bytes())['cases']
rows=[]
for case in cases:
    raw=(experiment/case['source_path']).read_bytes()
    source_hash=hashlib.sha256(raw).hexdigest()
    assert source_hash==case['sha256']
    declared={int(x) for x in re.findall(rb'^\s*#(\d+)\s*=',raw,re.M)}
    data=extract(raw)
    records=[field for part in data['bom'] for field in part['fields'].values() if field['value'] is not None]
    for kind in ('dimensions','tolerances','datums'):
        records.extend(data['engineering']['semantic'][kind])
    for record in records:
        assert record['file_sha256']==source_hash and record['engineering_verdict']=='Z',case['case']
        assert record['source_refs'],case['case']
        for ref in record['source_refs']:
            assert re.fullmatch(r'#[0-9]+',ref) and int(ref[1:]) in declared,(case['case'],ref)
    assert data['checkout_enabled'] is False and data['procurement_eligible'] is False
    assert data['payment_effects']==data['supplier_effects']==0
    rows.append({'case':case['case'],'sha256':source_hash,'critical_records':len(records),'valid_entity_links':sum(len(x['source_refs']) for x in records)})
assert len(rows)==26 and sum(x['critical_records'] for x in rows)==860
print(json.dumps({'result':'PASS','cases':rows,'critical_records':860,'files':26},indent=2))
