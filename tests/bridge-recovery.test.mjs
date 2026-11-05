import test from 'node:test';
import assert from 'node:assert/strict';
import {createHmac} from 'node:crypto';
import {createSettingsController,decodeSettings} from '../codex_source/payload/game/bin/x64/plugins/cyber_engine_tweaks/mods/AiNpcCodexBridge/bridge.mjs';

const saved={model:2,reasoning:1},selected=decodeSettings(saved),manual=decodeSettings({model:3,reasoning:1});
const response=value=>({ok:true,status:200,text:async()=>JSON.stringify(value)});
const defer=()=>{let resolve;const promise=new Promise(r=>resolve=r);return{promise,resolve};};
function fixture({available=true,ensure,request:customRequest}={}){
 const calls=[],statuses=[],timers=new Map();let clock=0,nextTimer=0,starts=0,selection={...manual},identity={status:'ok',service:'codex-companion-bridge',version:1,auth_mode:'chatgpt',local_auth:'bearer-v1'};
 const request=async(url,options={})=>{
  calls.push({url,method:options.method??'GET',body:options.body&&JSON.parse(options.body)});
  if(customRequest){const result=await customRequest(url,options,calls.length);if(result!==undefined)return result;}
  if(!available)throw Error('connection refused');
  if(url.endsWith('/healthz'))return response({...identity,...selection,local_auth_proof:createHmac('sha256','a'.repeat(64)).update('AiNpcCodexBridge/bearer-v1\n17865\n'+options.headers['X-AiNpc-Challenge']).digest('hex')});
  if(options.method==='POST')selection=JSON.parse(options.body);
  return response({status:'ok',...selection});
 };
 const controller=createSettingsController({request,connectionFor:async()=>({origin:'http://127.0.0.1:17865',token:'a'.repeat(64),configuredModel:'codex-default'}),persist:async s=>statuses.push(s),autoStart:{ensure:async()=>{starts++;if(ensure)return ensure();throw Error('startup failed');}},
  setTimer:(fn,ms)=>{const id={id:++nextTimer,unref(){}};timers.set(id,{fn,ms});return id;},clearTimer:id=>timers.delete(id)});
 return{controller,calls,statuses,timers,get starts(){return starts;},setAvailable:v=>available=v,setSelection:v=>selection={...v},setIdentity:v=>identity={...identity,...v},
  async activate(values={}){assert.equal(controller.activate({settings:()=>values}),undefined);await controller.whenIdle();},
  async tick(){assert.equal(timers.size,1);const [id,timer]=[...timers][0];timers.delete(id);clock+=timer.ms;timer.fn();await controller.whenIdle();},
  posts:()=>calls.filter(c=>c.method==='POST'),healthCalls:()=>calls.filter(c=>c.url.endsWith('/healthz'))};
}

test('a healthy manually started backend is borrowed without automatic startup or unsaved selection changes',async()=>{
 const f=fixture();await f.activate();assert.equal(f.starts,0);assert.equal(f.posts().length,0);assert.equal(f.statuses.at(-1).state,'ready');assert.equal(f.statuses.at(-1).model,manual.model);
 const controlCalls=f.calls.filter(c=>c.url.endsWith('/codex/settings')).length;
 for(let i=0;i<4;i++)await f.tick();
 assert.equal(f.starts,0);assert.equal(f.posts().length,0);assert.equal(f.calls.filter(c=>c.url.endsWith('/codex/settings')).length,controlCalls);assert.equal(f.healthCalls().length,6);assert.equal([...f.timers.values()][0].ms,30000);
 f.controller.close();assert.equal(f.timers.size,0);
});

test('an initial unavailable error retries by health alone and applies the cached selection after recovery',async()=>{
 const f=fixture({available:false});await f.activate(saved);assert.equal(f.starts,0);assert.equal(f.statuses.at(-1).state,'idle');
 f.setAvailable(true);await f.tick();assert.equal(f.starts,0);assert.deepEqual(f.posts().at(-1).body,selected);assert.equal(f.statuses.at(-1).state,'applied');
 const writes=f.posts().length;await f.tick();await f.tick();assert.equal(f.posts().length,writes);assert.equal(f.starts,0);f.controller.close();
});

test('recovery with no saved selection preserves the manually selected backend model',async()=>{
 const f=fixture({available:false});await f.activate();f.setAvailable(true);await f.tick();
 assert.equal(f.posts().length,0);assert.equal(f.statuses.at(-1).model,manual.model);assert.equal(f.statuses.at(-1).state,'ready');f.controller.close();
});

test('a later backend restart is detected and the saved selection is reapplied without a launcher',async()=>{
 const f=fixture();await f.activate(saved);assert.equal(f.posts().length,1);f.setSelection(manual);await f.tick();
 assert.equal(f.posts().length,2);assert.deepEqual(f.posts().at(-1).body,selected);assert.equal(f.starts,0);f.controller.close();
});

test('an incompatible service is neither adopted nor sent settings and may recover on a later health poll',async()=>{
 const f=fixture();f.setIdentity({service:'other-server'});await f.activate(saved);
 assert.equal(f.starts,0);assert.equal(f.posts().length,0);assert.equal(f.statuses.at(-1).errorCode,'invalid_bridge_response');
 f.setIdentity({service:'codex-companion-bridge'});await f.tick();assert.equal(f.posts().length,1);assert.equal(f.starts,0);f.controller.close();
});

test('asynchronous checks stay single-flight and a newer settings change supersedes an old unapplied selection',async()=>{
 const entered=defer(),release=defer();let inFlight=0,maxInFlight=0;
 const f=fixture({request:async(url,options,n)=>{inFlight++;maxInFlight=Math.max(maxInFlight,inFlight);try{if(n===1){entered.resolve();await release.promise;}}finally{inFlight--;}}});
 f.controller.activate({settings:()=>saved});await entered.promise;
 const newer={model:3,reasoning:1};assert.equal(f.controller.onSettings(newer),undefined);assert.equal(f.timers.size,0);release.resolve();await f.controller.whenIdle();
 assert.equal(maxInFlight,1);assert.deepEqual(f.posts().map(c=>c.body),[decodeSettings(newer)]);assert.equal(f.timers.size,1);f.controller.close();
});

test('closing during a health check suppresses late writes, settings changes and new timers',async()=>{
 const entered=defer(),release=defer();const f=fixture({request:async(_url,_options,n)=>{if(n===1){entered.resolve();await release.promise;}}});
 f.controller.activate({settings:()=>saved});await entered.promise;f.controller.close();release.resolve();await f.controller.whenIdle();
 assert.equal(f.posts().length,0);assert.equal(f.statuses.length,0);assert.equal(f.starts,0);assert.equal(f.timers.size,0);
});

test('unchanged settings do not schedule more work while the periodic monitor stays bounded',async()=>{
 const f=fixture();await f.activate(saved);const count=f.calls.length;
 for(let i=0;i<10;i++)f.controller.onSettings({...saved});await f.controller.whenIdle();assert.equal(f.calls.length,count);assert.equal(f.timers.size,1);f.controller.close();
});
