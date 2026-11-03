'use strict';
const paths = {
  grid:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  clock:'M12 8v5l3 2 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',
  check:'m5 12 4 4L19 6', circle:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 m-14 0 3 3 6-6',
  file:'M14 2H5v20h14V7z M14 2v6h5 M8 13h8 M8 17h5',
  plus:'M12 5v14 M5 12h14', arrow:'M4 12h16 m-6-6 6 6-6 6',
  back:'M20 12H4 m6-6-6 6 6 6', house:'m3 10 9-7 9 7 M5 9v12h14V9 M9 21v-8h6v8',
  spark:'m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z',
  upload:'M12 16V3 m-5 5 5-5 5 5 M4 15v6h16v-6',
  play:'m9 5 10 7-10 7z', edit:'m14 4 6 6 M4 16 16 4l4 4L8 20H4z',
  x:'m6 6 12 12 M18 6 6 18', shield:'m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z m-4 9 3 3 5-5',
  video:'M3 5h12v14H3z m12 5 6-3v10l-6-3', download:'M12 3v13 m-5-5 5 5 5-5 M4 17v4h16v-4',
  eye:'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12 M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
  search:'M16 16l5 5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
  leaf:'M5 20C-1 7 12 3 21 3c0 10-2 18-13 15 M5 20 16 9', lock:'M6 10h12v11H6z M8 10V6a4 4 0 0 1 8 0v4',
  level:'M2 9h20v6H2z M10 9v6 M14 9v6 M12 11v2'
};
const icon = (name) => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name] || paths.circle}"/></svg>`;
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const house = `<svg class="house-drawing" viewBox="0 0 420 290" fill="none" aria-hidden="true"><g stroke="currentColor" stroke-width="1.1" stroke-linejoin="round"><path d="m35 202 172-100 175 100-173 82z" opacity=".25"/><path d="m71 155 137-79 132 76v80l-133 77-136-78z" transform="translate(0 -30)" fill="#e8eddf"/><path d="m62 127 82-97 89 51 57-1 64 73-139 81z" fill="#e0e7d4"/><path d="m144 30 90 52-82 98-90-53z" fill="#f4f5e9"/><path d="m152 180 63 24 139-81 M215 204v75 M152 180v61 M233 81l-18 123 M290 80l-57 1 M79 147v58l61 35v-59"/><path d="m166 198 31 18v46l-31-18z" fill="#f6f7ee"/><path d="m244 191 28-16v36l-28 16z m43-25 28-16v36l-28 16z" fill="#d2deca"/><path d="m257 184 1 36 M244 209l28-16 M301 158v36 M287 184l28-16"/><path d="m87 155 35 21v31l-35-20z" fill="#d2deca"/><path d="m103 165 1 32 M87 171l35 20"/><path d="m125 77 17-20 61 35-17 20z M118 86l61 35 M111 96l61 35 M104 106l61 35 M97 116l61 35" opacity=".35"/><path d="m215 280 32 18 57-33 M71 208l-27 16 M340 202l35 21 M207 72V19" stroke-dasharray="3 4" opacity=".4"/><path d="m289 233 17-9v-31l13-8v31l17-10"/><path d="M350 206c17-27 12-47 5-46-7-1-14 28-5 46z M355 209v22" fill="#dbe4ce"/><path d="M53 188c-18-31-8-53-1-52 9-1 15 34 1 52z M52 190v31" fill="#dbe4ce"/><path d="m30 251 65-37 M326 263l65-37" stroke-dasharray="2 5" opacity=".35"/></g><g fill="#698953"><circle cx="284" cy="161" r="4"/><circle cx="164" cy="148" r="4"/></g><g stroke="#8caa74" opacity=".5"><circle cx="284" cy="161" r="12"/><circle cx="164" cy="148" r="12"/></g></svg>`;
const main = document.querySelector('main');
const modal = document.querySelector('#modal');
const state = { clips:[], page:'overview', clip:null, filter:'all', search:'', upload:null, focus:null, timers:[], analyzing:false, replay:false, stage:0, lastFocus:null };
let toastTimer;
async function api(url, options={}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = 'Unable to connect. Please try again.';
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
function showError(error) { notify(error.message || 'Something went wrong. Please try again.'); }
function cancelTimers() { state.timers.forEach(clearTimeout); state.timers=[]; }
function navigation() {
  const signed = state.clips.filter(c => c.signed_by).length;
  const links = [['overview','grid','Overview',''],['history','clock','Clip history',state.clips.length],['reports','file','Reports',signed]];
  document.querySelector('#nav').innerHTML = links.map(([page, image, label, count]) => `<button class="nav-button ${state.page===page?'active':''}" data-action="nav" data-page="${page}" title="${label}" ${state.page===page?'aria-current="page"':''}>${icon(image)}<span class="nav-label">${label}</span>${count!==''?`<span class="count">${count}</span>`:''}</button>`).join('');
  const labels={overview:'Overview',history:'Clip history',reports:'Reports',review:'Review findings',analysis:'Analyze clip',success:'Inspection signed off',report:'Inspection report'};
  document.querySelector('#breadcrumb').innerHTML=`Workspace <span>/</span> ${labels[state.page]||'Overview'}`;
}
function view(html) {
  navigation();
  main.innerHTML=`<div class="page-enter">${html}</div>`;
  window.scrollTo({top:0,behavior:'instant'});
  main.focus({preventScroll:true});
}
function steps(active) {
  return `<div class="steps" aria-label="Inspection progress">${['Analyze clip','Review findings','Sign off'].map((label,i)=>`${i?'<span class="step-line"></span>':''}<div class="step ${i===active?'current':i<active?'done':''}"><span class="num">${i<active?'✓':i+1}</span>${label}</div>`).join('')}</div>`;
}
function stats() {
  const all = state.clips.flatMap(c=>c.findings);
  const nums = [[state.clips.length,'Clips analyzed','video','in your workspace'],[all.filter(f=>f.source==='unspoken').length,'AI-flagged findings','spark','a second perspective'],[state.clips.filter(c=>c.signed_by).length,'Clips signed off','shield','reviewed by you'],[state.clips.filter(c=>!c.signed_by).length,'Awaiting review','clock','ready when you are']];
  return `<section class="stats" aria-label="Workspace summary">${nums.map(([n,label,image,note])=>`<div class="stat"><div class="stat-top">${label}${icon(image)}</div><div class="stat-number"><strong>${String(n).padStart(2,'0')}</strong><small>${note}</small></div></div>`).join('')}</section>`;
}
function roomTitle(clip) {
  const names = clip.rooms.filter(r=>r!=='Unassigned');
  if (clip.id.includes('kitchen')) return 'Kitchen walkthrough';
  if (clip.id.includes('garage')) return 'Garage & interior';
  return names.length ? names.slice(0,2).join(' & ') : 'Room walkthrough';
}
const date = (value) => new Date(value).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});
function clipCard(clip,index) {
  const stamp = clip.signed_by ? `<span class="badge">${icon('circle')} Signed off</span>` : `<span class="badge amber">${icon('clock')} ${clip.pending?'Awaiting review':'Ready to sign'}</span>`;
  return `<article class="clip-card stagger" style="--i:${index}"><div class="clip-image">${clip.thumbnail?`<img src="${esc(clip.thumbnail)}" alt="Evidence from ${esc(roomTitle(clip))}" loading="lazy">`:house}${stamp}<span class="play">${icon('play')}</span><span class="clip-duration">${icon('video')} WALKTHROUGH</span></div><div class="clip-body"><h3>${esc(roomTitle(clip))}</h3><p title="${esc(clip.title)}">${esc(clip.title)}</p><div class="clip-card-meta"><span>${clip.findings.length-clip.ai_count} from your inspection</span><span>·</span><span class="ai-text">${icon('spark')} ${clip.ai_count} flagged by AI</span></div><div class="clip-bottom"><small>${clip.signed_by?`Signed by ${esc(clip.signed_by)}`:date(clip.updated*1000)}</small><button class="${clip.signed_by?'soft':'primary'}" data-action="${clip.signed_by?'report':'review'}" data-id="${esc(clip.id)}">${clip.signed_by?'View report':'Review findings'} ${icon('arrow')}</button></div></div></article>`;
}
function empty(message='Your first walkthrough starts here.',description='Upload an inspection clip. We’ll help you take a closer look.') {
  return `<div class="empty">${icon('video')}<h3>${message}</h3><p>${description}</p><button class="primary" data-action="analyze">${icon('plus')} Analyze new clip</button></div>`;
}
function story() {
  const items=[['video','Narrate as you film','Walk the home and say what you see. Voice Transcribe captures every word.'],['search','AI finds it in the video','Muse Spark pulls out each defect you mention. SAM 3.1 pinpoints it, frame by frame.'],['spark','A second look','Spark checks the footage for issues nobody mentioned and confirms the ones you did.'],['shield','You approve & sign','Accept, edit or reject each finding. Only what you sign reaches the client report.']];
  return `<section class="story" aria-label="How Second Inspector works">${items.map(([image,title,text],i)=>`<div class="story-step stagger" style="--i:${i}"><div class="story-top"><span class="story-num">${i+1}</span>${icon(image)}</div><h3>${title}</h3><p>${text}</p></div>`).join('')}</section>`;
}
function overview() {
  state.page='overview';
  const awaiting = state.clips.filter(c=>!c.signed_by);
  view(`<div class="intro"><div><h1>Your inspection workspace</h1><p>A little more confidence. In every detail.</p></div><span class="date">${icon('leaf')} Good inspections deserve a second look.</span></div><section class="hero"><div class="hero-copy"><div class="eyebrow"><span class="status-dot"></span> YOUR AI CO-INSPECTOR</div><h1>A second pair<br>of eyes.</h1><p>You know homes. We help you see the whole picture.<br>Review your findings, catch overlooked details, and sign off with confidence.</p><div class="hero-actions"><button class="primary" data-action="analyze">${icon('plus')} Analyze new clip ${icon('arrow')}</button>${state.clips.length?`<button class="ghost" data-action="demo">${icon('play')} Watch the demo replay</button>`:`<button class="ghost" data-action="nav" data-page="history">View clip history ${icon('clock')}</button>`}</div></div><div class="hero-art">${house}<div class="drawing-note one">${icon('circle')}<div>Every detail, in focus<small>EVIDENCE-BACKED FINDINGS</small></div></div><div class="drawing-note two">${icon('spark')}<div>A fresh perspective<small>YOU MAKE THE FINAL CALL</small></div></div><span class="drawing-caption">BUILT FOR A CLOSER LOOK.</span></div></section>${story()}${stats()}<section><div class="section-heading"><div><h2>Pick up where you left off</h2><p>Your walkthroughs, ready for a second look.</p></div><button class="ghost text-button" data-action="nav" data-page="history">All clips ${icon('arrow')}</button></div>${awaiting.length?`<div class="clip-grid">${awaiting.map(clipCard).join('')}</div>`:state.clips.length?`<div class="empty">${icon('circle')}<h3>All caught up.</h3><p>Every clip is signed off. Your reports are ready.</p><button class="primary" data-action="nav" data-page="reports">View reports ${icon('arrow')}</button></div>`:empty()}</section><div class="workflow-note">${icon('shield')}<p><b>Your judgment is the final word.</b> AI flags potential findings. You review, confirm, and sign off on every detail.</p></div>`);
}
function history() {
  state.page='history';
  const filtered = state.clips.filter(c=>(state.filter==='all'||(state.filter==='pending'?!c.signed_by:!!c.signed_by))&&`${roomTitle(c)} ${c.title}`.toLowerCase().includes(state.search.toLowerCase()));
  view(`<div class="intro"><div><h1>Every walkthrough, in one place.</h1><p>Return to a clip, review the details, or pick up a finished report.</p></div><button class="primary" data-action="analyze">${icon('plus')} Analyze new clip</button></div><div class="toolbar" role="group" aria-label="Filter clips">${[['all','All clips'],['pending','Needs review'],['signed','Signed off']].map(([key,label])=>`<button class="filter ${state.filter===key?'active':''}" aria-pressed="${state.filter===key}" data-action="filter" data-filter="${key}">${label}</button>`).join('')}<label class="search"><input id="clip-search" type="search" aria-label="Search clips" placeholder="Search walkthroughs…" value="${esc(state.search)}"></label></div><div class="clip-grid">${filtered.map(clipCard).join('')}</div>${!filtered.length?empty('No clips here yet.','Try another filter or analyze a new walkthrough.'):''}`);
}
function reportsView() {
  state.page='reports';
  const signed=state.clips.filter(c=>c.signed_by);
  view(`<div class="intro"><div><h1>From findings to a finished report.</h1><p>Your signed-off inspections, ready to share.</p></div></div><div class="section-heading"><h2>Available reports</h2><span class="badge">${signed.length} ready</span></div><div class="table-list">${signed.map(c=>`<article class="signed-clip"><div><h3>${icon('circle')} ${esc(roomTitle(c))}</h3><p>${esc(c.signed_by)} · ${date(c.signed_at)} · ${c.findings.filter(f=>f.decision!=='rejected').length} included findings</p></div><div class="signed-buttons"><button data-action="review" data-id="${esc(c.id)}">Review clip</button><button class="primary" data-action="report" data-id="${esc(c.id)}">${icon('file')} View report ${icon('arrow')}</button></div></article>`).join('')}</div>${!signed.length?empty('The final word is yours.','Review a clip and sign off to make its report available.'):''}`);
}
async function refresh() { state.clips=await api('/api/clips'); }
async function navigate(page) {
  if (state.analyzing) { notify('Your analysis continues in the background.'); }
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
  openOrUpdate(`${modalHeader('A fresh set of eyes.','Start with a walkthrough. We’ll help you look closer.')}<div class="modal-tabs"><button class="${!replay?'active':''}" data-action="analyze-tab" data-mode="upload">${icon('upload')} Upload a new clip</button><button class="${replay?'active':''}" data-action="analyze-tab" data-mode="replay">${icon('play')} Replay a processed clip</button></div>${replay?`<label class="field">Choose a walkthrough<select id="replay-clip">${state.clips.map(c=>`<option value="${esc(c.id)}">${esc(c.filename||c.id)} · ${c.findings.length} findings</option>`).join('')}</select></label><div class="modal-info"><b>Demo replay</b><br>A short analysis sequence, followed by your real processed findings. Existing decisions and sign-offs are preserved.</div>`:`<div class="upload-zone" id="drop-zone">${icon('upload')}<strong>Drop your walkthrough here</strong><small>MP4, MOV, M4V · up to 512 MB</small><button type="button" class="upload-choose" data-action="choose-upload">Choose file</button><small id="upload-filename">No file selected</small><input type="file" id="clip-upload" accept=".mp4,.mov,.m4v" aria-label="Room clip" hidden></div><div class="modal-info">We’ll compare your narration with the video and flag details that deserve a second look. Live analysis can take several minutes.</div>`}<p class="form-error" id="upload-error" role="alert"></p><div class="modal-actions"><button data-action="close">Cancel</button><button class="primary" data-action="${replay?'start-replay':'start-upload'}" ${replay&&!state.clips.length?'disabled':''}>${icon(replay?'play':'spark')} ${replay?'Start demo analysis':'Analyze clip'} ${icon('arrow')}</button></div>`);
  state.upload=null;
}
function openOrUpdate(content) { if(modal.open) modal.innerHTML=content; else openModal(content); }
const plural=(n,word)=>`${n} ${word}${n===1?'':'s'}`;
function replayFacts(clip) {
  if(!clip)return [];
  const spoken=clip.findings.filter(f=>f.source==='spoken'),ai=clip.findings.filter(f=>f.source==='unspoken');
  return [`${plural(spoken.length,'defect')} heard in the narration`,`${spoken.filter(f=>f.located).length} of ${spoken.length} pinpointed in the video`,`${plural(ai.length,'unmentioned issue')} flagged · ${spoken.filter(f=>f.corroborated).length} spoken confirmed by AI`];
}
function analysisScreen(replay=false,stage=0,error='') {
  state.page='analysis';
  const stages=['Transcribe the narration and pull out defects','Locate each defect in the video with SAM 3.1','Look again for anything nobody mentioned'];
  const facts=replay?replayFacts(state.clips.find(c=>c.id===state.replayId)):[];
  view(`${steps(0)}<section class="analysis-page"><span class="badge ${replay?'amber':''}">${icon('spark')} ${replay?'DEMO REPLAY':'ANALYSIS IN PROGRESS'}</span><div class="scan-scene">${house}<div class="scan-line"></div><div class="scan-corner"></div><div class="scan-corner b"></div></div><h1>A closer look,<br>frame by frame.</h1><p>Your experience sets the direction. A second perspective helps bring the details into focus.</p>${error?`<div class="analysis-error" role="alert"><h3>Let’s try that again.</h3><p>${esc(error)}</p><button data-action="analyze">Choose another clip</button></div>`:`<div class="analysis-stages">${stages.map((label,i)=>`<div class="analysis-stage ${i<stage?'done':i===stage?'active':''}"><span>${i<stage?'✓':i===stage?'':i+1}</span>${label}<small>${i<stage?esc(facts[i]||'Complete'):i===stage?'In progress':''}</small></div>`).join('')}</div><p class="analysis-hint">${replay?'Replaying existing results for your showcase. No new analysis is being run.':'Your clip is being analyzed. This can take several minutes; your findings appear when the run completes.'}</p>`}<button class="ghost" data-action="nav" data-page="history">${icon('back')} Back to clip history</button></section>`);
}
async function startReplay() {
  const id=document.querySelector('#replay-clip').value;
  closeModal(); cancelTimers();
  state.analyzing=true;state.replay=true;state.stage=0;state.replayId=id;
  analysisScreen(true,0);
  [1,2,3].forEach(i=>state.timers.push(setTimeout(()=>{state.stage=i;if(state.page==='analysis')analysisScreen(true,i);},i*1800)));
  state.timers.push(setTimeout(async()=>{state.analyzing=false;try{await openReview(id);notify('Demo replay complete. These are your saved findings.');}catch(e){showError(e);}},6600));
}
async function startUpload(button) {
  const file=state.upload||document.querySelector('#clip-upload').files[0];
  const error=document.querySelector('#upload-error');
  if(!file){error.textContent='Choose a walkthrough clip first.';return;}
  if(!/\.(mp4|mov|m4v)$/i.test(file.name)||file.size===0||file.size>512*1024*1024){error.textContent='Choose a nonempty MP4, MOV, or M4V file under 512 MB.';return;}
  button.disabled=true;button.innerHTML='<span class="spinner"></span> Uploading clip…';
  try {
    // Use a safe ASCII label in HTTP headers; uploaded names are not inspection identifiers.
    const filename=file.name.replace(/[^A-Za-z0-9_.-]/g,'-');
    const {job}=await api('/api/analyze',{method:'POST',headers:{'x-filename':filename,'Content-Type':'application/octet-stream'},body:file});
    closeModal();state.analyzing=true;state.replay=false;state.stage=0;analysisScreen(false,0);
    const poll=async()=>{
      try{
        const result=await api(`/api/jobs/${job}`);
        if(result.status==='error'){state.analyzing=false;analysisScreen(false,0,result.error);return;}
        if(result.status==='complete'){state.analyzing=false;await refresh();await openReview(result.clip);notify('Analysis complete. Your findings are ready.');return;}
        if(result.stage!==state.stage){state.stage=result.stage;if(state.page==='analysis')analysisScreen(false,state.stage);}
        state.timers.push(setTimeout(poll,1800));
      }catch(e){state.analyzing=false;analysisScreen(false,0,e.message);}
    };
    poll();
  }catch(e){error.textContent=e.message;button.disabled=false;button.innerHTML=`${icon('spark')} Analyze clip ${icon('arrow')}`;}
}
const clock=(t)=>t==null?'':`${Math.floor(t/60).toString().padStart(2,'0')}:${Math.floor(t%60).toString().padStart(2,'0')}`;
const findingTitle=(f)=>`${f.component_phrase||'Inspection finding'}${f.defect_phrase?` — ${f.defect_phrase}`:''}`;
function trustBadges(f) {
  const out=[];
  if(['spoken','unspoken'].includes(f.source))out.push(f.located?`<span class="badge" title="SAM 3.1 found this in the video">${icon('eye')} Located in video${f.confidence!=null?` · ${Math.round(f.confidence*100)}%`:''}</span>`:`<span class="badge neutral" title="Not pinpointed in the video. Confirm on site.">${icon('search')} Not pinpointed</span>`);
  if(f.corroborated)out.push(`<span class="badge blue" title="An independent AI pass flagged the same issue">${icon('spark')} AI saw it too</span>`);
  return out.join('');
}
function findingCard(f,index) {
  const decision=f.decision||'pending';
  const labels={spoken:['Inspector noted','blue','video'],unspoken:[decision==='pending'?'AI-flagged · your review needed':'Flagged by AI','amber','spark'],sensor:['Sensor measurement','neutral','grid'],inspector:['Added by inspector','','edit']};
  const [label,color,image]=labels[f.source]||['Finding','neutral','eye'];
  const time=clock(f.t_start);
  const manual=f.source==='inspector';
  return `<article class="finding ${esc(decision)} ${state.focus===f.id?'focused':''} stagger" style="--i:${Math.min(index,5)}" id="finding-${esc(f.id)}" data-finding="${esc(f.id)}"><div class="finding-header"><div><span class="badge ${color}">${icon(image)}${label}</span>${trustBadges(f)}${decision!=='pending'?`<span class="badge ${decision==='rejected'?'red':''}">${decision==='edited'?'Edited & accepted':decision==='rejected'?'Rejected':'Accepted'}</span>`:''}</div>${time?`<button class="ghost small" data-action="seek" data-id="${esc(f.id)}" data-time="${f.t_start}" aria-label="Show evidence at ${time}">${icon('play')} ${time}</button>`:'<small>INSPECTOR REVIEW</small>'}</div><div class="finding-content">${f.image?`<img class="finding-evidence" src="${esc(f.image)}" alt="Evidence: ${esc(f.component_phrase||'inspection finding')}" loading="lazy">`:''}<div><h3>${esc(f.component_phrase||'Inspection finding')}${f.defect_phrase?` — ${esc(f.defect_phrase)}`:''}</h3><p>${esc(f.description)}</p>${f.utterance?`<blockquote>“${esc(f.utterance)}”</blockquote>`:''}<small>${esc(f.room||'Unassigned')} · ${esc(f.sop_section||'General')}</small>${f.note?`<p><small>Review note: ${esc(f.note)}</small></p>`:''}</div></div>${manual?`<div class="finding-actions"><small>${icon('circle')} Confirmed by the inspector who added it</small></div>`:`<div class="finding-actions"><button class="accept ${['accepted','edited'].includes(decision)?'selected':''}" aria-pressed="${['accepted','edited'].includes(decision)}" data-action="decide" data-id="${esc(f.id)}" data-decision="accepted">${icon('check')} Accept</button><button data-action="edit" data-id="${esc(f.id)}">${icon('edit')} Edit</button><button class="reject ${decision==='rejected'?'selected':''}" aria-pressed="${decision==='rejected'}" data-action="reject" data-id="${esc(f.id)}">${icon('x')} Reject</button></div>`}</article>`;
}
function focusMedia(c) {
  const f=c.findings.find(x=>x.id===state.focus);
  if(c.video)return `<video id="evidence-video" src="${esc(c.video)}" ${c.thumbnail?`poster="${esc(c.thumbnail)}"`:''} controls playsinline preload="metadata"></video>`;
  const image=f?.image||c.thumbnail;
  return image?`<img src="${esc(image)}" alt="Evidence: ${esc(f?findingTitle(f):'inspection walkthrough')}">`:`<div class="placeholder">${icon('video')}<p>Review evidence alongside each finding.</p></div>`;
}
function focusDetail(c) {
  const f=c.findings.find(x=>x.id===state.focus);
  if(!f)return '';
  const time=clock(f.t_start);
  const said=f.utterance?`<blockquote>“${esc(f.utterance)}”<small>Inspector, on site${time?` · ${time}`:''}</small></blockquote>`:f.source==='unspoken'?`<p class="focus-ai">${icon('spark')} Not mentioned in the narration. AI flagged it from the footage${time?` at ${time}`:''}.</p>`:'';
  return `<div class="focus-card"><div class="focus-top"><span class="eyebrow">Selected finding</span>${time?`<span class="badge neutral">${icon('clock')} ${time}${f.t_end!=null?` – ${clock(f.t_end)}`:''}</span>`:''}</div><h3>${esc(findingTitle(f))}</h3>${said}<div class="focus-badges">${trustBadges(f)}</div>${f.located&&!c.video?'<small>The red box marks where SAM 3.1 found it.</small>':''}</div>`;
}
function selectFinding(id,scroll=false) {
  state.focus=id;
  document.querySelectorAll('.finding.focused').forEach(el=>el.classList.remove('focused'));
  const card=document.querySelector(`#finding-${CSS.escape(id)}`);
  card?.classList.add('focused');
  if(!state.clip.video)document.querySelector('#focus-media').innerHTML=focusMedia(state.clip);
  document.querySelector('#focus-detail').innerHTML=focusDetail(state.clip);
  if(scroll)card?.scrollIntoView({block:'nearest',behavior:'smooth'});
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
  const c=state.clip,total=c.findings.length,done=total-c.pending;
  const cover=Object.values(c.coverage||{}).flatMap(r=>r.items||[]);
  view(`${steps(1)}<div class="review-heading"><div><span class="eyebrow">${esc(roomTitle(c))}</span><h1>Review the details.</h1><p>A finding is a starting point. Your judgment makes it final.</p></div><span class="badge ${c.signed_by?'':'amber'}">${icon(c.signed_by?'shield':'spark')}${c.signed_by?'Signed off':`${c.ai_count} AI-flagged`}</span></div><div class="review-layout"><aside class="evidence-panel"><div><div class="video-frame" id="focus-media">${focusMedia(c)}</div><div class="panel-caption"><span>${icon('video')} ${esc(roomTitle(c))}</span><span>${c.video?'ORIGINAL WALKTHROUGH':'EVIDENCE FRAME'}</span></div><div id="focus-detail">${focusDetail(c)}</div></div>${cover.length?`<section class="coverage"><h3>Coverage at a glance</h3>${cover.slice(0,10).map(i=>`<div class="coverage-row"><span>${esc(i.label||i.item)}</span><span class="badge ${['not_seen','seen_not_mentioned'].includes(i.status)?'amber':''}">${esc(({not_seen:'Not seen',seen_not_mentioned:'Not mentioned',mentioned_not_seen:'Mentioned, not seen',tested:'Tested',inspected:'Inspected'})[i.status]||i.status)}</span></div>`).join('')}</section>`:''}${levelPanel(c)}</aside><section aria-label="Findings review"><div class="review-progress"><span><b>${done}</b> of ${total} findings reviewed</span><span>${c.pending?`${c.pending} to go`:'All details considered'}</span></div><div class="progress-track" role="progressbar" aria-valuenow="${done}" aria-valuemin="0" aria-valuemax="${total||1}" aria-label="Findings reviewed"><div class="progress-fill" style="transform:scaleX(${total?done/total:1})"></div></div><p class="shortcuts"><kbd>J</kbd><kbd>K</kbd> move <kbd>A</kbd> accept <kbd>E</kbd> edit <kbd>R</kbd> reject</p><div id="findings-list">${c.findings.map(findingCard).join('')}</div>${!total?'<div class="modal-info">No candidate findings were recorded. Review the clip and add any findings before signing off.</div>':''}<button class="add-finding" data-action="add">${icon('plus')} Add missing finding</button><div class="sign-area">${c.pending||c.signed_by?`<p>${icon('lock')} ${c.pending?'Review every finding before signing off.':`Signed by ${esc(c.signed_by)}. Further changes require a new sign-off.`}</p>`:''}${c.signed_by?'<button class="primary" data-action="current-report">View signed report '+icon('arrow')+'</button>':`<button class="primary" data-action="sign" ${c.pending?'disabled':''}>${icon('shield')} Sign off on this clip ${icon('arrow')}</button>`}</div></section></div>`);
}
function levelPanel(c) {
  const lv=c.level||{rooms:[],readings:0};
  const rows=lv.rooms.map(r=>`<div class="coverage-row"><span>${esc(r.room)}</span><span class="badge ${r.max_slope_deg>lv.threshold_deg?'red':''}">max ${r.max_slope_deg.toFixed(2)}°</span></div>${r.map?`<img class="level-map" src="${esc(r.map)}" alt="Slope map for ${esc(r.room)}">`:''}`).join('');
  return `<section class="level-panel"><h3>${icon('level')} Floor level</h3>${lv.readings?`<p class="level-note">${plural(lv.readings,'phone reading')} · flagged above ${lv.threshold_deg}° (¼ in over 32 in)</p>${rows}`:'<p class="level-note">Lay your phone on the floor to measure slope. Readings over the limit become findings here.</p>'}<button class="ghost small" data-action="measure-level">${icon('level')} Measure with your phone</button></section>`;
}
function levelLink(c) { return `${location.origin}/level?clip=${encodeURIComponent(c.id)}`; }
function levelModal() {
  const c=state.clip,local=['localhost','127.0.0.1','[::1]'].includes(location.hostname);
  openModal(`${modalHeader('Measure the floor.','Your phone becomes a level. Each reading lands in this inspection.')}<div class="modal-info" data-level-modal>${local?`<b>Phones need HTTPS.</b> In a terminal run <code>cloudflared tunnel --url ${esc(location.origin.replace('127.0.0.1','localhost'))}</code>, then open the printed link plus <code>/level?clip=${esc(encodeURIComponent(c.id))}</code> on your phone.`:`Open this link on your phone:<br><a href="${esc(levelLink(c))}" target="_blank" rel="noopener">${esc(levelLink(c))}</a>`}</div><ol class="level-steps"><li>Tap <b>Start sensor</b> and allow motion access.</li><li><b>Flip calibrate</b>: tap it, turn the phone 180° on the same spot, tap again.</li><li>Lay the phone flat, top edge toward the same wall each time. Name the room and spot, tap <b>Record</b>, and let go.</li></ol><p class="level-live" id="level-live">${icon('clock')} ${plural(c.level?.readings||0,'reading')} so far. New readings appear here as you record.</p><div class="modal-actions">${local?'':`<button data-action="copy-level">${icon('file')} Copy link</button>`}<button class="primary" data-action="close">Done</button></div>`);
  let seen=c.level?.readings||0;
  const poll=async()=>{
    if(!modal.open||!modal.querySelector('[data-level-modal]'))return;
    try{
      const data=await api(clipURL(c));
      const count=data.level?.readings||0;
      if(count!==seen){seen=count;updateReview(data);document.querySelector('#level-live').innerHTML=`${icon('check')} ${plural(count,'reading')} recorded. Findings and the slope map are updated.`;}
    }catch{}
    state.timers.push(setTimeout(poll,2500));
  };
  state.timers.push(setTimeout(poll,2500));
}
function updateReview(data,findingId) {
  state.clip=data;
  const index=state.clips.findIndex(c=>c.id===data.id);
  if(index>=0)state.clips[index]=data;
  const scroll=window.scrollY,video=document.querySelector('#evidence-video');
  const videoTime=video?.currentTime||0;
  reviewView();
  document.querySelectorAll('.stagger,.page-enter').forEach(el=>el.style.animation='none');
  const restored=document.querySelector('#evidence-video');
  if(restored&&videoTime)restored.currentTime=videoTime;
  window.scrollTo({top:scroll,behavior:'instant'});
  if(findingId)document.querySelector(`#finding-${CSS.escape(findingId)} .finding-actions button`)?.focus({preventScroll:true});
}
async function decide(id,decision,button) {
  button.disabled=true;
  try{const data=await post(clipURL(state.clip,'decision'),{id,decision});updateReview(data,id);notify(decision==='accepted'?'Finding accepted.':'Decision saved.');}
  catch(e){button.disabled=false;showError(e);}
}
function findingForm(finding=null) {
  const adding=!finding;
  openModal(`${modalHeader(adding?'Add your observation.':'Make it your own.',adding?'Your experience fills in the picture.':'Refine the finding before it becomes part of the report.')}<form id="finding-form" data-finding="${esc(finding?.id||'')}"><div class="field-row"><label class="field">Component<input name="component_phrase" value="${esc(finding?.component_phrase)}" required placeholder="e.g. Outlet cover"></label><label class="field">Issue<input name="defect_phrase" value="${esc(finding?.defect_phrase)}" placeholder="e.g. Missing"></label></div><div class="field-row"><label class="field">Room<input name="room" value="${esc(finding?.room||state.clip.rooms[0]||'')}" required></label><label class="field">Report section<select name="sop_section">${['General','Interior','Exterior','Kitchen','Bathroom(s)','Electrical','Plumbing','Structure','Attached Garage','Roof','HVAC'].map(s=>`<option ${s===(finding?.sop_section||'General')?'selected':''}>${s}</option>`).join('')}${finding?.sop_section&&!['General','Interior','Exterior','Kitchen','Bathroom(s)','Electrical','Plumbing','Structure','Attached Garage','Roof','HVAC'].includes(finding.sop_section)?`<option selected>${esc(finding.sop_section)}</option>`:''}</select></label></div><label class="field">Description<textarea name="description" required placeholder="Describe what you observed…">${esc(finding?.description)}</textarea></label><p class="form-error" id="form-error" role="alert"></p><div class="modal-actions"><button type="button" data-action="close">Cancel</button><button class="primary" type="submit">${icon('check')} ${adding?'Add finding':'Save changes'}</button></div></form>`);
}
function rejectForm(id) {
  openModal(`${modalHeader('Leave it out of the report.','The observation stays in your review history.')}<form id="reject-form" data-finding="${esc(id)}"><label class="field">Reason for rejection (optional)<textarea name="note" placeholder="e.g. Reflection, not a crack."></textarea></label><p class="form-error" id="form-error" role="alert"></p><div class="modal-actions"><button type="button" data-action="close">Keep reviewing</button><button class="primary" type="submit">Confirm rejection</button></div></form>`);
}
function signForm() {
  if(state.clip.pending)return;
  openModal(`${modalHeader('Your final word.','Confirm your review and sign off on this walkthrough.')}<form id="sign-form"><div class="modal-info"><b>${esc(roomTitle(state.clip))}</b><br>${state.clip.findings.filter(f=>f.decision!=='rejected').length} findings included · ${state.clip.findings.filter(f=>f.decision==='rejected').length} rejected<br>This sign-off covers this clip and the rooms represented in it.</div><label class="field">Inspector name<input name="name" autocomplete="name" required placeholder="Your full name"></label><label class="checkbox-label"><input type="checkbox" name="confirm" required>I have reviewed every finding and confirm that this clip is ready to be included in the report.</label><p class="form-error" id="form-error" role="alert"></p><div class="modal-actions"><button type="button" data-action="close">Keep reviewing</button><button class="primary" type="submit">${icon('shield')} Confirm sign-off</button></div></form>`);
}
function successView() {
  state.page='success';
  const c=state.clip;
  view(`${steps(3)}<section class="signed-page"><div class="success-icon">${icon('check')}</div><span class="eyebrow">THE DETAILS MAKE THE DIFFERENCE</span><h1>Reviewed. Confirmed.<br>Signed.</h1><p>Your expertise, with a second perspective. This walkthrough is signed off and ready for its report.</p><div class="signed-receipt"><div class="receipt-row"><span>Walkthrough</span><strong>${esc(roomTitle(c))}</strong></div><div class="receipt-row"><span>Reviewed & signed by</span><strong>${esc(c.signed_by)}</strong></div><div class="receipt-row"><span>Signed on</span><strong>${date(c.signed_at)}</strong></div><div class="receipt-row"><span>Included findings</span><strong>${c.findings.filter(f=>f.decision!=='rejected').length}</strong></div><div class="receipt-row"><span>Status</span><span class="badge">${icon('circle')} Ready for report</span></div></div><div class="signed-actions"><button class="primary" data-action="current-report">${icon('file')} View report ${icon('arrow')}</button><button data-action="nav" data-page="reports">All reports</button></div></section>`);
}
async function openReport(id) {
  state.clip=await api(`/api/clips/${encodeURIComponent(id)}`);
  if(!state.clip.signed_by){await openReview(id);notify('Sign off on the clip to generate its report.');return;}
  state.page='report';
  const c=state.clip;
  const sections=['Property & sign-off','Summary & how it was made','Findings by system & room, with evidence'];
  if(c.has_level) sections.push('Floor level measurements');
  if(Object.keys(c.coverage||{}).length) sections.push('Coverage checklist');
  sections.push('Items not inspected & limitations');
  view(`<div class="review-heading"><div><span class="eyebrow">FROM A CLOSER LOOK TO A CLEARER PICTURE</span><h1>Ready for the next chapter.</h1><p>${esc(roomTitle(c))} · Reviewed by ${esc(c.signed_by)}</p></div><span class="badge">${icon('shield')} Signed & verified</span></div><div class="report-layout"><aside class="report-aside"><div><h3>Inside your report</h3><p>Structured for a clear handover.</p><ol>${sections.map(label=>`<li>${label}</li>`).join('')}</ol></div><div><button class="primary" data-action="print-report">${icon('download')} Print / Save as PDF</button></div></aside><div class="report-paper"><iframe title="Signed inspection report" src="${clipURL(c,'report')}"></iframe></div></div>`);
}
async function submitForm(form) {
  const button=form.querySelector('[type=submit]');
  button.disabled=true;
  try {
    const data=Object.fromEntries(new FormData(form));
    let result;
    if(form.id==='finding-form'){
      if(!data.description.trim()||!data.component_phrase.trim()||!data.room.trim())throw new Error('Enter a component, room, and description.');
      const id=form.dataset.finding;
      result=await post(clipURL(state.clip,id?'decision':'add'),id?{id,decision:'edited',edits:data}:data);
      closeModal();updateReview(result,id);notify(id?'Finding updated and accepted.':'Your finding has been added.');
      if(id===state.focus){const next=nextFinding(1,true);if(next)selectFinding(next,true);}
    }else if(form.id==='reject-form'){
      const id=form.dataset.finding;
      result=await post(clipURL(state.clip,'decision'),{id,decision:'rejected',note:data.note});
      closeModal();updateReview(result,id);notify('Finding rejected. It will stay out of the report.');
      if(id===state.focus){const next=nextFinding(1,true);if(next)selectFinding(next,true);}
    }else if(form.id==='sign-form'){
      if(!data.name.trim())throw new Error('Enter your name to sign off.');
      state.clip=await post(clipURL(state.clip,'sign'),{name:data.name.trim()});
      closeModal();await refresh();successView();
    }
  }catch(e){form.querySelector('#form-error').textContent=e.message;button.disabled=false;}
}
document.addEventListener('submit',e=>{if(['finding-form','reject-form','sign-form'].includes(e.target.id)){e.preventDefault();submitForm(e.target);}});
document.addEventListener('click',async e=>{
  const button=e.target.closest('[data-action]');
  const card=e.target.closest('.finding[data-finding]');
  if(!button&&card&&state.page==='review'){selectFinding(card.dataset.finding);return;}
  if(!button||button.disabled)return;
  const {action,id,page}=button.dataset;
  try {
    switch(action){
      case 'nav': await navigate(page); break;
      case 'filter': state.filter=button.dataset.filter;history();break;
      case 'analyze': if(state.analyzing){state.page='analysis';analysisScreen(state.replay,state.stage);notify('An analysis is already running.');}else analyzeModal();break;
      case 'analyze-tab': analyzeModal(button.dataset.mode);break;
      case 'demo': if(state.analyzing){state.page='analysis';analysisScreen(state.replay,state.stage);}else analyzeModal('replay');break;
      case 'close':closeModal();break;
      case 'start-replay':await startReplay();break;
      case 'start-upload':await startUpload(button);break;
      case 'choose-upload':document.querySelector('#clip-upload').click();break;
      case 'review':await openReview(id);break;
      case 'report':await openReport(id);break;
      case 'current-report':await openReport(state.clip.id);break;
      case 'decide':await decide(id,button.dataset.decision,button);break;
      case 'edit':findingForm(state.clip.findings.find(f=>f.id===id));break;
      case 'add':findingForm();break;
      case 'reject':rejectForm(id);break;
      case 'sign':signForm();break;
      case 'seek':{selectFinding(id);const video=document.querySelector('#evidence-video');if(video){video.currentTime=Number(button.dataset.time);await video.play();}else if(matchMedia('(max-width:900px)').matches)document.querySelector('#focus-media').scrollIntoView({behavior:'smooth'});break;}
      case 'measure-level':levelModal();break;
      case 'copy-level':await navigator.clipboard.writeText(levelLink(state.clip));notify('Link copied. Open it on your phone.');break;
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
    else{await decide(f.id,'accepted',document.querySelector(`#finding-${CSS.escape(f.id)} .accept`));const id=nextFinding(1,true);if(id)selectFinding(id,true);}
  }catch(error){showError(error);}
});
document.addEventListener('keydown',()=>document.body.classList.add('keyboard-navigation'));
document.addEventListener('pointerdown',()=>document.body.classList.remove('keyboard-navigation'));
refresh().then(overview).catch(error=>{view(`<div class="empty"><h3>Let’s reconnect.</h3><p>${esc(error.message)}</p><button class="primary" data-action="nav" data-page="overview">Try again</button></div>`);});
