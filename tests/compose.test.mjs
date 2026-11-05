import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync,writeFileSync,mkdirSync,mkdtempSync,readdirSync,rmSync,unlinkSync,existsSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,dirname,resolve,basename} from 'node:path';
import {pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';
import {composeCommunityCode} from '../common/community-compose.mjs';

const CODE='red4ext/plugins/AiNpcCyberpunkCode',RUNTIME='red4ext/plugins/AiNpcCyberpunkMod/app';
const sha=b=>createHash('sha256').update(b).digest('hex'),bytes=v=>Buffer.from(JSON.stringify(v,null,2)+'\n');
const installer=readFileSync(new URL('../common/install-code.mjs',import.meta.url)),helper=readFileSync(new URL('../common/community-compose.mjs',import.meta.url));
const original=Buffer.from('export const mode = "base";\n'),jp=Buffer.from('export const mode = "japanese";\n'),cx=Buffer.from('export const mode = "codex";\n'),both=Buffer.from('export const mode = "both";\n');
const roster=[{key:'judy',summary:'Original biography',records:['Protected.record'],voice:'protected-voice'}];

function tree(root){
 const out={};
 const walk=(folder,prefix='')=>{for(const row of readdirSync(folder,{withFileTypes:true})){const rel=prefix+row.name;if(row.isDirectory())walk(join(folder,row.name),rel+'/');else out[rel]=readFileSync(join(folder,row.name)).toString('hex');}};
 walk(root);return out;
}
async function fixture(t){
 const root=mkdtempSync(join(tmpdir(),'community-compose-'));
 t.after(()=>{assert.equal(dirname(root),resolve(tmpdir()));assert.ok(basename(root).startsWith('community-compose-'));rmSync(root,{recursive:true,force:true});});
 const put=(rel,value)=>{const p=join(root,...rel.split('/'));mkdirSync(dirname(p),{recursive:true});writeFileSync(p,value);return p;};
 const codeRoot=join(root,CODE),runtimeApp=join(root,RUNTIME),initial=new Map([
  ['bridge/example.mjs',original],['bridge/unrelated.mjs',Buffer.from('export const protectedCode = true;\n')],
  ['characters/roster.json',bytes(roster)],['defaults/runtime-code-files.json',Buffer.from('{"version":1,"runtime":"0.4.6","digits":24,"files":{}}\n')],
  ['launcher/start-service.mjs',Buffer.from("import{writeFileSync}from'node:fs';import{dirname,resolve}from'node:path';writeFileSync(resolve(dirname(process.argv[1]),'../defaults/service-started.json'),JSON.stringify({argv:process.argv.slice(2)}));\n")],
 ]);
 for(const [rel,value]of initial)put(CODE+'/app/'+rel,value);
 const manifest={version:1,product:'AI-NPC-Cyberpunk-Mod',package:'scripts-code',release:'0.4.6',game:'2.5',commit:'fixture',runtimeBase:'0.3.3',removes:['bridge/retired.mjs'],files:[...initial].map(([path,b])=>({path,size:b.length,sha256:sha(b)}))};
 const manifestBytes=bytes(manifest);put(CODE+'/code.json',manifestBytes);put(CODE+'/install-code.mjs',installer);put('red4ext/plugins/AiNpcCommunityAuto/community-compose.mjs',helper);
 put(RUNTIME+'/release.json',bytes({version:'0.3.3',game:'2.5'}));put(RUNTIME+'/defaults/convai-auth.json','protected-user-credentials');
 for(const rel of [RUNTIME+'/node/node.exe',RUNTIME+'/python/python.exe',CODE+'/CyberpunkConvai.dll',CODE+'/CyberpunkConvaiNative.dll'])put(rel,'fixture-not-an-executable');
 put('bin/x64/plugins/cyber_engine_tweaks/mods/AiNpcCyberpunkMod/runtime/settings.json','protected-player-settings');
 const imported=await import(pathToFileURL(join(codeRoot,'install-code.mjs')).href);
 const install=composed=>imported.installCode({codeApp:join(codeRoot,'app'),runtimeApp,manifest:composed.manifest,sourceFor:composed.sourceFor});
 install({manifest,sourceFor:rel=>readFileSync(join(codeRoot,'app',...rel.split('/')))});
 const folder=id=>'red4ext/plugins/'+(id==='codex'?'AiNpcCodexBridge':'AiNpcJapaneseOptimization');
 const recipe=(id,name,rel,value,baseSha=sha(initial.get(rel)??Buffer.alloc(0)))=>{const source='payload/'+name;put(folder(id)+'/'+source,value);return{path:CODE+'/app/'+rel,source,sha256:sha(value),outputSha256:sha(value),baseSha256:baseSha};};
 const feature=(id,files,extra={})=>{const value={schema:1,id,upstreamRelease:'0.4.6',release:id==='codex'?'1.2.2-rc.1':'1.0.4-rc.1',releaseFamily:'companion-addons-046-rc1',supportedPairing:{codex:'1.2.2-rc.1',japanese:'1.0.4-rc.1'},baseManifestSha256:sha(manifestBytes),files,...extra};put(folder(id)+'/auto-feature.json',bytes(value));return value;};
 const compose=()=>composeCommunityCode({codeRoot,manifest:JSON.parse(readFileSync(join(codeRoot,'code.json')))});
 return{root,codeRoot,runtimeApp,initial,manifest,manifestBytes,put,folder,recipe,feature,compose,install,imported,
  read:rel=>readFileSync(join(root,...rel.split('/'))),remove:rel=>unlinkSync(join(root,...rel.split('/')))};
}

test('base startup ignores legacy feature.json and retains the complete original manifest',async t=>{
 const f=await fixture(t);f.put(f.folder('codex')+'/feature.json',bytes({schema:1,id:'codex',files:[]}));
 const before=tree(f.codeRoot),c=f.compose();assert.deepEqual(c.features,[]);assert.deepEqual(c.manifest,f.manifest);assert.deepEqual(c.manifest.removes,['bridge/retired.mjs']);
 f.install(c);assert.deepEqual(tree(f.codeRoot),before);assert.equal(f.read(RUNTIME+'/bridge/example.mjs').toString(),original.toString());
});

test('Japanese-only deployment applies guarded profile fields and leaves identities, Code and user data untouched',async t=>{
 const f=await fixture(t),overlay={profiles:[{profileKey:'judy',fields:{summary:'日本語の紹介'},expectedFieldSha256:{summary:sha(Buffer.from(JSON.stringify(roster[0].summary)))}}]};
 const translated=bytes([{...roster[0],summary:'日本語の紹介'}]),profile=f.recipe('japanese','roster.json','characters/roster.json',bytes(overlay));
 profile.transform='profile-overlay';profile.outputSha256=sha(translated);
 f.feature('japanese',[f.recipe('japanese','jp.mjs','bridge/example.mjs',jp),profile,{path:'bin/x64/plugins/cyber_engine_tweaks/mods/AiNpcCyberpunkMod/init.lua',source:'private-lua-is-not-node-code'}]);
 const before=tree(f.codeRoot),c=f.compose();f.install(c);
 assert.deepEqual(c.features,['japanese']);assert.equal(c.manifest.files.length,f.manifest.files.length);assert.equal(f.read(RUNTIME+'/bridge/example.mjs').toString(),jp.toString());
 assert.deepEqual(JSON.parse(f.read(RUNTIME+'/characters/roster.json')),[{...roster[0],summary:'日本語の紹介'}]);assert.deepEqual(tree(f.codeRoot),before);
 assert.equal(f.read(RUNTIME+'/defaults/convai-auth.json').toString(),'protected-user-credentials');assert.equal(f.read('bin/x64/plugins/cyber_engine_tweaks/mods/AiNpcCyberpunkMod/runtime/settings.json').toString(),'protected-player-settings');
});

test('Codex-only and combined recipes select one coherent payload and regenerate the runtime diagnostic list',async t=>{
 const f=await fixture(t),newFile=Buffer.from('export const social = true;\n');
 const codex=f.feature('codex',[f.recipe('codex','codex.mjs','bridge/example.mjs',cx),f.recipe('codex','new.mjs','bridge/social-memory.mjs',newFile,null)],{combinations:{'codex+japanese':[f.recipe('codex','both.mjs','bridge/example.mjs',both)]}});
 const before=tree(f.codeRoot);let c=f.compose();f.install(c);assert.deepEqual(c.features,['codex']);assert.equal(f.read(RUNTIME+'/bridge/example.mjs').toString(),cx.toString());
 f.feature('japanese',[f.recipe('japanese','jp.mjs','bridge/example.mjs',jp)]);c=f.compose();f.install(c);assert.deepEqual(c.features,['codex','japanese']);assert.equal(f.read(RUNTIME+'/bridge/example.mjs').toString(),both.toString());
 assert.equal(c.manifest.files.length,f.manifest.files.length+1);assert.deepEqual(tree(f.codeRoot),before);assert.equal(codex.files.length,2);
 const diagnostic=JSON.parse(f.read(RUNTIME+'/defaults/runtime-code-files.json'));assert.equal(diagnostic.files['bridge/example.mjs'],sha(both).slice(0,24));assert.equal(diagnostic.files['bridge/social-memory.mjs'],sha(newFile).slice(0,24));assert.equal(diagnostic.files['bridge/unrelated.mjs'],sha(f.initial.get('bridge/unrelated.mjs')).slice(0,24));assert.equal(diagnostic.files['characters/roster.json'],undefined);
 const row=c.manifest.files.find(r=>r.path==='defaults/runtime-code-files.json');assert.equal(row.sha256,sha(f.read(RUNTIME+'/'+row.path)));
});

test('disabling an add-on restores base files and removes only previously listed add-on code',async t=>{
 const f=await fixture(t);f.feature('codex',[f.recipe('codex','cx.mjs','bridge/example.mjs',cx),f.recipe('codex','extra.mjs','bridge/extra.mjs',Buffer.from('added'),null)]);
 f.install(f.compose());f.put(RUNTIME+'/bridge/unrelated-extra.mjs','user-owned-unknown-file');
 f.remove(f.folder('codex')+'/auto-feature.json');const c=f.compose();const result=f.install(c);
 assert.equal(result.removed,1);assert.equal(existsSync(join(f.runtimeApp,'bridge/extra.mjs')),false);assert.equal(f.read(RUNTIME+'/bridge/example.mjs').toString(),original.toString());assert.equal(f.read(RUNTIME+'/bridge/unrelated-extra.mjs').toString(),'user-owned-unknown-file');
 assert.equal(f.read(RUNTIME+'/defaults/convai-auth.json').toString(),'protected-user-credentials');
});

test('conflicting recipes without a combined variant fail before any Runtime write',async t=>{
 const f=await fixture(t);f.feature('codex',[f.recipe('codex','cx.mjs','bridge/example.mjs',cx)]);f.feature('japanese',[f.recipe('japanese','jp.mjs','bridge/example.mjs',jp)]);
 const before=tree(f.runtimeApp);assert.throws(f.compose,{code:'COMMUNITY_COMBINATION_MISSING'});assert.deepEqual(tree(f.runtimeApp),before);
});

test('identical shared recipes coexist without a redundant combined variant',async t=>{
 const f=await fixture(t);f.feature('codex',[f.recipe('codex','same.mjs','bridge/example.mjs',both)]);f.feature('japanese',[f.recipe('japanese','same.mjs','bridge/example.mjs',both)]);
 f.install(f.compose());assert.equal(f.read(RUNTIME+'/bridge/example.mjs').toString(),both.toString());
});

test('changed legacy Code manifests, changed base files and damaged payloads fail without modifying Runtime',async t=>{
 const f=await fixture(t),feature=f.feature('codex',[f.recipe('codex','cx.mjs','bridge/example.mjs',cx)]),before=tree(f.runtimeApp);
 f.put(CODE+'/code.json',bytes({...f.manifest,commit:'old-manual-patch'}));assert.throws(f.compose,{code:'COMMUNITY_BASE_CHANGED'});f.put(CODE+'/code.json',f.manifestBytes);
 f.put(CODE+'/app/bridge/example.mjs','old-patched-code');assert.throws(f.compose,{code:'COMMUNITY_BASE_CHANGED'});f.put(CODE+'/app/bridge/example.mjs',original);
 f.put(f.folder('codex')+'/'+feature.files[0].source,'damaged');assert.throws(f.compose,{code:'COMMUNITY_PAYLOAD_DAMAGED'});assert.deepEqual(tree(f.runtimeApp),before);
});

test('installer validates every pending source before writing even the first valid override',async t=>{
 const f=await fixture(t);f.feature('japanese',[f.recipe('japanese','jp.mjs','bridge/example.mjs',jp)]);
 f.put(CODE+'/app/bridge/unrelated.mjs','bad original source');f.remove(RUNTIME+'/bridge/unrelated.mjs');
 const before=tree(f.runtimeApp),c=f.compose();assert.throws(()=>f.install(c),{code:'SCRIPTS_DAMAGED'});assert.deepEqual(tree(f.runtimeApp),before);assert.equal(f.read(RUNTIME+'/bridge/example.mjs').toString(),original.toString());
});

test('invalid descriptors, traversal and incompatible baseline targets are rejected without touching Code or Runtime',async t=>{
 const f=await fixture(t),valid=f.recipe('codex','cx.mjs','bridge/example.mjs',cx),code=tree(f.codeRoot),runtime=tree(f.runtimeApp);
 for(const extra of [{schema:2},{id:'japanese'},{upstreamRelease:'0.4.4'},{files:[{...valid,source:'payload/../../outside'}]},{files:[{...valid,path:CODE+'/app/bridge/../outside.mjs'}]},{files:[{...valid,baseSha256:null}]}]){
  f.feature('codex',[valid],extra);assert.throws(f.compose);
 }
 assert.deepEqual(tree(f.codeRoot),code);assert.deepEqual(tree(f.runtimeApp),runtime);
});

test('unlisted old Code additions do not become sources for a current add-on',async t=>{
 const f=await fixture(t),current=Buffer.from('export const current = true;\n');f.put(CODE+'/app/bridge/extra.mjs','obsolete old patch code');
 f.feature('codex',[f.recipe('codex','current.mjs','bridge/extra.mjs',current,null)]);const before=tree(f.codeRoot);f.install(f.compose());assert.equal(f.read(RUNTIME+'/bridge/extra.mjs').toString(),current.toString());assert.deepEqual(tree(f.codeRoot),before);
});

test('the deployed installer main composes automatically and forwards prepare/lifeline arguments to the official startup path',async t=>{
 const f=await fixture(t);f.feature('codex',[f.recipe('codex','cx.mjs','bridge/example.mjs',cx)]);const before=tree(f.codeRoot);
 const run=spawnSync(process.execPath,[join(f.codeRoot,'install-code.mjs'),'--game-root',f.root,'--game-pid','42','--prepare-only','--lifeline','stdin'],{encoding:'utf8',windowsHide:true,timeout:15000});
 assert.equal(run.status,0,run.stderr);assert.equal(f.read(RUNTIME+'/bridge/example.mjs').toString(),cx.toString());
 const started=JSON.parse(f.read(RUNTIME+'/defaults/service-started.json'));assert.deepEqual(started.argv,['--game-root',f.root,'--game-pid','42','--prepare-only','--lifeline','stdin']);assert.deepEqual(tree(f.codeRoot),before);
});

test('mixed release families or a missing pairing declaration restore base instead of selecting an old combined payload',async t=>{
 const f=await fixture(t);
 f.feature('japanese',[f.recipe('japanese','jp.mjs','bridge/example.mjs',jp)]);
 const row=f.recipe('codex','old-combined.mjs','bridge/example.mjs',both);
 for(const extra of [{release:'1.2.1-preview.3',releaseFamily:undefined,supportedPairing:undefined},
   {releaseFamily:'another-generation'},{supportedPairing:{codex:'1.2.2-rc.1',japanese:'old'}}]) {
  f.feature('codex',[f.recipe('codex','cx.mjs','bridge/example.mjs',cx)],{combinations:{'codex+japanese':[row]},...extra});
  const c=f.compose();assert.deepEqual(c.features,[]);assert.equal(c.diagnostics[0].code,'COMMUNITY_PAIRING_INCOMPATIBLE');
  f.install(c);assert.equal(f.read(RUNTIME+'/bridge/example.mjs').toString(),original.toString());
 }
});

test('an incomplete Full installation has a dedicated dependency message before code copy or service start',async t=>{
 const f=await fixture(t);f.remove(RUNTIME+'/python/python.exe');
 const before=f.read(RUNTIME+'/bridge/example.mjs');
 const run=spawnSync(process.execPath,[join(f.codeRoot,'install-code.mjs'),'--game-root',f.root,'--game-pid','0'],{encoding:'utf8',windowsHide:true,timeout:15000});
 assert.equal(run.status,1);assert.match(run.stderr,/COMMUNITY_FULL_INSTALL_REQUIRED/);assert.match(run.stderr,/0\.4\.6 Full/);
 assert.deepEqual(f.read(RUNTIME+'/bridge/example.mjs'),before);assert.equal(existsSync(join(f.runtimeApp,'defaults/service-started.json')),false);
});
test('Windows reserved paths and case aliases cannot overwrite another Code target',async t=>{
 const f=await fixture(t),before=tree(f.runtimeApp);
 for(const rel of ['bridge/Example.mjs','bridge/CON.mjs','bridge/NUL/extra.mjs']) {
  f.feature('codex',[f.recipe('codex','alias.mjs',rel,cx,null)]);assert.throws(f.compose);
 }
 assert.deepEqual(tree(f.runtimeApp),before);
});
