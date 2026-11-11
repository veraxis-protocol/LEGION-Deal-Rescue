/* Demand-first buyer entrance to the ORIGINAL LEGION Deal Rescue page.
   User files POST to localhost only. No supplier uploads / actual payment / external consent.
*/
(() => {
 'use strict';
 const E=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const $=s=>document.querySelector(s);
 const fmt=n=>typeof n==='number'?('$'+(n/100).toFixed(2)):'Unknown';
 let panel=null,result=null,session=null,pending=null;
 const stages=['DRAWING','PARTS','LEGION AT WORK','REVIEW','PAYPAL'];
 function stage(name){
   const nav=$('#df-stages');if(nav)nav.innerHTML=stages.map(s=>`<span ${s===name?'aria-current="step"':''} style="padding:6px;${s===name?'font-weight:bold;background:#dbe6ff':''}">${E(s)}</span>`).join(' → ');
   panel.dataset.screen=name;
 }
 const style=`position:fixed;inset:2vh 2vw;background:#f6f8fb;color:#152033;z-index:10001;overflow:auto;padding:24px 4vw;border:1px solid #dce4f1;border-radius:16px;box-shadow:0 20px 80px #091c4059;font:15px/1.5 system-ui`;
 function mount(){
   if($('#legion-start-drawing'))return;
   const btn=document.createElement('button');btn.id='legion-start-drawing';btn.textContent='Start with a drawing / BOM';
   btn.style.cssText='background:#194ec9;color:white;border:0;padding:10px 16px;border-radius:8px;font-weight:700;cursor:pointer';
   (document.querySelector('header')||document.body).appendChild(btn);
   btn.onclick=open;
   panel=document.createElement('section');panel.id='legion-demand-intake';panel.setAttribute('role','dialog');
   panel.setAttribute('aria-label','Industrial order and engineering drawing intake');panel.setAttribute('aria-modal','true');
   panel.style.cssText=style;panel.hidden=true;document.body.appendChild(panel);
 }
 function open(){mount();panel.hidden=false;renderForm();}
 function close(){if(panel)panel.hidden=true;}
 function renderForm(){
   panel.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:start;gap:16px"><div><h1 style="margin:0">LEGION · Industrial Orders</h1><p>Upload drawing → Review parts → Find suppliers and peers → Validate cost & MOQ → Confirm feasibility → PayPal authorization</p></div><button id="df-close">Close</button></div>
   <nav id="df-stages" aria-label="Purchasing workflow" style="display:flex;flex-wrap:wrap;gap:4px"></nav>
   <p style="padding:12px;border:1px solid #e9dba8;background:#fff8e4">Extraction is not engineering approval. Missing information remains Z. External RFQs, supplier orders and PayPal remain disabled. Demo inputs are clearly marked synthetic.</p>
   <form id="df-form" style="background:white;padding:20px;border-radius:12px;display:grid;gap:12px;max-width:900px">
     <label>CAD / BOM file <input id="df-file" type="file" accept=".dxf,.svg,.csv,.json,.pdf,.step,.stp,.stl" required></label>
     <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px">
      <label>Part number <input id="df-part" value="SLS-BRACKET-REV-C" required></label>
      <label>Revision <input id="df-rev" value="REV-C" required></label>
      <label>Process <input id="df-process" value="SLS" required></label>
      <label>Material <input id="df-mat" value="PA12" required></label>
      <label>Engineering spec SHA-256 <input id="df-hash" value="45fb81e09beb1bff53d8519b84cdbed21291af89a197a41f760471fd54248182" minlength="64" maxlength="64" required></label>
      <label>Budget including own shipping (USD) <input id="df-budget" type="number" min="0" step="0.01" value="780" required></label>
      <label>Individual shipping estimate (USD) <input id="df-ship" type="number" min="0" step="0.01" value="25" required></label>
      <label>Required by <input id="df-date" type="date" value="2026-12-10" required></label>
     </div>
     <label><input id="df-consent" type="checkbox"> Allow matching this request with compatible demand (no contact data disclosed).</label>
     <label><input id="df-demo" type="checkbox" checked> Use SYNTHETIC demo buyer pool and fixture prices (never a real quote).</label>
     <div style="display:flex;gap:12px;flex-wrap:wrap"><button type="button" id="df-sample">Load exact test BOM</button><button type="submit" style="background:#1749be;color:white;padding:10px 18px;border:0;border-radius:8px">Extract and review parts</button></div>
   </form><div id="df-result" aria-live="polite"></div>`;
   $('#df-close').onclick=close;
   $('#df-sample').onclick=async()=>{
     const file=new File([JSON.stringify({bom:[{part_no:'SLS-BRACKET-REV-C',qty:20}]})],'DEMO-BRACKET-20.json',{type:'application/json'});
     const dt=new DataTransfer();dt.items.add(file);$('#df-file').files=dt.files;$('#df-consent').checked=true;
   };
   $('#df-form').onsubmit=submit;
   stage('DRAWING');pending=null;
 }
 const cents=id=>Math.round(Number($(id).value)*100);
 async function submit(ev){
   ev.preventDefault();result=null;session=null;
   const file=$('#df-file').files[0];const max=file&&/\.(step|stp)$/i.test(file.name)?16777216:2097152;
   if(!file||file.size>max){$('#df-result').textContent='File exceeds limit: STEP 16 MB; other formats 2 MB.';return;}
   const raw=new Uint8Array(await file.arrayBuffer());let binary='';for(let i=0;i<raw.length;i+=8192){binary+=String.fromCharCode(...raw.slice(i,i+8192))}
   const spec={part_no:$('#df-part').value.trim(),spec_revision:$('#df-rev').value.trim(),
     spec_digest:$('#df-hash').value.trim(),process:$('#df-process').value.trim(),material:$('#df-mat').value.trim()};
   const demo=$('#df-demo').checked;
   const claim={demo,buyer_id:demo?'DEMO-BUYER-NEW':'USER-BUYER-NOT-VERIFIED',
     requirements:spec,budget_cents:cents('#df-budget'),own_shipping_cents:cents('#df-ship'),
     due_date:$('#df-date').value,taxes_cents:demo?0:null,payment_fees_cents:demo?0:null,
     discovery_consent:$('#df-consent').checked,fixture_case:'coalition'};
   $('#df-result').textContent='Extracting engineering evidence…';
   try{
     const payload={filename:file.name,file_b64:btoa(binary),claim};
     const r=await fetch('/api/industrial/engineering-extract',{method:'POST',headers:{'Content-Type':'application/json'},
       body:JSON.stringify(payload)});
     const x=await r.json();if(!r.ok)throw Error(x.code||x.error||`HTTP ${r.status}`);
     pending=payload;renderParts(x);
   }catch(e){$('#df-result').textContent='Blocked: '+e.message;}
 }
 function renderParts(intake){
   stage('PARTS');$('#df-form').style.display='none';panel.scrollTop=0;
   const evidence=intake.engineering_evidence||{}, eng=evidence.engineering||{};
   $('#df-result').innerHTML=`<h2>PARTS · Confirm purchase intent</h2>
     <p style="overflow-wrap:anywhere">Source SHA-256: ${E(intake.file_sha256)}</p>
     <p>Engineering qualification: Z · Extraction: ${E(intake.extraction)}. Select the components you intend to purchase; this does not approve engineering or authorize an order.</p>
     ${intake.bom.map((p,i)=>`<section style="background:white;padding:12px;margin:10px 0;overflow-wrap:anywhere"><label><input class="df-select" data-index="${i}" type="checkbox"> ${E(p.part_no||'Unknown part number — Z')}</label>
     <p>Quantity: ${E(p.quantity)} · Revision: ${E(p.revision??'Z')} · Material: ${E(p.material??'Z')} · Process: ${E(p.process??'Z')}</p>
     <p>STEP source entities: ${E((p.source_refs||[]).join(', ')||p.origin||'Z')}</p>
     <details><summary>Component specifications and provenance</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">${E(JSON.stringify(p.fields||p,null,2))}</pre></details></section>`).join('')||'<p>No extractable BOM. Provide a structured BOM or resolve parser diagnostics.</p>'}
     <p>Dimensions: ${E(eng.semantic?.dimensions?.length??0)} · GD&amp;T: ${E(eng.semantic?.tolerances?.length??0)} · Units: ${E(JSON.stringify(evidence.units||{}))}</p>
     <details><summary>Engineering evidence, unsupported features and parser diagnostics</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">${E(JSON.stringify(intake,null,2))}</pre></details>
     <label><input id="df-parts-consent" type="checkbox"> I confirm the selected components and quantities are my purchase intent, not engineering approval.</label>
     <p><button id="df-source" disabled>Confirm parts → LEGION AT WORK</button> <button id="df-back">Back to drawing</button></p>`;
   const update=()=>{$('#df-source').disabled=!$('#df-parts-consent').checked||!document.querySelector('.df-select:checked')};
   document.querySelectorAll('.df-select,#df-parts-consent').forEach(el=>el.onchange=update);
   $('#df-back').onclick=renderForm;
   $('#df-source').onclick=async()=>{
     const selected=[...document.querySelectorAll('.df-select:checked')].map(el=>intake.bom[Number(el.dataset.index)]);
     const claim={...pending.claim,parts_confirmed:true,drawing_sha256:intake.file_sha256,
       selected_parts:selected.map(p=>({part_id:p.part_id,part_no:p.part_no,quantity:p.quantity}))};
     stage('LEGION AT WORK');$('#df-result').textContent='Checking exact component requirements. No supplier requests or payments…';
     try{
       const response=await fetch('/api/industrial/intake',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...pending,claim})});
       const x=await response.json();if(!response.ok)throw Error(x.code||x.error);
       result=x;session=x.demo_session;
       stage('REVIEW');renderResult(x);
     }catch(e){$('#df-result').textContent='Blocked: '+e.message;}
   };
 }
 function renderResult(r){
   const lines=r.lines.map(l=>{
     const p=l.demand_pool||{};const a=l.allocation||{};
     return `<section style="background:white;padding:16px;border:1px solid #dfe6f0;border-radius:8px;margin:10px 0"><h3>${E(l.part_no)} — ${E(l.status)}</h3>
       <p>Route: ${E(l.best_route||'Unknown')} · Verified participant pool: ${E(p.source||'Not connected')} · ${E(p.buyer_count??0)} candidate buyers · ${E(p.quantity??0)}/${E(p.moq??'unknown')} units · missing ${E(p.missing_units??'?')}.</p>
       <p>Fixture group cost: ${fmt(a.total_all_buyers_cents)}; each buyer pays own shipping. Buyer own share: ${fmt(a.per_buyer?.[0]?.all_in_cents)} vs cap ${fmt(a.per_buyer?.[0]?.budget_cents)}.</p>
       <details><summary>Exact gates and missing real evidence</summary><pre style="overflow:auto">${E(JSON.stringify(l.gates||{},null,2))}</pre></details></section>`;
   }).join('');
   $('#df-result').innerHTML=`<section style="margin-top:20px"><h2>Engineering intake → supplier search → feasibility</h2>
     <p><b>Overall:</b> ${E(r.overall)} · <b>Live execution:</b> ${E(r.live_execution_gate)} · <b>New PayPal captures:</b> ${E(r.new_paypal_captures)}.</p>
     <p><b>Drawing digest:</b> ${E(r.intake.file_sha256)} · <b>Extraction:</b> ${E(r.intake.extraction)} · raw file retained: NO.</p>
     <h3>Detected component list</h3><table style="width:100%;background:white"><thead><tr><th>Part</th><th>Qty</th><th>Origin</th></tr></thead><tbody>${r.intake.bom.map(p=>`<tr><td>${E(p.part_no)}</td><td>${E(p.quantity)}</td><td>${E(p.origin)}</td></tr>`).join('')}</tbody></table>
     <h3>Procurement decisions</h3>${lines||'<p>Missing machine-readable BOM. Upload CSV/JSON or provide BOM manually.</p>'}
     ${r.customer_call_to_action==='REVIEW_AND_CONFIRM_DEMO_ONLY'?`<button id="df-confirm" style="padding:11px;background:#164ac1;color:white;border:0;border-radius:8px">Confirm demo feasibility review — NOT an order</button>`:''}
     <button id="df-passport">Download evidence passport</button> <button id="df-payment-review">PayPal gate status</button><div id="df-confirm-result"></div></section>`;
   $('#df-payment-review').onclick=()=>{stage('PAYPAL');$('#df-confirm-result').textContent='PayPal authorization: Z. No payment or supplier order is enabled by extraction or purchase-intent confirmation.'};
   $('#df-passport').onclick=()=>{
     const obj=new Blob([JSON.stringify(r,null,2)],{type:'application/json'}),url=URL.createObjectURL(obj),a=document.createElement('a');
     a.href=url;a.download='LEGION_DEMAND_FIRST_PASSPORT.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);
   };
   const confirm=$('#df-confirm');if(confirm)confirm.onclick=async()=>{
     const share=r.lines[0].allocation.per_buyer[0];
     const id='demo_'+Math.random().toString(36).slice(2)+'_'+Date.now();
     const b={demo_session:session,evidence_sha256:r.evidence_sha256,buyer_id:r.buyer_id,
       total_cents:share.all_in_cents,idempotency_key:id,agree:true};
     const t=await fetch('/api/industrial/demo-confirm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});
     const answer=await t.json();$('#df-confirm-result').textContent=t.ok?'Demo-only intent recorded; no PayPal transaction.':'Demo confirmation unavailable: '+(answer.error||answer.code);
   };
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
 document.addEventListener('keydown',e=>{if(e.key==='Escape')close()});
})();
