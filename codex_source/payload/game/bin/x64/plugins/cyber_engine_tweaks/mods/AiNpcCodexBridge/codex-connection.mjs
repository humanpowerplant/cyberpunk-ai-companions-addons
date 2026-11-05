// The local transport credential is not a Codex login/API credential.
// Keep this module out of prompts, status files and diagnostic output.
import {open} from 'node:fs/promises';
import {homedir} from 'node:os';
import {randomBytes, createHmac, timingSafeEqual} from 'node:crypto';
import path from 'node:path';

const DEFAULT_ORIGIN = 'http://127.0.0.1:17865';
const PATHS = new Set(['/healthz', '/codex/settings', '/shutdown', '/v1/models', '/models', '/v1/chat/completions', '/chat/completions']);

async function readSmallJson(file, limit) {
  const handle = await open(file, 'r');
  try {
    const stat = await handle.stat();
    if (!stat.isFile() || stat.size > limit) throw Error('invalid local bridge configuration');
    const data = Buffer.alloc(limit + 1);
    const {bytesRead} = await handle.read(data, 0, data.length, 0);
    if (bytesRead > limit) throw Error('invalid local bridge configuration');
    return JSON.parse(data.subarray(0, bytesRead).toString('utf8').replace(/^\uFEFF/, ''));
  } finally { await handle.close(); }
}

export async function readConnection({stateDirectory = path.join(process.env.LOCALAPPDATA || path.join(homedir(), '.local', 'state'), 'AiNpcCodexBridge')} = {}) {
  let config = {};
  try { config = await readSmallJson(path.join(stateDirectory, 'config.json'), 16384); }
  catch (error) { if (error?.code !== 'ENOENT') throw Error('invalid local bridge configuration'); }
  const port = config.port ?? 17865;
  if ((config.host ?? '127.0.0.1') !== '127.0.0.1' || !Number.isInteger(port) || port < 1024 || port > 65535) {
    throw Error('invalid local bridge configuration');
  }
  if (config.model !== undefined && (typeof config.model !== 'string' || (config.model !== '' && !/^[A-Za-z0-9_.-]{1,100}$/.test(config.model)))) {
    throw Error('invalid local bridge configuration');
  }
  let token = '';
  try {
    const value = await readSmallJson(path.join(stateDirectory, 'local-token.json'), 1024);
    if (value?.schema !== 1 || typeof value.token !== 'string' || !/^[a-f0-9]{64}$/.test(value.token)) throw Error();
    token = value.token;
  } catch (error) {
    if (error?.code !== 'ENOENT') throw Error('invalid local bridge credential');
  }
  const origin = `http://127.0.0.1:${port}`;
  return {origin, baseUrl: `${origin}/v1`, token, configuredModel: config.model || 'codex-default'};
}

function match(url, connection) {
  try {
    const value = new URL(url);
    return !value.username && !value.password && !value.search && !value.hash && value.origin === connection.origin && PATHS.has(value.pathname);
  } catch { return false; }
}

// Only the shipped default Codex endpoint is remapped. An explicit unrelated
// Custom provider URL, including another loopback port, is left untouched.
export function remapCodexUrl(url, connection) {
  try {
    const value = new URL(url);
    if (!value.username && !value.password && !value.search && !value.hash && value.origin === DEFAULT_ORIGIN && PATHS.has(value.pathname)) {
      return connection.origin + value.pathname;
    }
  } catch {}
  return url;
}

export function codexRequestOptions(url, options = {}, connection) {
  if (!connection || !match(url, connection)) return options;
  const headers = new Headers(options.headers);
  // Preserve an explicit credential rather than overwrite or send it elsewhere.
  if (connection.token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${connection.token}`);
  return {...options, headers, redirect: 'error'};
}

async function boundedResponse(response, limit = 16384) {
  if (!response.body?.getReader) {
    const text = await response.text();
    if (text.length > limit) throw Error('invalid bridge response');
    return JSON.parse(text);
  }
  const reader = response.body.getReader(), chunks = []; let length = 0;
  try {
    while (true) {
      const {value, done} = await reader.read(); if (done) break;
      length += value.byteLength;
      if (length > limit) { await reader.cancel(); throw Error('invalid bridge response'); }
      chunks.push(Buffer.from(value));
    }
    return JSON.parse(Buffer.concat(chunks, length).toString('utf8'));
  } finally { reader.releaseLock(); }
}

// A service name is self-reported. Prove possession before disclosing Bearer.
// A fresh challenge is required immediately before each authenticated request.
export async function verifyConnection(connection, {request = (...args) => fetch(...args), signal} = {}) {
  const nonce = randomBytes(32).toString('hex');
  const response = await request(connection.origin + '/healthz', {headers:{'X-AiNpc-Challenge':nonce},
    redirect:'error', signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(2500)]) : AbortSignal.timeout(2500)});
  let value;
  try { value = await boundedResponse(response); }
  catch { throw Object.assign(Error('invalid bridge response'), {identityMismatch:true}); }
  if (!response.ok || value?.status !== 'ok' || value.service !== 'codex-companion-bridge' || value.version !== 1 || value.auth_mode !== 'chatgpt') {
    throw Object.assign(Error('invalid bridge response'), {identityMismatch:true});
  }
  if (value.local_auth !== 'bearer-v1') throw Object.assign(Error('old bridge restart required'), {identityMismatch:true});
  if (!connection.token) throw Object.assign(Error('local bridge credential unavailable'), {identityMismatch:true});
  const expected = createHmac('sha256', connection.token).update(`AiNpcCodexBridge/bearer-v1\n${new URL(connection.origin).port}\n${nonce}`).digest();
  if (typeof value.local_auth_proof !== 'string' || !/^[a-f0-9]{64}$/.test(value.local_auth_proof)
      || !timingSafeEqual(expected, Buffer.from(value.local_auth_proof,'hex'))) {
    throw Object.assign(Error('local bridge proof rejected'), {identityMismatch:true});
  }
  return value;
}
