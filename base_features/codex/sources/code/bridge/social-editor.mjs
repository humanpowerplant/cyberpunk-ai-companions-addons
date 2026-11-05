// A small, local editor for V's automatic-reply personality. The parent owns the loopback HTTP server.
import {randomBytes, timingSafeEqual} from 'node:crypto';
import {SOCIAL_PLAYER_LIMITS} from './social-player-profile.mjs';

const STRINGS = {
  ja: {title: 'Vの自発会話と性格', intro: 'Vが仲間の自発会話へ応答する際の性格です。自動応答は初期状態ではオフです。ゲーム内メニューで、必要なときだけ返す設定を選べます。',
    custom: '性格と一人称をここで編集した場合は、ゲーム内の「Vの性格」で「カスタム」を選んでください。大切にすること・背景・避けたいことは他のプリセットにも適用されます。',
    name: '呼び名', firstPerson: '一人称', style: '性格・話し方', values: '大切にしていること', background: 'V自身の背景', avoid: '避けたい話し方・話題',
    save: '保存', reset: '性格を初期値に戻す', saved: '保存しました。次の自動応答から使います。', loading: '読み込み中…', error: '保存できませんでした。',
    resetAsk: 'Vの性格設定を初期値に戻しますか？ 経験の記憶は残ります。', memory: '自発会話用の記憶', memoryNote: 'ここで消すのは、この拡張が持つ記憶だけです。通常の仲間の会話履歴やゲームのセーブは変更しません。',
    forgetPlayer: 'Vの経験記憶を消す', forgetRelations: '仲間同士の関係を初期化', forgetAsk: '選んだ自発会話用の記憶を消しますか？', forgotten: '選んだ記憶を初期化しました。',
    mode: '現在のVの自動応答', off: 'オフ', asked: 'Vへ問いかけられたとき', contextual: 'Vに応答の必要があるとき', chars: '文字',
    footer: '台詞を自動生成しても、ゲーム内の選択・購入・約束の操作は行いません。プレイヤーの発話や操作を優先し、返答が不要なら沈黙します。'},
  en: {title: "V's automatic replies and personality", intro: "This personality is used when V answers spontaneous companion chatter. Automatic replies are off by default. Choose when V may reply in the in-game menu.",
    custom: 'To use the speaking style and first person edited here, choose Custom under V personality in the game menu. Values, background and things to avoid also apply to the other presets.',
    name: 'Name', firstPerson: 'First-person pronoun', style: 'Personality and speaking style', values: 'What matters to V', background: "V's background", avoid: 'Topics or mannerisms to avoid',
    save: 'Save', reset: 'Reset personality', saved: 'Saved. The next automatic reply will use these settings.', loading: 'Loading…', error: 'Could not save.',
    resetAsk: "Reset V's personality to its defaults? Experience memories will remain.", memory: 'Memories for spontaneous conversation', memoryNote: 'These controls only clear memories held by this extension. Normal companion conversation history and game saves are not changed.',
    forgetPlayer: "Clear V's experience memories", forgetRelations: 'Reset companion relationships', forgetAsk: 'Clear the selected spontaneous-conversation memories?', forgotten: 'The selected memories were reset.',
    mode: "V's automatic replies", off: 'Off', asked: 'When directly asked', contextual: 'When a reply from V is needed', chars: 'characters',
    footer: 'Generated speech does not operate game choices, purchases or agreements. Player input takes priority; V stays silent when no reply is needed.'},
};
const escape = text => String(text).replace(/[&<>"']/gu, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const safeJson = value => JSON.stringify(value).replace(/</gu, '\\u003c').replace(/\u2028/gu, '\\u2028').replace(/\u2029/gu, '\\u2029');
const equal = (a, b) => {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  const one = Buffer.from(a), two = Buffer.from(b);
  return one.length === two.length && timingSafeEqual(one, two);
};
const HEADERS = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY',
  'Cross-Origin-Resource-Policy': 'same-origin', 'Cross-Origin-Opener-Policy': 'same-origin'};

export function renderSocialPlayerEditor({language = 'ja', token, nonce} = {}) {
  const lang = language === 'ja' ? 'ja' : 'en', s = STRINGS[lang];
  const fields = ['name', 'firstPerson', 'style', 'values', 'background', 'avoid'].map(key => {
    const input = ['name', 'firstPerson'].includes(key)
      ? `<input id="${key}" name="${key}" maxlength="${SOCIAL_PLAYER_LIMITS[key]}" autocomplete="off" required>`
      : `<textarea id="${key}" name="${key}" maxlength="${SOCIAL_PLAYER_LIMITS[key]}" rows="${key === 'style' || key === 'background' ? 5 : 3}"></textarea>`;
    return `<label for="${key}">${escape(s[key])}<span class="count" id="${key}-count"></span>${input}</label>`;
  }).join('\n');
  return `<!doctype html><html lang="${lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(s.title)}</title>
<style nonce="${escape(nonce)}">:root{color-scheme:dark light;font-family:system-ui,sans-serif}body{max-width:850px;margin:auto;padding:24px;line-height:1.6}h1{font-size:1.5rem}label{display:block;margin:18px 0}input,textarea{display:block;box-sizing:border-box;width:100%;font:inherit;padding:9px;margin-top:5px}textarea{resize:vertical}.count{float:right;font-size:.8rem;opacity:.75}button{font:inherit;padding:9px 16px;min-height:44px}button+button{margin-left:8px}.actions{display:flex;flex-wrap:wrap;gap:8px}.actions button+button{margin-left:0}.note{opacity:.8}#result{min-height:1.6em}hr{margin:28px 0}a{color:inherit}button:disabled{opacity:.5}@media(max-width:500px){body{padding:14px}.actions button{width:100%}}</style></head><body>
<h1>${escape(s.title)}</h1><p>${escape(s.intro)}</p><p class="note">${escape(s.custom)}</p><p id="mode">${escape(s.loading)}</p>
<form id="profile-form">${fields}<div class="actions"><button type="submit">${escape(s.save)}</button><button type="button" id="reset">${escape(s.reset)}</button></div></form>
<p id="result" role="status" aria-live="polite"></p><hr><h2>${escape(s.memory)}</h2><p class="note">${escape(s.memoryNote)}</p><div class="actions"><button type="button" id="forget-player">${escape(s.forgetPlayer)}</button><button type="button" id="forget-relations">${escape(s.forgetRelations)}</button></div><p class="note">${escape(s.footer)}</p>
<script nonce="${escape(nonce)}">(()=>{'use strict';const strings=${safeJson(s)},token=${safeJson(token)},limits=${safeJson(SOCIAL_PLAYER_LIMITS)};const fields=['name','firstPerson','style','values','background','avoid'];const get=id=>document.getElementById(id);const result=get('result');let busy=false;
const count=()=>{for(const k of fields)get(k+'-count').textContent=Array.from(get(k).value).length+' / '+limits[k]+' '+strings.chars;};
const show=p=>{for(const k of fields)get(k).value=typeof p[k]==='string'?p[k]:'';count();};
const request=async(path,method='GET',body)=>{const r=await fetch('/social-player/'+path,{method,headers:{'x-social-token':token,...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body),credentials:'same-origin'});const d=await r.json();if(!r.ok)throw new Error(d.error||'request-failed');return d;};
const work=async fn=>{if(busy)return;busy=true;for(const b of document.querySelectorAll('button'))b.disabled=true;try{await fn();}catch(e){result.textContent=strings.error+' ('+e.message+')';}finally{busy=false;for(const b of document.querySelectorAll('button'))b.disabled=false;}};
get('profile-form').addEventListener('input',count);get('profile-form').addEventListener('submit',e=>{e.preventDefault();void work(async()=>{const p=Object.fromEntries(fields.map(k=>[k,get(k).value]));show((await request('profile','PUT',p)).profile);result.textContent=strings.saved;});});
get('reset').addEventListener('click',()=>{if(confirm(strings.resetAsk))void work(async()=>{show((await request('reset','POST',{})).profile);result.textContent=strings.saved;});});
for(const [id,kind]of[['forget-player','player'],['forget-relations','relationships']])get(id).addEventListener('click',()=>{if(confirm(strings.forgetAsk))void work(async()=>{await request('forget','POST',{kind});result.textContent=strings.forgotten;});});
void work(async()=>{show((await request('profile')).profile);const d=await request('status');get('mode').textContent=strings.mode+': '+(strings[d.replyMode]||strings.off);});})();</script></body></html>`;
}

const body = async request => {
  if (!/^application\/json(?:\s*;|$)/iu.test(request.headers?.['content-type'] ?? '')) throw Object.assign(Error('bad-content-type'), {status: 415});
  let bytes = 0; const chunks = [];
  for await (const chunk of request) { const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk); bytes += buffer.length; if (bytes <= 32_000) chunks.push(buffer); }
  if (bytes > 32_000) throw Object.assign(Error('too-large'), {status: 413});
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { throw Object.assign(Error('bad-json'), {status: 400}); }
};

