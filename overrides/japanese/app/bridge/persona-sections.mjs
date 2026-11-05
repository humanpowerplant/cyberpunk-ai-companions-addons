// Parser vocabulary only. No user text is translated or rewritten by this module.
export const SECTION_JA = Object.freeze({
  IDENTITY: '人物像',
  'ESTABLISHED BACKGROUND': '確かな来歴',
  'ESTABLISHED RELATIONSHIPS': '既知の関係',
  'KNOWLEDGE AND CURRENT SAVE': '知識と現在のセーブ',
  'KNOWLEDGE LIMITS': '知識の限界',
  'WHO YOU ARE NOT AND WHAT YOU KNOW': '人物の区別と知識',
  'PUBLIC INTRINSIC TOPIC MATERIAL': '人物固有の話題',
  'Your appearance:': '外見:',
});
const EN = new Map(Object.entries(SECTION_JA).flatMap(([key, value]) => [[key, key], [value, key]]));
EN.set('Your appearance', 'Your appearance:'); EN.set('外見', 'Your appearance:'); EN.set('外見：', 'Your appearance:');
export const canonicalSection = value => EN.get(String(value ?? '').trim()) ?? String(value ?? '').trim();
export const isPersonaSection = value => EN.has(String(value ?? '').trim()) || /^(?:[A-Z][A-Z0-9 &'/-]{3,})$/.test(String(value ?? '').trim());
export const SCOPE_PREFIX = /^(?:Scope:|適用範囲[:：])/;
export const TOPIC_PREFACE_JA = '背景と本人の見解であり、Vとの面識や出典の出来事をVが体験した根拠ではない。関連する情報を一つ、自分の言葉で一、二文にして使い、検証済みのゲーム情報を優先する。';
export const SAVE_PREFACE_JA = '検証済みの現在のセーブ情報を優先する。呼び出された事実だけで、クエストの結末、生存、恋愛関係、面識を確定せず、未確認の重要事実を補わない。秘密の動機や内密の会話は、この相手に開示済みと検証できる場合だけ話す。グループ招待や質問だけでは開示済みとみなさない。';
