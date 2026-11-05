// Compose optional community payloads in memory. The Vortex-owned Code tree is read-only.
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';

const CODE = 'red4ext/plugins/AiNpcCyberpunkCode/app/';
const CET = 'bin/x64/plugins/cyber_engine_tweaks/mods/AiNpcCyberpunkMod/';
const FEATURES = Object.freeze({codex: 'AiNpcCodexBridge', japanese: 'AiNpcJapaneseOptimization'});
const PREFIXES = ['bridge/', 'launcher/', 'assets/', 'characters/', 'research/', 'vision/', 'licenses/client/'];
const FILES = ['package.json', 'defaults/characters.json', 'defaults/multilingual-profiles.json', 'defaults/runtime-code-files.json'];
const DIGEST = /^[0-9a-f]{64}$/;
const RELEASE_FAMILY = 'companion-addons-046-rc1';
const PAIRING = Object.freeze({codex: '1.2.2-rc.1', japanese: '1.0.4-rc.1'});
const plain = value => !!value && typeof value === 'object' && !Array.isArray(value);
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const encode = value => Buffer.from(JSON.stringify(value, null, 2) + '\n');
const safe = rel => typeof rel === 'string' && rel.length > 0 && rel.length <= 300 && !/[\x00-\x1f\\:*?"<>|]/.test(rel)
  && !rel.startsWith('/') && rel.split('/').every(part => part && part !== '.' && part !== '..' && !/[. ]$/.test(part) && !/~\d/.test(part)
    && !/^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)/i.test(part));
const isCode = rel => safe(rel) && (FILES.includes(rel) || PREFIXES.some(prefix => rel.startsWith(prefix)));
const fail = (message, code = 'COMMUNITY_FEATURE_INVALID') => { throw Object.assign(Error(message), {code}); };
const diagnosticCode = rel => /^(?:bridge|launcher|assets)\//.test(rel) && /\.(?:mjs|cjs|js|py)$/i.test(rel)
  && !rel.split('/').some(part => ['node_modules', '__pycache__'].includes(part));

/** Existing Japanese overlay semantics: character identifiers and unrelated fields stay untouched. */
export function profileOverlay(original, overlay) {
  const rows = JSON.parse(original.toString('utf8').replace(/^\uFEFF/, ''));
  if (!Array.isArray(rows) || !plain(overlay) || !Array.isArray(overlay.profiles)) fail('Invalid Japanese character overlay.');
  const byKey = new Map(rows.map(row => [row.key, row]));
  const fields = new Set(['summary', 'backstory', 'speakingStyleDescription', 'speakingStyleSampleDialogues', 'rules']);
  for (const item of overlay.profiles) {
    const target = byKey.get(item?.profileKey);
    if (!target || !plain(item.fields) || !plain(item.expectedFieldSha256)) fail('Unknown character or invalid fields in the Japanese overlay.');
    for (const [name, value] of Object.entries(item.fields)) {
      if (!fields.has(name)) fail('Overlay tries to change a character identifier.');
      if (sha(Buffer.from(JSON.stringify(target[name] ?? null))) !== item.expectedFieldSha256[name]) fail('A base character field was changed.', 'COMMUNITY_BASE_CHANGED');
      target[name] = value;
    }
  }
  return encode(rows);
}

/**
 * Returns a complete manifest and synchronous sourceFor(appRelativePath) -> Buffer.
 * Only auto-feature.json opts in; the older feature.json/Apply state is never consulted.
 * No file is created, changed or deleted here. installCode retains its all-sources preflight.
 */
