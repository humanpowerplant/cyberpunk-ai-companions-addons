// Filesystem-only PowerShell 5.1 fixtures. Python resolution and native CLI
// login are replaced in a TEMP COPY before execution. No real authentication,
// Codex home, bridge, model, game or server is opened.
import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync, mkdirSync, readFileSync, readdirSync, writeFileSync, rmSync, existsSync, realpathSync} from 'node:fs';
import {join, dirname, resolve, basename} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';

const source = resolve(dirname(fileURLToPath(import.meta.url)), '../payload/game/red4ext/plugins/AiNpcCodexBridge');
const actual = readFileSync(join(source, 'login.ps1'), 'utf8');
const powershell = process.env.SystemRoot && join(process.env.SystemRoot, 'System32/WindowsPowerShell/v1.0/powershell.exe');
const supported = process.platform === 'win32' && powershell && existsSync(powershell);
// Hosted Windows exposes TEMP through an 8.3 alias. PowerShell expands that
// alias; construct every fixture from the same canonical parent from the start.
const fixtureTemp = realpathSync.native(tmpdir());
const json = file => JSON.parse(readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));
// Core cmdlets are imported directly rather than searching every installed
// Windows Server module while constructing the synthetic user's empty cache.
const fixtureModules = `
$PSModuleAutoLoadingPreference = 'None'
Import-Module ($PSHOME + '\\Modules\\Microsoft.PowerShell.Utility\\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
Import-Module ($PSHOME + '\\Modules\\Microsoft.PowerShell.Management\\Microsoft.PowerShell.Management.psd1') -ErrorAction Stop
`;

function fixtureEnvironment(root, extra = {}) {
  const local = join(root, 'local-data'), roaming = join(root, 'roaming-data');
  mkdirSync(local, {recursive:true});
  mkdirSync(roaming, {recursive:true});
  const env = {};
  // Retain only Windows routing paths. In particular, do not inherit hosted
  // runners' PowerShell module catalogs, agent settings or provider keys.
  for (const name of ['SystemRoot', 'WINDIR', 'SYSTEMDRIVE', 'COMSPEC', 'PATH', 'PATHEXT',
    'ProgramFiles', 'ProgramFiles(x86)', 'ProgramW6432', 'ProgramData', 'ALLUSERSPROFILE', 'PUBLIC']) {
    if (process.env[name] !== undefined) env[name] = process.env[name];
  }
  return {...env, TEMP:fixtureTemp, TMP:fixtureTemp, USERPROFILE:root, HOME:root,
    LOCALAPPDATA:local, APPDATA:roaming,
    // Use the Windows PowerShell 5.1 built-ins, never pwsh/hosted user modules.
    PSModulePath:join(dirname(powershell), 'Modules'),
    PSModuleAnalysisCachePath:join(local, 'ModuleAnalysisCache'), ...extra};
}

function fixtureResult(run) {
  // Output belongs to the synthetic fixture: real login and model calls are
  // replaced before it runs, and no inherited provider credentials are used.
  return JSON.stringify({error:run.error?.message, status:run.status, signal:run.signal,
    stdout:run.stdout, stderr:run.stderr}, null, 2);
}

function replaceOnce(text, before, after) {
  assert.equal(text.split(before).length - 1, 1, 'fixture stub anchor must still match actual product source exactly');
  return text.replace(before, after);
}