export function createSocialEditor({profiles, memory = null, settings = () => ({}), token = randomBytes(24).toString('base64url'), log = () => {}} = {}) {
  if (!profiles || !equal(token, token) || token.length < 24) throw Error('Social editor needs profiles and a session token.');
  const send = (res, status, value) => {
    const text = JSON.stringify(value);
    res.writeHead(status, {'Content-Type': 'application/json; charset=utf-8', 'Content-Length': Buffer.byteLength(text), ...HEADERS}); res.end(text);
  };
  return {
    pagePath({language = 'ja'} = {}) { return '/social-player?t=' + encodeURIComponent(token) + '&lang=' + (language === 'ja' ? 'ja' : 'en'); },
    async handle(req, res, suppliedUrl) {
      let url;
      try { url = suppliedUrl instanceof URL ? suppliedUrl : new URL(req.url, 'http://' + req.headers?.host); } catch { return false; }
      if (url.pathname !== '/social-player' && !url.pathname.startsWith('/social-player/')) return false;
      const host = req.headers?.host, match = typeof host === 'string' ? /^127\.0\.0\.1:(\d{1,5})$/u.exec(host) : null;
      const port = match ? Number(match[1]) : 0;
      const remote = req.socket?.remoteAddress;
      if (!match || port < 1024 || port > 65535 || (req.socket?.localPort && req.socket.localPort !== port)
        || (remote && !['127.0.0.1', '::1', '::ffff:127.0.0.1'].includes(remote)) || url.origin !== 'http://' + host) { send(res, 403, {error: 'forbidden'}); return true; }
      const origin = 'http://' + host;
      if ((req.headers.origin && req.headers.origin !== origin) || (req.headers['sec-fetch-site'] && !['same-origin', 'none'].includes(req.headers['sec-fetch-site']))) { send(res, 403, {error: 'forbidden'}); return true; }
      if (req.method === 'GET' && url.pathname === '/social-player') {
        if (!equal(url.searchParams.get('t'), token)) { send(res, 404, {error: 'not-found'}); return true; }
        const nonce = randomBytes(18).toString('base64url');
        const html = renderSocialPlayerEditor({language: url.searchParams.get('lang') === 'ja' ? 'ja' : 'en', token, nonce});
        res.writeHead(200, {'Content-Type': 'text/html; charset=utf-8', ...HEADERS, 'Content-Security-Policy': `default-src 'none'; script-src 'nonce-${nonce}'; style-src 'nonce-${nonce}'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`}); res.end(html); return true;
      }
      if (!equal(req.headers['x-social-token'], token)) { send(res, 401, {error: 'unauthorized'}); return true; }
      try {
        if (req.method === 'GET' && url.pathname === '/social-player/profile') send(res, 200, {profile: profiles.get(), limits: SOCIAL_PLAYER_LIMITS});
        else if (req.method === 'GET' && url.pathname === '/social-player/status') {
          const current = typeof settings === 'function' ? settings() : settings;
          const replyMode = ['asked', 'contextual'].includes(current?.socialVReplies) ? current.socialVReplies : 'off';
          send(res, 200, {replyMode, memoryAvailable: !!memory});
        } else if (req.method === 'PUT' && url.pathname === '/social-player/profile') send(res, 200, {profile: await profiles.update(await body(req))});
        else if (req.method === 'POST' && url.pathname === '/social-player/reset') {
          const data = await body(req); if (!data || Array.isArray(data) || Object.keys(data).length) throw Object.assign(Error('bad-request'), {status: 400});
          send(res, 200, {profile: await profiles.reset()});
        } else if (req.method === 'POST' && url.pathname === '/social-player/forget') {
          const data = await body(req);
          if (!data || Object.keys(data).some(key => key !== 'kind') || !['player', 'relationships', 'all'].includes(data.kind)) throw Object.assign(Error('bad-request'), {status: 400});
          if (!memory || typeof memory.clear !== 'function') throw Object.assign(Error('unavailable'), {status: 503});
          const accepted = await memory.clear({kind: data.kind});
          if (!accepted) throw Object.assign(Error('unavailable'), {status: 503});
          if (typeof memory.flush === 'function' && !await memory.flush()) throw Object.assign(Error('not-saved'), {status: 500});
          send(res, 200, {ok: true});
        } else send(res, 405, {error: 'method-not-allowed'});
      } catch (error) {
        const status = error?.code === 'invalid' ? 422 : (error?.status ?? 500);
        if (status === 500) log('Social editor request failed.');
        send(res, status, {error: error?.code === 'invalid' ? 'invalid' : status === 500 ? 'not-saved' : error.message, ...(error?.errors ? {errors: error.errors} : {})});
      }
      return true;
    },
  };
}
