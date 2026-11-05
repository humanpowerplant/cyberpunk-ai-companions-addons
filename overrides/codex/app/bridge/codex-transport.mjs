// Optional local Codex add-on: never intercept other providers or remote hosts.
const helperUrl = new URL('../../../../../bin/x64/plugins/cyber_engine_tweaks/mods/AiNpcCodexBridge/codex-connection.mjs', import.meta.url);
const starterUrl = new URL('./auto-start.mjs', helperUrl);
let helper, starter;
const loadStarter = async () => starter ??= new (await import(starterUrl.href)).CodexAutoStart();
const completionPaths = new Set(['/v1/chat/completions', '/chat/completions']);
const cancelled = signal => {if (signal?.aborted) throw signal.reason ?? Object.assign(Error('Conversation cancelled'), {name:'AbortError'});};
async function waitForStart(pending, signal) {
  if (!signal) return pending;
  cancelled(signal);
  let abort;
  try { return await Promise.race([pending, new Promise((_,reject) => {
    abort = () => {try {cancelled(signal);} catch(error) {reject(error);}};
    signal.addEventListener('abort',abort,{once:true});if(signal.aborted)abort();
  })]); } finally {signal.removeEventListener('abort',abort);}
}
export function codexTransport(fetchImpl, provider, {load = () => helper ??= import(helperUrl.href), start = loadStarter} = {}) {
  if (provider !== 'custom') return fetchImpl;
  return async (url, options) => {
    let parsed;
    try { parsed = new URL(url); } catch { return fetchImpl(url, options); }
    if (parsed.protocol !== 'http:' || parsed.hostname !== '127.0.0.1' || parsed.username || parsed.password || parsed.search || parsed.hash
      || !completionPaths.has(parsed.pathname)) return fetchImpl(url, options);
    let api;
    try { api = await load(); } catch (error) {
      if (error?.code === 'ERR_MODULE_NOT_FOUND' && parsed.origin !== 'http://127.0.0.1:17865') return fetchImpl(url, options);
      throw Error('Codex connection helper is unavailable; reinstall the Party/Codex add-on.');
    }
    let connection = await api.readConnection();
    let target = api.remapCodexUrl(url, connection);
    if (new URL(target).origin !== connection.origin) return fetchImpl(url, options);
    let started = false;
    const ensure = async () => {
      cancelled(options?.signal);
      const service = await start();
      await waitForStart(service.ensure(), options?.signal);started = true;
      cancelled(options?.signal);
      connection = await api.readConnection();target = api.remapCodexUrl(url, connection);
      if (!connection.token || new URL(target).origin !== connection.origin) throw Error('Codex bridge connection changed or is not ready; retry after checking its settings.');
    };
    if (!connection.token) await ensure();
    cancelled(options?.signal);
    const send = async () => {
      cancelled(options?.signal);
      // Prove the listener knows the local secret without ever transmitting it.
      // Recheck before every Bearer request; do not cache an identity by port.
      await api.verifyConnection(connection, {request:fetchImpl, signal:options?.signal});
      cancelled(options?.signal);
      return fetchImpl(target, api.codexRequestOptions(target, options, connection));
    };
    try { return await send(); }
    catch (error) {
      // Only a refused TCP connection proves that no request was accepted.
      // Do not replay a sent completion, HTTP 401, timeout or partial stream.
      if (started || error?.cause?.code !== 'ECONNREFUSED') throw error;
      await ensure();
      return send();
    }
  };
}
