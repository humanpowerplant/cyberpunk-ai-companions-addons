// Bounded, synthetic CI diagnostics. No login, provider, game or profile script.
import {spawnSync} from 'node:child_process';
import {mkdtempSync, mkdirSync, writeFileSync, rmSync} from 'node:fs';
import {join, dirname} from 'node:path';
import {tmpdir} from 'node:os';

if (process.platform !== 'win32') throw Error('Windows diagnostics only');
const root = mkdtempSync(join(tmpdir(), 'codex-ps-probe-'));
try {
  const powershell = join(process.env.SystemRoot, 'System32/WindowsPowerShell/v1.0/powershell.exe');
  const local = join(root,'local'), roaming = join(root,'roaming');
  mkdirSync(local); mkdirSync(roaming);
  const isolated = {};
  for (const name of ['SystemRoot','WINDIR','SYSTEMDRIVE','COMSPEC','PATH','PATHEXT',
    'ProgramFiles','ProgramFiles(x86)','ProgramW6432','ProgramData','ALLUSERSPROFILE','PUBLIC']) {
    if (process.env[name] !== undefined) isolated[name] = process.env[name];
  }
  Object.assign(isolated, {TEMP:tmpdir(),TMP:tmpdir(),USERPROFILE:root,HOME:root,
    LOCALAPPDATA:local,APPDATA:roaming,PSModulePath:join(dirname(powershell),'Modules'),
    PSModuleAnalysisCachePath:join(local,'ModuleAnalysisCache')});
  const script = `[Console]::WriteLine('engine entered')
$ErrorActionPreference='Stop'
@{fixture='synthetic'} | ConvertTo-Json -Compress
[Console]::WriteLine('utility completed')
`;
  const file = join(root,'probe.ps1'); writeFileSync(file,script);
  const osProfile = {...isolated};
  for (const name of ['USERPROFILE','HOME','APPDATA','LOCALAPPDATA']) {
    if (process.env[name] === undefined) delete osProfile[name];
    else osProfile[name] = process.env[name];
  }
  for (const [label, env, encoded, ignoreInput] of [
    ['inherited file',process.env,false],
    ['isolated file',isolated,false],
    ['isolated encoded',isolated,true],
    ['OS profile file',osProfile,false],
    ['isolated file, closed input',isolated,false,true],
  ]) {
    const args = ['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
      ...(encoded ? ['-EncodedCommand',Buffer.from(script,'utf16le').toString('base64')] : ['-File',file])];
    const started = Date.now();
    const r = spawnSync(powershell,args,{env,encoding:'utf8',windowsHide:true,timeout:8000,
      ...(ignoreInput ? {stdio:['ignore','pipe','pipe']} : {})});
    console.log(JSON.stringify({label,ms:Date.now()-started,status:r.status,error:r.error?.code,
      stdout:r.stdout,stderr:r.stderr}));
  }
} finally { rmSync(root,{recursive:true,force:true}); }
