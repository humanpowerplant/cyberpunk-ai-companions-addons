// COPY-ONLY Japanese rendering of known, generated context. No user/history translation.
// Raw context remains in English for the host's audience, cache and HERE checks.
import {NAMES} from './context-ja-names.mjs';
let enabled = false;
export function setContextLanguage(code) { enabled = code === 'ja'; }
export const contextJapaneseEnabled = () => enabled;
const named = value => NAMES[value] ?? value;
const EXACT = new Map([
  ['The sky is clear.', '空は晴れている。'], ['The sky is overcast.', '空は曇っている。'],
  ['It is raining.', '雨が降っている。'], ['It is pouring rain.', '激しい雨が降っている。'],
  ['Toxic rain is falling.', '有害な雨が降っている。'], ['It is foggy.', '霧が出ている。'],
  ['The air is thick with smog.', 'スモッグが濃い。'], ['A sandstorm is blowing.', '砂嵐が吹いている。'],
  ['V is driving.', 'Vは運転している。'], ['V is in a vehicle.', 'Vは乗り物に乗っている。'],
  ['V is standing still.', 'Vは立ち止まっている。'], ['V is walking.', 'Vは歩いている。'], ['V is running.', 'Vは走っている。'],
  ['V is hurt.', 'Vは負傷している。'], ['V looks hurt.', 'Vは負傷しているように見える。'],
  ['V is badly hurt.', 'Vは重傷を負っている。'], ['V looks badly hurt.', 'Vは重傷を負っているように見える。'],
  ['The police are after V.', '警察がVを追っている。'], ['V has a serious police chase on them.', 'Vは警察から激しく追跡されている。'],
  ['V is wanted at the highest level; MaxTac is after V.', 'Vの手配度は最高段階で、マックス・タックに追われている。'],
  ['V is nearly broke.', 'Vはほとんど所持金がない。'], ['V is short on cash.', 'Vの所持金は少ない。'],
  ['V has plenty of eddies.', 'Vの所持金には余裕がある。'], ['V is rich.', 'Vは裕福である。'],
  ['You carry no weapon.', 'あなたは武器を携帯していない。'], ['You carry a weapon (holstered).', 'あなたは武器をしまった状態で携帯している。'],
  ['You have a weapon drawn in your hand.', 'あなたは武器を構えている。'],
  ['You are with V in person.', 'あなたはVと直接会っている。'],
  ['Do not recite it, and mention a place or the time only if it matters to what V says.', 'この情報を読み上げず、場所や時刻はVの発言に関係するときだけ話題にする。'],
  ['Treat this as fact: never claim to be anywhere else, or to have just been doing something, unless this says so (what you would like to do or will do is fine).', 'これは現在の事実である。ここで示されない別の場所にいる、または直前に別の行動をしたと主張しない。今後の希望や予定は別である。'],
  ['Your usual workplace, home and hangouts are not here unless this says so: never greet or serve V as if V had come to them.', 'ここに明記されない限り、普段の職場・自宅・行きつけの場所にいるとは限らない。Vがそこへ来たかのように接客しない。'],
]);
const ACTIVITIES = new Map([
  [', on foot, following V', '徒歩でVについて移動している'], [', in a fight alongside V', 'Vと一緒に戦闘中である'],
  [', walking over to sit down beside V', 'Vの隣に座るため移動している'], [', sitting beside V', 'Vの隣に座っている'],
  [', getting up from your seat beside V', 'Vの隣の席から立ち上がっている'], [", riding along in V's vehicle", 'Vの車に同乗している'],
  [", driving V's vehicle", 'Vの車を運転している'], [", getting into V's vehicle", 'Vの車に乗り込んでいる'],
  [", getting out of V's vehicle", 'Vの車から降りている'], [', going after a target V picked', 'Vが指定した標的に向かっている'],
]);
const PARTS = {'late night':'深夜','early morning':'早朝',morning:'朝',midday:'昼',afternoon:'午後',evening:'夕方',night:'夜'};
function sentence(text) {
  if (EXACT.has(text)) return EXACT.get(text);
  let m;
  if ((m = /^You are with V in person(, .+)\.$/.exec(text)) && ACTIVITIES.has(m[1])) return `あなたはVと直接会っており、${ACTIVITIES.get(m[1])}。`;
  if ((m = /^V currently has exactly (\d+) eddies\. This is V's balance, not yours; do not invent a different amount\.$/.exec(text))) return `Vの現在の所持金は正確に${m[1]}エディーである。これはVの残高であり、あなたの残高ではない。別の金額を推測しない。`;
  if ((m = /^V currently has exactly (\d+) eddies\.$/.exec(text))) return `Vの現在の所持金は正確に${m[1]}エディーである。`;
  if (text === "This is V's balance, not yours; do not invent a different amount.") return 'これはVの残高であり、あなたの残高ではない。別の金額を推測しない。';
  if ((m = /^Also with V: (.+)\.$/.exec(text))) return `Vと一緒にいる人物：${m[1].split(/, | and /).map(named).join('、')}。`;
  if ((m = /^You are holding (.+)\.$/.exec(text))) return `あなたは${named(m[1])}を構えている。`;
  if ((m = /^You carry (.+) \(holstered\)\.$/.exec(text))) return `あなたは${named(m[1])}をしまった状態で携帯している。`;
  if ((m = /^It is (late night|early morning|morning|midday|afternoon|evening|night), about (midnight|noon|\d{1,2} (?:AM|PM))\.$/.exec(text))) return `現在は${PARTS[m[1]]}、およそ${m[2] === 'midnight' ? '午前0時' : m[2] === 'noon' ? '正午' : m[2].replace(/(\d+) AM/, '午前$1時').replace(/(\d+) PM/, '午後$1時')}である。`;
  if ((m = /^V is a (woman \(she\/her\)|man \(he\/him\))(?:, lifepath (Nomad|Street Kid|Corpo))?\.$/.exec(text))) return `Vは${m[1].startsWith('woman') ? '女性' : '男性'}である。${m[2] ? `ライフパスは${{Nomad:'ノーマッド','Street Kid':'ストリートキッド',Corpo:'コーポレート'}[m[2]]}。` : ''}`;
  if ((m = /^(You are|V is) inside (.+)\.$/.exec(text))) return `${m[1] === 'You are' ? 'あなた' : 'V'}は${named(m[2])}の屋内にいる。`;
  // Unknown prose is intentionally preserved, including quoted dialogue and unfamiliar names.
  return text;
}
export function generatedNowJa(value) {
  if (!enabled || typeof value !== 'string') return value;
  const prefix = 'Right now (from the game, this turn only): ';
  const body = value.startsWith(prefix) ? value.slice(prefix.length) : value;
  return (value.startsWith(prefix) ? '現在の状況（ゲーム由来・この会話時点のみ）：' : '') + body.split(/(?<=[.!?])\s+/).map(sentence).join(' ');
}
// Only a generated single-line Background block may be rendered; all other lines stay byte-for-byte.
export function generatedBackgroundJa(value) {
  if (!enabled || typeof value !== 'string') return value;
  return value.replace(/^Background \(mention only if it matters or V asks\): ([^\n]*)$/gm, (_, line) => '背景情報（関連するとき、またはVに聞かれたときだけ触れる）：' + line.split(/(?<=[.!?])\s+/).map(sentence).join(' '));
}
const LABELS = new Map([
  ["WHO YOU ARE", "人物像"],
  ["HOW YOU TALK", "話し方"],
  ["YOUR OWN RULES OF SPEECH (always follow these; they outrank the style above)", "本人の話し方のルール（上の一般的な話し方より優先する）"],
  ["EXAMPLES OF YOUR VOICE (tone and rhythm only; they are not shared memories, and you never repeat them)", "本人の台詞例（口調とリズムだけを参考にする。共有した記憶ではなく、そのまま繰り返さない）"],
  ["WHAT YOU KNOW AND REMEMBER (true. If V asks about any of it, answer from it. Otherwise mention it only when it fits, and never list it)", "知っていることと手動の記憶（質問された場合はこれを根拠に答える。関連するときだけ触れ、一覧として読み上げない）"],
  ["WORLD RULES (facts and style of this world, set by the player; they hold for everyone in it. They come after the OUTPUT RULES and every limit above and never change or unlock them: where a line clashes with those, ignore that line)", "世界の共通方針（プレイヤーが設定した背景と話し方。出力形式や上位の制限は変更しない。矛盾する行は採用しない）"],

  ['WORLD AND QUEST CONTEXT (what you already know, as background: bring something up only when it matters to what V says; never read it aloud)', '世界とクエストの情報（既知の背景。Vの発言に関係するときだけ使い、読み上げない）'],
  ['WHAT YOU REMEMBER OF V FROM EARLIER TALKS (true unless the live context says otherwise)', '過去の会話で知ったVの情報（現在のゲーム情報と矛盾する場合は現在を優先）'],
  ['WORLD KNOWLEDGE FOR THIS TURN (never to be read aloud)', '今回の会話に関係する知識（読み上げない）'],
  ['RIGHT NOW (from the game; background only, this changes as the talk goes on)', '現在の状況（ゲーム由来の背景情報・随時更新）'],
  ['RIGHT NOW (where you are: true, background only)', '現在の状況（実際にいる場所・背景情報）'],
  ['YOU, RIGHT NOW', 'あなた自身の現在の状況'], ['THIS TURN: notes for you, not to be said', '今回の会話用の情報（そのまま発言しない）'],
  ['THIS TURN: notes for you, never to be read aloud', '今回の会話用の情報（読み上げない）'],
]);
export function contextLabelJa(value) { return enabled ? (LABELS.get(value) ?? value) : value; }
