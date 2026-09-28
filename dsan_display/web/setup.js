'use strict';
const $=id=>document.getElementById(id);
let state=null, key='', busy=false, stopped=false;
const roleName=role=>role==='limitimer'?'Limitimer':'PerfectCue';
function message(error){$('error').textContent=error;$('error').hidden=!error;}
async function command(action,data={}){
  if(busy)return;
  busy=true;message('');
  document.querySelectorAll('button').forEach(b=>b.disabled=true);
  try{
    const r=await fetch('/api/setup/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),signal:AbortSignal.timeout(15000)});
    const result=await r.json();if(!r.ok)throw new Error(result.error||'Setup request failed');
    state=result;key='';render();
  }catch(e){message(e.message);}
  finally{busy=false;document.querySelectorAll('button').forEach(b=>b.disabled=false);}
}
function answer(value){command('answer',{session:state.session,prompt:state.prompt.id,answer:value});}
function button(label,action,primary=false){const b=document.createElement('button');b.textContent=label;if(primary)b.className='primary';b.onclick=action;$('actions').append(b);}
function render(){
  const nextKey=JSON.stringify(state);if(key===nextKey)return;key=nextKey;
  $('target').textContent=state.target;
  $('actions').replaceChildren();$('review').replaceChildren();$('name-form').hidden=true;
  $('live').hidden=state.status!=='complete';
  $('cancel').hidden=!['waiting','working','review'].includes(state.status);
  $('notice').textContent='';message(state.error);
  for(const [id,active] of [['step-pair',['idle','working','waiting','error'].includes(state.status)],['step-review',['review','applying'].includes(state.status)],['step-live',state.status==='complete']])$(id).classList.toggle('active',active);
  $('messages').replaceChildren(...state.messages.map(text=>{const p=document.createElement('p');p.textContent=text;return p;}));
  if(state.status==='idle'){
    $('heading').textContent='Identify your dongles';$('instruction').textContent='Keep any connected dongles in place. We’ll guide you through identifying one at a time. Existing assignments are replaced only when you save.';
    button('Start device setup',()=>command('start'),true);
    if(state.has_saved)button('Resume saved inputs',()=>command('resume'));
  }else if(state.status==='waiting'){
    const p=state.prompt;
    $('heading').textContent=p.kind==='role'?'Which input are you adding?':p.kind==='name'?'Dongle identified':'Check the USB connection';
    $('instruction').textContent=p.text.replace(/,? then press Enter: ?$/,'; then click Check connection.').replace(/,? press Enter: ?$/,'; then click Check connection.');
    if(p.kind==='role'){
      button('Add Limitimer',()=>answer('1'),true);button('Add PerfectCue',()=>answer('2'),true);button('Review paired devices',()=>answer(''));
    }else if(p.kind==='name'){$('name-form').hidden=false;$('input-name').value=p.default;$('input-name').focus();}
    else button('Check connection',()=>answer(''),true);
    $('notice').textContent=p.note||'';
  }else if(state.status==='review'){
    $('heading').textContent='Review your inputs';$('instruction').textContent='Save and start replaces the current device assignments and initializes each dongle for its selected role. It does not change firmware or internal switches.';
    for(const s of state.config.sources){const row=document.createElement('p');const name=document.createElement('strong');name.textContent=s.label;row.append(name,document.createTextNode(' · '+roleName(s.role)));$('review').append(row);}
    button('Save and start inputs',()=>command('apply',{session:state.session}),true);
  }else if(state.status==='complete'){
    $('heading').textContent='Your inputs are configured';$('instruction').textContent='Check the received data below before using video output.';
    button('Change device setup',()=>command('start'));
  }else if(state.status==='error'){
    $('heading').textContent='Setup needs attention';$('instruction').textContent='Check the connections and try setup again. No other dongle will be substituted for a missing input.';button('Start setup again',()=>command('start'),true);
  }else{$('heading').textContent=state.status==='applying'?'Saving and starting inputs…':state.status==='restoring'?'Starting saved inputs…':'Checking devices…';$('instruction').textContent='Please wait.';}
}
$('name-form').onsubmit=e=>{e.preventDefault();answer($('input-name').value.trim());};
$('cancel').onclick=()=>command('cancel');
$('quit').onclick=async()=>{
  if(!confirm('Quit DSAN application? This stops all inputs and video outputs.'))return;
  try{const r=await fetch('/api/quit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm:true})});if(!r.ok)throw new Error('Quit request failed');stopped=true;$('heading').textContent='Application shutting down';$('instruction').textContent='You can close this page.';document.querySelectorAll('button').forEach(b=>b.disabled=true);}catch(e){message(e.message);}
};
function readings(sources){
  $('readings').replaceChildren(...sources.map(s=>{
    const row=document.createElement('div');row.className='source';const title=document.createElement('div');const strong=document.createElement('strong');strong.textContent=s.label;
    const status=document.createElement('small');status.textContent=roleName(s.role)+' · '+s.status+(s.fresh?'':' · waiting for fresh data');title.append(strong,status);
    const value=document.createElement('div');value.className='reading';
    if(s.role==='perfectcue'){value.textContent=s.cue_active?(s.cue==='next'?'▶ Next':'◀ Previous'):'Waiting for cue';if(s.cue_active)value.classList.add(s.cue);}
    else{
      const p=s.programs.find(p=>p.index===s.selected);
      if(p&&s.fresh){const n=Math.abs(p.seconds),unit=p.minutes_seconds?1:60;value.textContent=(p.seconds<0?'−':'')+Math.floor(n/(60*unit))+':'+String(Math.floor(n/unit)%60).padStart(2,'0');}
      else value.textContent='—';
    }
    if(s.error){status.textContent+=' · '+s.error;}
    row.append(title,value);return row;
  }));
}
async function poll(){
  if(stopped)return;
  try{
    const r=await fetch('/api/setup',{cache:'no-store',signal:AbortSignal.timeout(5000)});const data=await r.json();if(!r.ok)throw new Error(data.error||'Setup unavailable');
    if(!busy){state=data;render();}
    if(state?.status==='complete'){const r=await fetch('/api/state',{cache:'no-store',signal:AbortSignal.timeout(3000)});if(!r.ok)throw new Error('Input status unavailable');const data=await r.json();if(data.application.status==='stopping'){stopped=true;$('heading').textContent='Application shutting down';}else readings(data.sources);}
  }catch(e){message('Connection unavailable: '+e.message);$('readings').replaceChildren();}
  if(!stopped)setTimeout(poll,500);
}
poll();
