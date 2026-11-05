import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {createHmac} from 'node:crypto';
import vm from 'node:vm';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const game = process.argv[2], variant = process.argv[3];
const mapping = JSON.parse(fs.readFileSync(path.join(root, 'source-overrides.json'), 'utf8'));
const sourceRows = variant === 'combined' ? mapping.combinations['codex+japanese'] : mapping.files[variant] ?? [];
const changedModules = sourceRows.filter(row => row.path.includes('/app/') && row.path.endsWith('.mjs')).map(row => row.path.split('/app/')[1]);
const runtime = path.join(game, 'red4ext/plugins/AiNpcCyberpunkMod/app');
if(variant!=='none') {
  const bridge=fs.readFileSync(path.join(runtime,'bridge/convai-bridge.mjs'),'utf8');
  const declaration=bridge.split(/\r?\n/).find(line=>line.startsWith('const game = process.env.CYBERPUNK_CONVAI_GAME || '));
  assert.ok(declaration);
  const inferred=vm.runInNewContext(`(()=>{${declaration}return game;})()`,{process:{env:{}},project:runtime,resolve:path.resolve});
  assert.equal(path.resolve(inferred),path.resolve(game),'fallback must resolve the installed game, independent of store or drive');
  const explicit=path.join(game,'explicit-override');
  assert.equal(vm.runInNewContext(`(()=>{${declaration}return game;})()`,{process:{env:{CYBERPUNK_CONVAI_GAME:explicit}},project:runtime,resolve:path.resolve}),explicit);
}
if (variant === 'none') {
  const restored = await import(pathToFileURL(path.join(runtime, 'bridge/conversation-style.mjs')).href);
  assert.equal(typeof restored.followUpContext, 'function');
  assert.equal(restored.conversationStyleBlock, undefined);
  assert.ok(restored.followUpContext({}).includes('your own call'));
  console.log(JSON.stringify({allPassed: true, variant, originalStyleModuleRestored: true}));
} else {
  let checked = 0;
  if (!process.argv.includes('--skip-syntax')) for (const relative of changedModules) {
    const file = path.join(runtime, relative);
    const result = spawnSync(process.execPath, ['--check', file], {encoding: 'utf8', windowsHide: true});
    assert.equal(result.status, 0, result.stderr);
    checked++;
  }
  const load = name => import(pathToFileURL(path.join(runtime, 'bridge', name)).href);
  const {PersonaBook, systemHead} = await load('mistral-prompt.mjs');
  const {BASE_PROFILE} = await load('prompt-profiles.mjs');
  const {conversationStyleBlock} = await load('conversation-style.mjs');
  const style = await load('conversation-style.mjs');
  assert.equal(typeof style.followUpContext, 'function');
  assert.ok(style.followUpContext({}).includes('your own call'));
  await load('quest-context.mjs');
  const roster = JSON.parse(fs.readFileSync(path.join(runtime, 'characters/roster.json'), 'utf8'));
  const persona = new PersonaBook(roster, {lean: true, topics: true}).persona('jackie-welles');
  assert.equal(persona.known, true);
  const system = systemHead({persona, profile: BASE_PROFILE});
  assert.ok(system.includes(conversationStyleBlock(persona)));
  assert.ok(system.includes(persona.style));
  if (variant === 'codex') {
    assert.equal(fs.existsSync(path.join(runtime, 'bridge/persona-sections.mjs')), false);
    assert.equal(fs.readFileSync(path.join(runtime, 'bridge/mistral-prompt.mjs'), 'utf8').includes("from './context-ja.mjs'"), false);
  }
  if (variant === 'codex' || variant === 'combined') {
    await load('v-voice.mjs');
    await load('social-controller.mjs');
    const {streamChat} = await load('mistral-client.mjs');
    let proofs=0, completions=0;
    const token='a'.repeat(64), origin='http://127.0.0.1:19876';
    const request=async(url,options)=>{
      assert.equal(new URL(url).origin,origin,'installed helper did not remap the configured port');
      const headers=new Headers(options.headers);
      if(new URL(url).pathname==='/healthz') {
        proofs++;assert.equal(headers.has('Authorization'),false);
        const nonce=headers.get('X-AiNpc-Challenge');assert.match(nonce,/^[a-f0-9]{64}$/);
        const proof=createHmac('sha256',token).update('AiNpcCodexBridge/bearer-v1\n19876\n'+nonce).digest('hex');
        return Response.json({status:'ok',service:'codex-companion-bridge',version:1,auth_mode:'chatgpt',local_auth:'bearer-v1',local_auth_proof:proof});
      }
      completions++;assert.equal(proofs,completions,'proof must precede every authenticated completion');
      assert.equal(new URL(url).pathname,'/v1/chat/completions');assert.equal(headers.get('Authorization'),'Bearer '+token);
      return Response.json({choices:[{message:{content:'Fixture transport reply.'},finish_reason:'stop'}]});
    };
    const result=await streamChat({provider:'custom',endpoint:'http://127.0.0.1:17865/v1/chat/completions',trustedOrigin:'http://127.0.0.1:17865',
      fetchImpl:request,model:'codex-default',messages:[{role:'user',content:'Fixture only.'}],retries:0,maxTokens:32});
    assert.equal(result.text,'Fixture transport reply.');assert.equal(proofs,1);assert.equal(completions,1);
    let invalidProofs=0;
    const impostor=async(url,options)=>{
      assert.equal(new URL(url).pathname,'/healthz');assert.equal(new Headers(options.headers).has('Authorization'),false);invalidProofs++;
      return Response.json({status:'ok',service:'codex-companion-bridge',version:1,auth_mode:'chatgpt',local_auth:'bearer-v1',local_auth_proof:'0'.repeat(64)});
    };
    await assert.rejects(streamChat({provider:'custom',endpoint:'http://127.0.0.1:17865/v1/chat/completions',trustedOrigin:'http://127.0.0.1:17865',
      fetchImpl:impostor,model:'codex-default',messages:[{role:'user',content:'Fixture only.'}],retries:1,maxTokens:32}),{identityMismatch:true,noRetry:true});
    assert.equal(invalidProofs,1,'identity mismatch must not enter generic client retries');
  }
  console.log(JSON.stringify({allPassed: true, variant, checkedSyntaxModules: checked,
    actualPromptModuleResolved: true, characterStyleRetained: true, privateProfileLoaded: false, modelCalls: 0}));
}