function fixture(t, {home = 'isolated', answer = 'n', guard = null, loginExit = 0} = {}) {
  const root = mkdtempSync(join(fixtureTemp, 'codex-login-fixture-'));
  t.after(() => {
    assert.equal(dirname(root), fixtureTemp);
    assert.ok(basename(root).startsWith('codex-login-fixture-'));
    rmSync(root, {recursive:true, force:true});
  });
  const state = join(root, 'isolated-state');
  mkdirSync(state);
  const settings = {codex_home:home, model:'default', port:32123, preserved:{label:'fixture-only'}};
  const before = JSON.stringify(settings, null, 2) + '\n';
  writeFileSync(join(state, 'config.json'), before);
  writeFileSync(join(root, 'bridge-common.ps1'), readFileSync(join(source, 'bridge-common.ps1')));
  writeFileSync(join(root, 'config.example.json'), readFileSync(join(source, 'config.example.json')));
  writeFileSync(join(root, 'fixture-cli.marker'), 'This is not an executable.');
  if (guard) {
    mkdirSync(join(state, 'codex-home'));
    writeFileSync(join(state, 'codex-home', guard), 'fixture instructions must remain untouched');
  }
  let copy = replaceOnce(actual, '$python = Get-BridgePython $PythonPath', "$python = 'fixture-python-not-executed'");
  copy = replaceOnce(copy, '$resolved = $resolver | & $python -B - $PSScriptRoot $configPath',
    "$resolved = @{executable=(Join-Path $PSScriptRoot 'fixture-cli.marker')} | ConvertTo-Json; $global:LASTEXITCODE = 0");
  copy = replaceOnce(copy, '$result = Invoke-OfficialCodexLogin $executable $dedicatedHome', `
    @{ home=$env:CODEX_HOME; argument='login'; version=$PSVersionTable.PSVersion.Major } |
      ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'fixture-login.json') -Encoding utf8
    $result = ${loginExit}`);
  copy = replaceOnce(copy, 'finally { $env:CODEX_HOME = $previousHome }', `finally {
    $env:CODEX_HOME = $previousHome
    @{ restored=$env:CODEX_HOME } | ConvertTo-Json |
      Set-Content -LiteralPath (Join-Path $PSScriptRoot 'fixture-restored.json') -Encoding utf8
  }`);
  // Assertions against accidentally leaving either native invocation active.
  assert.ok(!copy.includes('$resolver | & $python'));
  assert.ok(!copy.includes('$result = Invoke-OfficialCodexLogin $executable $dedicatedHome'));
  assert.ok(!copy.includes('$python = Get-BridgePython'));
  writeFileSync(join(root, 'login.ps1'), copy);
  writeFileSync(join(root, 'driver.ps1'), `
${fixtureModules}
$ErrorActionPreference = 'Stop'
function global:Read-Host { param([string]$Prompt) return $env:FIXTURE_ANSWER }
& (Join-Path $PSScriptRoot 'login.ps1') -StateDirectory (Join-Path $PSScriptRoot 'isolated-state')
exit $LASTEXITCODE
`);
  const outerHome = join(root, 'outer-home-marker');
  const run = spawnSync(powershell, ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', join(root, 'driver.ps1')],
    {encoding:'utf8', windowsHide:true, timeout:15000, stdio:['ignore','pipe','pipe'],
      env:fixtureEnvironment(root, {CODEX_HOME:outerHome,FIXTURE_ANSWER:answer})});
  assert.equal(run.error, undefined, fixtureResult(run));
  return {root,state,settings,before,outerHome,run,
    backups:() => readdirSync(state).filter(name => /^config\.before-isolated-[a-f0-9]+\.json$/.test(name)),
    login:() => json(join(root, 'fixture-login.json')),
    restored:() => json(join(root, 'fixture-restored.json'))};
}

test('Login.cmd exposes only the explicitly launched local login helper', () => {
  const command = readFileSync(join(source, 'Login.cmd'), 'utf8');
  assert.match(command, /powershell\.exe\s+-NoProfile\s+-ExecutionPolicy\s+Bypass\s+-File\s+"%~dp0login\.ps1"/i);
  assert.doesNotMatch(command, /start-service|start\.ps1|https?:|curl|auth\.json|\.codex/i);
});

test('dedicated login passes isolated CODEX_HOME and restores its prior value', {skip:!supported}, t => {
  const f = fixture(t);
  assert.equal(f.run.status, 0, f.run.stderr);
  assert.equal(f.login().version, 5, 'the test must execute Windows PowerShell 5.1, not pwsh');
  assert.equal(f.login().argument, 'login');
  assert.equal(f.login().home, join(f.state, 'codex-home'));
  assert.equal(f.restored().restored, f.outerHome);
  assert.equal(readFileSync(join(f.state, 'config.json'), 'utf8'), f.before);
  assert.deepEqual(f.backups(), []);
});

test('CLI failure exit code survives while CODEX_HOME is still restored', {skip:!supported}, t => {
  const f = fixture(t, {loginExit:17});
  assert.equal(f.run.status, 17, f.run.stderr);
  assert.equal(f.restored().restored, f.outerHome);
});

test('approved legacy mode keeps an exact backup and preserves unrelated settings', {skip:!supported}, t => {
  const f = fixture(t, {home:'legacy', answer:'y'});
  assert.equal(f.run.status, 0, f.run.stderr);
  assert.equal(f.backups().length, 1);
  assert.equal(readFileSync(join(f.state, f.backups()[0]), 'utf8'), f.before);
  assert.deepEqual(json(join(f.state, 'config.json')), {...f.settings,codex_home:'isolated'});
  assert.equal(f.login().home, join(f.state, 'codex-home'));
  assert.equal(f.restored().restored, f.outerHome);
  assert.ok(!readdirSync(f.state).some(name => name.endsWith('.tmp')));
});

