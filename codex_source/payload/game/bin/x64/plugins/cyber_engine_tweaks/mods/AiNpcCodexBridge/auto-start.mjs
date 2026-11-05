// Runs from the official add-on lifecycle, without delaying its synchronous activation.
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

export class CodexAutoStart {
  constructor({moduleUrl = import.meta.url, parentPid = process.pid, platform = process.platform, launch = spawn, timeoutMs = 24000, stateDirectory} = {}) {
    Object.assign(this, {parentPid, platform, launch, timeoutMs, stateDirectory});
    this.script = fileURLToPath(new URL('../../../../../../red4ext/plugins/AiNpcCodexBridge/start.ps1', moduleUrl));
    this.pending = null;
  }
  ensure() {
    if (this.pending) return this.pending;
    if (this.platform !== 'win32') return Promise.reject(Error('automatic startup requires Windows'));
    this.pending = new Promise((resolve, reject) => {
      let child, timer, settled = false;
      const finish = error => {
        if (settled) return;
        settled = true; clearTimeout(timer);
        error ? reject(error) : resolve();
      };
      try {
        child = this.launch('powershell.exe', ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', this.script,
          ...(this.stateDirectory ? ['-StateDirectory', this.stateDirectory] : []),
          '-ParentProcessId', String(this.parentPid)], {windowsHide: true, stdio: 'ignore'});
        child.once('error', () => finish(Error('automatic startup failed')));
        // Wait for the launcher, not any pipe handle inherited by its server.
        child.once('exit', code => finish(code === 0 ? null : Error('automatic startup failed')));
        timer = setTimeout(() => { child.kill(); finish(Error('automatic startup timed out')); }, this.timeoutMs);
        timer.unref?.();
      } catch { finish(Error('automatic startup failed')); }
    }).finally(() => {this.pending = null;});
    return this.pending;
  }
}
