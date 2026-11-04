'use strict';
const paths = {
  grid:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  clock:'M12 8v5l3 2 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',
  check:'m5 12 4 4L19 6', circle:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 m-14 0 3 3 6-6',
  file:'M14 2H5v20h14V7z M14 2v6h5 M8 13h8 M8 17h5',
  plus:'M12 5v14 M5 12h14', back:'M20 12H4 m6-6-6 6 6 6',
  spark:'m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z',
  upload:'M12 16V3 m-5 5 5-5 5 5 M4 15v6h16v-6',
  play:'m9 5 10 7-10 7z', edit:'m14 4 6 6 M4 16 16 4l4 4L8 20H4z',
  x:'m6 6 12 12 M18 6 6 18', shield:'m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z m-4 9 3 3 5-5',
  video:'M3 5h12v14H3z m12 5 6-3v10l-6-3', download:'M12 3v13 m-5-5 5 5 5-5 M4 17v4h16v-4',
  search:'M16 16l5 5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
  alert:'M12 8v5 M12 16.5v.5 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0'
};
const icon = (name) => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name] || paths.circle}"/></svg>`;
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// Drawn in graphite with defects marked in red pen, matching the evidence frames.
const house = `<svg class="house-drawing" viewBox="0 0 420 290" fill="none" aria-hidden="true"><g stroke="currentColor" stroke-width="1.1" stroke-linejoin="round"><path d="m35 202 172-100 175 100-173 82z" opacity=".25"/><path d="m71 155 137-79 132 76v80l-133 77-136-78z" transform="translate(0 -30)" fill="#eef2f4"/><path d="m62 127 82-97 89 51 57-1 64 73-139 81z" fill="#e6ecef"/><path d="m144 30 90 52-82 98-90-53z" fill="#f7f9fa"/><path d="m152 180 63 24 139-81 M215 204v75 M152 180v61 M233 81l-18 123 M290 80l-57 1 M79 147v58l61 35v-59"/><path d="m166 198 31 18v46l-31-18z" fill="#fafbfb"/><path d="m244 191 28-16v36l-28 16z m43-25 28-16v36l-28 16z" fill="#dbe5ec"/><path d="m257 184 1 36 M244 209l28-16 M301 158v36 M287 184l28-16"/><path d="m87 155 35 21v31l-35-20z" fill="#dbe5ec"/><path d="m103 165 1 32 M87 171l35 20"/><path d="m125 77 17-20 61 35-17 20z M118 86l61 35 M111 96l61 35 M104 106l61 35 M97 116l61 35" opacity=".35"/><path d="m215 280 32 18 57-33 M71 208l-27 16 M340 202l35 21 M207 72V19" stroke-dasharray="3 4" opacity=".4"/><path d="m289 233 17-9v-31l13-8v31l17-10"/><path d="M350 206c17-27 12-47 5-46-7-1-14 28-5 46z M355 209v22" fill="#e1e8ec"/><path d="M53 188c-18-31-8-53-1-52 9-1 15 34 1 52z M52 190v31" fill="#e1e8ec"/><path d="m30 251 65-37 M326 263l65-37" stroke-dasharray="2 5" opacity=".35"/></g><g stroke="#c2302a" stroke-width="2"><circle cx="284" cy="161" r="11"/><circle cx="164" cy="148" r="11"/></g></svg>`;
const main = document.querySelector('main');
const modal = document.querySelector('#modal');
const state = { clips:[], page:'overview', clip:null, filter:'all', search:'', upload:null, focus:null, timers:[], analyzing:false, replay:false, stage:0, lastFocus:null };
let toastTimer;
async function api(url, options={}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = 'Could not reach the inspection server. Check that it is running, then try again.';
    try { message = (await response.json()).error || message; } catch {}
    throw new Error(message);
  }
  return response.json();
}
const post = (url, data) => api(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
const clipURL = (clip, action='') => `/api/clips/${encodeURIComponent(clip.id)}${action ? '/'+action : ''}`;
function notify(message) {
  const toast = document.querySelector('#toast');
  clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.add('visible');
  toastTimer = setTimeout(() => toast.classList.remove('visible'), 3200);
}
function showError(error) { notify(error.message || 'Something went wrong. Your saved decisions are safe; try again.'); }
function cancelTimers() { state.timers.forEach(clearTimeout); state.timers=[]; }
const plural=(n,word)=>`${n} ${word}${n===1?'':'s'}`;
const sourceCount=(clip,source)=>clip.findings.filter(f=>f.source===source).length;
function navigation() {
  const pending = state.clips.filter(c => !c.signed_by).length, signed = state.clips.filter(c => c.signed_by).length;
  const section = {review:'history',analysis:'history',success:'reports',report:'reports'}[state.page] || state.page;
  const links = [['overview','Home',0,''],['history','Clips',pending,'to review'],['reports','Reports',signed,'signed']];
  document.querySelector('#nav').innerHTML = links.map(([page, label, count, what]) => `<button class="nav-button ${section===page?'active':''}" data-action="nav" data-page="${page}" ${section===page?'aria-current="page"':''}>${label}${count?`<span class="count"><span class="sr">, </span>${count}<span class="sr"> ${what}</span></span>`:''}</button>`).join('');
  const titles={overview:'Home',history:'Clips',reports:'Reports',review:`Review ${state.clip?roomTitle(state.clip):''}`,analysis:'Analyzing',success:'Signed off',report:'Inspection report'};
  document.title=`${titles[state.page]||'Home'} – Second Inspector`;
}
function view(html) {
  navigation();
  main.innerHTML=html;
  window.scrollTo({top:0,behavior:'instant'});
  main.focus({preventScroll:true});
}
function roomTitle(clip) {
  const names = clip.rooms.filter(r=>r!=='Unassigned');
  if (clip.id.includes('kitchen')) return 'Kitchen walkthrough';
  if (clip.id.includes('garage')) return 'Garage & interior';
  return names.length ? names.slice(0,2).join(' & ') : 'Room walkthrough';
}
const date = (value) => new Date(value).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});
function clipMeta(clip) {
  const sensor=sourceCount(clip,'sensor');
  return `<p class="clip-card-meta"><span class="tag">${plural(sourceCount(clip,'spoken'),'finding')} from your narration</span><span class="tag ai ai-text">${icon('spark')}${clip.ai_count} flagged by AI</span>${sensor?`<span class="tag">${sensor} measured</span>`:''}</p>`;
}
function clipCard(clip) {
  const status = clip.signed_by ? `<b>Signed off</b>${esc(clip.signed_by)}, ${date(clip.signed_at)}` : clip.pending ? `<b>${clip.pending} to review</b>of ${plural(clip.findings.length,'finding')}` : '<b>Ready to sign</b>All findings decided';
  const button = clip.signed_by ? `<button data-action="report" data-id="${esc(clip.id)}">View report</button>` : `<button class="primary" data-action="review" data-id="${esc(clip.id)}">${clip.pending?'Review findings':'Review and sign'}</button>`;
  return `<article class="clip-card"><div class="clip-thumb">${clip.thumbnail?`<img src="${esc(clip.thumbnail)}" alt="" loading="lazy">`:house}</div><div class="clip-main"><h3>${esc(roomTitle(clip))}</h3><p class="clip-file" title="${esc(clip.filename)}">${esc(clip.filename)}</p>${clipMeta(clip)}</div><p class="clip-status">${status}</p>${button}</article>`;
}
function empty(message='Your first walkthrough starts here.',description='Film a room on your phone and say what you see. Upload the clip and Second Inspector will find each defect in the footage.',action=`<button class="primary" data-action="analyze">${icon('upload')} Upload a walkthrough</button>`) {
  return `<div class="empty">${icon('video')}<h3>${message}</h3><p>${description}</p>${action}</div>`;
}
function heroFigure() {
  const all=state.clips.flatMap(c=>c.findings);
  const f=all.find(x=>x.located&&x.image&&x.utterance)||all.find(x=>x.located&&x.image)||all.find(x=>x.image);
  if(!f)return `<figure class="markup-figure plain">${house}</figure>`;
  const notes=[];
  if(f.utterance)notes.push(['','The inspector said',`“${f.utterance}”`]);
  if(f.located)notes.push(['mark','SAM 3.1 found it in the video',f.confidence!=null?`${Math.round(f.confidence*100)}% match, boxed in red`:'Boxed in red on the frame']);
  if(f.corroborated)notes.push(['ai','A second AI pass agrees','Muse Spark flagged the same defect on its own']);
  if(!notes.length)notes.push(['','Evidence frame',findingTitle(f)]);
  return `<figure class="markup-figure"><img src="${esc(f.image)}" alt="Evidence frame: ${esc(findingTitle(f))}"><figcaption>${notes.map(([kind,label,text])=>`<p class="callout ${kind}"><b>${label}</b><span>${esc(text)}</span></p>`).join('')}</figcaption></figure>`;
}
function story() {
  const items=[['','Narrate as you film','Walk the home and say what you see. Voice Transcribe captures every word.','You'],['ai','Each defect is found in the video','Muse Spark pulls out the defects you mention. SAM 3.1 boxes each one on the frame.','AI'],['ai','A second look','Muse Spark watches the footage again for problems nobody mentioned.','AI'],['','You decide and sign','Accept, edit or reject each finding. Only what you sign goes in the client report.','You']];
  return `<section aria-labelledby="how-title"><div class="section-head"><h2 id="how-title">How it works</h2></div><ol class="process">${items.map(([kind,title,text,who])=>`<li class="${kind}"><h3>${title}</h3><p>${text}</p><span class="tag who ${who==='AI'?'ai':''}">${who==='AI'?`${icon('spark')}AI`:'You'}</span></li>`).join('')}</ol></section>`;
}
function overview() {
  state.page='overview';
  const awaiting = state.clips.filter(c=>!c.signed_by);
  const actions = state.clips.length ? `<button class="primary" data-action="demo">${icon('play')} Watch the demo</button><button data-action="analyze">${icon('upload')} Upload a walkthrough</button>` : `<button class="primary" data-action="analyze">${icon('upload')} Upload a walkthrough</button>`;
  const queue = awaiting.length ? `<div class="sheet clip-list">${awaiting.map(clipCard).join('')}</div>` : state.clips.length ? `<div class="sheet">${empty('All caught up.','Every clip is signed off and its report is ready.',`<button class="primary" data-action="nav" data-page="reports">${icon('file')} View reports</button>`)}</div>` : `<div class="sheet">${empty()}</div>`;
  view(`<section class="home-hero"><div class="home-copy"><h1>Turn a walkthrough video into a signed inspection report.</h1><p>Narrate while you film. AI finds each defect you mention in the footage, then looks for the ones you didn’t. You decide what goes in the report.</p><div class="hero-actions">${actions}</div></div>${heroFigure()}</section><section aria-labelledby="queue-title"><div class="section-head"><h2 id="queue-title">${awaiting.length?`${plural(awaiting.length,'clip')} to review`:'Clips to review'}</h2>${state.clips.length?'<button class="link" data-action="nav" data-page="history">All clips</button>':''}</div>${queue}</section>${story()}`);
}
function history() {
  state.page='history';
  const filtered = state.clips.filter(c=>(state.filter==='all'||(state.filter==='pending'?!c.signed_by:!!c.signed_by))&&`${roomTitle(c)} ${c.title} ${c.filename}`.toLowerCase().includes(state.search.toLowerCase()));
  view(`<div class="page-head"><div><h1>Clips</h1><p>Every walkthrough you have uploaded. Open one to review its findings or view its report.</p></div></div><div class="toolbar" role="group" aria-label="Filter clips">${[['all','All clips'],['pending','Needs review'],['signed','Signed off']].map(([key,label])=>`<button class="filter ${state.filter===key?'active':''}" aria-pressed="${state.filter===key}" data-action="filter" data-filter="${key}">${label}</button>`).join('')}<label class="search"><span class="sr">Search clips</span><input id="clip-search" type="search" aria-label="Search clips" placeholder="Search by room or file name…" value="${esc(state.search)}" spellcheck="false"></label></div>${filtered.length?`<div class="sheet clip-list">${filtered.map(clipCard).join('')}</div>`:`<div class="sheet">${empty('No clips here yet.','Try another filter, or upload a new walkthrough.')}</div>`}`);
}
function reportsView() {
  state.page='reports';
  const signed=state.clips.filter(c=>c.signed_by);
  view(`<div class="page-head"><div><h1>Reports</h1><p>Signed inspections, ready to print or save as PDF.</p></div></div>${signed.length?`<div class="sheet">${signed.map(c=>`<article class="signed-clip"><div><h3>${esc(roomTitle(c))}</h3><p>Signed by ${esc(c.signed_by)} on ${date(c.signed_at)}. ${plural(c.findings.filter(f=>f.decision!=='rejected').length,'finding')} included.</p></div><div class="signed-buttons"><button data-action="review" data-id="${esc(c.id)}">Reopen clip</button><button class="primary" data-action="report" data-id="${esc(c.id)}">${icon('file')} View report</button></div></article>`).join('')}</div>`:`<div class="sheet">${empty('No signed reports yet.','Review a clip and sign off. Its report appears here.',`<button class="primary" data-action="nav" data-page="history">Go to clips</button>`)}</div>`}`);
}
async function refresh() { state.clips=await api('/api/clips'); }
async function navigate(page) {
  if (state.analyzing) { notify('The analysis keeps running in the background.'); }
  if (!state.analyzing) cancelTimers();
  await refresh();
  if(page==='overview') overview();
  else if(page==='history') history();
  else reportsView();
}
function openModal(content) {
  state.lastFocus=document.activeElement;
  modal.innerHTML=content;
  modal.showModal();
}
function closeModal() { modal.close(); state.lastFocus?.focus(); }
function modalHeader(title,description) {
  return `<div class="modal-header"><div><h2 id="modal-title">${title}</h2><p>${description}</p></div><button class="close-button" data-action="close" aria-label="Close dialog">×</button></div>`;
}
function analyzeModal(mode='upload') {
  const replay=mode==='replay';
  openOrUpdate(`${modalHeader('Start an inspection','Upload a walkthrough you narrated, or replay a clip that has already been analyzed.')}<div class="modal-tabs"><button class="${!replay?'active':''}" aria-pressed="${!replay}" data-action="analyze-tab" data-mode="upload">${icon('upload')} Upload a clip</button><button class="${replay?'active':''}" aria-pressed="${replay}" data-action="analyze-tab" data-mode="replay">${icon('play')} Replay a processed clip</button></div>${replay?`<label class="field">Walkthrough<select id="replay-clip">${state.clips.map(c=>`<option value="${esc(c.id)}">${esc(c.filename||c.id)} (${plural(c.findings.length,'finding')})</option>`).join('')}</select></label><div class="modal-info"><b>Demo replay.</b> Plays a short version of the analysis, then opens the saved findings. No models run, and your decisions and sign-offs are kept.</div>`:`<div class="upload-zone" id="drop-zone">${icon('upload')}<strong>Drop a video here</strong><small>MP4, MOV or M4V, up to 512 MB</small><button type="button" class="upload-choose" data-action="choose-upload">Choose file</button><small id="upload-filename">No file selected</small><input type="file" id="clip-upload" accept=".mp4,.mov,.m4v" aria-label="Walkthrough video" hidden></div><div class="modal-info">Say what you see while you film. We match your words to the video and look for anything you didn’t mention. Live analysis can take several minutes.</div>`}<p class="form-error" id="upload-error" role="alert"></p><div class="modal-actions"><button data-action="close">Cancel</button><button class="primary" data-action="${replay?'start-replay':'start-upload'}" ${replay&&!state.clips.length?'disabled':''}>${icon(replay?'play':'spark')} ${replay?'Start demo replay':'Start analysis'}</button></div>`);
  state.upload=null;
}
function openOrUpdate(content) { if(modal.open) modal.innerHTML=content; else openModal(content); }
function replayFacts(clip) {
  if(!clip)return [];
  const spoken=clip.findings.filter(f=>f.source==='spoken'),ai=clip.findings.filter(f=>f.source==='unspoken');
  return [`${plural(spoken.length,'defect')} heard in the narration`,`${spoken.filter(f=>f.located).length} of ${spoken.length} boxed in the video`,`${plural(ai.length,'issue')} nobody mentioned, and ${spoken.filter(f=>f.corroborated).length} of yours confirmed`];
}
function analysisScreen(replay=false,stage=0,error='') {
  state.page='analysis';
  const stages=['Transcribe the narration and pull out each defect','Find each defect in the video with SAM 3.1','Look again for anything nobody mentioned'];
  const facts=replay?replayFacts(state.clips.find(c=>c.id===state.replayId)):[];
  view(`<section class="analysis"><span class="tag ${replay?'ai':''}">${icon('spark')} ${replay?'Demo replay of saved results':'Analyzing your walkthrough'}</span><div class="scan-scene">${house}<div class="scan-line"></div></div><h1>${error?'The analysis stopped':'Analyzing the walkthrough…'}</h1>${error?`<div class="analysis-error" role="alert"><p>${esc(error)}</p><button data-action="analyze">Choose another clip</button></div>`:`<ol class="analysis-stages" aria-live="polite">${stages.map((label,i)=>`<li class="${i<stage?'done':i===stage?'active':''}"><span class="dot">${i<stage?icon('check'):''}</span>${label}<small>${i<stage?esc(facts[i]||'Done'):i===stage?'Working…':'Waiting'}</small></li>`).join('')}</ol><p class="analysis-hint">${replay?'This replays saved results. No new analysis is running.':'This can take several minutes. Your findings open as soon as it finishes.'}</p>`}<button class="ghost" data-action="nav" data-page="history">${icon('back')} Back to clips</button></section>`);
}
async function startReplay(id=document.querySelector('#replay-clip').value) {
  if(modal.open)closeModal();
  cancelTimers();
  state.analyzing=true;state.replay=true;state.stage=0;state.replayId=id;
  analysisScreen(true,0);
  [1,2,3].forEach(i=>state.timers.push(setTimeout(()=>{state.stage=i;if(state.page==='analysis')analysisScreen(true,i);},i*1800)));
  state.timers.push(setTimeout(async()=>{state.analyzing=false;try{await openReview(id);notify('Replay finished. These are the saved findings.');}catch(e){showError(e);}},6600));
}
async function startUpload(button) {
  const file=state.upload||document.querySelector('#clip-upload').files[0];
  const error=document.querySelector('#upload-error');
  if(!file){error.textContent='Choose a walkthrough clip first.';return;}
  if(!/\.(mp4|mov|m4v)$/i.test(file.name)||file.size===0||file.size>512*1024*1024){error.textContent='Choose an MP4, MOV or M4V video under 512 MB.';return;}
  button.disabled=true;button.innerHTML='<span class="spinner"></span> Uploading…';
  try {
    // Use a safe ASCII label in HTTP headers; uploaded names are not inspection identifiers.
    const filename=file.name.replace(/[^A-Za-z0-9_.-]/g,'-');
    const {job}=await api('/api/analyze',{method:'POST',headers:{'x-filename':filename,'Content-Type':'application/octet-stream'},body:file});
    closeModal();state.analyzing=true;state.replay=false;state.stage=0;analysisScreen(false,0);
    const poll=async()=>{
      try{
        const result=await api(`/api/jobs/${job}`);
        if(result.status==='error'){state.analyzing=false;analysisScreen(false,0,result.error);return;}
        if(result.status==='complete'){state.analyzing=false;await refresh();await openReview(result.clip);notify('Analysis finished. Your findings are ready to review.');return;}
        if(result.stage!==state.stage){state.stage=result.stage;if(state.page==='analysis')analysisScreen(false,state.stage);}
        state.timers.push(setTimeout(poll,1800));
      }catch(e){state.analyzing=false;analysisScreen(false,0,e.message);}
    };
    poll();
  }catch(e){error.textContent=e.message;button.disabled=false;button.innerHTML=`${icon('spark')} Start analysis`;}
}
const clock=(t)=>t==null?'':`${Math.floor(t/60).toString().padStart(2,'0')}:${Math.floor(t%60).toString().padStart(2,'0')}`;
const findingTitle=(f)=>[f.component_phrase||'Inspection finding',f.defect_phrase].filter(Boolean).join(', ');
const SOURCES={spoken:['you','Your narration'],unspoken:['ai','AI only'],sensor:['sensor','Level sensor'],inspector:['inspector','Added by you']};
const DECISIONS={pending:'Needs a decision',accepted:'Accepted',edited:'Edited and accepted',rejected:'Rejected'};
function findingRow(f) {
  const decision=f.source==='inspector'?'inspector':f.decision||'pending';
  const [kind,label]=SOURCES[f.source]||['you','Finding'];
  const mark={accepted:icon('check'),edited:icon('edit'),inspector:icon('check'),rejected:icon('x')}[decision]||'';
  return `<li><button class="finding ${esc(decision)} ${state.focus===f.id?'focused':''}" id="finding-${esc(f.id)}" data-action="select" data-id="${esc(f.id)}" data-finding="${esc(f.id)}" ${state.focus===f.id?'aria-current="true"':''}><span class="status-icon">${mark}<span class="sr">${decision==='inspector'?'Included':DECISIONS[decision]}: </span></span><span class="row-main"><span class="row-title">${esc(f.component_phrase||'Inspection finding')}</span><span class="row-sub"><span class="src ${kind}">${label}</span>${f.t_start!=null?`<span class="time">${clock(f.t_start)}</span>`:''}</span></span>${f.defect_phrase?`<span class="defect-tag">${esc(f.defect_phrase)}</span>`:''}</button></li>`;
}
function focusMedia(c) {
  const f=c.findings.find(x=>x.id===state.focus);
  if(c.video)return `<video id="evidence-video" src="${esc(c.video)}" ${c.thumbnail?`poster="${esc(c.thumbnail)}"`:''} controls playsinline preload="metadata"></video>`;
  return f?.image?`<img ${f.source==='sensor'?'class="chart" ':''}src="${esc(f.image)}" alt="${f.source==='sensor'?'Level reading':'Evidence frame'}: ${esc(findingTitle(f))}">`:`<div class="placeholder">${icon('video')}<p>${f?.source==='inspector'?'You added this finding during review, so there is no frame.':'No evidence frame for this finding.'}</p></div>`;
}
function said(f) {
  const time=clock(f.t_start);
  if(f.source==='spoken')return f.utterance?`<blockquote class="said you"><p>“${esc(f.utterance)}”</p><cite>You, on site${time?` at ${time}`:''}</cite></blockquote>`:'<p class="said">From your narration.</p>';
  if(f.source==='unspoken')return `<div class="said ai">${icon('spark')}<p><b>You didn’t mention this.</b> AI spotted it in the footage${time?` at ${time}`:''}. Look at the frame before you accept it.</p></div>`;
  if(f.source==='sensor')return '<p class="said">Measured with the phone’s level sensor while you walked the room.</p>';
  return '<p class="said">You added this during review. It is included in the report.</p>';
}
function checks(f) {
  if(!['spoken','unspoken'].includes(f.source))return '';
  const out=[f.located?`<li class="ok">${icon('check')} Found in the video${f.confidence!=null?` (${Math.round(f.confidence*100)}% match)`:''}</li>`:`<li class="warn">${icon('alert')} Not pinpointed in the video. Confirm on site.</li>`];
  if(f.corroborated)out.push(`<li class="ai">${icon('spark')} A second AI pass flagged it too</li>`);
  return `<ul class="checks" aria-label="Evidence checks">${out.join('')}</ul>`;
}
function focusDetail(c) {
  const f=c.findings.find(x=>x.id===state.focus);
  if(!f)return `<div class="detail-body">${empty('No findings in this clip.','Nothing was flagged. Add anything you noticed, then sign off.',`<button class="primary" data-action="add">${icon('plus')} Add a finding</button>`)}</div>`;
  const decision=f.decision||'pending',manual=f.source==='inspector';
  const time=clock(f.t_start),range=time?`${time}${f.t_end!=null&&clock(f.t_end)!==time?`–${clock(f.t_end)}`:''}`:'';
  const status=decision==='rejected'?`<p class="decided rejected">${icon('x')} Rejected. It stays out of the report.</p>`:['accepted','edited'].includes(decision)?`<p class="decided">${icon('check')} ${DECISIONS[decision]}. It will appear in the report.</p>`:'';
  const actions=manual?`<p class="decided">${icon('check')} Included. You added this finding.</p>`:`${status}<button class="accept ${['accepted','edited'].includes(decision)?'selected':''}" aria-pressed="${['accepted','edited'].includes(decision)}" aria-keyshortcuts="A" data-action="decide" data-id="${esc(f.id)}" data-decision="accepted">${icon('check')} ${['accepted','edited'].includes(decision)?'Accepted':'Accept'}</button><button aria-keyshortcuts="E" data-action="edit" data-id="${esc(f.id)}">${icon('edit')} Edit</button><button class="reject ${decision==='rejected'?'selected':''}" aria-pressed="${decision==='rejected'}" aria-keyshortcuts="R" data-action="reject" data-id="${esc(f.id)}">${icon('x')} ${decision==='rejected'?'Rejected':'Reject'}</button>`;
  return `<div class="detail-body"><div class="detail-top">${f.defect_phrase?`<span class="defect-tag">${esc(f.defect_phrase)}</span>`:''}${range?`<span class="time">${range}</span>`:''}</div><h2>${esc(f.component_phrase||'Inspection finding')}</h2><p class="where">${esc(f.room||'Unassigned room')}, ${esc(f.sop_section||'General')} section</p>${said(f)}<p class="description">${esc(f.description)}</p>${checks(f)}${f.note?`<p class="review-note">Your note: ${esc(f.note)}</p>`:''}</div><div class="decision-bar">${actions}</div>`;
}
function selectFinding(id,scroll=false) {
  state.focus=id;
  document.querySelectorAll('.finding.focused').forEach(el=>{el.classList.remove('focused');el.removeAttribute('aria-current');});
  const row=document.querySelector(`#finding-${CSS.escape(id)}`);
  row?.classList.add('focused');row?.setAttribute('aria-current','true');
  const f=state.clip.findings.find(x=>x.id===id);
  if(state.clip.video){const video=document.querySelector('#evidence-video');if(video&&f?.t_start!=null)video.currentTime=f.t_start;}
  else document.querySelector('#focus-media').innerHTML=focusMedia(state.clip);
  document.querySelector('#evidence-note').hidden=!(f?.located&&!state.clip.video);
  document.querySelector('#focus-detail').innerHTML=focusDetail(state.clip);
  // On narrow screens the detail sits above the list, so bring it into view; on wide screens keep the row visible.
  if(matchMedia('(max-width:1080px)').matches)document.querySelector('#detail').scrollIntoView({behavior:'smooth',block:'start'});
  else if(scroll)row?.scrollIntoView({block:'nearest',behavior:'smooth'});
}
function nextFinding(step,pendingOnly=false) {
  const list=state.clip.findings,start=list.findIndex(f=>f.id===state.focus);
  for(let n=1;n<=list.length;n++){
    const f=list[((start+step*n)%list.length+list.length)%list.length];
    if(!pendingOnly||f.decision==='pending')return f.id;
  }
  return null;
}
async function openReview(id) {
  state.clip=await api(`/api/clips/${encodeURIComponent(id)}`);
  state.page='review';
  state.focus=(state.clip.findings.find(f=>f.decision==='pending')||state.clip.findings[0])?.id||null;
  reviewView();
}
function reviewView() {
  const c=state.clip,total=c.findings.length,done=total-c.pending,f=c.findings.find(x=>x.id===state.focus);
  const cover=Object.values(c.coverage||{}).flatMap(r=>r.items||[]);
  const statusCell=c.signed_by?`Signed by ${esc(c.signed_by)}`:c.pending?`${c.pending} of ${total} need a decision`:'Ready to sign';
  const signButton=c.signed_by?`<button class="primary" data-action="current-report">${icon('file')} View signed report</button>`:`<button class="primary" data-action="sign" ${c.pending?'disabled':''}>${icon('shield')} Sign off on this clip</button>`;
  view(`<header class="review-head"><button class="link back" data-action="nav" data-page="history">${icon('back')} All clips</button><div class="title-block"><div class="tb-cell tb-title"><span class="tb-label">Walkthrough</span><h1>${esc(roomTitle(c))}</h1></div><div class="tb-cell"><span class="tb-label">Findings</span><span>${sourceCount(c,'spoken')} narrated, ${c.ai_count} AI, ${sourceCount(c,'sensor')} measured</span></div><div class="tb-cell"><span class="tb-label">Source clip</span><span title="${esc(c.filename)}">${esc(c.filename)}</span></div><div class="tb-cell"><span class="tb-label">Status</span><span>${statusCell}</span></div></div></header><div class="review-bar ${!c.pending&&!c.signed_by?'ready':''}"><div class="progress"><div class="progress-track" role="progressbar" aria-valuenow="${done}" aria-valuemin="0" aria-valuemax="${total||1}" aria-label="Findings reviewed"><div class="progress-fill" style="transform:scaleX(${total?done/total:1})"></div></div><span><b>${done}</b> of ${total} reviewed</span></div><p class="shortcuts"><kbd>J</kbd><kbd>K</kbd><span>move</span><kbd>A</kbd><span>accept</span><kbd>E</kbd><span>edit</span><kbd>R</kbd><span>reject</span></p>${signButton}</div><div class="review-layout"><section class="queue-pane" aria-label="Findings"><ol class="finding-list" id="findings-list">${c.findings.map(findingRow).join('')}</ol><button class="add-finding" data-action="add">${icon('plus')} Add missing finding</button>${cover.length?`<section class="coverage sheet"><h3>Coverage checklist</h3>${cover.slice(0,10).map(i=>`<div class="coverage-row"><span>${esc(i.label||i.item)}</span><span class="badge ${['not_seen','seen_not_mentioned'].includes(i.status)?'attention':''}">${esc(({not_seen:'Not seen',seen_not_mentioned:'Not mentioned',mentioned_not_seen:'Mentioned, not seen',tested:'Tested',inspected:'Inspected'})[i.status]||i.status)}</span></div>`).join('')}</section>`:''}</section><section class="detail-pane" id="detail" aria-label="Selected finding"><article class="detail-sheet"><div class="evidence" id="focus-media">${focusMedia(c)}</div><p class="evidence-note" id="evidence-note" ${f?.located&&!c.video?'':'hidden'}>The red box is where SAM 3.1 found it.</p><div id="focus-detail">${focusDetail(c)}</div></article></section></div>`);
}
function updateReview(data,findingId) {
  state.clip=data;
  const index=state.clips.findIndex(c=>c.id===data.id);
  if(index>=0)state.clips[index]=data;
  const scroll=window.scrollY,video=document.querySelector('#evidence-video');
  const videoTime=video?.currentTime||0;
  reviewView();
  const restored=document.querySelector('#evidence-video');
  if(restored&&videoTime)restored.currentTime=videoTime;
  window.scrollTo({top:scroll,behavior:'instant'});
  if(findingId)document.querySelector('#focus-detail .decision-bar button')?.focus({preventScroll:true});
}
// After a decision on the selected finding, move to the next one that still needs a decision.
function advanceFrom(id) {
  if(id!==state.focus)return;
  const next=nextFinding(1,true);
  if(next){selectFinding(next,true);document.querySelector('#focus-detail .decision-bar button')?.focus({preventScroll:true});}
  else if(!state.clip.signed_by)notify('Every finding has a decision. Sign off when you’re ready.');
}
async function decide(id,decision,button) {
  if(button)button.disabled=true;
  try{const data=await post(clipURL(state.clip,'decision'),{id,decision});updateReview(data,id);notify('Accepted. It will appear in the report.');advanceFrom(id);}
  catch(e){if(button)button.disabled=false;showError(e);}
}
const SECTIONS=['General','Interior','Exterior','Kitchen','Bathroom(s)','Electrical','Plumbing','Structure','Attached Garage','Roof','HVAC'];
function findingForm(finding=null) {
  const adding=!finding;
  const section=finding?.sop_section||'General';
  openModal(`${modalHeader(adding?'Add a finding':'Edit finding',adding?'Record something the video or the AI missed. It goes straight into the report.':'Your wording replaces the AI’s in the report. Saving also accepts the finding.')}<form id="finding-form" data-finding="${esc(finding?.id||'')}"><div class="field-row"><label class="field">Component<input name="component_phrase" value="${esc(finding?.component_phrase)}" autofocus required placeholder="Outlet cover…" autocomplete="off"></label><label class="field">Issue<input name="defect_phrase" value="${esc(finding?.defect_phrase)}" placeholder="Missing…" autocomplete="off"></label></div><div class="field-row"><label class="field">Room<input name="room" value="${esc(finding?.room||state.clip.rooms[0]||'')}" required autocomplete="off"></label><label class="field">Report section<select name="sop_section">${[...SECTIONS,...(SECTIONS.includes(section)?[]:[section])].map(s=>`<option ${s===section?'selected':''}>${esc(s)}</option>`).join('')}</select></label></div><label class="field">Description<textarea name="description" required placeholder="What you saw and where…">${esc(finding?.description)}</textarea></label><p class="form-error" id="form-error" role="alert"></p><div class="modal-actions"><button type="button" data-action="close">Cancel</button><button class="primary" type="submit">${icon('check')} ${adding?'Add finding':'Save changes'}</button></div></form>`);
}
function rejectForm(id) {
  openModal(`${modalHeader('Reject this finding?','It stays in your review history but won’t appear in the report.')}<form id="reject-form" data-finding="${esc(id)}"><label class="field">Reason (optional)<textarea name="note" autofocus placeholder="Reflection, not a crack…"></textarea></label><p class="form-error" id="form-error" role="alert"></p><div class="modal-actions"><button type="button" data-action="close">Cancel</button><button class="primary" type="submit">${icon('x')} Reject finding</button></div></form>`);
}
function signForm() {
  if(state.clip.pending)return;
  const included=state.clip.findings.filter(f=>f.decision!=='rejected').length,rejected=state.clip.findings.length-included;
  openModal(`${modalHeader('Sign off on this clip','Your name goes on the report as the reviewing inspector.')}<form id="sign-form"><div class="modal-info"><b>${esc(roomTitle(state.clip))}</b>: ${plural(included,'finding')} included${rejected?`, ${rejected} rejected`:''}.</div><label class="field">Inspector name<input name="name" autocomplete="name" autofocus required placeholder="Your full name…"></label><label class="checkbox-label"><input type="checkbox" name="confirm" required>I have reviewed every finding and this clip is ready for the report.</label><p class="form-error" id="form-error" role="alert"></p><div class="modal-actions"><button type="button" data-action="close">Cancel</button><button class="primary" type="submit">${icon('shield')} Confirm sign-off</button></div></form>`);
}
function successView() {
  state.page='success';
  const c=state.clip,included=c.findings.filter(f=>f.decision!=='rejected').length;
  view(`<section class="signed-page"><div class="stamp" aria-hidden="true"><span>Reviewed and signed</span><b>${esc(c.signed_by)}</b><span>${date(c.signed_at)}</span></div><h1>Signed off. The report is ready.</h1><p>${plural(included,'finding')} will appear in the report under your name. You can reopen the clip later; any change needs a new sign-off.</p><dl class="sheet receipt"><div><dt>Walkthrough</dt><dd>${esc(roomTitle(c))}</dd></div><div><dt>Signed by</dt><dd>${esc(c.signed_by)}</dd></div><div><dt>Findings included</dt><dd>${included}</dd></div></dl><div class="signed-actions"><button class="primary" data-action="current-report">${icon('file')} View report</button><button data-action="nav" data-page="reports">All reports</button></div></section>`);
}
async function openReport(id) {
  state.clip=await api(`/api/clips/${encodeURIComponent(id)}`);
  if(!state.clip.signed_by){await openReview(id);notify('Sign off on the clip to create its report.');return;}
  state.page='report';
  const c=state.clip;
  const sections=['Property & sign-off','Summary & how it was made','Findings by system & room, with evidence'];
  if(c.has_level) sections.push('Floor level measurements');
  if(Object.keys(c.coverage||{}).length) sections.push('Coverage checklist');
  sections.push('Items not inspected & limitations');
  view(`<div class="page-head"><div><h1>Inspection report</h1><p>${esc(roomTitle(c))}, signed by ${esc(c.signed_by)} on ${date(c.signed_at)}.</p></div><button class="link" data-action="nav" data-page="reports">${icon('back')} All reports</button></div><div class="report-layout"><aside class="report-aside"><div><h2>In this report</h2><ol>${sections.map(label=>`<li>${label}</li>`).join('')}</ol></div><button class="primary" data-action="print-report">${icon('download')} Print / Save as PDF</button></aside><div class="report-paper"><iframe title="Signed inspection report" src="${clipURL(c,'report')}"></iframe></div></div>`);
}
async function submitForm(form) {
  const button=form.querySelector('[type=submit]');
  button.disabled=true;
  try {
    const data=Object.fromEntries([...new FormData(form)].map(([k,v])=>[k,typeof v==='string'?v.trim():v]));
    let result;
    if(form.id==='finding-form'){
      if(!data.description||!data.component_phrase||!data.room)throw new Error('Enter a component, room and description.');
      const id=form.dataset.finding;
      result=await post(clipURL(state.clip,id?'decision':'add'),id?{id,decision:'edited',edits:data}:data);
      closeModal();updateReview(result,id);notify(id?'Saved and accepted.':'Finding added to the report.');
      if(id)advanceFrom(id);
    }else if(form.id==='reject-form'){
      const id=form.dataset.finding;
      result=await post(clipURL(state.clip,'decision'),{id,decision:'rejected',note:data.note});
      closeModal();updateReview(result,id);notify('Rejected. It stays out of the report.');
      advanceFrom(id);
    }else if(form.id==='sign-form'){
      if(!data.name)throw new Error('Enter your name to sign off.');
      state.clip=await post(clipURL(state.clip,'sign'),{name:data.name});
      closeModal();await refresh();successView();
    }
  }catch(e){form.querySelector('#form-error').textContent=e.message;button.disabled=false;}
}
document.addEventListener('submit',e=>{if(['finding-form','reject-form','sign-form'].includes(e.target.id)){e.preventDefault();submitForm(e.target);}});
document.addEventListener('click',async e=>{
  const button=e.target.closest('[data-action]');
  if(!button||button.disabled)return;
  const {action,id,page}=button.dataset;
  try {
    switch(action){
      case 'nav': await navigate(page); break;
      case 'filter': state.filter=button.dataset.filter;history();break;
      case 'analyze': if(state.analyzing){state.page='analysis';analysisScreen(state.replay,state.stage);notify('An analysis is already running.');}else analyzeModal();break;
      case 'analyze-tab': analyzeModal(button.dataset.mode);break;
      case 'demo': if(state.analyzing){state.page='analysis';analysisScreen(state.replay,state.stage);}else if(state.clips[0])await startReplay(state.clips[0].id);else analyzeModal('replay');break;
      case 'close':closeModal();break;
      case 'start-replay':await startReplay();break;
      case 'start-upload':await startUpload(button);break;
      case 'choose-upload':document.querySelector('#clip-upload').click();break;
      case 'review':await openReview(id);break;
      case 'report':await openReport(id);break;
      case 'current-report':await openReport(state.clip.id);break;
      case 'select':selectFinding(id);break;
      case 'decide':await decide(id,button.dataset.decision,button);break;
      case 'edit':findingForm(state.clip.findings.find(f=>f.id===id));break;
      case 'add':findingForm();break;
      case 'reject':rejectForm(id);break;
      case 'sign':signForm();break;
      case 'print-report':{const frame=document.querySelector('iframe');frame.contentWindow.focus();frame.contentWindow.print();break;}
    }
  }catch(error){showError(error);}
});
document.addEventListener('input',e=>{
  if(e.target.id==='clip-search'){
    state.search=e.target.value;
    const pos=e.target.selectionStart;
    history();
    const search=document.querySelector('#clip-search');search.focus();search.setSelectionRange?.(pos,pos);
  }
});
function selectUpload(file) {
  state.upload=file;
  document.querySelector('#upload-filename').textContent=file?.name||'No file selected';
}
document.addEventListener('change',e=>{if(e.target.id==='clip-upload')selectUpload(e.target.files[0]);});
modal.addEventListener('click',e=>{if(e.target===modal){const rect=modal.getBoundingClientRect();if(e.clientX<rect.left||e.clientX>rect.right||e.clientY<rect.top||e.clientY>rect.bottom)closeModal();}});
modal.addEventListener('cancel',()=>{state.lastFocus?.focus();});
document.addEventListener('dragover',e=>{if(e.target.closest('#drop-zone')){e.preventDefault();document.querySelector('#drop-zone').classList.add('drag-over');}});
document.addEventListener('dragleave',e=>{e.target.closest('#drop-zone')?.classList.remove('drag-over');});
document.addEventListener('drop',e=>{if(e.target.closest('#drop-zone')){e.preventDefault();selectUpload(e.dataTransfer.files[0]);document.querySelector('#drop-zone').classList.remove('drag-over');}});
document.addEventListener('keydown',async e=>{
  if(state.page!=='review'||modal.open||e.ctrlKey||e.metaKey||e.altKey||e.target.closest?.('input,textarea,select,video'))return;
  const key=e.key.toLowerCase(),f=state.clip.findings.find(x=>x.id===state.focus);
  if(key==='j'||key==='k'){const id=nextFinding(key==='j'?1:-1);if(id)selectFinding(id,true);return;}
  if(!f||f.source==='inspector'||!['a','e','r'].includes(key))return;
  e.preventDefault();
  try{
    if(key==='e')findingForm(f);
    else if(key==='r')rejectForm(f.id);
    else await decide(f.id,'accepted',document.querySelector('#focus-detail .accept'));
  }catch(error){showError(error);}
});
refresh().then(overview).catch(error=>{view(`<div class="empty">${icon('alert')}<h3>Could not load your inspections.</h3><p>${esc(error.message)}</p><button class="primary" data-action="nav" data-page="overview">Try again</button></div>`);});
