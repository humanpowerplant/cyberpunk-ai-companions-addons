// Real PowerShell startup logic with only the health HTTP response injected.
// This isolates PID ownership behavior from AppContainer loopback routing.
// No Python/CLI/model process or existing service is started, stopped or adopted.
import test from 'node:test';
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {spawn} from 'node:child_process';
import {mkdir,mkdtemp,copyFile,writeFile,readFile,readdir,rm} from 'node:fs/promises';
import {join,dirname,resolve,basename} from 'node:path';
import {tmpdir} from 'node:os';

test('PowerShell borrows compatible readiness without a PID record or claiming an existing server', {skip:process.platform!=='win32',timeout:30000},async t=>{
 const root=await mkdtemp(join(tmpdir(),'codex-borrow-')),backend=join(root,'Backend with spaces'),state=join(root,'state');
 await mkdir(backend,{recursive:true});await mkdir(state,{recursive:true});
 t.after(async()=>{assert.equal(dirname(root),resolve(tmpdir()));assert.ok(basename(root).startsWith('codex-borrow-'));await rm(root,{recursive:true,force:true});});
 const source=new URL('../codex_source/payload/game/red4ext/plugins/AiNpcCodexBridge/',import.meta.url);
 for(const file of ['start.ps1','bridge-common.ps1','config.example.json'])await copyFile(new URL(file,source),join(backend,file));
 let identity={status:'ok',service:'codex-companion-bridge',version:1,auth_mode:'chatgpt',local_auth:'bearer-v1'};
 await writeFile(join(state,'config.json'),JSON.stringify({host:'127.0.0.1',port:17866}));
 await writeFile(join(state,'local-token.json'),JSON.stringify({schema:1,token:'f'.repeat(64)}));
 const healthFile=join(root,'health-response.json'),queries=join(root,'health-queries.log'),authQueries=join(root,'auth-queries.log');
 const literal=value=>"'"+value.replaceAll("'","''")+"'";
 const run=async()=>{
  await writeFile(healthFile,JSON.stringify(identity));
  const script=`function global:Invoke-RestMethod {
    param($Uri,$TimeoutSec,$Headers,$MaximumRedirection)
    if ($MaximumRedirection -ne 0) { throw 'Redirect must be forbidden' }
    if ($Uri -eq 'http://127.0.0.1:17866/codex/settings') {
      if ($Headers.Authorization -ne ('Bearer ' + ('f' * 64))) { throw 'Missing fixture token' }
      Add-Content -LiteralPath ${literal(authQueries)} -Value 'authenticated'; return @{status='ok'}
    }
    if ($Uri -ne 'http://127.0.0.1:17866/healthz') { throw 'Unexpected fixture request' }
    if ($Headers.Authorization) { throw 'Bearer must never be disclosed to a health probe' }
    Add-Content -LiteralPath ${literal(queries)} -Value 'health'
    $health = Get-Content -LiteralPath ${literal(healthFile)} -Raw | ConvertFrom-Json
    if ($Headers -and $Headers['X-AiNpc-Challenge']) {
      $hmac = New-Object Security.Cryptography.HMACSHA256
      try {
        $hmac.Key = [Text.Encoding]::ASCII.GetBytes('f' * 64)
        $data = 'AiNpcCodexBridge/bearer-v1' + [char]10 + '17866' + [char]10 + $Headers['X-AiNpc-Challenge']
        $proof = [BitConverter]::ToString($hmac.ComputeHash([Text.Encoding]::ASCII.GetBytes($data))).Replace('-','').ToLowerInvariant()
      } finally { $hmac.Dispose() }
      if ($health.fixture_wrong_proof) { $proof = '0' * 64 }
      $health | Add-Member -NotePropertyName local_auth_proof -NotePropertyValue $proof -Force
    }
    return $health
  }; & ${literal(join(backend,'start.ps1'))} -StateDirectory ${literal(state)} -PythonPath ${literal(join(root,'must-not-launch-python.exe'))}`;
  const child=spawn('powershell.exe',['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-EncodedCommand',Buffer.from(script,'utf16le').toString('base64')],{windowsHide:true,stdio:['ignore','pipe','pipe']});
  let output='',error='';child.stdout.on('data',v=>output+=v);child.stderr.on('data',v=>error+=v);const [code]=await once(child,'close');return{code,output,error};
 };
 let result=await run();assert.equal(result.code,0,result.error);assert.equal(JSON.parse(result.output).service,'codex-companion-bridge');assert.deepEqual((await readdir(state)).sort(),['config.json','local-token.json','startup.lock']);
 const stale='{ this record belongs to nobody }';await writeFile(join(state,'server.pid.json'),stale);
 result=await run();assert.equal(result.code,0,result.error);assert.equal(await readFile(join(state,'server.pid.json'),'utf8'),stale);assert.deepEqual((await readdir(state)).sort(),['config.json','local-token.json','server.pid.json','startup.lock']);
 identity={...identity,auth_mode:'api-key'};result=await run();assert.notEqual(result.code,0);assert.match(result.error,/incompatible service/);assert.equal(await readFile(join(state,'server.pid.json'),'utf8'),stale);
 identity={...identity,auth_mode:'chatgpt',local_auth:undefined};result=await run();assert.notEqual(result.code,0);assert.match(result.error,/older unauthenticated Codex bridge/);assert.equal(await readFile(join(state,'server.pid.json'),'utf8'),stale);
 identity={...identity,local_auth:'bearer-v1',fixture_wrong_proof:true};result=await run();assert.notEqual(result.code,0);assert.match(result.error,/Local bridge proof rejected/);
 assert.equal((await readFile(queries,'utf8')).trim().split(/\r?\n/).length,8);
 assert.equal((await readFile(authQueries,'utf8')).trim().split(/\r?\n/).length,2,'Spoofed service must not receive Bearer');
 assert.equal((await readdir(backend)).some(name=>name==='bridge.py'),false);
});
