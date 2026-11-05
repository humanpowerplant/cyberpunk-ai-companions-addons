// Expand test files without depending on shell glob behavior on Windows.
import {readdirSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const tests = ['tests', 'codex_source/tests'].flatMap(folder =>
  readdirSync(resolve(root, folder)).filter(name => name.endsWith('.test.mjs'))
    .sort().map(name => resolve(root, folder, name)));
if (!tests.length) throw Error('No Node test files found');
const result = spawnSync(process.execPath, ['--test', ...tests], {
  cwd: root, stdio: 'inherit', windowsHide: true, shell: false,
});
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
