const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const source = fs.readFileSync('frontend/js/app.js', 'utf8');
function harness() {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, { style: {}, classList: {add(){},remove(){},toggle(){}}, lastChild: {}, innerHTML:'', textContent:'', querySelector(){return {textContent:''}}, querySelectorAll(){return []}, setAttribute(){}, removeAttribute(){}, options:[], selectedOptions:[] });
    return elements.get(id);
  };
  element('report-modal').hidden = true;
  const context = vm.createContext({console, URL, URLSearchParams, AbortController, setTimeout, clearTimeout, setInterval, clearInterval,
    document:{head:{appendChild(){}},createElement(){return {}},addEventListener(){},getElementById:element,querySelector(){return null},querySelectorAll(){return []}},
    window:{addEventListener(){},location:{hostname:'localhost',protocol:'http:',host:'localhost'}},
    fetch:async()=>{throw Error('unexpected request')}});
  vm.runInContext(source+`;globalThis.stateRef=state;globalThis.optionsRef=options;`,context);
  vm.runInContext(`stopPlayback=()=>{};showWaveform=()=>{};setReviewWorkflowStage=()=>{};resetReviewDeck=()=>{state.complianceRequestId++};
    startActivity=()=>{};connectProgressWS=()=>{};addActivityStep=()=>{};stopActivity=()=>{};showToast=()=>{};
    buttonIcon=()=>'';setComplianceLoading=()=>{};setComplianceError=()=>{};renderDeliveryCompliance=x=>{globalThis.rendered=x};`,context);
  return context;
}
test('starting a failed job removes the prior downloadable result', async()=>{
  const c=harness(); Object.assign(c.stateRef,{fileId:'one',hasProcessed:true,processedRevision:'old',processedUrl:'/old.wav'});
  c.optionsRef.normalize = true;
  let destroyed=false;c.stateRef.wavesurferProcessed={destroy(){destroyed=true}};
  c.fetch=async()=>({ok:false,json:async()=>({detail:'interrupted'})});
  await c.startProcessing();
  assert.equal(c.stateRef.hasProcessed,false);assert.equal(c.stateRef.processedRevision,null);assert.equal(destroyed,true);assert.equal(c.stateRef.isProcessing,false);
  assert.equal(c.stateRef.workspaceRun.phase, 'failed');
  assert.equal(c.document.getElementById('progress-current-step').textContent, '');
});
test('a source with no selected processing choices does not submit a render', async () => {
  const c = harness();
  c.stateRef.fileId = 'one';
  c.fetch = async () => assert.fail('a render needs an explicit treatment or output profile');
  await c.startProcessing();
  assert.equal(c.stateRef.workspaceRun.phase, 'ready');
  assert.equal(c.stateRef.processedRevision, null);
});
test('workspace reset detaches progress from the previous file', () => {
  const c = harness();
  const progress = c.document.getElementById('progress-current-step');
  progress.textContent = 'Complete!';
  let stopped = false;
  const connection = {onmessage() {}, close() { stopped = true; }};
  c.stateRef.wsConnection = connection;
  c.clearWorkspaceProgress();
  assert.equal(connection.onmessage, null);
  assert.equal(stopped, true);
  assert.equal(c.stateRef.wsConnection, null);
  assert.equal(progress.textContent, '');
  assert.equal(c.document.getElementById('progress-percent').textContent, '0%');
});
test('an old compliance response cannot replace new-revision evidence', async()=>{
  const c=harness();Object.assign(c.stateRef,{fileId:'one',hasProcessed:true,processedRevision:'old'});
  let finish;c.fetch=()=>new Promise(resolve=>{finish=resolve});
  const pending=c.loadDeliveryCompliance();c.stateRef.processedRevision='new';
  finish({ok:true,json:async()=>({revision:'old'})});await pending;assert.equal(c.rendered,undefined);
});
test('a late report cannot open for the previous file or revision', async () => {
  const c = harness();
  const modal = c.document.getElementById('report-modal');
  modal.hidden = true;
  Object.assign(c.stateRef, {fileId: 'one', processingReportUrl: '/api/reports/one?revision=old'});
  let finish;
  c.fetch = () => new Promise(resolve => { finish = resolve; });
  const pending = c.openProcessingReport();

  c.stateRef.processingReportUrl = '/api/reports/one?revision=new';
  finish({ok: true, json: async () => ({revision: 'old'})});
  await pending;
  assert.equal(modal.hidden, true);
  assert.equal(c.stateRef.currentReport, null);
});
test('download is unavailable while processing and without a completed result', async()=>{
  const c=harness();Object.assign(c.stateRef,{fileId:'one',hasProcessed:true,processedRevision:'old',isProcessing:true});
  await c.downloadFile('mp3');c.stateRef.isProcessing=false;c.stateRef.hasProcessed=false;await c.downloadFile('wav');
});
test('a completed response for a replaced file is discarded', async()=>{
  const c=harness();Object.assign(c.stateRef,{fileId:'one'});let finish;
  c.optionsRef.normalize = true;
  c.fetch=()=>new Promise(resolve=>{finish=resolve});const pending=c.startProcessing();c.stateRef.fileId='two';
  finish({ok:true,json:async()=>({revision:'old',format:'wav',output_url:'/old.wav'})});await pending;
  assert.equal(c.stateRef.hasProcessed,false);assert.equal(c.stateRef.processedUrl,null);
});

