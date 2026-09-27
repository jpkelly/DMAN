'use strict';
// Original window-placement helpers. Coordinates are browser CSS pixels, including
// negative positions for displays to the left/above the primary display.
(function(root){
  function screenKey(screen){
    return JSON.stringify([screen.label || '',screen.left,screen.top,screen.width,screen.height]);
  }
  function screenLabel(screen,index){
    const tags=[screen.isInternal?'Built-in':'External'];
    if(screen.isPrimary) tags.push('Primary');
    return `Display ${index+1}${screen.label?' · '+screen.label:''} · ${screen.width}×${screen.height} · ${tags.join(', ')}`;
  }
  function windowFeatures(screen){
    if(!screen) return 'popup=yes,width=1280,height=720';
    const values=[screen.availLeft,screen.availTop,screen.availWidth,screen.availHeight];
    if(!values.every(Number.isFinite) || screen.availWidth<=0 || screen.availHeight<=0) throw new Error('Invalid display geometry');
    return `popup=yes,left=${Math.round(screen.availLeft)},top=${Math.round(screen.availTop)},width=${Math.round(screen.availWidth)},height=${Math.round(screen.availHeight)}`;
  }
  function openOutput(url,key,screens,open){
    const screen=key?screens.find(s=>screenKey(s)===key):null;
    if(key && !screen) throw new Error('Selected display is no longer connected. Choose a display again.');
    const popup=open(url,'_blank',windowFeatures(screen));
    if(!popup) throw new Error('Output window was blocked. Allow pop-up windows for this app and try again.');
    // The output stays script-closable without retaining access to the operator.
    popup.opener=null;
    popup.focus();
    return popup;
  }
  function installOutputExit(win,doc,onBlocked){
    let enteredFullscreen=!!doc.fullscreenElement, closing=false;
    function close(){
      if(closing) return;
      closing=true;
      win.close();
      win.setTimeout(()=>{if(!win.closed){closing=false;onBlocked();}},150);
    }
    doc.addEventListener('keydown',event=>{
      if(event.key==='Escape'){event.preventDefault();close();}
    });
    doc.addEventListener('fullscreenchange',()=>{
      if(doc.fullscreenElement) enteredFullscreen=true;
      else if(enteredFullscreen) close();
    });
    close.markFullscreenEntered=()=>{enteredFullscreen=true;};
    return close;
  }
  const api={screenKey,screenLabel,windowFeatures,openOutput,installOutputExit};
  if(typeof module!=='undefined' && module.exports) module.exports=api;
  else root.DsanDisplays=api;
})(globalThis);
