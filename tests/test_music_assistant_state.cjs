const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const source = fs.readFileSync('frontend/js/music-assistant.js', 'utf8');
const html = fs.readFileSync('frontend/index.html', 'utf8');
const preset = {
  id: 'podcast_intro', name: 'Podcast intro', description: 'An original starting point.',
  defaults: {style:'Ambient',secondary_style:'',instrumental:true,bpm:90,duration_seconds:20,instruments:'Piano',exclusions:'Drums',
    sections:[{name:'Intro',direction:'Start softly'},{name:'Main',direction:'Develop gently'},{name:'Outro',direction:'Leave room'}]}
};
function element(id) {
  let value='';
  return {id, get value(){return value}, set value(next){value=String(next)},textContent:'',dataset:{},hidden:false,disabled:false,
    listeners:{},children:[],attributes:{}, set innerHTML(_){throw Error('Unsafe HTML assignment')},
    addEventListener(type,fn){this.listeners[type]=fn},setAttribute(key,value){this.attributes[key]=value},
    replaceChildren(){this.children=[]},appendChild(child){this.children.push(child)},
    reportValidity(){return true},focus(){this.focused=true},setSelectionRange(start,end){this.selectionStart=start;this.selectionEnd=end},
    scrollIntoView(options){this.scrollOptions=options},select(){this.selected=true},click(){this.clicked=true},remove(){this.removed=true}};
}
function harness() {
  const elements=new Map([...html.matchAll(/id="(music-[^"]+)"/g)].map(match=>[match[1],element(match[1])]));
  elements.set('setting-ollama-editorial',element('setting-ollama-editorial'));
  const context=vm.createContext({console,URL,Blob,setTimeout,clearTimeout,
    navigator:{clipboard:{writeText:async()=>{}}},
    state:{runtimePrivacy:{ollama_editorial_allowed:true}},
    switchPanel:panel=>{context.currentPanel=panel},
    readApiError:async response=>response.detail||'Failed request',
    document:{getElementById:id=>elements.get(id)||null,createElement:tag=>element(tag),body:{appendChild(){}},querySelector:()=>null},
    fetch:async()=>{throw Error('Unexpected request')}});
  vm.runInContext(source+';globalThis.musicState=musicAssistantState;',context);
  context.musicState.initialized=true;
  context.musicState.presets=[preset];
  const el=id=>elements.get(`music-${id}`);
  el('preset').value='podcast_intro';
  context.musicApplyPreset();
  el('description').value='Warm music beneath a story';
  context.musicRevise(true);
  return {c:context,s:context.musicState,el};
}
const ok=data=>({ok:true,json:async()=>data});
const plain=value=>JSON.parse(JSON.stringify(value));
function builtResult(brief) {return {caption:'Original structured prompt',lyrics:brief.lyrics,brief:plain(brief),engine:'structured-local',text_only:true,schema_version:1,warnings:[]};}
async function build(h) {
  h.c.fetch=async()=>ok(builtResult(h.c.musicReadBrief()));
  await h.c.musicBuild();
}
function deferred(){let resolve;const promise=new Promise(done=>resolve=done);return {promise,resolve};}

test('build makes one local request and export preserves edited caption, original caption and exact lyrics',async()=>{
  const h=harness();h.el('lyrics').value='  Keep my words\n\n[Chorus]\n<unaltered>  ';
  let request;
  h.c.fetch=async(url,options)=>{request={url,body:JSON.parse(options.body)};return ok(builtResult(request.body))};
  await h.c.musicBuild();
  assert.equal(request.url,'/api/music/brief');
  assert.equal(request.body.lyrics,h.el('lyrics').value);
  h.el('caption').value='My edited prompt';h.c.musicRevise(false);
  const exported=h.c.musicExportData();
  assert.equal(exported.caption,'My edited prompt');
  assert.equal(exported.original_caption,'Original structured prompt');
  assert.equal(exported.lyrics,h.el('lyrics').value);
  assert.equal(exported.text_only,true);
  assert.equal(exported.engine,'structured-local');
  assert.equal(exported.suggestions_applied,false);
});

test('a new build starts review at the beginning of the focused prompt',async()=>{
  const h=harness();h.el('caption').scrollTop=300;h.el('caption').selectionStart=80;h.el('caption').selectionEnd=80;
  await build(h);
  assert.equal(h.el('caption').focused,true);
  assert.equal(h.el('caption').selectionStart,0);assert.equal(h.el('caption').selectionEnd,0);
  assert.equal(h.el('caption').scrollTop,0);
});

test('Settings handoff focuses and reveals the local permission without changing or saving it',()=>{
  const h=harness();const control=h.c.document.getElementById('setting-ollama-editorial');control.checked=false;
  h.c.musicOpenSettings();
  assert.equal(h.c.currentPanel,'settings-panel');assert.equal(control.focused,true);
  assert.equal(control.scrollOptions.block,'center');assert.equal(control.checked,false);
  assert.equal(h.c.state.runtimePrivacy.ollama_editorial_allowed,true);
});

test('a late build cannot overwrite a prompt edited while the request is pending',async()=>{
  const h=harness();await build(h);const request=deferred();h.c.fetch=()=>request.promise;
  const pending=h.c.musicBuild();
  h.el('caption').value='Keep this draft';h.c.musicRevise(false);
  request.resolve(ok(builtResult(h.c.musicReadBrief())));await pending;
  assert.equal(h.el('caption').value,'Keep this draft');
  assert.equal(h.s.building,false);
});

test('changed form keeps its previous prompt but requires rebuild for export and refinements',async()=>{
  const h=harness();await build(h);h.el('duration').value='30';h.c.musicRevise(true);
  assert.equal(h.el('caption').value,'Original structured prompt');
  assert.equal(h.el('export').disabled,true);
  assert.equal(h.el('refine').disabled,true);
  assert.equal(h.c.musicExportData(),null);
  h.c.fetch=async()=>{throw Error('Must not request refinements from a stale form')};
  await h.c.musicRefine();
});

test('form edits during first build discard its stale response',async()=>{
  const h=harness();const request=deferred();const response=builtResult(h.c.musicReadBrief());h.c.fetch=()=>request.promise;
  const pending=h.c.musicBuild();h.el('instruments').value='Guitar';h.c.musicRevise(true);
  request.resolve(ok(response));await pending;
  assert.equal(h.s.built,null);assert.equal(h.el('caption').value,'');
  assert.match(h.el('status').textContent,/changed during the build/);
});

test('late model suggestions cannot become appendable after prompt changes',async()=>{
  const h=harness();await build(h);const request=deferred();h.c.fetch=()=>request.promise;
  const pending=h.c.musicRefine();h.el('caption').value='New user draft';h.c.musicRevise(false);
  request.resolve(ok({suggestions:'Outdated advice',model:'local',engine:'ollama-local'}));await pending;
  assert.equal(h.s.suggestion,null);assert.equal(h.el('append').disabled,true);assert.equal(h.el('suggestions').hidden,true);
  h.c.musicAppendSuggestions();assert.equal(h.el('caption').value,'New user draft');
});

test('revoking and re-enabling privacy does not revive a previous model response',async()=>{
  const h=harness();await build(h);h.c.refreshMusicAssistantPrivacy();const request=deferred();h.c.fetch=()=>request.promise;
  const pending=h.c.musicRefine();h.c.state.runtimePrivacy.ollama_editorial_allowed=false;h.c.refreshMusicAssistantPrivacy();
  assert.equal(h.el('refine').disabled,true);
  h.c.state.runtimePrivacy.ollama_editorial_allowed=true;h.c.refreshMusicAssistantPrivacy();
  request.resolve(ok({suggestions:'Expired advice',model:'local'}));await pending;
  assert.equal(h.s.suggestion,null);assert.equal(h.el('suggestions').hidden,true);
});

test('unknown privacy prevents requests, while deterministic building remains available',async()=>{
  const h=harness();await build(h);h.c.state.runtimePrivacy=null;h.c.refreshMusicAssistantPrivacy();
  assert.equal(h.el('refine').disabled,true);assert.equal(h.el('build').disabled,false);
  h.c.fetch=async()=>{throw Error('Must not contact a model without permission')};await h.c.musicRefine();
});

test('previewing presets changes no draft and explicit apply preserves description, lyrics and prompt',async()=>{
  const h=harness();await build(h);h.el('lyrics').value='Preserve this\n';h.el('style').value='My style';
  const before=plain(h.c.musicReadBrief());h.c.musicPreviewPreset();
  assert.deepEqual(plain(h.c.musicReadBrief()),before);
  h.c.musicApplyPreset();
  assert.equal(h.el('style').value,'Ambient');assert.equal(h.el('description').value,before.description);
  assert.equal(h.el('lyrics').value,before.lyrics);assert.equal(h.el('caption').value,'Original structured prompt');
  assert.equal(h.el('export').disabled,true);
});

test('suggestions remain plain text until explicit append and provenance records the local model',async()=>{
  const h=harness();await build(h);const text='<img src=x onerror=alert(1)>\nReview this';
  h.c.fetch=async()=>ok({suggestions:text,model:'gemma-local',engine:'ollama-local'});await h.c.musicRefine();
  assert.equal(h.el('suggestion-text').textContent,text);assert.equal(h.el('caption').value,'Original structured prompt');
  h.c.musicAppendSuggestions();
  assert.equal(h.el('caption').value,'Original structured prompt\n\n'+text);
  const exported=h.c.musicExportData();assert.equal(exported.model,'gemma-local');assert.equal(exported.suggestions_applied,true);
  assert.equal(exported.original_caption,'Original structured prompt');assert.equal(exported.applied_suggestions[0].suggestions,text);
  assert.equal(h.el('append').disabled,true);
});

test('model errors preserve the prompt and re-enable retries',async()=>{
  const h=harness();await build(h);h.c.fetch=async()=>({ok:false,detail:'No local model is available.'});
  await h.c.musicRefine();assert.equal(h.el('caption').value,'Original structured prompt');
  assert.match(h.el('status').textContent,/No local model/);assert.equal(h.el('refine').disabled,false);
});

test('rejected clipboard write selects text and explains manual copying',async()=>{
  const h=harness();await build(h);h.c.navigator.clipboard.writeText=async()=>{throw Error('Denied')};
  await h.c.musicCopy();assert.equal(h.el('caption').selected,true);assert.match(h.el('status').textContent,/keyboard/);
});

test('slow preset loading cannot erase directions already typed',async()=>{
  const h=harness();h.s.formRevision=0;h.s.presets=[];const request=deferred();h.c.fetch=()=>request.promise;
  const pending=h.c.musicLoadPresets();h.el('style').value='User style while loading';h.c.musicRevise(true);
  request.resolve(ok({presets:[preset]}));await pending;
  assert.equal(h.el('style').value,'User style while loading');assert.equal(h.el('build').disabled,false);
});
