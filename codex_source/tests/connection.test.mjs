import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, writeFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {createHmac} from 'node:crypto';
import {readConnection, remapCodexUrl, codexRequestOptions, verifyConnection} from '../payload/game/bin/x64/plugins/cyber_engine_tweaks/mods/AiNpcCodexBridge/codex-connection.mjs';
import {createSettingsController, decodeSettings} from '../payload/game/bin/x64/plugins/cyber_engine_tweaks/mods/AiNpcCodexBridge/bridge.mjs';

const connection = {origin:'http://127.0.0.1:22881', baseUrl:'http://127.0.0.1:22881/v1', token:'e'.repeat(64), configuredModel:'portable-test-model'};
test('private config selects port and model; only local token file is read', async () => {
  const directory = await mkdtemp(path.join(tmpdir(), 'codex-transport-'));
  try {
    await writeFile(path.join(directory, 'config.json'), JSON.stringify({host:'127.0.0.1', port:22881, model:'portable-test-model'}));
    await writeFile(path.join(directory, 'local-token.json'), JSON.stringify({schema:1,token:connection.token}));
    assert.deepEqual(await readConnection({stateDirectory:directory}), connection);
    await writeFile(path.join(directory,'config.json'), JSON.stringify({host:'attacker.example',port:22881}));
    await assert.rejects(readConnection({stateDirectory:directory}), /invalid local bridge configuration/);
  } finally { await rm(directory,{recursive:true,force:true}); }
});
test('Bearer never leaves exact Codex origin or known path, and redirect is blocked', () => {
  const good = connection.origin + '/v1/chat/completions';
  const options = codexRequestOptions(good, {method:'POST'}, connection);
  assert.equal(options.headers.get('Authorization'), 'Bearer '+connection.token);
  assert.equal(options.redirect, 'error');
  for(const url of ['https://example.com/v1/chat/completions','http://localhost:22881/v1/chat/completions',connection.origin+'/unrelated',good+'?relay=1',good+'#hash','http://u:p@127.0.0.1:22881/v1/chat/completions','http://127.0.0.1:9999/v1/chat/completions']) {
    const input = {method:'POST'};
    assert.equal(codexRequestOptions(url,input,connection),input,url);
  }
  assert.equal(codexRequestOptions(good,{headers:{Authorization:'Bearer explicit'}},connection).headers.get('Authorization'),'Bearer explicit');
  assert.equal(remapCodexUrl('http://127.0.0.1:17865/v1/chat/completions',connection),good);
  assert.equal(remapCodexUrl('http://127.0.0.1:9999/v1/chat/completions',connection),'http://127.0.0.1:9999/v1/chat/completions');
});
test('missing fields use portable defaults; legacy indices and invalid effort remain explicit',()=>{
  assert.deepEqual(decodeSettings(),{model:'codex-default',reasoningEffort:'auto'});
  assert.deepEqual(decodeSettings({model:4,reasoning:2}),{model:'gpt-6.1-terra',reasoningEffort:'medium'});
  assert.deepEqual(decodeSettings({model:12,reasoning:7},connection),{model:'portable-test-model',reasoningEffort:'auto'});
  assert.throws(()=>decodeSettings({model:6,reasoning:6}),/model or effort unsupported/);
  assert.throws(()=>decodeSettings({model:12}, {configuredModel:'bad; shell'}),/invalid local bridge configuration/);
});
function fixture(response, values={}) {
  const persisted=[],calls=[];
  let ensured=0;
  const controller=createSettingsController({connectionFor:async()=>connection,autoStart:{ensure:async()=>{ensured++;}},
    request:async(url,opts)=>{calls.push({url,opts});const value=await response(url,opts);if(url.endsWith('/healthz') && value.local_auth==='bearer-v1') value.local_auth_proof=proof(opts.headers['X-AiNpc-Challenge']);return Response.json(value);},
    persist:async v=>persisted.push(v),setTimer:()=>({unref(){}}),clearTimer:()=>{}});
  controller.activate({settings:()=>values,log:()=>{}});
  return {controller,persisted,calls,ensured:()=>ensured};
}
const secureHealth={status:'ok',service:'codex-companion-bridge',version:1,auth_mode:'chatgpt',local_auth:'bearer-v1',model:'portable-test-model',reasoningEffort:'auto',instruction_home:'dedicated'};
const proof=(nonce,port='22881')=>createHmac('sha256',connection.token).update(`AiNpcCodexBridge/bearer-v1\n${port}\n${nonce}`).digest('hex');
test('settings use configured port and token, custom model works without fixed catalog',async()=>{
  const f=fixture(async(url,opts)=> url.endsWith('/healthz') ? secureHealth : {status:'ok',...JSON.parse(opts.body)}, {model:12,reasoning:7});
  await f.controller.whenIdle();f.controller.close();
  assert.equal(f.persisted.at(-1).state,'applied');
  assert.equal(f.calls.length,3);
  assert.equal(f.calls[2].url,connection.origin+'/codex/settings');
  assert.equal(f.calls[2].opts.headers.get('Authorization'),'Bearer '+connection.token);
  assert.notEqual(f.calls[0].opts.headers['X-AiNpc-Challenge'],f.calls[1].opts.headers['X-AiNpc-Challenge']);
  assert.equal(f.ensured(),0);
});
test('legacy unauthenticated server is not borrowed or started/stopped',async()=>{
  const f=fixture(async()=>({...secureHealth,local_auth:undefined}));
  await f.controller.whenIdle();f.controller.close();
  assert.equal(f.persisted.at(-1).errorCode,'old_bridge_restart_required');
  assert.equal(f.calls.length,1);assert.equal(f.ensured(),0);
});
test('legacy shared-home warning persists without changing unsaved model',async()=>{
  const f=fixture(async url=>url.endsWith('/healthz') ? {...secureHealth,instruction_home:'legacy-shared'} : {status:'ok',model:'portable-test-model',reasoningEffort:'auto'});
  await f.controller.whenIdle();f.controller.close();
  assert.equal(f.persisted.at(-1).warning,'legacy_shared_codex_home');
  assert.equal(f.calls[2].opts.method,'GET');
});
test('proof is fresh, port-bound and never sends the local credential to a spoofed service',async()=>{
  const nonces=[];
  const request=async(url,opts)=>{assert.equal(new Headers(opts.headers).has('Authorization'),false);nonces.push(opts.headers['X-AiNpc-Challenge']);return Response.json({...secureHealth,local_auth_proof:proof(nonces.at(-1))});};
  await verifyConnection(connection,{request});await verifyConnection(connection,{request});
  assert.notEqual(nonces[0],nonces[1]);
  for(const value of [undefined,'0'.repeat(64),proof('a'.repeat(64)),proof('a'.repeat(64),'17865')]) {
    await assert.rejects(verifyConnection(connection,{request:async(url,opts)=>{assert.equal(new Headers(opts.headers).has('Authorization'),false);return Response.json({...secureHealth,local_auth_proof:value});}}),/local bridge proof rejected/);
  }
});
test('installing the addon with another provider never starts Codex until explicit setting action',async()=>{
  let ensured=0;const rows=[];
  const c=createSettingsController({connectionFor:async()=>connection,autoStart:{ensure:async()=>{ensured++;throw Error('fixture no CLI');}},
    request:async()=>{throw Error('fixture connection refused');},persist:async v=>rows.push(v),setTimer:()=>({unref(){}}),clearTimer:()=>{}});
  c.activate({settings:()=>({}),log:()=>{}});await c.whenIdle();
  assert.equal(ensured,0);assert.equal(rows.at(-1).state,'idle');
  c.onSettings({model:11,reasoning:7});await c.whenIdle();c.close();
  assert.equal(ensured,1);assert.equal(rows.at(-1).errorCode,'bridge_unavailable');
});