test('cancelled legacy conversion keeps config and starts no login', {skip:!supported}, t => {
  const f = fixture(t, {home:'legacy', answer:'n'});
  assert.equal(f.run.status, 0, f.run.stderr);
  assert.equal(readFileSync(join(f.state, 'config.json'), 'utf8'), f.before);
  assert.deepEqual(f.backups(), []);
  assert.equal(existsSync(join(f.root, 'fixture-login.json')), false);
  assert.equal(existsSync(join(f.state, 'codex-home')), false);
});

for (const guard of ['AGENTS.md', 'AGENTS.override.md']) {
  test(`${guard} blocks login and is never removed`, {skip:!supported}, t => {
    const f = fixture(t, {guard});
    assert.notEqual(f.run.status, 0);
    assert.equal(existsSync(join(f.root, 'fixture-login.json')), false);
    assert.equal(readFileSync(join(f.state, 'codex-home', guard), 'utf8'), 'fixture instructions must remain untouched');
    assert.equal(readFileSync(join(f.state, 'config.json'), 'utf8'), f.before);
  });
}

test('native login process receives only the explicit environment allowlist', {skip:!supported}, t => {
  const root = mkdtempSync(join(fixtureTemp, 'codex-login-fixture-'));
  t.after(() => {
    assert.equal(dirname(root), fixtureTemp);
    assert.ok(basename(root).startsWith('codex-login-fixture-'));
    rmSync(root, {recursive:true,force:true});
  });
  // Execute the actual launcher function, substituting only its final native
  // Process.Start. Its ProcessStartInfo and clearing/copy logic are unchanged.
  const begin = actual.indexOf('function Invoke-OfficialCodexLogin {');
  const end = actual.indexOf('$statePath =', begin);
  assert.ok(begin >= 0 && end > begin);
  const launcher = replaceOnce(actual.slice(begin,end), '[Diagnostics.Process]::Start($startInfo)', '(New-FixtureProcess $startInfo)');
  writeFileSync(join(root,'fixture.ps1'), `
${fixtureModules}
$ErrorActionPreference='Stop'
function New-FixtureProcess {
  param($StartInfo)
  @{
    version=$PSVersionTable.PSVersion.Major
    openai=$StartInfo.EnvironmentVariables.ContainsKey('OPENAI_API_KEY')
    codex=$StartInfo.EnvironmentVariables.ContainsKey('CODEX_API_KEY')
    unrelated=$StartInfo.EnvironmentVariables.ContainsKey('FIXTURE_UNRELATED_SECRET')
    inheritedProfile=$StartInfo.EnvironmentVariables.ContainsKey('CODEX_PROFILE')
    ownHome=$StartInfo.EnvironmentVariables['CODEX_HOME']
    systemRootPresent=$StartInfo.EnvironmentVariables.ContainsKey('SYSTEMROOT')
    argument=$StartInfo.Arguments
    shell=$StartInfo.UseShellExecute
    cwd=$StartInfo.WorkingDirectory
  } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'environment.json') -Encoding utf8
  $fake=New-Object PSObject -Property @{ExitCode=0}
  $fake | Add-Member -MemberType ScriptMethod -Name WaitForExit -Value {}
  $fake | Add-Member -MemberType ScriptMethod -Name Dispose -Value {}
  return $fake
}
${launcher}
$result=Invoke-OfficialCodexLogin 'fixture-not-executable' (Join-Path $PSScriptRoot 'dedicated-home')
exit $result
`);
  const run = spawnSync(powershell,['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',join(root,'fixture.ps1')],{
    encoding:'utf8',windowsHide:true,timeout:15000,stdio:['ignore','pipe','pipe'],
    env:fixtureEnvironment(root, {
      OPENAI_API_KEY:'fixture-dummy-not-a-real-provider-key',CODEX_API_KEY:'fixture-dummy-not-a-real-provider-key',
      CODEX_PROFILE:'fixture-inherited-profile',FIXTURE_UNRELATED_SECRET:'fixture-private-marker',CODEX_HOME:join(root,'wrong-home')})});
  assert.equal(run.error,undefined,fixtureResult(run));
  assert.equal(run.status,0,run.stderr);
  const observed=json(join(root,'environment.json'));
  assert.equal(observed.version,5);
  for (const key of ['openai','codex','unrelated','inheritedProfile']) assert.equal(observed[key],false,key);
  assert.equal(observed.ownHome,join(root,'dedicated-home'));
  assert.equal(observed.cwd,join(root,'dedicated-home'));
  assert.equal(observed.systemRootPresent,true);
  assert.equal(observed.argument,'login');
  assert.equal(observed.shell,false);
});