export function composeCommunityCode({codeRoot, manifest, read = readFileSync} = {}) {
  if (typeof codeRoot !== 'string' || !plain(manifest) || manifest.version !== 1 || manifest.package !== 'scripts-code'
    || manifest.release !== '0.4.6' || !Array.isArray(manifest.files)) fail('Community add-ons require the original AI Companions 0.4.6 Code manifest.', 'COMMUNITY_BASE_CHANGED');
  const base = new Map();
  const aliases = new Map();
  for (const row of manifest.files) {
    if (!plain(row) || !isCode(row.path) || !Number.isSafeInteger(row.size) || row.size < 0 || !DIGEST.test(row.sha256 ?? '') || base.has(row.path)) fail('The base Code manifest is malformed.', 'COMMUNITY_BASE_CHANGED');
    if (aliases.has(row.path.toLowerCase())) fail('Case-insensitive aliases in the base Code manifest.', 'COMMUNITY_BASE_CHANGED');
    aliases.set(row.path.toLowerCase(), row.path);base.set(row.path, {...row});
  }
  const readBytes = (file, max = 64 * 1024 * 1024) => {
    const bytes = read(file);
    if (!Buffer.isBuffer(bytes) || bytes.length > max) fail('A community source file is invalid or too large.');
    return bytes;
  };
  const features = [];
  let baseManifestBytes;
  for (const [id, folder] of Object.entries(FEATURES)) {
    const directory = resolve(codeRoot, '..', folder), descriptorPath = resolve(directory, 'auto-feature.json');
    let bytes;
    try { bytes = readBytes(descriptorPath, 4 * 1024 * 1024); } catch (error) { if (error?.code === 'ENOENT') continue; throw error; }
    let value; try { value = JSON.parse(bytes.toString('utf8').replace(/^\uFEFF/, '')); } catch { fail('A community auto-feature.json is damaged: ' + id); }
    if (!plain(value) || value.schema !== 1 || value.id !== id || value.upstreamRelease !== '0.4.6'
      || !Array.isArray(value.files) || value.files.length > 1000 || (value.combinations !== undefined && !plain(value.combinations))) fail('Unsupported community auto-feature.json: ' + id);
    if (value.baseManifestSha256 !== undefined) {
      if (!DIGEST.test(value.baseManifestSha256)) fail('Invalid base manifest fingerprint: ' + id);
      baseManifestBytes ??= readBytes(resolve(codeRoot, 'code.json'), 4 * 1024 * 1024);
      if (sha(baseManifestBytes) !== value.baseManifestSha256) fail('The Code manifest was modified by an older manual patch. Deploy the original 0.4.6 Code baseline supplied with this add-on before starting.', 'COMMUNITY_BASE_CHANGED');
    }
    features.push({...value, directory});
  }
  const baseSource = rel => {
    if (!isCode(rel)) fail('A source path is outside the Code set.');
    return readBytes(resolve(codeRoot, 'app', ...rel.split('/')));
  };
  if (!features.length) return {manifest, sourceFor: baseSource, features: []};
  // A combined recipe is only valid for the exact pair it was built with.
  // In particular an older combined payload must never override a newer peer.
  const incompatible = features.some(feature => feature.releaseFamily !== RELEASE_FAMILY || feature.release !== PAIRING[feature.id]
    || !plain(feature.supportedPairing) || Object.entries(PAIRING).some(([id, release]) => feature.supportedPairing[id] !== release));
  if (incompatible) return {manifest, sourceFor: baseSource, features: [], diagnostics: [{code: 'COMMUNITY_PAIRING_INCOMPATIBLE',
    message: 'Community add-ons disabled: update Japanese and Party/Codex packages to the same release family, then Deploy with the newer shared loader winning. The original 0.4.6 code will run.'}]};
  const chosen = new Map(), collisions = new Set();
  const rowFor = (row, owner) => {
    if (!plain(row) || typeof row.path !== 'string') fail('A community recipe row is malformed.');
    if (row.path.startsWith(CET)) return null; // The shared Lua shim owns these private variants.
    if (!row.path.startsWith(CODE) || !isCode(row.path.slice(CODE.length))) fail('A community recipe target is outside the Code set.');
    const rel = row.path.slice(CODE.length), canonical = aliases.get(rel.toLowerCase());
    if (canonical && canonical !== rel) fail('Case-insensitive community Code target alias: ' + rel);
    aliases.set(rel.toLowerCase(), rel);
    if (!safe(row.source) || !row.source.startsWith('payload/') || !DIGEST.test(row.sha256 ?? '') || !DIGEST.test(row.outputSha256 ?? '')
      || !(row.baseSha256 === null || DIGEST.test(row.baseSha256 ?? '')) || ![undefined, 'profile-overlay'].includes(row.transform)) fail('A community Code recipe is malformed: ' + row.path);
    return {...row, rel: row.path.slice(CODE.length), owner};
  };
  for (const feature of features) {
    const own = new Set();
    for (const value of feature.files) {
      const row = rowFor(value, feature.directory); if (!row) continue;
      if (own.has(row.rel)) fail('Duplicate Code recipe target: ' + row.rel); own.add(row.rel);
      if (chosen.has(row.rel) && chosen.get(row.rel).outputSha256 !== row.outputSha256) collisions.add(row.rel);
      else chosen.set(row.rel, row);
    }
  }
  const combination = features.map(feature => feature.id).sort().join('+'), combined = new Map();
  for (const feature of features) {
    for (const [key, rows] of Object.entries(feature.combinations ?? {})) {
      if (!['codex', 'japanese', 'codex+japanese'].includes(key) || !Array.isArray(rows) || rows.length > 1000) fail('Invalid community combination recipe.');
      if (key !== combination) continue;
      for (const value of rows) {
        const row = rowFor(value, feature.directory); if (!row) continue;
        if (combined.has(row.rel) && combined.get(row.rel).outputSha256 !== row.outputSha256) fail('Community combination recipes disagree: ' + row.rel);
        combined.set(row.rel, row); chosen.set(row.rel, row); collisions.delete(row.rel);
      }
    }
  }
  if (collisions.size) fail('No compatible community combination for: ' + [...collisions].join(', '), 'COMMUNITY_COMBINATION_MISSING');
  const overrides = new Map(), rows = new Map(base);
  for (const [rel, recipe] of chosen) {
    const original = base.get(rel);
    if ((original?.sha256 ?? null) !== recipe.baseSha256) fail('The Code baseline does not match this add-on: ' + rel, 'COMMUNITY_BASE_CHANGED');
    let originalBytes;
    if (original) {
      originalBytes = baseSource(rel);
      if (originalBytes.length !== original.size || sha(originalBytes) !== original.sha256) fail('The original Code file has been modified: ' + rel + '. Redeploy the original 0.4.6 Code baseline.', 'COMMUNITY_BASE_CHANGED');
    }
    const payload = readBytes(resolve(recipe.owner, ...recipe.source.split('/')));
    if (sha(payload) !== recipe.sha256) fail('Damaged community payload: ' + rel, 'COMMUNITY_PAYLOAD_DAMAGED');
    let output = payload;
    if (recipe.transform === 'profile-overlay') {
      if (!originalBytes) fail('A character overlay requires its original roster.');
      let overlay; try { overlay = JSON.parse(payload.toString('utf8').replace(/^\uFEFF/, '')); } catch { fail('Damaged Japanese profile overlay.'); }
      output = profileOverlay(originalBytes, overlay);
    }
    if (sha(output) !== recipe.outputSha256) fail('Community output fingerprint differs: ' + rel, 'COMMUNITY_PAYLOAD_DAMAGED');
    overrides.set(rel, output); rows.set(rel, {path: rel, size: output.length, sha256: sha(output)});
  }
  // The diagnostic manifest is generated from the composed code set, without hashing a large archive or changing Code/app.
  const diagnostic = {};
  for (const [rel, row] of [...rows].sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)) if (diagnosticCode(rel)) diagnostic[rel] = row.sha256.slice(0, 24);
  const listPath = 'defaults/runtime-code-files.json';
  const list = Buffer.from(JSON.stringify({version: 1, runtime: manifest.release, digits: 24, files: diagnostic}) + '\n');
  overrides.set(listPath, list); rows.set(listPath, {path: listPath, size: list.length, sha256: sha(list)});
  return {manifest: {...manifest, files: [...rows.values()].sort((a, b) => a.path < b.path ? -1 : a.path > b.path ? 1 : 0)},
    sourceFor: rel => overrides.get(rel) ?? baseSource(rel), features: features.map(feature => feature.id)};
}
