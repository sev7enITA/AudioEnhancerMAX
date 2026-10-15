const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const source = fs.readFileSync('frontend/js/app.js', 'utf8');
function harness() {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, { style: {}, classList: {add(){},remove(){},toggle(){}}, lastChild: {}, innerHTML:'', textContent:'', querySelector(){return {textContent:''}}, setAttribute(){}, removeAttribute(){}, options:[] });
    return elements.get(id);
  };
  const context = vm.createContext({console, URL, URLSearchParams, setTimeout, clearTimeout, setInterval, clearInterval,
    document:{head:{appendChild(){}},createElement(){return {}},addEventListener(){},getElementById:element,querySelector(){return null},querySelectorAll(){return []}},
    window:{addEventListener(){},location:{hostname:'localhost',protocol:'http:',host:'localhost'}},
    fetch:async()=>{throw Error('unexpected request')}});
  vm.runInContext(source+`;globalThis.stateRef=state;`,context);
  vm.runInContext(`stopPlayback=()=>{};showWaveform=()=>{};setReviewWorkflowStage=()=>{};resetReviewDeck=()=>{state.complianceRequestId++};
    startActivity=()=>{};connectProgressWS=()=>{};addActivityStep=()=>{};stopActivity=()=>{};showToast=()=>{};
    buttonIcon=()=>'';setComplianceLoading=()=>{};setComplianceError=()=>{};renderDeliveryCompliance=x=>{globalThis.rendered=x};`,context);
  return context;
}
test('starting a failed job removes the prior downloadable result', async()=>{
  const c=harness(); Object.assign(c.stateRef,{fileId:'one',hasProcessed:true,processedRevision:'old',processedUrl:'/old.wav'});
  let destroyed=false;c.stateRef.wavesurferProcessed={destroy(){destroyed=true}};
  c.fetch=async()=>({ok:false,json:async()=>({detail:'interrupted'})});
  await c.startProcessing();
  assert.equal(c.stateRef.hasProcessed,false);assert.equal(c.stateRef.processedRevision,null);assert.equal(destroyed,true);assert.equal(c.stateRef.isProcessing,false);
});
test('an old compliance response cannot replace new-revision evidence', async()=>{
  const c=harness();Object.assign(c.stateRef,{fileId:'one',hasProcessed:true,processedRevision:'old'});
  let finish;c.fetch=()=>new Promise(resolve=>{finish=resolve});
  const pending=c.loadDeliveryCompliance();c.stateRef.processedRevision='new';
  finish({ok:true,json:async()=>({revision:'old'})});await pending;assert.equal(c.rendered,undefined);
});
test('download is unavailable while processing and without a completed result', async()=>{
  const c=harness();Object.assign(c.stateRef,{fileId:'one',hasProcessed:true,processedRevision:'old',isProcessing:true});
  await c.downloadFile('mp3');c.stateRef.isProcessing=false;c.stateRef.hasProcessed=false;await c.downloadFile('wav');
});
test('a completed response for a replaced file is discarded', async()=>{
  const c=harness();Object.assign(c.stateRef,{fileId:'one'});let finish;
  c.fetch=()=>new Promise(resolve=>{finish=resolve});const pending=c.startProcessing();c.stateRef.fileId='two';
  finish({ok:true,json:async()=>({revision:'old',format:'wav',output_url:'/old.wav'})});await pending;
  assert.equal(c.stateRef.hasProcessed,false);assert.equal(c.stateRef.processedUrl,null);
});
