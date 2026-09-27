'use strict';
const $ = id => document.getElementById(id);
let sources = [], requestFailed = false, hideTimer, layoutInitialized=false, displayedSourceId=null;
const preferences = (() => {try{return JSON.parse(localStorage.getItem('dsan-display') || '{}');}catch{return {};}})();
const outputMode = document.body.classList.contains('output');
const outputParams = new URLSearchParams(location.search);
if(outputMode){
  document.title = 'DSAN video output';
  for(const [param,key] of [['source','source'],['cue','cueSource'],['program','program']]){
    if(outputParams.has(param)) preferences[key]=outputParams.get(param);
  }

}
$('display-mode').value=['timer','cue','both'].includes(preferences.displayMode)?preferences.displayMode:'both';
$('program').value = preferences.program || 'active';
$('warning').value = Number.isFinite(preferences.warning) ? preferences.warning : 30;
$('overtime').checked = !!preferences.overtime;
$('minimal').checked = !!preferences.minimal;
function sizePercent(value){const n=Number(value);return value==null || value==='' || !Number.isFinite(n) ? 100 : Math.max(50,Math.min(150,n));}
$('timer-size').value=sizePercent(preferences.timerSize);
$('cue-size').value=sizePercent(preferences.cueSize);
document.body.classList.toggle('minimal', outputMode && $('minimal').checked);
function save(){if(outputMode)return;try{localStorage.setItem('dsan-display',JSON.stringify({source:$('source').value,cueSource:$('cue-source').value,program:$('program').value}));}catch{}}
let videoReady=false, videoRevision=-1, videoSaving=false, pendingVideoChanges={}, videoSaveTimer;
const videoFields={'display-mode':'displayMode',minimal:'minimal','timer-size':'timerSize','cue-size':'cueSize',warning:'warning',overtime:'overtime'};
function receiveVideoSettings(video){
  if(!video || !video.settings || videoSaving || Object.keys(pendingVideoChanges).length) return;
  videoReady=true;
  if(video.revision<=videoRevision) return;
  videoRevision=video.revision;
  for(const [id,key] of Object.entries(videoFields)){
    const element=$(id);
    if(element.type==='checkbox') element.checked=video.settings[key];
    else element.value=video.settings[key];
  }
  $('video-settings-status').textContent='Video output settings synced';
}
function changeVideoSetting(id){
  const element=$(id), key=videoFields[id];
  let value=element.type==='checkbox'?element.checked:element.value;
  if(['timerSize','cueSize'].includes(key)) value=sizePercent(value);
  if(key==='warning') value=Math.max(0,Math.min(3600,Math.round(Number(value)||0)));
  pendingVideoChanges[key]=value;
  $('video-settings-status').textContent='Updating video output…';
  clearTimeout(videoSaveTimer);
  videoSaveTimer=setTimeout(flushVideoSettings,120);
  render();
}
async function flushVideoSettings(){
  if(videoSaving || !Object.keys(pendingVideoChanges).length) return;
  const changes=pendingVideoChanges; pendingVideoChanges={}; videoSaving=true;
  let retryDelay=0;
  try{
    const response=await fetch('/api/video-settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(changes),signal:AbortSignal.timeout(3000)});
    const result=await response.json();
    if(!response.ok) throw new Error(result.error || 'Update failed');
    videoSaving=false;
    receiveVideoSettings(result);
  }catch(error){
    pendingVideoChanges={...changes,...pendingVideoChanges};
    $('video-settings-status').textContent='Video update not saved; retrying. '+error.message;
    retryDelay=1000;
  }finally{
    videoSaving=false;
    if(Object.keys(pendingVideoChanges).length) videoSaveTimer=setTimeout(flushVideoSettings,retryDelay);
  }
}

function applySizes(){
  const clock=$('clock'), cue=$('cue-signal'), monitor=$('monitor');
  const timerPercent=sizePercent($('timer-size').value), cuePercent=sizePercent($('cue-size').value);
  const timerScale=outputMode?timerPercent/100:1, cueScale=outputMode?cuePercent/100:1;
  $('timer-size-value').textContent=`${timerPercent}%`;
  $('cue-size-value').textContent=`${cuePercent}%`;
  clock.style.fontSize=''; cue.style.fontSize=''; cue.style.minHeight='';
  const clockSize=parseFloat(getComputedStyle(clock).fontSize)*(monitor.classList.contains('cue-display')?cueScale:timerScale);
  const cueHeight=parseFloat(getComputedStyle(cue).minHeight)*cueScale;
  const cueFont=parseFloat(getComputedStyle(cue).fontSize)*cueScale;
  const setSizes=fit=>{clock.style.fontSize=`${clockSize*fit}px`;cue.style.fontSize=`${cueFont*fit}px`;cue.style.minHeight=`${cueHeight*fit}px`;};
  setSizes(1);
  const style=getComputedStyle(monitor), width=monitor.clientWidth-parseFloat(style.paddingLeft)-parseFloat(style.paddingRight);
  const children=[...monitor.children].filter(el=>getComputedStyle(el).display!=='none');
  const widest=Math.max(1,...children.map(el=>el.scrollWidth));
  let fit=Math.min(1,width/widest);
  if(outputMode || document.fullscreenElement){
    const height=innerHeight-parseFloat(style.paddingTop)-parseFloat(style.paddingBottom);
    const total=children.reduce((sum,el)=>{const s=getComputedStyle(el);return sum+el.getBoundingClientRect().height+parseFloat(s.marginTop)+parseFloat(s.marginBottom);},0);
    const scalable=clock.getBoundingClientRect().height+($('cue-overlay').hidden?0:cue.getBoundingClientRect().height);
    if(scalable>0) fit=Math.min(fit,Math.max(0.1,(height-(total-scalable))/scalable));
  }
  setSizes(fit);
}
function cueText(source){
  if(requestFailed || source.status==='disconnected') return 'DISCONNECTED';
  if(source.status==='ended') return 'REPLAY ENDED';
  if(source.warming) return 'SYNCHRONIZING';
  if(!source.cue_active) return 'WAITING FOR CUE';
  return {next:'▶\uFE0E',previous:'◀\uFE0E','blank-off':'⊗ BLANK','blank-on':'⊗ BLANK'}[source.cue] || 'UNKNOWN';
}
function cueDirection(source){return !requestFailed && source.status==='connected' && !source.warming && source.cue_active && ['next','previous'].includes(source.cue) ? source.cue : '';}
function cueIdle(source){return !requestFailed && source.status==='connected' && !source.warming && !source.cue_active;}
function format(seconds, minutesSeconds){
  const negative = seconds < 0 ? '−' : '', value = Math.abs(Math.trunc(seconds));
  if (!minutesSeconds) return negative + String(Math.floor(value / 3600)).padStart(2,'0') + ':' + String(Math.floor(value / 60) % 60).padStart(2,'0');
  return negative + String(Math.floor(value / 60)).padStart(1,'0') + ':' + String(value % 60).padStart(2,'0');
}
function renderConnections(){
  const describe=source=>{
    const cue=source.role==='perfectcue';
    const selected=[];
    if(source.id===$('source').value) selected.push('selected timer');
    if(source.id===$('cue-source').value) selected.push('selected cue');
    const transport={pi:'Pi USB via SSH',hid:'Native USB HID',replay:'Recorded replay'}[source.kind] || source.kind;
    return [
      `${source.label} · ${cue?'PerfectCue':'Limitimer'} · ${transport}`,
      selected.length?`Selection: ${selected.join(', ')}`:'Selection: not selected for this view',
      `Connection: ${requestFailed?'DISPLAY SERVER UNREACHABLE (last known: '+source.status+')':source.status}`,
      `Device / source path: ${source.target}`,
      `Reports: ${source.reports} · Rejected: ${source.rejected}`,
      cue?`Decoded cues: ${source.cue_sequence} · Last cue: ${source.cue || 'none'}`:`Timer frames: ${source.states} · Data: ${source.fresh?'fresh':'stale / unavailable'}`,
      `Last ${cue?'cue':'timer state'}: ${source.age===null?'never':source.age.toFixed(1)+' s ago'}`,
      cue?`Unknown cue bytes: ${source.unknown_cue_bytes} · Last raw report: ${source.last_report_hex || 'none'}`:`Checksum: ${source.checksum || 'not available'}`,
      cue?'Cue mapping: emulator + dongle tested; real PerfectCue and Blank untested. Silence is not a heartbeat.':'Time advances only on received state.',
      source.error?`Error: ${source.error}`:''
    ].filter(Boolean).join('\n');
  };
  const live=sources.filter(s=>s.kind!=='replay'), replays=sources.filter(s=>s.kind==='replay');
  $('diagnostics').textContent=[
    `LIVE CONNECTIONS (${live.length})`,live.map(describe).join('\n\n') || 'No live sources configured.',
    replays.length?`REPLAY SOURCES (${replays.length})\n${replays.map(describe).join('\n\n')}`:''
  ].filter(Boolean).join('\n\n');
}
function render(){
  document.body.classList.toggle('minimal', outputMode && $('minimal').checked);
  renderConnections();
  const videoMode=$('display-mode').value;
  const overlay=sources.find(s=>s.id===$('cue-source').value && s.role==='perfectcue');
  const timer=sources.find(s=>s.id===$('source').value && s.role!=='perfectcue');
  const mode=outputMode?videoMode:(timer?(overlay?'both':'timer'):(overlay?'cue':'timer'));
  const source=mode==='cue'?overlay:timer;
  displayedSourceId=source?.id || null;
  $('source').disabled=$('program').disabled=videoMode==='cue';
  $('cue-source').disabled=videoMode==='timer';
  $('warning').disabled=$('overtime').disabled=$('timer-size').disabled=!videoReady || videoMode==='cue';
  $('cue-size').disabled=!videoReady || videoMode==='timer';
  $('minimal').disabled=$('display-mode').disabled=!videoReady;
  if (!source){
    $('monitor').className='stale';
    $('clock').textContent='--:--';
    $('clock').dataset.idle='false';
    $('clock').dataset.cue='';
    $('clock').removeAttribute('aria-label');
    $('status').textContent=mode==='cue'?'CUE SOURCE UNAVAILABLE':'TIMER SOURCE UNAVAILABLE';
    $('message').textContent='Select the required source in the operator view';
    $('cue-overlay').hidden=true;
    $('restart').hidden=true;
    applySizes();
    return;
  }
  const isCue = mode==='cue';
  $('cue-overlay').hidden = mode!=='both';
  if(overlay){
    $('cue-signal').textContent=cueText(overlay);
    $('cue-signal').dataset.cue=cueDirection(overlay);
    $('cue-signal').dataset.idle=String(cueIdle(overlay));
    $('cue-signal').setAttribute('aria-label',cueDirection(overlay) || cueText(overlay));
    $('cue-caption').textContent=`${overlay.label} · Emulator tested · Real PerfectCue untested · Local 1 s hold`;
  }else if(mode==='both'){
    $('cue-overlay').hidden=false;
    $('cue-signal').textContent='CUE SOURCE UNAVAILABLE';
    $('cue-signal').dataset.cue='';
    $('cue-signal').dataset.idle='false';
    $('cue-signal').setAttribute('aria-label','Cue source unavailable');
    $('cue-caption').textContent='Check source binding in the operator view';
  }
  const index = $('program').value === 'active' ? source.selected : Number($('program').value);
  const program = source.programs[index];
  const stale = requestFailed || !source.fresh;
  const seconds = program ? (outputMode && $('overtime').checked ? program.raw_seconds : program.seconds) : null;
  const classes = [];
  if (source.kind === 'replay') classes.push('replay');
  if (stale) classes.push('stale');
  if (program && !program.running) classes.push('paused');
  if (seconds !== null && seconds <= 0) classes.push('expired');
  else if (seconds !== null && seconds <= (outputMode?Math.max(0,Number($('warning').value)||0):30)) classes.push('warning');
  $('monitor').className = classes.join(' ');
  $('source-name').textContent = source.label;
  $('program-name').textContent = index == null ? '' : `Program ${index+1}${$('program').value==='active'?' · Follow controller':''}`;
  const value = program && !source.warming ? format(seconds, program.minutes_seconds) : '--:--';
  $('clock').textContent = value;
  $('clock').dataset.cue = '';
  $('clock').dataset.idle = 'false';
  $('clock').removeAttribute('aria-label');
  $('clock').classList.toggle('long', value.length > 6);
  const prefix = source.kind === 'replay' ? 'REPLAY · ' : '';
  let status, message;
  if (requestFailed){status='DISPLAY CONNECTION LOST';message='Last received value · not advancing';}
  else if (source.warming){status='SYNCHRONIZING';message='Waiting for current device state';}
  else if (source.status === 'ended'){status='REPLAY ENDED';message='Last recorded value · restart to play again';}
  else if (source.status === 'disconnected'){status='DISCONNECTED';message='Last received value · not advancing';}
  else if (!program){status='WAITING FOR DATA';message='No decoded timer state received';}
  else if (!source.fresh){status='STALE DATA';message='Last received value · not advancing';}
  else {status=prefix+(program.running?'RUNNING':'PAUSED / STOPPED');message=source.kind==='replay'?'Recorded hardware data · playback at original speed':'Received device time';}
  $('status').textContent = status;
  $('message').textContent = message;
  $('restart').hidden = source.kind !== 'replay';
  if(isCue){
    $('monitor').className = 'cue-display' + (source.kind==='replay' ? ' replay' : '') + (requestFailed || source.status !== 'connected' ? ' stale' : '');
    $('program-name').textContent = 'PerfectCue';
    $('clock').classList.add('long');
    $('clock').textContent = cueText(source);
    $('clock').dataset.cue = cueDirection(source);
    $('clock').dataset.idle = String(cueIdle(source));
    $('clock').setAttribute('aria-label',cueDirection(source) || cueText(source));
    $('status').textContent = (source.kind==='replay' ? 'REPLAY · ' : '') + 'EMULATOR TESTED · HARDWARE UNVERIFIED';
    $('message').textContent = 'Captured framed cues · Local 1 second hold · Silence is not a heartbeat';
  }
  applySizes();
}
function updateOptions(){
  const timers=sources.filter(s=>s.role!=='perfectcue');
  const cues=sources.filter(s=>s.role==='perfectcue');
  const legacyCue=sources.find(s=>s.id===preferences.source && s.role==='perfectcue');
  if(!layoutInitialized && sources.length){
    if(!['timer','cue','both'].includes(preferences.displayMode)) $('display-mode').value=legacyCue || !timers.length?'cue':cues.length?'both':'timer';
    if(legacyCue && !preferences.cueSource) preferences.cueSource=legacyCue.id;
    layoutInitialized=true;
  }
  const old = $('source').value || preferences.source;
  if ([...$('source').options].map(o=>o.value).join() !== timers.map(s=>s.id).join()){
    $('source').replaceChildren(...timers.map(s=>new Option(s.label+(s.kind==='replay'?' · Replay':''),s.id)));
    if (timers.some(s=>s.id===old)) $('source').value=old;
  }
  const oldCue = $('cue-source').value || preferences.cueSource;
  if([...$('cue-source').options].slice(1).map(o=>o.value).join() !== cues.map(s=>s.id).join()){
    $('cue-source').replaceChildren(new Option('None',''),...cues.map(s=>new Option(s.label,s.id)));
    if(cues.some(s=>s.id===oldCue)) $('cue-source').value=oldCue;
    else if(preferences.cueSource === undefined && cues.length===1) $('cue-source').value=cues[0].id;
  }
  // An explicitly bound output never silently switches to another device.
  if(outputMode && outputParams.has('source')) $('source').value=preferences.source;
  if(outputMode && outputParams.has('cue')) $('cue-source').value=preferences.cueSource;
}
async function poll(){
  try{
    const response=await fetch('/api/state',{cache:'no-store',signal:AbortSignal.timeout(1500)});
    if(!response.ok) throw new Error('State request failed');
    const state=await response.json();
    sources=state.sources;requestFailed=false;updateOptions();receiveVideoSettings(state.video);render();
  }catch{requestFailed=true;render();}
  setTimeout(poll,200);
}
for(const id of ['source','cue-source','program']) $(id).addEventListener('change',()=>{save();render();});
for(const id of Object.keys(videoFields)) $(id).addEventListener($(id).type==='range'?'input':'change',()=>changeVideoSetting(id));
window.addEventListener('resize',render);
$('open-output').addEventListener('click',()=>{
  const url=new URL('/output',location.origin);
  url.search=new URLSearchParams({source:$('source').value,cue:$('cue-source').value,program:$('program').value}).toString();
  window.open(url.toString(),'_blank','noopener');
});
$('restart').addEventListener('click',async()=>{
  $('restart').disabled=true;
  try{await fetch('/api/restart-replay',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:displayedSourceId})});}
  finally{$('restart').disabled=false;}
});
async function fullscreen(){try{if(document.fullscreenElement)await document.exitFullscreen();else await document.body.requestFullscreen();}catch{$('message').textContent='Use your browser’s fullscreen command';}}
$('fullscreen').addEventListener('click',fullscreen);
document.addEventListener('keydown',e=>{if(e.key.toLowerCase()==='f'&&!['INPUT','SELECT','TEXTAREA'].includes(e.target.tagName)){e.preventDefault();fullscreen();}});
function showControls(){document.body.classList.remove('quiet');clearTimeout(hideTimer);hideTimer=setTimeout(()=>{if(document.fullscreenElement&&!document.querySelector('details[open]'))document.body.classList.add('quiet');},3000);}
document.addEventListener('mousemove',showControls);document.addEventListener('focusin',showControls);document.addEventListener('fullscreenchange',()=>{$('fullscreen').textContent=document.fullscreenElement?'Exit fullscreen':'Fullscreen';showControls();});
poll();
