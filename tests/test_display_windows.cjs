// Synthetic screen geometry and browser-event tests; not physical monitor tests.
const test=require('node:test');
const assert=require('node:assert/strict');
const {screenKey,screenLabel,windowFeatures,openOutput,installOutputExit}=require('../dsan_display/web/display-windows.js');

const external={label:'External test display',left:-1920,top:0,width:1920,height:1080,
  availLeft:-1920,availTop:0,availWidth:1920,availHeight:1040,isInternal:false,isPrimary:false};

test('selected display placement preserves negative coordinates and work area',()=>{
  assert.equal(windowFeatures(external),'popup=yes,left=-1920,top=0,width=1920,height=1040');
  assert.match(screenLabel(external,1),/Display 2.*1920×1080.*External/);
});

test('opens the selected screen in a separate script-controlled popup',()=>{
  const calls=[];let focused=false;
  const popup={opener:{},focus:()=>{focused=true;}};
  const other={...external,label:'Other display',left:0,availLeft:0};
  assert.equal(openOutput('/output?managed=1',screenKey(external),[other,external],(...args)=>{calls.push(args);return popup;}),popup);
  assert.equal(calls[0][2],windowFeatures(external));
  assert.equal(calls[0][1],'_blank');
  assert.equal(popup.opener,null);
  assert.ok(focused);
});

test('disconnected selection never silently falls back to another screen',()=>{
  let opened=false;
  assert.throws(()=>openOutput('/output',screenKey(external),[],()=>{opened=true;}),/no longer connected/);
  assert.equal(opened,false);
});

test('blocked popup and invalid geometry produce explicit errors',()=>{
  assert.throws(()=>openOutput('/output','',[],()=>null),/blocked/);
  assert.throws(()=>windowFeatures({...external,availWidth:NaN}),/geometry/);
  assert.throws(()=>windowFeatures({...external,availHeight:0}),/geometry/);
});

function browser(closes=true){
  const events={};let closeCalls=0,blocked=0;
  const win={closed:false,close(){closeCalls++;if(closes)this.closed=true;},setTimeout(fn){fn();}};
  const doc={fullscreenElement:null,addEventListener(name,handler){events[name]=handler;}};
  const close=installOutputExit(win,doc,()=>{blocked++;});
  return {win,doc,events,close,get closeCalls(){return closeCalls;},get blocked(){return blocked;}};
}

test('Escape closes an output without needing fullscreen',()=>{
  const b=browser();let prevented=false;
  b.events.keydown({key:'Escape',preventDefault(){prevented=true;}});
  assert.equal(b.closeCalls,1);assert.ok(b.win.closed);assert.ok(prevented);
});

test('browser-handled fullscreen exit closes output even without keydown',()=>{
  const b=browser();b.doc.fullscreenElement={};b.events.fullscreenchange();
  b.doc.fullscreenElement=null;b.events.fullscreenchange();
  assert.equal(b.closeCalls,1);
});

test('completed fullscreen request is remembered before its change event arrives',()=>{
  const b=browser();b.close.markFullscreenEntered();b.events.fullscreenchange();
  assert.equal(b.closeCalls,1);
});

test('unrelated keys and initial non-fullscreen state do not close output',()=>{
  const b=browser();b.events.keydown({key:'f'});b.events.fullscreenchange();
  assert.equal(b.closeCalls,0);
});

test('direct tabs that cannot be closed receive a visible fallback',()=>{
  const b=browser(false);b.events.keydown({key:'Escape',preventDefault(){}});
  assert.equal(b.closeCalls,1);assert.equal(b.blocked,1);
});
