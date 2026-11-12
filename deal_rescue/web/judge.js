/* LEGION Judge Experience: DRAWING -> PARTS -> ENGINEERING REVIEW -> PROCUREMENT -> COALITION -> PAYMENT -> RESULT.
   CASE A (real engineering, computed now) and CASE B (recorded commerce replay) are always labelled; no screen shows
   a stored PASS: every value comes from the server's current run or the recorded evidence files. */
(function(){
 const $=s=>document.querySelector(s);
 const esc=v=>String(v??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
 const usd=c=>c==null?'—':'$'+(c/100).toLocaleString('en-US',{minimumFractionDigits:2});
 const badge=v=>`<b class="jx-b jx-${esc(String(v).split(/[ :]/)[0])}">${esc(v)}</b>`;
 const STEPS=['DRAWING','PARTS','ENGINEERING REVIEW','PROCUREMENT','COALITION','PAYMENT','RESULT'];
 const CASE=['A','A','A','A','MECHANISM','B','A+B'];
 let panel=null,state=null,part=null;
 async function get(url){const r=await fetch(url);const x=await r.json();if(!r.ok)throw Error((x.error||('HTTP '+r.status))+(x.reason?': '+x.reason:'')+(x.action?' — '+x.action:''));return x;}
 function style(){
   const st=document.createElement('style');st.textContent=`
   #jx{position:fixed;inset:12px;z-index:70;background:#f6f7fb;border-radius:14px;box-shadow:0 10px 40px #0004;overflow:auto;padding:20px 24px;font:14px system-ui;color:#1d2433}
   #jx table{border-collapse:collapse;width:100%;background:#fff}#jx td,#jx th{border-bottom:1px solid #e3e6ee;padding:5px 8px;text-align:left;vertical-align:top}
   #jx .steps{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 14px}#jx .steps span{padding:5px 10px;border-radius:16px;background:#e5e8f1;font-size:12px}
   #jx .steps span.on{background:#1749be;color:#fff}#jx .steps span.on .tag{background:#ffffff33;color:#fff}#jx .card{background:#fff;border-radius:10px;padding:14px 16px;margin-bottom:12px;border:1px solid #e3e6ee}
   #jx .caseA{border-left:5px solid #1749be}#jx .caseB{border-left:5px solid #0a7d4f}#jx .synth{border-left:5px dashed #c9a400}
   #jx button.go{background:#1749be;color:#fff;border:0;border-radius:8px;padding:9px 16px;cursor:pointer}
   #jx .tag{font-size:11px;padding:2px 7px;border-radius:10px;background:#eef;margin-left:6px}
   .jx-b{padding:1px 7px;border-radius:6px;background:#eee}.jx-T,.jx-EARNED,.jx-FULFILLED,.jx-PASS_COMPLETED,.jx-SANDBOX_PAYMENT_CONFIRMED{background:#d9f5df}
   .jx-F,.jx-REFUTED,.jx-FAILED,.jx-BLOCKED,.jx-REFUSED{background:#fbdcdc}.jx-Z,.jx-OPEN,.jx-HOLD{background:#fff1c2}
   #jx code{font-size:12px;word-break:break-all}#jx a{color:#1749be}`;
   document.head.appendChild(st);
 }
 async function mount(){
   if($('#legion-judge'))return;style();
   const b=document.createElement('button');b.id='legion-judge';b.textContent='Judge walkthrough · drawing to payment';
   b.style.cssText='background:#0a7d4f;color:#fff;border:0;border-radius:8px;padding:8px 12px;margin-left:8px;cursor:pointer';
   b.onclick=()=>open(0);(document.querySelector('header')||document.body).appendChild(b);
   try{state=await get('/api/judge/state');}catch(e){state={cad:{configured:false,reason:e.message}};}
   const m=/judge=([1-7])/.exec(location.hash);if(m)autoplay(Number(m[1]));
 }
 function shell(i){
   return `<div style="display:flex;justify-content:space-between;align-items:center"><div><h2 style="margin:0">LEGION · from drawing to payment</h2>
   <div style="color:#555">CASE A = real reBot engineering (computed now) · CASE B = recorded commerce replay (PayPal Sandbox) · they are never mixed</div></div>
   <button id="jx-close">Close</button></div>
   <div class="steps">${STEPS.map((s,k)=>`<span class="${k===i?'on':''}">${k+1}. ${s}<span class="tag">${CASE[k]}</span></span>`).join('')}</div><div id="jx-body"><p>Working…</p></div>`;
 }
 function open(i){
   if(!panel){panel=document.createElement('div');panel.id='jx';document.body.appendChild(panel);}
   panel.hidden=false;show(i);
 }
 function next(i,label){return `<button class="go" id="jx-next" data-i="${i}">${esc(label)}</button>`;}
 function show(i){
   panel.innerHTML=shell(i);$('#jx-close').onclick=()=>panel.hidden=true;
   [drawing,parts,review,procurement,coalition,payment,result][i]().then(()=>{const n=$('#jx-next');if(n)n.onclick=()=>show(Number(n.dataset.i));})
     .catch(e=>{$('#jx-body').innerHTML=`<div class="card" id="jx-error"><b>Blocked:</b> ${esc(e.message)}</div>`;});
 }
 async function drawing(){
   if(!state.cad.configured){$('#jx-body').innerHTML=`<div class="card caseA"><h3>CAD is not configured on this server</h3><p>${esc(state.cad.reason)}</p><p><b>Action:</b> ${esc(state.cad.action||'')}</p></div>`;return;}
   const r=await get('/api/industrial/cad027/stage?n=1'),d=r.drawing;
   $('#jx-body').innerHTML=`<div class="card caseA"><h3>1. Drawing <span class="tag">CASE A · REAL</span></h3>
   <p><b>${esc(d.file)}</b> · ${(d.bytes/1e6).toFixed(2)} MB · run ${esc(r.run_utc)}</p>
   <p>SHA-256 <code>${esc(d.sha256)}</code> ${badge(d.status)} ${d.status==='T'?'matches the pinned source':'does not match the pin — the run is blocked'}</p>
   <p>Source: Seeed-Projects/reBot-DevArm (pinned commit, see <a href="/api/judge/evidence?name=SOURCE_MANIFEST.json" target="_blank">SOURCE_MANIFEST.json</a>)</p>
   <table><tr><th>Document</th><th>SHA-256</th></tr>${Object.entries(r.source_documents||{}).map(([k,v])=>`<tr><td>${esc(v.path)}</td><td><code>${esc(v.sha256)}</code></td></tr>`).join('')}</table>
   ${d.status==='T'?next(1,'Read the assembly (OpenCascade XCAF)'):''}</div>`;
 }
 async function parts(){
   const r=await get('/api/industrial/cad027/stage?n=2'),x=r.xcaf,b=r.bom;
   part=part||(b.rows.find(p=>p.group==='cnc')||b.rows[0]).part_id;
   $('#jx-body').innerHTML=`<div class="card caseA"><h3>2. Parts <span class="tag">CASE A · REAL</span></h3>
   <p>XCAF computed now: <b id="jx-xcaf">${x.assemblies} sub-assemblies · ${x.leaf_definitions} part definitions · ${x.leaf_instances} instances</b> · unit ${esc(x.length_unit)}</p>
   <p>Factory BOM: <b id="jx-bom">${b.mandatory_positions_matched}/${b.mandatory_positions} parts · ${b.mandatory_instances_step}/${b.mandatory_instances_readme} instances</b> ${badge(r.bom_status)} · optional ${b.optional.map(o=>esc(o.part_id)+' ×'+o.quantity+' (STEP '+o.step_quantity+')').join(', ')} · purchased rows ${b.purchased_readme_positions}</p>
   <p>Select a part for procurement: <select id="jx-part">${b.rows.map(p=>`<option ${p.part_id===part?'selected':''}>${esc(p.part_id)}</option>`).join('')}</select></p>
   <table><tr><th>Part</th><th>Qty readme / STEP</th><th>Material</th><th>Process</th><th>Geometry (STEP)</th><th>Tolerance</th></tr>
   ${b.rows.map(p=>`<tr><td>${esc(p.part_id)}</td><td>${p.quantity} / ${p.step_quantity} ${badge(p.quantity_match?'T':'F')}</td><td>${esc(p.material)}</td><td>${esc(p.manufacturing_process)}</td><td>${p.geometry?esc(p.geometry.bbox.join(' × '))+' mm':'—'}</td><td>${p.tolerances?esc(p.tolerances):'<i>not stated in source</i>'}</td></tr>`).join('')}</table>
   ${next(2,'Engineering review (ZTL)')}</div>`;
   $('#jx-part').onchange=e=>{part=e.target.value;};
 }
 async function review(){
   const r=await get('/api/industrial/cad027/stage?n=3'),z=r.ztl,c=r.cad025,t=z.integration_test;
   $('#jx-body').innerHTML=`<div class="card caseA"><h3>3. Engineering review <span class="tag">CASE A · REAL</span></h3>
   <p>reBot production verdict: <span id="jx-ztl">${badge(z.production_verdict)}</span> — ${esc(z.production_scope)}</p>
   ${z.predicates.map(p=>`<div class="card"><b>${esc(p.requirement)}</b> — ${badge(p.verdict)} ${p.RAIL_TOLERANCE?'· RAIL_TOLERANCE '+badge(p.RAIL_TOLERANCE):''} · stand called: ${p.stand_called?'yes':'no — inputs incomplete, nothing invented'}
     <table>${Object.entries(p.inputs||{}).map(([k,v])=>`<tr><td>${esc(k)}</td><td>${esc(v.value)}</td><td>${esc(v.source)}</td></tr>`).join('')}</table>
     <p>Missing: ${p.missing.map(esc).join('; ')}</p></div>`).join('')}
   <div class="card synth"><b>Integration test — NOT a reBot check</b> <span class="tag">TEST_SCENARIO_NOT_REBOT</span><br>
   Real ZTL stand on ${esc(t.brick_source)}: ${badge(t.verdict)} · judge ${esc(t.judge)} · ${esc(t.via)} (${t.seconds}s). ${esc(t.scope)}</div>
   <p>CAD-025: spec ${esc(c.spec_validation.status)} ${esc(c.spec_validation.code||'')} · ENGINEERING_ADMISSION <span id="jx-adm">${badge(c.engineering_admission)}</span></p>
   ${next(3,'Procurement for '+part)}</div>`;
 }
 async function procurement(){
   await get('/api/industrial/cad027/stage?n=4');
   const p=await get('/api/judge/procurement?part='+encodeURIComponent(part||''));
   $('#jx-body').innerHTML=`<div class="card caseA"><h3>4. Procurement <span class="tag">CASE A · REAL</span></h3>
   <p>Part <b>${esc(p.part_id)}</b> × ${p.quantity_per_arm} per arm · status <span id="jx-proc">${badge(p.status)}</span> — ${esc(p.why)} (ENGINEERING_ADMISSION ${badge(p.engineering_admission)})</p>
   <table><tr><th>Required for a supplier request (CAD-025 fields)</th><th>Value</th><th>Status</th><th>Source</th></tr>
   ${p.fields.map(f=>`<tr><td>${esc(f.field)}</td><td>${esc(f.value??'—')}</td><td>${badge(f.status)}</td><td>${esc(f.source)}</td></tr>`).join('')}</table>
   <p>Confirmed ${p.confirmed}/${p.required}</p>
   <table><tr><th>Route</th><th>MOQ</th><th>Price</th><th>Needs</th></tr>${p.routes.map(r=>`<tr><td>${esc(r.route)}</td><td>${esc(r.moq)}</td><td>${esc(r.price)}</td><td>${r.needs.map(esc).join('; ')}</td></tr>`).join('')}</table>
   <p><i>${esc(p.rfq_draft.text)}</i> · sent: no · CAD attached: no</p>
   ${next(4,'How a coalition order works')}</div>`;
 }
 async function coalition(){
   const c=await get('/api/judge/coalition');
   $('#jx-body').innerHTML=`<div class="card synth"><h3>5. Coalition <span class="tag">MECHANISM · SYNTHETIC FIXTURE</span></h3>
   <p>${esc(c.label)} · computed now by ${esc(c.computed_by)}</p>
   <p>Five requests of 20 → <b id="jx-coal">${c.units}/${c.moq} units</b> · route ${badge(c.route)} · group ${usd(c.total_cents)} (production ${usd(c.production_cents)} + shipping ${usd(c.shipping_cents)}) · live execution ${badge(c.live_execution_gate)}</p>
   <table><tr><th>Buyer (synthetic)</th><th>Qty</th><th>All-in</th><th>Cap</th><th>Within cap</th></tr>${c.requests.map(r=>`<tr><td>${esc(r.buyer)}</td><td>${r.qty}</td><td>${usd(r.all_in_cents)}</td><td>${usd(r.budget_cents)}</td><td>${badge(r.within_budget?'T':'F')}</td></tr>`).join('')}</table>
   ${next(5,'Recorded payment workflow (CASE B)')}</div>`;
 }
 async function payment(){
   const p=await get('/api/judge/payment');
   $('#jx-body').innerHTML=`<div class="card caseB"><h3>6. Payment <span class="tag">CASE B · RECORDED SANDBOX REPLAY</span></h3>
   <p>${esc(p.label)} · contract <code>${esc(p.contract_hash)}</code> · MOQ ${p.moq}</p>
   <p>Requests: ${p.requests.map(r=>`${esc(r.customer)} ${r.units} units (alone: ${esc(r.alone)})`).join(' · ')}</p>
   <table><tr><th>Terms</th><th>Design</th><th>Per buyer</th><th>Total</th><th>Outcome</th></tr>${p.terms_versions.map(t=>`<tr><td>v${t.version}</td><td>${esc(t.design)}</td><td>${usd(t.per_buyer_cents)}</td><td>${usd(t.total_cents)}</td><td>${badge(t.final_state)} ${esc(t.why||'')}</td></tr>`).join('')}</table>
   <p>Independent Judge: ${badge(p.judge.verdict)} ${esc(p.judge.checks)} · ${esc(p.judge.scope)}</p>
   <table><tr><th>Payer</th><th>Amount</th><th>Order</th><th>Capture</th><th>State</th></tr>${p.captures.map(s=>`<tr><td>${esc(s.customer)}</td><td>${usd(s.amount_cents)}</td><td><code>${esc(s.order_id)}</code></td><td><code>${esc(s.capture_id)}</code></td><td>${badge(s.state)}</td></tr>`).join('')}</table>
   <p id="jx-pay">${p.readback_confirmed_captures}/5 readback-confirmed · ${usd(p.provider_confirmed_cents)} · ${esc(p.badge)}</p>
   ${next(6,'Execution passport')}</div>`;
 }
 async function result(){
   const r=await get('/api/judge/result'),a=r.case_a,b=r.case_b,g=r.judge_go_no_go;
   $('#jx-body').innerHTML=`<div class="card"><h3>7. Result — execution passport</h3>
   <table><tr><th></th><th>CASE A · real reBot engineering</th><th>CASE B · recorded commerce replay</th></tr>
   <tr><td>Identity</td><td><code>${esc(a.contract_hash)}</code><br>CAD <code>${esc(a.cad_sha256)}</code></td><td>contract <code>${esc(b.contract_hash)}</code></td></tr>
   <tr><td>Result</td><td>OCP ${badge(a.ocp)} · BOM ${badge(a.bom)} · ZTL ${badge(a.ztl_production)} · RAIL_TOLERANCE ${badge(a.rail_tolerance)} · ENGINEERING_ADMISSION ${badge(a.engineering_admission)} · procurement ${badge(a.procurement)}</td>
   <td>Judge ${badge(b.judge.verdict)} ${esc(b.judge.checks)} · ${b.captures} Sandbox captures · ${usd(b.provider_confirmed_cents)}</td></tr>
   <tr><td>Payments</td><td>${a.payments}</td><td>${b.captures} (this contract only)</td></tr></table>
   <p>Attributing CASE B captures to CASE A: <span id="jx-cross">${badge(r.cross_case_payment_attribution.startsWith('REFUSED')?'REFUSED':'F')}</span> ${esc(r.cross_case_payment_attribution.slice(0,90))}…</p>
   <h4>How CASE A would reach payment</h4><table><tr><th>Gate</th><th>Requires</th><th>CASE A now</th></tr>${r.bridge.map(x=>`<tr><td>${esc(x.gate)}</td><td>${esc(x.requires)}</td><td>${badge(x.case_a_status)}</td></tr>`).join('')}</table>
   <h4>Boundaries</h4><table>${Object.entries(r.boundaries).map(([k,v])=>`<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join('')}</table>
   <h4>Judge verdict</h4><p>${g?`JUDGE_GO_NO_GO final ${badge(g.final)} · commit <code>${esc(g.git_commit)}</code>${g.gates&&g.gates.browser_e2e==='Z'?' · browser E2E not recorded yet (final becomes T only after it passes)':''} · negatives ${esc(g.negative_tests)} · required skips ${esc(g.skipped_required)}`:'Not produced by this server start (run python -m scripts.judge_demo).'}</p>
   <p>Evidence: ${['JUDGE_GO_NO_GO.json','SOURCE_MANIFEST.json','CAD_XCAF_RESULT.json','BOM_RESULT.json','ZTL_RESULT.json','COMMERCE_REPLAY_RESULT.json','PAYPAL_EVIDENCE_CHECK.json','NEGATIVE_TESTS.json','TEST_RESULTS.json','CLEAN_CLONE_LOG.txt'].map(n=>`<a href="/api/judge/evidence?name=${n}" target="_blank">${n}</a>`).join(' · ')}
   · <a href="/api/industrial/cad027/report.json" download>CAD run JSON</a></p></div>`;
 }
 async function autoplay(n){
   open(0);
   for(let i=1;i<n;i++){for(let k=0;k<600&&!$('#jx-next');k++)await new Promise(r=>setTimeout(r,200));const b=$('#jx-next');if(!b)return;b.click();await new Promise(r=>setTimeout(r,150));}
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
})();
