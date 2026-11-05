// Real simultaneous PowerShell entry points; health and native launch are inert
// filesystem fixtures. No Python, CLI, login, game or existing listener is used.
import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp, mkdir, readFile, writeFile, copyFile, readdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve, dirname, basename} from 'node:path';

test('concurrent startup launches only one owned backend and preserves its PID receipt',
  {skip:process.platform !== 'win32', timeout:30000}, async t => {
    const root=await mkdtemp(join(tmpdir(),'codex-start-serialization-'));
    const state=join(root,'state'), backend=join(root,'backend');
    const children=[];
    t.after(async()=>{
      await Promise.all(children.map(child=>{
        if(child.exitCode!==null || child.signalCode!==null) return;
        return new Promise(finish=>{
          const timer=setTimeout(finish,2000);
          child.once('close',()=>{clearTimeout(timer);finish();});
          child.kill();
        });
      }));
      assert.equal(dirname(root),resolve(tmpdir()));
      assert.ok(basename(root).startsWith('codex-start-serialization-'));
      await rm(root,{recursive:true,force:true});
    });
    await mkdir(state);await mkdir(backend);
    const source=new URL('../payload/game/red4ext/plugins/AiNpcCodexBridge/',import.meta.url);
    for(const name of ['bridge-common.ps1','config.example.json']) await copyFile(new URL(name,source),join(backend,name));
    let start=await readFile(new URL('start.ps1',source),'utf8');
    const anchor='$python = Get-BridgePython $PythonPath';
    assert.equal(start.split(anchor).length-1,1);
    start=start.replace(anchor,"$python = 'fixture-not-executed'");
    await writeFile(join(backend,'start.ps1'),start);
    await writeFile(join(state,'config.json'),JSON.stringify({host:'127.0.0.1',port:17866}));
    await writeFile(join(state,'local-token.json'),JSON.stringify({schema:1,token:'f'.repeat(64)}));
    const quote=value=>"'"+value.replaceAll("'","''")+"'";
    const driver=`param([string]$Name)
$ErrorActionPreference='Stop'
$PSModuleAutoLoadingPreference='None'
Import-Module ($PSHOME + '\\Modules\\Microsoft.PowerShell.Utility\\Microsoft.PowerShell.Utility.psd1')
Import-Module ($PSHOME + '\\Modules\\Microsoft.PowerShell.Management\\Microsoft.PowerShell.Management.psd1')
$global:fixtureRoot=${quote(root)}
$global:fixtureName=$Name
function global:Invoke-RestMethod {
  param($Uri,$TimeoutSec,$Headers,$MaximumRedirection,$Method)
  if ($MaximumRedirection -ne 0) { throw 'Redirects must remain forbidden' }
  if ($Uri -eq 'http://127.0.0.1:17866/codex/settings') {
    if ($Headers.Authorization -ne ('Bearer ' + ('f' * 64))) { throw 'Expected fixture credential' }
    return @{status='ok'}
  }
  if ($Uri -ne 'http://127.0.0.1:17866/healthz') { throw 'Unexpected fixture request' }
  if ($Headers.Authorization) { throw 'Health must not receive the credential' }
  if (-not ([IO.File]::Exists($global:fixtureRoot + '\\ready-a') -or [IO.File]::Exists($global:fixtureRoot + '\\ready-b') -or [IO.File]::Exists($global:fixtureRoot + '\\ready-retry'))) {
    [Threading.Thread]::Sleep(150)
    throw 'Fixture is not yet ready'
  }
  $value=@{status='ok';service='codex-companion-bridge';version=1;auth_mode='chatgpt';local_auth='bearer-v1'}
  if ($Headers -and $Headers['X-AiNpc-Challenge']) {
    $hmac=New-Object Security.Cryptography.HMACSHA256
    try {
      $hmac.Key=[Text.Encoding]::ASCII.GetBytes('f' * 64)
      $data='AiNpcCodexBridge/bearer-v1' + [char]10 + '17866' + [char]10 + $Headers['X-AiNpc-Challenge']
      $value.local_auth_proof=[BitConverter]::ToString($hmac.ComputeHash([Text.Encoding]::ASCII.GetBytes($data))).Replace('-','').ToLowerInvariant()
    } finally { $hmac.Dispose() }
  }
  return $value
}
function global:Start-Process {
  param($FilePath,$ArgumentList,$WorkingDirectory,$WindowStyle,[switch]$PassThru,$RedirectStandardOutput,$RedirectStandardError)
  if ($FilePath -ne 'fixture-not-executed' -or $WindowStyle -ne 'Hidden') { throw 'Unexpected native launch' }
  [IO.File]::WriteAllText($global:fixtureRoot + '\\launch-' + $global:fixtureName,'launched')
  [Threading.Thread]::Sleep(500)
  [IO.File]::WriteAllText($global:fixtureRoot + '\\ready-' + $global:fixtureName,'ready')
  $fake=New-Object PSObject -Property @{Id=424242;StartTime=[DateTime]::UtcNow;Path='fixture-not-executed';HasExited=$false}
  $fake | Add-Member -MemberType ScriptMethod -Name Refresh -Value {}
  return $fake
}
function global:Get-Process {
  param($Id,$ErrorAction)
  if ($global:fixtureName -ne 'retry' -or $Id -ne 424242) { throw 'Unexpected fixture PID lookup' }
  $record=Get-Content -LiteralPath ($global:fixtureRoot + '\\state\\server.pid.json') -Raw | ConvertFrom-Json
  $fake=New-Object PSObject -Property @{Id=424242;StartTime=[DateTime]::new([long]$record.start_ticks,[DateTimeKind]::Utc);Path='fixture-not-executed';HasExited=$false}
  $fake | Add-Member -MemberType ScriptMethod -Name Refresh -Value {
    [IO.File]::WriteAllText($global:fixtureRoot + '\\ready-retry','ready')
  }
  return $fake
}
[IO.File]::WriteAllText($global:fixtureRoot + '\\barrier-' + $Name,'ready')
$until=[DateTime]::UtcNow.AddSeconds(5)
while (-not ([IO.File]::Exists($global:fixtureRoot + '\\barrier-a') -and [IO.File]::Exists($global:fixtureRoot + '\\barrier-b'))) {
  if ([DateTime]::UtcNow -gt $until) { throw 'Fixture launch barrier timed out' }
  [Threading.Thread]::Sleep(20)
}
& ${quote(join(backend,'start.ps1'))} -StateDirectory ${quote(state)}
`;
    await writeFile(join(root,'driver.ps1'),driver);
    const invoke=name=>new Promise((resolveResult,reject)=>{
      const child=spawn('powershell.exe',['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',join(root,'driver.ps1'),'-Name',name],
        {windowsHide:true,stdio:['ignore','pipe','pipe']});
      children.push(child);
      let output='',error='';
      child.stdout.on('data',part=>output+=part);child.stderr.on('data',part=>error+=part);
      const timer=setTimeout(()=>{child.kill();reject(Error('Fixture PowerShell timed out'));},12000);
      child.once('error',e=>{clearTimeout(timer);reject(e);});
      child.once('close',code=>{clearTimeout(timer);resolveResult({code,output,error});});
    });
    const results=await Promise.all([invoke('a'),invoke('b')]);
    for(const result of results) assert.equal(result.code,0,result.error);
    assert.equal((await readdir(root)).filter(name=>name.startsWith('launch-')).length,1);
    const record=JSON.parse((await readFile(join(state,'server.pid.json'),'utf8')).replace(/^\uFEFF/,''));
    assert.equal(record.pid,424242);
    assert.equal(record.executable,'fixture-not-executed');
    // A prior launcher can time out before CLI capability/auth checks finish.
    // Its exact PID receipt must be reused rather than overwritten by a retry.
    const receipt=await readFile(join(state,'server.pid.json'),'utf8');
    await rm(join(root,'ready-a'),{force:true});await rm(join(root,'ready-b'),{force:true});
    const retry=await invoke('retry');
    assert.equal(retry.code,0,retry.error);
    assert.equal((await readdir(root)).filter(name=>name.startsWith('launch-')).length,1);
    assert.equal(await readFile(join(state,'server.pid.json'),'utf8'),receipt);
  });
