import test from 'node:test';
import assert from 'node:assert/strict';
import {codexTransport} from '../overrides/codex/app/bridge/codex-transport.mjs';
import {codexRequestOptions, remapCodexUrl} from '../codex_source/payload/game/bin/x64/plugins/cyber_engine_tweaks/mods/AiNpcCodexBridge/codex-connection.mjs';

const connection = {origin: 'http://127.0.0.1:19876', baseUrl: 'http://127.0.0.1:19876/v1', token: 'a'.repeat(64)};
const fixture = () => {
  const calls = [], events=[];let reads = 0;
  const fetch = async (url, options) => {events.push('fetch');calls.push({url, options});return 'response';};
  const verifyConnection=async current=>{assert.equal(current.token,connection.token);events.push('proof');return {status:'ok'};};
  const load = async () => ({readConnection: async () => {reads++;return connection;}, remapCodexUrl, codexRequestOptions, verifyConnection});
  return {calls, events, verifyConnection, get reads() {return reads;}, fetch, load};
};
test('actual helper adds the per-user local token after configured-port remap, on every call', async () => {
  const f = fixture(), send = codexTransport(f.fetch, 'custom', {load: f.load});
  const options = {method: 'POST', headers: {'Content-Type':'application/json'}, body:'fixture', signal: new AbortController().signal};
  assert.equal(await send('http://127.0.0.1:17865/v1/chat/completions', options),'response');
  assert.equal(f.calls[0].url, connection.origin + '/v1/chat/completions');
  assert.equal(f.calls[0].options.headers.get('Authorization'), 'Bearer ' + connection.token);
  assert.equal(f.calls[0].options.redirect, 'error');assert.equal(f.calls[0].options.signal, options.signal);
  assert.equal(options.headers.Authorization,undefined);
  await send(connection.origin + '/v1/chat/completions', options);assert.equal(f.reads,2);
  assert.deepEqual(f.events,['proof','fetch','proof','fetch']);
});
test('external endpoints, userinfo, query, fragments and unrelated providers never read or receive the local token', async () => {
  const f=fixture(), options={headers:{Authorization:'Bearer <EXAMPLE_ONLY>'}};
  for(const url of ['https://example.com/v1/chat/completions','http://localhost:17865/v1/chat/completions',
    'http://127.0.0.1:17865/v1/chat/completions?key=x','http://127.0.0.1:17865/v1/chat/completions#x',
    'http://user@127.0.0.1:17865/v1/chat/completions','http://127.0.0.1:17865/unrelated']) {
    await codexTransport(f.fetch,'custom',{load:f.load})(url,options);assert.equal(f.calls.at(-1).options,options);
  }
  await codexTransport(f.fetch,'gemini',{load:f.load})(connection.origin+'/v1/chat/completions',options);
  assert.equal(f.reads,0);
});
test('another loopback port is not remapped or authenticated and explicit local Authorization is preserved', async () => {
  const f=fixture(),send=codexTransport(f.fetch,'custom',{load:f.load});
  const original={headers:{Authorization:'Bearer player-explicit'}};
  await send('http://127.0.0.1:12345/v1/chat/completions',original);
  assert.equal(f.calls[0].url,'http://127.0.0.1:12345/v1/chat/completions');assert.equal(f.calls[0].options,original);
  await send(connection.origin+'/v1/chat/completions',original);
  assert.equal(f.calls[1].options.headers.get('Authorization'),'Bearer player-explicit');
});
test('missing Codex helper or invalid local credential fails before fetch; unrelated ports remain optional', async () => {
  const f=fixture();
  const missing=async()=>{throw Object.assign(Error('missing'),{code:'ERR_MODULE_NOT_FOUND'});};
  await assert.rejects(codexTransport(f.fetch,'custom',{load:missing})('http://127.0.0.1:17865/v1/chat/completions',{}),/reinstall/);
  await codexTransport(f.fetch,'custom',{load:missing})('http://127.0.0.1:12345/v1/chat/completions',{});
  assert.equal(f.calls.length,1);
  const invalid=async()=>({readConnection:async()=>{throw Error('invalid local bridge credential');}});
  await assert.rejects(codexTransport(f.fetch,'custom',{load:invalid})('http://127.0.0.1:17865/v1/chat/completions',{}),/invalid local bridge credential/);
  assert.equal(f.calls.length,1);
});
test('completion starts lazily only when required and rereads the token after startup',async()=>{
 const f=fixture();let ready=false,starts=0;
 const load=async()=>({readConnection:async()=>({...connection,token:ready?connection.token:''}),remapCodexUrl,codexRequestOptions,verifyConnection:f.verifyConnection});
 const start=async()=>({ensure:async()=>{starts++;ready=true;}});
 await codexTransport(f.fetch,'custom',{load,start})('http://127.0.0.1:17865/v1/chat/completions',{});
 assert.equal(starts,1);assert.equal(f.calls[0].options.headers.get('Authorization'),'Bearer '+connection.token);
 await codexTransport(f.fetch,'custom',{load,start})('http://127.0.0.1:17865/healthz',{});
 assert.equal(starts,1);
});
test('listener proof rejection prevents Bearer transmission and never starts or replaces the listener',async()=>{
 const f=fixture();let starts=0;
 const load=async()=>({...await f.load(),verifyConnection:async()=>{throw Object.assign(Error('Codex listener identity mismatch'),{identityMismatch:true});}});
 await assert.rejects(codexTransport(f.fetch,'custom',{load,start:async()=>({ensure:async()=>{starts++;}})})
   ('http://127.0.0.1:17865/v1/chat/completions',{}),{identityMismatch:true});
 assert.equal(f.calls.length,0);assert.equal(starts,0);
});
test('only ECONNREFUSED is retried after lazy startup; HTTP 401 and ambiguous failures are never replayed',async()=>{
 const f=fixture();let starts=0,attempts=0;
 const start=async()=>({ensure:async()=>{starts++;}});
 const refused=async(url,options)=>{if(++attempts===1)throw Object.assign(Error('fetch failed'),{cause:{code:'ECONNREFUSED'}});return f.fetch(url,options);};
 await codexTransport(refused,'custom',{load:f.load,start})('http://127.0.0.1:17865/v1/chat/completions',{});
 assert.equal(starts,1);assert.equal(attempts,2);
 const response=await codexTransport(async()=>({status:401}),'custom',{load:f.load,start})('http://127.0.0.1:17865/v1/chat/completions',{});
 assert.equal(response.status,401);assert.equal(starts,1);
 await assert.rejects(codexTransport(async()=>{throw Error('socket closed after request');},'custom',{load:f.load,start})('http://127.0.0.1:17865/v1/chat/completions',{}));
 assert.equal(starts,1);
});
test('aborted completion does not fetch or wait for a background launcher',async()=>{
 const f=fixture(),controller=new AbortController();let requested=false;
 const load=async()=>({readConnection:async()=>({...connection,token:''}),remapCodexUrl,codexRequestOptions});
 const start=async()=>({ensure:()=>{requested=true;queueMicrotask(()=>controller.abort());return new Promise(()=>{});}});
 await assert.rejects(codexTransport(f.fetch,'custom',{load,start})('http://127.0.0.1:17865/v1/chat/completions',{signal:controller.signal}),{name:'AbortError'});
 assert.equal(requested,true);assert.equal(f.calls.length,0);
});
