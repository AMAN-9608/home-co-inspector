'use strict';
// Browser-local demo data is not a shared or authenticated inspection record.
(() => {
  const key = 'second-inspector-pages-review-v1';
  const sample = fetch(new URL('demo/sample.json', document.baseURI)).then(r => {
    if (!r.ok) throw new Error('The demo data could not be loaded.');
    return r.json();
  });
  let source;
  const copy = value => JSON.parse(JSON.stringify(value));
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const empty = () => ({items:{}, added:[], signed_by:null, signed_at:null});
  const read = () => {
    const saved = localStorage.getItem(key);
    return saved ? JSON.parse(saved) : empty();
  };
  const save = state => localStorage.setItem(key, JSON.stringify(state));
  const unsign = state => { state.signed_by=null; state.signed_at=null; };
  function detail(state) {
    const clip=copy(source);
    clip.findings=clip.findings.map(f => {
      const entry=state.items[f.id]||{};
      return {...f,...(entry.decision==='edited'?entry.edits:{}),decision:entry.decision||'pending',note:entry.note||''};
    });
    clip.findings.push(...state.added.map(f=>({...f,source:'inspector',decision:'accepted',image:null})));
    clip.pending=clip.findings.filter(f=>f.decision==='pending').length;
    clip.signed_by=state.signed_by; clip.signed_at=state.signed_at;
    return clip;
  }
  async function request(path, options={}) {
    source ||= await sample;
    const state=read();
    if(path==='/api/clips' && !options.method)return [detail(state)];
    const match=path.match(/^\/api\/clips\/([^/]+)(?:\/(decision|add|sign))?$/);
    if(!match || decodeURIComponent(match[1])!==source.id)throw new Error('This action is not available in the demo.');
    if(!options.method && !match[2])return detail(state);
    if(options.method!=='POST')throw new Error('This action is not available in the demo.');
    const data=JSON.parse(options.body||'{}');
    if(match[2]==='decision') {
      if(!source.findings.some(f=>f.id===data.id))throw new Error('Finding not found.');
      if(!['accepted','edited','rejected','pending'].includes(data.decision))throw new Error('Invalid decision.');
      const allowed=['description','room','sop_section','component_phrase','defect_phrase','status'];
      const edits=data.edits||{};
      if(data.decision==='edited'&&(!Object.keys(edits).length||Object.keys(edits).some(k=>!allowed.includes(k))))throw new Error('Invalid edit.');
      state.items[data.id]={decision:data.decision,edits:data.decision==='edited'?edits:{},note:data.note||''};
      unsign(state);
    } else if(match[2]==='add') {
      if(typeof data.description!=='string'||!data.description.trim())throw new Error('Describe the finding first.');
      state.added.push({id:`inspector-${Date.now()}-${state.added.length}`,room:data.room||'',sop_section:data.sop_section||'General',component_phrase:data.component_phrase||'',defect_phrase:data.defect_phrase||'',description:data.description});
      unsign(state);
    } else if(match[2]==='sign') {
      if(typeof data.name!=='string'||!data.name.trim())throw new Error('Enter your name to sign off.');
      if(detail(state).pending)throw new Error('Review all pending findings before signing.');
      state.signed_by=data.name.trim();state.signed_at=new Date().toISOString();
    } else throw new Error('This action is not available in the demo.');
    save(state);
    return detail(state);
  }
  function report(clip) {
    if(!clip.signed_by || clip.pending)throw new Error('Review and sign the demo before opening the report.');
    const findings=clip.findings.filter(f=>f.decision!=='rejected');
    const groups=Object.create(null);
    for(const f of findings)(groups[f.sop_section||'General']||=Object.create(null))[f.room||'Unspecified']||=[];
    for(const f of findings)groups[f.sop_section||'General'][f.room||'Unspecified'].push(f);
    const image = (path,alt) => path?`<img src="${esc(new URL(path,document.baseURI).href)}" alt="${esc(alt)}">`:'<div class="noimg">No evidence image</div>';
    const cards=Object.keys(groups).sort().map(section=>`<h3>${esc(section)}</h3>${Object.keys(groups[section]).sort().map(room=>`<h4 class="room">${esc(room)}</h4>${groups[section][room].map(f=>`<article class="finding"><div class="img">${image(f.image,f.component_phrase||'Evidence')}</div><div class="text"><h4>${esc([f.component_phrase,f.defect_phrase].filter(Boolean).join(' — ')||'Finding')}</h4><div class="meta"><span class="badge ${esc(f.source)}">${esc(({spoken:'Spoken',unspoken:'AI-detected',sensor:'Sensor',inspector:'Inspector'})[f.source]||f.source)}</span></div><p>${esc(f.description)}</p>${f.utterance?`<p class="quote">Inspector said: “${esc(f.utterance)}”</p>`:''}${f.note?`<p><b>Inspector note:</b> ${esc(f.note)}</p>`:''}</div></article>`).join('')}`).join('')}`).join('');
    const levels=Object.entries(clip.level||{}).map(([room,info])=>`<div class="level"><h4>${esc(room)} — max slope ${esc(info.max_slope_deg)}°</h4>${info.image?image(info.image,`${room} floor level`):''}</div>`).join('');
    const coverage=Object.entries(clip.coverage||{}).flatMap(([room,info])=>(info.items||[]).map(item=>`<tr><td>${esc(room)}</td><td>${esc(item.label||item.item)}</td><td>${esc(item.status)}</td></tr>`)).join('');
    return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Demo inspection report – Home Co-Inspector</title><style>${source.report_css||''}</style></head><body><main><header><h1>Demo inspection report</h1><p class="prop">Sample property: 123 Jane Doe Street, Demo City, NY 100001</p><p>Demo only — not an actual inspection report.</p><div class="signed">Reviewed and signed by ${esc(clip.signed_by)} on ${esc(new Date(clip.signed_at).toLocaleDateString())}</div></header><nav class="contents"><h2>Contents</h2><ol><li><a href="#summary">Summary</a></li><li><a href="#findings">Findings</a></li>${levels?'<li><a href="#level">Floor level</a></li>':''}${coverage?'<li><a href="#coverage">Coverage</a></li>':''}<li><a href="#limits">Limitations</a></li></ol></nav><section id="summary"><h2>Summary</h2><p>${findings.length} findings included in this browser-local demo.</p></section><section id="findings"><h2>Findings</h2>${cards||'<p>No findings included.</p>'}</section>${levels?`<section id="level"><h2>Floor level</h2>${levels}</section>`:''}${coverage?`<section id="coverage"><h2>Coverage</h2><table><thead><tr><th>Room</th><th>Item</th><th>Status</th></tr></thead><tbody>${coverage}</tbody></table></section>`:''}<section id="limits"><h2>Items not inspected and limitations</h2><p>${esc(source.limitations||'')}</p></section><footer>Prepared with Home Co-Inspector. Demonstration only. Review state is stored in this browser.</footer></main></body></html>`;
  }
  window.pagesDemo={request,report};
})();
