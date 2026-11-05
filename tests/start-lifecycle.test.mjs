// Real PowerShell + Python + HTTP in a disposable fixture. No CLI/login/model calls.
import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdir, copyFile, readFile, writeFile} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {createServer} from 'node:net';
import {resolve, dirname} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {CodexAutoStart} from '../codex_source/payload/game/bin/x64/plugins/cyber_engine_tweaks/mods/AiNpcCodexBridge/auto-start.mjs';

test('deployed automatic startup reuses its owned bridge and parent exit closes it without manual commands', {skip:process.platform!=='win32',timeout:45000}, async () => {
  const root=resolve(dirname(fileURLToPath(import.meta.url)),'..'),source=resolve(root,'codex_source/payload/game/red4ext/plugins/AiNpcCodexBridge');
  const fixture=resolve(root,'build','startup-fixture-'+Date.now(),'Game with spaces'), backend=resolve(fixture,'red4ext/plugins/AiNpcCodexBridge');
  const addon=resolve(fixture,'bin/x64/plugins/cyber_engine_tweaks/mods/AiNpcCodexBridge'), state=resolve(fixture,'test-state');
  await mkdir(backend,{recursive:true});await mkdir(addon,{recursive:true});await mkdir(state,{recursive:true});
  for(const name of ['start.ps1','bridge-common.ps1','config.example.json'])await copyFile(resolve(source,name),resolve(backend,name));
  const reserve=createServer();reserve.listen(0,'127.0.0.1');await once(reserve,'listening');const port=reserve.address().port;await new Promise(r=>reserve.close(r));
  // Config validates a native executable even with the injected inert runner.
  // Use the already-running Node executable as a marker; never discover or run
  // a developer's installed Codex CLI, and keep clean CI machines independent.
  await writeFile(resolve(state,'config.json'),JSON.stringify({host:'127.0.0.1',port,model:'',reasoning_effort:'low',codex_path:process.execPath}));
  const imports=JSON.stringify(source.replaceAll('\\','/'));
  await writeFile(resolve(backend,'bridge.py'),`import sys,json,argparse,threading\nfrom pathlib import Path\nsys.path.insert(0,${imports})\nimport bridge as implementation\np=argparse.ArgumentParser();p.add_argument('--config',type=Path);p.add_argument('--data-dir',type=Path);p.add_argument('--parent-pid',type=int,required=True);a=p.parse_args()\nc=implementation.Config.load(a.config);c.state_directory=a.data_dir\ns=implementation.BridgeServer(c,runner=object());parent=implementation.WindowsParentLifeline(a.parent_pid)\nt=threading.Thread(target=implementation.watch_parent,args=(s,parent),daemon=True);t.start()\ntry:s.serve_forever(poll_interval=.1)\nfinally:s.stopping.set();t.join(1);parent.close();s.server_close()\n`);
  // Give the implementation a distinct import name; the fixture itself is bridge.py.
  const script=await readFile(resolve(backend,'bridge.py'),'utf8');
  await writeFile(resolve(backend,'bridge.py'),script.replace('import bridge as implementation',`import importlib.util\nspec=importlib.util.spec_from_file_location('actual_codex_bridge',str(Path(${imports})/'bridge.py'));implementation=importlib.util.module_from_spec(spec);sys.modules[spec.name]=implementation;spec.loader.exec_module(implementation)`)
    .replace('s=implementation.BridgeServer',"original_get=implementation.Handler.do_GET\ndef trace_get(self):\n print('fixture GET',self.path,flush=True)\n try:return original_get(self)\n finally:print('fixture GET completed',flush=True)\nimplementation.Handler.do_GET=trace_get\nprint('fixture building server',flush=True)\ns=implementation.BridgeServer")
    .replace('t=threading.Thread',"print('fixture server bound',s.server_address,flush=True)\nt=threading.Thread")
    .replace('try:s.serve_forever',"print('fixture serving',flush=True)\ntry:s.serve_forever"));
  const parent=spawn(process.execPath,['-e','setInterval(()=>{},1000)'],{windowsHide:true,stdio:'ignore'});
  const base='http://127.0.0.1:'+port;
  const hold=setInterval(()=>{},1000);
  try {
    let launchError='';
    const auto=new CodexAutoStart({moduleUrl:pathToFileURL(resolve(addon,'bridge.mjs')).href,parentPid:parent.pid,stateDirectory:state,timeoutMs:10000,
      launch:(command,args,options)=>{const child=spawn(command,args,{...options,stdio:['ignore','ignore','pipe']});child.stderr.on('data',b=>launchError+=b);return child;}});
    console.log('fixture: automatic start');
    await auto.ensure().catch(async e=>{
      const logs=await Promise.all(['server.status.log','server.errors.log'].map(name=>readFile(resolve(state,name),'utf8').catch(()=>'')));
      throw Error(e.message+': '+launchError+'\n'+logs.join('\n'));
    });console.log('fixture: first ready');assert.equal((await(await fetch(base+'/healthz',{signal:AbortSignal.timeout(3000)})).json()).service,'codex-companion-bridge');
    const first=JSON.parse((await readFile(resolve(state,'server.pid.json'),'utf8')).replace(/^\uFEFF/,''));
    await auto.ensure();console.log('fixture: reused');const second=JSON.parse((await readFile(resolve(state,'server.pid.json'),'utf8')).replace(/^\uFEFF/,''));assert.equal(first.pid,second.pid);
    const ended=once(parent,'close');parent.kill();await ended;
    let closed=false;
    for(let i=0;i<30;i++){await new Promise(r=>setTimeout(r,100));try{await fetch(base+'/healthz',{signal:AbortSignal.timeout(300)});}catch{closed=true;break;}}
    assert.equal(closed,true,'Automatic service must end with its owning conversation process');
  } finally {
    // Its lifeline is this fixture's own child, including on assertion failure.
    // The authenticated server correctly rejects an anonymous /shutdown.
    if(parent.exitCode===null){const ended=once(parent,'close',{signal:AbortSignal.timeout(3000)}).catch(()=>{});parent.kill();await ended;}
    clearInterval(hold);
  }
});
