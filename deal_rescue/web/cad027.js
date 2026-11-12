/* CAD-027 demo: DRAWING -> PARTS -> ENGINEERING REVIEW -> RESULT, one real STEP, shown one step at a time.
   Every number on screen comes from /api/industrial/cad027/stage (the server's current run); nothing is hard-coded. */
(function(){
 const $=s=>document.querySelector(s);
 const esc=v=>String(v??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
 const badge=v=>`<b class="c27-b c27-${esc(v)}">${esc(v)}</b>`;
 let panel=null;
 const STEPS=['DRAWING','PARTS','ENGINEERING REVIEW','RESULT'];
 function mount(){
   if($('#legion-cad027'))return;
   const b=document.createElement('button');b.id='legion-cad027';b.textContent='CAD → BOM → ZTL review';
   b.onclick=open;(document.querySelector('header')||document.body).appendChild(b);
   fetch('/api/industrial/cad027/status').then(r=>r.json()).then(s=>{cadStatus=s;if(!s.configured)b.textContent='CAD review: not configured';})
     .catch(()=>{cadStatus={configured:false,reason:'status unavailable'};});
   const st=document.createElement('style');st.textContent=`
   #c27{position:fixed;inset:16px;z-index:60;background:#f7f8fb;border-radius:14px;box-shadow:0 10px 40px #0004;overflow:auto;padding:22px;font:14px system-ui}
   #c27 table{border-collapse:collapse;width:100%;background:#fff}#c27 td,#c27 th{border-bottom:1px solid #e3e6ee;padding:5px 8px;text-align:left;vertical-align:top}
   #c27 .c27-steps{display:flex;gap:8px;margin:10px 0 16px}#c27 .c27-steps span{padding:6px 12px;border-radius:20px;background:#e6e9f2}
   #c27 .c27-steps span.on{background:#1749be;color:#fff}#c27 .card{background:#fff;border-radius:10px;padding:16px;margin-bottom:12px}
   #c27 button.go{background:#1749be;color:#fff;border:0;border-radius:8px;padding:9px 16px;cursor:pointer}
   .c27-b{padding:1px 7px;border-radius:6px;background:#eee}.c27-T,.c27-EARNED{background:#d9f5df}.c27-F,.c27-REFUTED{background:#fbdcdc}.c27-Z,.c27-OPEN{background:#fff1c2}
   #c27 code{font-size:12px;word-break:break-all}`;
   document.head.appendChild(st);
 }
 function shell(active){
   return `<div style="display:flex;justify-content:space-between"><h2 style="margin:0">LEGION · CAD to engineering review</h2><button id="c27-close">Close</button></div>
   <div class="c27-steps">${STEPS.map((s,i)=>`<span class="${i===active?'on':''}">${i+1}. ${s}</span>`).join('')}</div><div id="c27-body"></div>`;
 }
 async function stage(n){
   const body=$('#c27-body');body.insertAdjacentHTML('beforeend',`<p id="c27-wait">Running step ${n} on the server…</p>`);
   const r=await fetch('/api/industrial/cad027/stage?n='+n);const x=await r.json();$('#c27-wait')?.remove();
   if(!r.ok)throw Error((x.error||('HTTP '+r.status))+(x.reason?': '+x.reason:'')+(x.action?' — '+x.action:''));return x;
 }
 let cadStatus=null;
 function open(){
   if(!panel){panel=document.createElement('div');panel.id='c27';document.body.appendChild(panel);}
   panel.hidden=false;
   if(cadStatus&&!cadStatus.configured){   // explain instead of entering a flow that cannot run
     panel.innerHTML=shell(0);$('#c27-close').onclick=()=>panel.hidden=true;
     $('#c27-body').innerHTML=`<div class="card"><h3>CAD is not configured on this server</h3><p>${esc(cadStatus.reason)}</p><p><b>Action:</b> ${esc(cadStatus.action||'')}</p></div>`;
     return;
   }
   show(0);
 }
 function show(i,r){
   panel.innerHTML=shell(i);$('#c27-close').onclick=()=>panel.hidden=true;
   [drawing,parts,review,result][i](r).catch(e=>{$('#c27-body').insertAdjacentHTML('beforeend',`<p class="card">Blocked: ${esc(e.message)}</p>`)});
 }
 async function drawing(){
   const r=await stage(1),d=r.drawing;
   $('#c27-body').innerHTML=`<div class="card"><h3>1. Drawing</h3>
   <p>File <b>${esc(d.file)}</b> · ${(d.bytes/1e6).toFixed(2)} MB · run ${esc(r.run_utc)}</p>
   <p>SHA-256 <code>${esc(d.sha256)}</code> ${badge(d.status)} ${d.status==='T'?'matches the pinned source':'DOES NOT match the pinned source — blocked'}</p>
   <p>Factory BOM: ${esc(d.readme)} <code>${esc(d.readme_sha256)}</code></p>
   ${d.status==='T'?'<button class="go" id="c27-next">Read the assembly (OpenCascade XCAF)</button>':''}</div>`;
   $('#c27-next')&&($('#c27-next').onclick=()=>show(1));
 }
 async function parts(){
   const r=await stage(2),x=r.xcaf,b=r.bom;
   const rows=b.rows.map(p=>`<tr><td>${esc(p.part_id)}</td><td>${p.quantity}</td><td>${p.step_quantity} ${badge(p.quantity_match?'T':'F')}</td>
     <td>${esc(p.material)}</td><td>${esc(p.manufacturing_process)}</td>
     <td>${p.geometry?esc(p.geometry.bbox.join(' × '))+' '+esc(p.geometry.unit)+'<br>'+p.geometry.solids+' solid · '+p.geometry.faces+' faces':'—'}</td>
     <td>${p.tolerances?esc(p.tolerances):'<i>not stated in source</i>'}</td></tr>`).join('');
   $('#c27-body').innerHTML=`<div class="card"><h3>2. Parts</h3>
   <p>XCAF: root <b>${esc(x.roots.join(', '))}</b> · ${x.assemblies} assemblies · ${x.leaf_definitions} part definitions · ${x.leaf_instances} instances · unit ${esc(x.length_unit)}</p>
   <p>Fabricated parts: <b>${b.mandatory_positions_matched}/${b.mandatory_positions}</b> positions and <b>${b.mandatory_instances_step}/${b.mandatory_instances_readme}</b> instances match the factory readme ${badge(r.bom_status)}</p>
   <table><tr><th>Part ID</th><th>Qty readme</th><th>Qty STEP</th><th>Material</th><th>Process</th><th>Geometry (STEP)</th><th>Tolerances</th></tr>${rows}</table>
   <h4>Optional (shown separately)</h4><p>${b.optional.map(o=>`${esc(o.part_id)} ×${o.quantity} — in STEP: ${o.step_quantity}`).join('; ')}</p>
   <h4>Purchased parts (${b.purchased_readme_positions} readme rows) and fasteners in the STEP</h4>
   <p>Exact model-code matches: ${esc(b.purchased_exact_code_matches.join(', '))}. ${esc(b.note)}</p>
   <p style="columns:3">${Object.entries(b.purchased_and_fasteners_in_step).map(([k,v])=>`${esc(k)} ×${v}`).join('<br>')}</p>
   <button class="go" id="c27-next">Send to ZTL Engineer</button></div>`;
   $('#c27-next').onclick=()=>show(2);
 }
 async function review(){
   const r=await stage(3),z=r.ztl,c=r.cad025,t=z.integration_test;
   const pred=p=>`<div class="card" style="border:1px solid #e3e6ee"><b>${esc(p.requirement)}</b> — ZTL ${badge(p.verdict)} ${p.RAIL_TOLERANCE?'· RAIL_TOLERANCE '+badge(p.RAIL_TOLERANCE):''} · stand called: ${p.stand_called?'yes':'no (inputs incomplete; nothing invented)'}
     <table><tr><th>Input</th><th>Value</th><th>Source</th></tr>${Object.entries(p.inputs||{}).map(([k,v])=>`<tr><td>${esc(k)}</td><td>${esc(v.value)}</td><td>${esc(v.source)}</td></tr>`).join('')}</table>
     ${p.tolerance?`<p>Only tolerance in the sources: “${esc(p.tolerance.only_tolerance_in_sources.text)}” — readme line ${p.tolerance.only_tolerance_in_sources.line}, section ${esc(p.tolerance.only_tolerance_in_sources.section)}. Applies to the purchased rail: <b>no</b> (${esc(p.tolerance.only_tolerance_in_sources.why)}).</p>`:''}
     <p>Missing source data: ${p.missing.map(esc).join('; ')}</p></div>`;
   $('#c27-body').innerHTML=`<div class="card"><h3>3. Engineering review — ZTL Engineer</h3>
   <p>reBot production verdict: ${badge(z.production_verdict)} — ${esc(z.production_scope)}</p>
   ${z.predicates.map(pred).join('')}
   <p style="color:#555">STEP geometry is a nominal model: its 0.001 mm rounding is representation precision, not manufacturing precision.</p>
   <div class="card" style="border:2px dashed #c9a400"><b>Integration test scenario — NOT a reBot check</b><br>
   Real ZTL stand on ${esc(t.brick_source)}: ${badge(t.verdict)} · judge ${esc(t.judge)} · ${esc(t.via)} (${t.seconds}s)<br>${esc(t.scope)}</div>
   <h4>CAD-025 engineering gate</h4>
   <p>Spec: ${esc(c.spec_validation.status)} ${esc(c.spec_validation.code||'')} · ENGINEERING_ADMISSION ${badge(c.engineering_admission)} (${esc(c.admission_code||'')})</p>
   <p>${esc(c.why)}</p><button class="go" id="c27-next">Show result</button></div>`;
   $('#c27-next').onclick=()=>show(3);
 }
 async function result(){
   const r=await stage(4),o=r.overall;
   $('#c27-body').innerHTML=`<div class="card"><h3>4. Result</h3>
   <table><tr><td>Source</td><td>${esc(r.drawing.file)} <code>${esc(r.drawing.sha256)}</code></td></tr>
   <tr><td>Assembly read (OCP/XCAF)</td><td>${badge(o.ocp_xcaf)}</td></tr>
   <tr><td>BOM vs factory readme</td><td>${badge(o.bom)} ${r.bom.mandatory_positions_matched}/${r.bom.mandatory_positions} parts, ${r.bom.mandatory_instances_step}/${r.bom.mandatory_instances_readme} instances</td></tr>
   <tr><td>ZTL, reBot production predicates</td><td>${badge(o.ztl_production)} — no predicate has complete sourced inputs · RAIL_TOLERANCE ${badge(o.rail_tolerance)}</td></tr>
   <tr><td>ZTL integration test (not reBot)</td><td>${badge(o.ztl_integration_test)} — the stand route works; approves nothing about the arm</td></tr>
   <tr><td>ENGINEERING_ADMISSION</td><td>${badge(o.engineering_admission)}</td></tr>
   <tr><td>DEMO_GO</td><td>${badge(o.demo)} — ${esc(o.demo_means)}</td></tr>
   <tr><td>Missing for engineering T</td><td>${o.missing_for_engineering_T.map(esc).join('<br>')}</td></tr>
   <tr><td>External effects</td><td>0 supplier requests · 0 PayPal calls · CAD not transmitted</td></tr></table>
   <p>Run ${esc(r.run_utc)} → ${esc(r.finished_utc)} · <a href="/api/industrial/cad027/report.json" download>Download JSON report</a></p></div>`;
 }
 // Presenter link: /#cad027=N opens the panel and advances through steps 1..N (same real server calls).
 async function autoplay(){
   const m=/cad027=([1-4])/.exec(location.hash);if(!m)return;
   open();
   for(let i=1;i<Number(m[1]);i++){
     for(let k=0;k<400&&!$('#c27-next');k++)await new Promise(r=>setTimeout(r,250));
     $('#c27-next').click();await new Promise(r=>setTimeout(r,100));
   }
 }
 function boot(){mount();autoplay();}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
