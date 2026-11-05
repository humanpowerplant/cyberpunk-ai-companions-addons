import test from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {CodexAutoStart} from '../codex_source/payload/game/bin/x64/plugins/cyber_engine_tweaks/mods/AiNpcCodexBridge/auto-start.mjs';

test('official add-on startup uses the deployed script, hides its window, and joins concurrent startup requests', async () => {
  const child = new EventEmitter(), calls = [];
  const fakeRoot = 'C' + ':\\Game with spaces';
  const auto = new CodexAutoStart({moduleUrl: 'file:///C:/Game%20with%20spaces/bin/x64/plugins/cyber_engine_tweaks/mods/AiNpcCodexBridge/bridge.mjs',
    parentPid: 456, platform: 'win32', launch: (...args) => {calls.push(args); return child;}});
  const a = auto.ensure(), b = auto.ensure(); assert.equal(a, b); assert.equal(calls.length, 1);
  const [command, args, options] = calls[0];
  assert.equal(command, 'powershell.exe'); assert.equal(options.windowsHide, true); assert.equal(options.stdio, 'ignore');
  assert.ok(args.includes(fakeRoot + '\\red4ext\\plugins\\AiNpcCodexBridge\\start.ps1'));
  assert.deepEqual(args.slice(-2), ['-ParentProcessId', '456']);
  child.emit('exit', 0); await a; assert.equal(auto.pending, null);
});

test('a failed launch is reported and a later settings update may retry', async () => {
  const children = [], auto = new CodexAutoStart({platform: 'win32', launch: () => {const c=new EventEmitter();children.push(c);return c;}});
  const first=auto.ensure(); children[0].emit('exit', 1); await assert.rejects(first, /startup failed/);
  const second=auto.ensure(); children[1].emit('exit', 0); await second; assert.equal(children.length, 2);
});

test('a stalled startup terminates only its own launcher and releases the pending state', async () => {
  let killed=0;const child=new EventEmitter();child.kill=()=>{killed++;};
  const auto = new CodexAutoStart({platform:'win32',timeoutMs:15,launch:()=>child});
  const keepAlive=setTimeout(()=>{},100);
  try {await assert.rejects(auto.ensure(), /timed out/);assert.equal(killed,1);assert.equal(auto.pending,null);}
  finally {clearTimeout(keepAlive);}
});