test('replacing a source isolates late speech analysis results, errors and progress', async () => {
  for (const success of [true, false]) {
    const c = harness();
    c.stateRef.fileId = 'old';
    c.document.getElementById('speech-editor-fillers').value = '';
    const notice = c.document.getElementById('speech-analysis-status');
    const button = c.document.getElementById('btn-speech-editor-analyze');
    const toasts = [];
    const pending = [];
    c.showToast = (_, message) => toasts.push(message);
    c.fetch = (_, options) => new Promise(resolve => pending.push({resolve, signal: options.signal}));

    const oldAnalysis = c.runSpeechEditor();
    assert.equal(notice.hidden, false);
    c.clearSpeechAnalysis();
    assert.equal(pending[0].signal.aborted, true);
    c.stateRef.fileId = 'new';
    const newAnalysis = c.runSpeechEditor();

    pending[0].resolve(success
      ? {ok: true, json: async () => ({file_id: 'old', summary: {total_candidates: 2}})}
      : {ok: false, json: async () => ({detail: 'stale error'})});
    await oldAnalysis;
    assert.equal(c.stateRef.speechEdl, null);
    assert.deepEqual(toasts, []);
    assert.equal(notice.hidden, false);
    assert.equal(button.disabled, true);

    pending[1].resolve({ok: false, json: async () => ({detail: 'current error'})});
    await newAnalysis;
    assert.deepEqual(toasts, ['current error']);
    assert.equal(notice.hidden, true);
    assert.equal(button.disabled, false);
  }
});

test('unreadable privacy preferences disable controls and explain how to recover', async()=>{
  const c=harness();
  const safe={external_services_allowed:false,ollama_editorial_allowed:false,trusted_lan_processing_allowed:false,
    status:'invalid',warning:'Saved privacy preferences could not be read. Review and save your choices.'};
  let toast;c.showToast=(level,text)=>{toast={level,text}};
  c.fetch=async()=>({ok:true,json:async()=>safe});
  await c.loadRuntimePrivacySettings();
  assert.equal(c.document.getElementById('setting-external-services').checked,false);
  assert.equal(c.document.getElementById('setting-ollama-editorial').checked,false);
  assert.equal(c.document.getElementById('setting-offload-dsp').disabled,true);
  assert.equal(c.document.getElementById('privacy-settings-status').textContent,safe.warning);
  assert.deepEqual(toast,{level:'warning',text:safe.warning});
  c.document.getElementById('setting-ollama-editorial').checked=true;
  c.fetch=async(url,options)=>({ok:true,json:async()=>JSON.parse(options.body)});
  await c.saveRuntimePrivacySettings();
  assert.equal(c.stateRef.runtimePrivacy.ollama_editorial_allowed,true);
  assert.equal(c.stateRef.runtimePrivacy.external_services_allowed,false);
  assert.match(c.document.getElementById('privacy-settings-status').textContent,/Saved locally/);
});
