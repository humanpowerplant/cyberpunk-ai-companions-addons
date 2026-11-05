// Official AI Companions 1.1 settings hook. No conversation/provider hooks.
import {readFileSync} from 'node:fs';
import {mkdir, rename, writeFile} from 'node:fs/promises';
import {CodexAutoStart} from './auto-start.mjs';
import {readConnection, codexRequestOptions, verifyConnection} from './codex-connection.mjs';

export const apiVersion = '1.1';
const mapping = JSON.parse(readFileSync(new URL('./settings-map.json', import.meta.url), 'utf8'));
const runtime = new URL('./runtime/', import.meta.url);
const statusPath = new URL('./status.json', runtime);
const temporaryPath = new URL('./status.tmp.json', runtime);
const automaticService = new CodexAutoStart({moduleUrl: import.meta.url});

export function decodeSettings(values = {}, connection = {}) {
  const modelIndex = values.model ?? mapping.defaults.model;
  const effortIndex = values.reasoning ?? mapping.defaults.reasoning;
  if (!Number.isInteger(modelIndex) || !mapping.models[modelIndex - 1]
      || !Number.isInteger(effortIndex) || !mapping.efforts[effortIndex - 1]) {
    throw Error('invalid selection');
  }
  const model = mapping.models[modelIndex - 1], reasoningEffort = mapping.efforts[effortIndex - 1];
  if (!model.reasoningEfforts?.includes(reasoningEffort)) throw Error('model or effort unsupported');
  const id = model.id === 'config-model' ? connection.configuredModel : model.id;
  if (typeof id !== 'string' || !/^[A-Za-z0-9_.-]{1,100}$/.test(id)) throw Error('invalid local bridge configuration');
  return {model: id, reasoningEffort};
}

async function saveStatus(value) {
  await mkdir(runtime, {recursive: true});
  await writeFile(temporaryPath, JSON.stringify({version: 1, updated: Date.now(), ...value}, null, 2) + '\n', 'utf8');
  await rename(temporaryPath, statusPath);
}

async function control(settings, request, connection) {
  const endpoint = connection.origin + '/codex/settings';
  if (!connection.token) throw Error('local bridge credential unavailable');
  await verifyConnection(connection, {request});
  const response = await request(endpoint, codexRequestOptions(endpoint, {
    method: settings ? 'POST' : 'GET', redirect: 'error', signal: AbortSignal.timeout(2500),
    ...(settings ? {headers: {'Content-Type': 'application/json'}, body: JSON.stringify(settings)} : {})
  }, connection));
  const raw = await response.text();
  if (raw.length > 16384) throw Error('invalid bridge response');
  let value;
  try { value = JSON.parse(raw); } catch { throw Error('invalid bridge response'); }
  if (!response.ok) {
    if (response.status === 401) throw Error('local bridge credential unavailable');
    if (response.status === 422) throw Error('model or effort unsupported');
    throw Error('bridge rejected settings');
  }
  if (value.status !== 'ok' || typeof value.model !== 'string' || !/^[A-Za-z0-9_.-]{1,100}$/.test(value.model)
      || !mapping.efforts.includes(value.reasoningEffort)) throw Error('invalid bridge response');
  return {state: settings ? 'applied' : 'ready', model: value.model, reasoningEffort: value.reasoningEffort};
}

function selection(values) {
  return Object.hasOwn(values, 'model') || Object.hasOwn(values, 'reasoning')
    ? JSON.stringify([values.model ?? mapping.defaults.model, values.reasoning ?? mapping.defaults.reasoning]) : 'unsaved';
}

async function health(request, connection) {
  const value = await verifyConnection(connection, {request});
  if (typeof value.model !== 'string' || !/^[A-Za-z0-9_.-]{1,100}$/.test(value.model) || !mapping.efforts.includes(value.reasoningEffort)) {
    throw Object.assign(Error('invalid bridge response'), {identityMismatch: true});
  }
  return value;
}

