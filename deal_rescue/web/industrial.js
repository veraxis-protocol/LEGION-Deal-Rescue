/* LEGION Industrial Sourcing embedded in the existing Deal Rescue page.
   Read-only APIs, no credentials, no data export to providers, no payment action. */
(() => {
  'use strict';
  const esc = s => String(s ?? '').replace(/[&<>"']/g, v => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[v]));
  const fmt = c => c == null ? 'Unknown' : '$' + (c / 100).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
  let panel, active = 'coalition';
  const GET = async path => {
    const r = await fetch(path,{cache:'no-store'});
    if (!r.ok) throw new Error(`Request failed: HTTP ${r.status}`);
    return r.json();
  };
  function mount() {
    if (document.getElementById('legion-industrial-button')) return;
    const nav = document.querySelector('header') || document.body;
    const btn = document.createElement('button');
    btn.id='legion-industrial-button'; btn.textContent='Industrial Sourcing';
    btn.setAttribute('aria-label','Open industrial sourcing and coalition discovery');
    btn.style.cssText='background:#1749be;color:white;border:0;border-radius:8px;padding:9px 14px;cursor:pointer;font-weight:650';
    nav.appendChild(btn); btn.onclick = () => open();
    panel = document.createElement('section'); panel.id = 'legion-industrial-panel';
    panel.setAttribute('role','dialog'); panel.setAttribute('aria-modal','true');
    panel.setAttribute('aria-label','Industrial sourcing');
    panel.style.cssText='display:none;position:fixed;inset:3vh 3vw;background:#f6f7fa;z-index:9999;overflow:auto;padding:24px;box-shadow:0 12px 90px #17255466;border-radius:16px;color:#14181f;font:14px/1.5 system-ui';
    document.body.appendChild(panel);
  }
  async function open() {
    mount(); panel.style.display='block';
    panel.innerHTML='<p>Loading industrial sourcing...</p>';
    try {
      const [cases,registry,decision] = await Promise.all([
        GET('/api/industrial/cases'),GET('/api/industrial/registry'),GET('/api/industrial/decision?case='+encodeURIComponent(active))]);
      render(cases,registry,decision);
    } catch (e) {
      panel.textContent = 'Sourcing evidence unavailable: ' + e.message;
      const b=document.createElement('button');b.textContent='Close';b.onclick=close;panel.appendChild(b);
    }
  }
  function close() { if(panel) panel.style.display='none'; }
  function render(cases,registry,d) {
    const route=d.route_decision, group=d.demand.group, statuses=d.gates;
    const row = Object.entries(statuses).map(([k,v])=>`<tr><td>${esc(k.replaceAll('_',' '))}</td><td><strong style="color:${v==='T'?'#086b40':v==='F'?'#9b1c1c':'#745b12'}">${esc(v)}</strong></td></tr>`).join('');
    const offers=(route.alternatives||[]).map(a=>`<tr><td>${esc(a.route.replaceAll('_',' '))}</td><td>${fmt(a.landed_cents)}</td><td>${a.route===route.route?'Lowest illustrative route':'Compared'}</td></tr>`).join('');
    const sources=registry.records.map(s=>`<tr><td>${esc(s.name)}</td><td>${esc(s.kind.replaceAll('_',' '))}</td><td><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">Official site</a></td><td>${esc(s.quote_verdict)}</td></tr>`).join('');
    panel.innerHTML=`
      <div style="display:flex;align-items:center;flex-wrap:wrap;gap:12px;justify-content:space-between">
      <div><h1 style="margin:0">LEGION · Industrial Sourcing</h1><p style="margin:4px 0;color:#566078">Engineering constraints → buyer discovery → supplier alternatives → federation proposal.</p></div>
      <button id="li-close" style="padding:10px 16px">Close</button></div>
      <p style="background:#fff3d7;border:1px solid #e7d39d;border-radius:8px;padding:10px 14px"><b>Test-only demonstration.</b> No verified real customer demand, supplier quotation, ZTL engineering proof, manufacturing commitment or new PayPal capture. Existing historical PayPal evidence remains separate.</p>
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:18px 0">
      <label for="li-case">Scenario</label><select id="li-case" style="padding:10px;min-width:250px">${cases.map(c=>`<option value="${esc(c.id)}" ${c.id===d.case_id?'selected':''}>${esc(c.title)}</option>`).join('')}</select>
      <a download="INDUSTRIAL_PASSPORT_${esc(d.case_id)}.json" href="/api/industrial/passport?case=${encodeURIComponent(d.case_id)}">Download evidence passport</a>
      <a download="RFQ_${esc(d.case_id)}.txt" href="/api/industrial/rfq?case=${encodeURIComponent(d.case_id)}">Download draft supplier RFQ</a></div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px">
        <div style="background:white;border-radius:9px;padding:16px"><small>Buyer demand</small><h2>${group.member_count||0} prospects · ${group.units||0} units</h2><p>Same specification hash & version required. Permissioned inputs only.</p></div>
        <div style="background:white;border-radius:9px;padding:16px"><small>Production discovery</small><h2>${registry.total} source entrypoints</h2><p>Providers, networks, directories and RFQ sources. Not 36 onboarded suppliers.</p></div>
        <div style="background:white;border-radius:9px;padding:16px"><small>Best route within fixture</small><h2>${esc((route.route||'HOLD').replaceAll('_',' '))}</h2><p>${fmt(route.landed_cents)} · illustrative, not a binding quote.</p></div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;margin-top:18px">
       <div style="background:white;border-radius:9px;padding:16px"><h2>Commercial alternatives</h2><table style="width:100%;text-align:left"><thead><tr><th>Route</th><th>All-in synthetic</th><th>Decision</th></tr></thead><tbody>${offers}</tbody></table><p>Budget, MOQ, capacity, due date and exact spec are enforced before route selection.</p></div>
       <div style="background:white;border-radius:9px;padding:16px"><h2>Trust / engineering / authority</h2><table style="width:100%;text-align:left"><thead><tr><th>Obligation</th><th>T/F/Z</th></tr></thead><tbody>${row}</tbody></table><p><b>Federation:</b> ${esc(d.federation_proposal.reliance)}. <b>PayPal:</b> 0 captures for this new contract.</p></div>
      </div>
      <div style="background:white;border-radius:9px;padding:16px;margin-top:18px"><h2>Industrial supplier discovery (${registry.total} entrypoints)</h2>
        <p>Only public, source-linked discovery. No claimed stock, manufacturing capacity, quotation or API permission.</p>
        <div style="max-height:270px;overflow:auto"><table style="width:100%;text-align:left"><thead><tr><th>Company / network</th><th>Class</th><th>Source</th><th>Quote</th></tr></thead><tbody>${sources}</tbody></table></div></div>
      <p style="color:#566078">Evidence passport SHA-256: <code>${esc(d.passport_sha256)}</code>. No external effects. Scope: ${esc(d.test_scope)}.</p>`;
    panel.querySelector('#li-close').onclick=close;
    panel.querySelector('#li-case').onchange=e=>{active=e.target.value;open()};
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
  document.addEventListener('keydown',e=>{if(e.key==='Escape')close()});
})();
