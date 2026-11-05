// Imports only pure/product modules in a disposable upstream-shaped source tree.
// Never starts a bridge, model, voice worker, CLI, browser or game.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';

const [app, snapshotsFile, variant] = process.argv.slice(2);
const load = name => import(pathToFileURL(join(app, 'bridge', name)).href);
const {parseTurnContext, describeTurnContext} = await load('turn-context.mjs');
const {setContextLanguage, generatedNowJa} = await load('context-ja.mjs');
const {stripSnapshot} = await load('dynamic-info.mjs');
const {socialSettings} = await load('social-controller.mjs');
const {VVoice} = await load('v-voice.mjs');
const snapshots = JSON.parse(readFileSync(snapshotsFile, 'utf8'));
let assertions = 0;
const check = (actual, expected, label) => {assert.deepEqual(actual, expected, label); assertions++;};

const defaults = socialSettings({});
check(defaults.socialRelations, false, 'new users must opt into extra relationship review calls');
check(defaults.socialVReplies, 'off', 'new users retain control of V');
check(defaults.socialVVoice, false, 'new users must opt into automatic V speech');
check(defaults.socialMemory, true, 'bounded local heard memory stays available');
check(socialSettings({socialRelations:true,socialVVoice:true}).socialRelations, true, 'saved consent retained');
check(socialSettings({socialRelations:true,socialVVoice:true}).socialVVoice, true, 'saved speech choice retained');
check(socialSettings({socialRelations:'yes',socialVVoice:1}).socialVVoice, false, 'nonboolean does not enable audio');

// Constructing and updating VVoice performs no synthesis or helper start.
const voice = new VVoice({});
const manualOff = {vVoice:false,vVoiceChosen:true,vVoiceMic:false,vVoiceMicOwn:true};
voice.update({...manualOff,socialVReplies:'contextual'});
check(voice.autoEnabled, false, 'an absent automatic voice value stays disabled');
check(voice.enabled, false, 'manual typed voice preference preserved');
voice.update({...manualOff,socialVReplies:'asked',socialVVoice:true});
check(voice.autoEnabled, true, 'explicit automatic voice consent works without manual V voice');
voice.update({...manualOff,socialVReplies:'off',socialVVoice:true});
check(voice.autoEnabled, false, 'disabled automatic replies cannot start automatic V voice');

setContextLanguage('ja');
const current = snapshots.current;
check(parseTurnContext(current).moneyAmount, 100123, 'actual Lua balance reaches JS');
for (const text of ['所持金はいくら？', 'お金はどれくらい？', 'エディーはいくら持ってる？']) {
  const input = {profileKey:'judy-alvarez',text,turnContext:current};
  const rendered = generatedNowJa(describeTurnContext(input).text);
  assert.match(rendered, /Vの現在の所持金は正確に100123エディー/); assertions++;
  assert.doesNotMatch(rendered, /V is rich|V is comfortable/); assertions++;
}
check(parseTurnContext(snapshots.zero).moneyAmount, 0, 'real zero remains zero');
for (const [name,snapshot] of Object.entries(snapshots).filter(([name]) => !['current','zero'].includes(name))) {
  check(parseTurnContext(snapshot).moneyAmount, undefined, name + ' must not invent a balance');
}
for (const moneyAmount of [-1, 1.5, Number.MAX_SAFE_INTEGER + 1, Infinity, NaN, '100123']) {
  check(parseTurnContext({...current,moneyAmount}).moneyAmount, undefined, 'untrusted IPC balance rejected');
}
const off = new Set(['money']);
check(stripSnapshot(current,off).moneyAmount, undefined, 'money opt-out removes exact amount');
for (const input of [
  {profileKey:'judy-alvarez',channel:'phone',text:'所持金は？',turnContext:current},
  {profileKey:'stranger',text:'所持金は？',turnContext:current},
]) {
  const options = input.profileKey === 'stranger' ? {ambient:true} : {};
  assert.doesNotMatch(describeTurnContext(input,options).text, /100123/); assertions++;
}
assert.doesNotMatch(describeTurnContext({profileKey:'judy-alvarez',text:'所持金は？',turnContext:current},{off}).text,/100123/); assertions++;
assert.doesNotMatch(describeTurnContext({profileKey:'judy-alvarez',text:'今日はいい日だね',turnContext:current}).text,/100123/); assertions++;
console.log(JSON.stringify({passed:true,variant,assertions,realLuaSnapshots:true,modelCalls:0,voiceCalls:0,liveWrites:0}));