/** One in-flight settings/readiness operation; periodic healthy checks never launch PowerShell or the CLI. */
export function createSettingsController({autoStart = automaticService, request = (...args) => fetch(...args), persist = saveStatus,
  connectionFor = readConnection, setTimer = setTimeout, clearTimer = clearTimeout, retryMs = 30000} = {}) {
  let log = () => {}, pending, desired = null, pumping = false, active = false, healthy = false, lastSelection;
  let timer = null, revision = 0, work = Promise.resolve();
  const clear = () => { if (timer !== null) clearTimer(timer); timer = null; };
  const current = row => active && row.revision === revision;
  const arm = () => {
    clear(); if (!active) return;
    timer = setTimer(() => { timer = null; schedule(desired, true); }, retryMs);
    timer?.unref?.();
  };
  async function pump() {
    try {
      while (active && pending !== undefined) {
        const row = pending; pending = undefined;
        try {
          let connection = await connectionFor();
          const settings = row.values === null ? null : decodeSettings(row.values, connection);
          let observed;
          try { observed = await health(request, connection); }
          catch (error) {
            if (error?.identityMismatch || !current(row)) throw error;
            healthy = false;
            if (!row.explicit || row.periodic) {
              await persist({state: 'idle'});
              continue;
            }
            await autoStart.ensure();
            if (!current(row)) continue;
            connection = await connectionFor();
            observed = await health(request, connection);
          }
          if (!current(row)) continue;
          const matches = settings && observed.model === settings.model && observed.reasoningEffort === settings.reasoningEffort;
          const status = row.periodic && healthy && (!settings || matches)
            ? {state: settings ? 'applied' : 'ready', model: observed.model, reasoningEffort: observed.reasoningEffort}
            : await control(settings, request, connection);
          if (observed.instruction_home === 'legacy-shared') status.warning = 'legacy_shared_codex_home';
          if (!current(row)) continue;
          await persist(status); if (!current(row)) continue;
          healthy = true; log(`Last check: ${status.state} ${status.model}/${status.reasoningEffort}`);
        } catch (error) {
          if (!current(row)) continue;
          healthy = false;
          const known = ['invalid selection', 'model or effort unsupported', 'bridge rejected settings', 'invalid bridge response',
            'old bridge restart required', 'local bridge credential unavailable', 'invalid local bridge configuration', 'invalid local bridge credential'];
          known.push('local bridge proof rejected');
          const message = known.includes(error?.message) ? error.message : 'bridge unavailable';
          try { await persist({state: 'error', message, errorCode: message.replaceAll(' ', '_')}); } catch { /* mod folder may be read-only */ }
          if (current(row) && !row.periodic) log(`Last check failed: ${message}`);
        }
      }
    } finally { pumping = false; arm(); }
  }
  function schedule(values, periodic = false, explicit = false) {
    if (!active) return;
    clear(); pending = {values: values === null ? null : {...values}, periodic, explicit, revision};
    if (pumping) return;
    // The host permits synchronous hooks only; network and startup work begins after the hook returns.
    pumping = true; work = Promise.resolve().then(pump).catch(() => log('Last check failed: status write failed'));
  }
  return {
    activate(ctx) {
      active = true; healthy = false; revision++;
      log = typeof ctx.log === 'function' ? ctx.log : log;
      const saved = ctx.settings(); lastSelection = selection(saved);
      // No saved selection means read-only checking, including on later recovery.
      desired = Object.hasOwn(saved, 'model') || Object.hasOwn(saved, 'reasoning') ? {...saved} : null;
      schedule(desired);
    },
    onSettings(values) {
      const next = selection(values); if (next === lastSelection) return;
      lastSelection = next; revision++;
      desired = Object.hasOwn(values, 'model') || Object.hasOwn(values, 'reasoning') ? {...values} : null;
      schedule(desired, false, true);
    },
    close() { active = false; revision++; pending = undefined; clear(); },
    whenIdle: () => work,
  };
}

const controller = createSettingsController();
export function activate(ctx) { controller.activate(ctx); }
export function onSettings(values) { controller.onSettings(values); }
export function deactivate() { controller.close(); }
process.once('beforeExit', deactivate);
