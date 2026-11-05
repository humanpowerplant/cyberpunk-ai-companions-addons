// The player's editable personality for optional automatic V replies. No game/save edits.
import {readFile, mkdir, writeFile, rename, unlink} from 'node:fs/promises';
import {dirname} from 'node:path';
import {randomBytes} from 'node:crypto';

export const SOCIAL_PLAYER_LIMITS = Object.freeze({name: 80, firstPerson: 24, style: 1800, values: 1600, background: 2000, avoid: 1200, total: 6000});
export const SOCIAL_PLAYER_DEFAULTS = Object.freeze({name: 'V', firstPerson: '俺', style: '', values: '', background: '', avoid: ''});
const FIELDS = Object.keys(SOCIAL_PLAYER_DEFAULTS);
const plain = value => value !== null && typeof value === 'object' && !Array.isArray(value)
  && [Object.prototype, null].includes(Object.getPrototypeOf(value));
const chars = value => Array.from(value).length;
const controls = /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f\u2028\u2029]/u;
export function validateSocialPlayerProfile(patch, current = SOCIAL_PLAYER_DEFAULTS) {
  const errors = [], next = {...SOCIAL_PLAYER_DEFAULTS, ...current};
  if (!plain(patch)) return {ok: false, errors: [{field: '', code: 'bad-request'}]};
  for (const field of Object.keys(patch)) {
    if (!FIELDS.includes(field)) { errors.push({field, code: 'unknown-field'}); continue; }
    if (typeof patch[field] !== 'string') { errors.push({field, code: 'bad-type'}); continue; }
    const value = patch[field].replace(/\r\n?/g, '\n').trim();
    if (controls.test(value)) { errors.push({field, code: 'control-character'}); continue; }
    if (chars(value) > SOCIAL_PLAYER_LIMITS[field]) { errors.push({field, code: 'too-long', max: SOCIAL_PLAYER_LIMITS[field]}); continue; }
    if ((field === 'name' || field === 'firstPerson') && (!value || /\n/u.test(value))) { errors.push({field, code: 'required-line'}); continue; }
    next[field] = value;
  }
  if (FIELDS.reduce((sum, field) => sum + chars(next[field]), 0) > SOCIAL_PLAYER_LIMITS.total) errors.push({field: '', code: 'total-long', max: SOCIAL_PLAYER_LIMITS.total});
  return errors.length ? {ok: false, errors} : {ok: true, value: next};
}

export class SocialPlayerProfile {
  constructor({file, now = Date.now, log = () => {}} = {}) {
    this.file = file; this.now = now; this.log = log;
    this.profile = {...SOCIAL_PLAYER_DEFAULTS}; this.queue = Promise.resolve(); this.updatedAt = 0;
  }
  get() { return {...this.profile}; }
  async load() {
    if (!this.file) return true;
    try {
      const raw = await readFile(this.file);
      if (raw.length > 32_000) throw Error('too-large');
      const document = JSON.parse(raw.toString('utf8').replace(/^\uFEFF/u, ''));
      if (!plain(document) || document.version !== 1 || !plain(document.profile)) throw Error('invalid-profile-file');
      const checked = validateSocialPlayerProfile(document.profile);
      if (!checked.ok) throw Error('invalid-profile-file');
      this.profile = checked.value;
      this.updatedAt = Number.isSafeInteger(document.updatedAt) && document.updatedAt >= 0 ? document.updatedAt : 0;
      return true;
    } catch (error) {
      if (error?.code === 'ENOENT') return true;
      this.log('V personality could not be loaded; defaults remain in memory.');
      return false;
    }
  }
  update(patch) {
    // Validate again inside the queue so simultaneous partial edits cannot overwrite one another.
    const operation = this.queue.then(async () => {
      const checked = validateSocialPlayerProfile(patch, this.profile);
      if (!checked.ok) throw Object.assign(Error('invalid'), {code: 'invalid', errors: checked.errors});
      const updatedAt = Math.max(0, Math.floor(this.now()));
      if (this.file) {
        const temporary = this.file + '.' + randomBytes(8).toString('hex') + '.tmp';
        try {
          await mkdir(dirname(this.file), {recursive: true});
          await writeFile(temporary, JSON.stringify({version: 1, updatedAt, profile: checked.value}, null, 2) + '\n', {encoding: 'utf8', mode: 0o600});
          await rename(temporary, this.file);
        } catch (error) {
          await unlink(temporary).catch(() => {});
          throw Object.assign(Error('not-saved'), {code: 'not-saved', cause: error});
        }
      }
      this.profile = checked.value; this.updatedAt = updatedAt;
      return this.get();
    });
    this.queue = operation.catch(() => {});
    return operation;
  }
  reset() { return this.update({...SOCIAL_PLAYER_DEFAULTS}); }
}
