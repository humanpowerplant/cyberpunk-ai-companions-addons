// Local deterministic segmentation only; no network, models, file I/O or live settings.
export const hasJapanese = value => /[\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}]/u.test(String(value ?? ''));
let segmenter;
const segment = () => segmenter ??= new Intl.Segmenter('ja', {granularity: 'word'});
/** Indices remain native JavaScript UTF-16 offsets for callers slicing the source. */
export function spokenWordSpans(value) {
  const text = String(value ?? '');
  if (!hasJapanese(text)) return [...text.matchAll(/\S+/g)].map(m => ({text: m[0], index: m.index, end: m.index + m[0].length}));
  return [...segment().segment(text)].filter(row => row.isWordLike).map(row => ({text: row.segment, index: row.index, end: row.index + row.segment.length}));
}
const STOP_JA = new Set(('は が を に へ と で も の や か な ね よ ぞ さ から まで だけ ので でも って です ます だ だろう でしょう いる ある する した して され それ これ あれ どれ こと もの どう 何 なに なん 私 僕 俺 あたし あなた あんた お前 君 わたし たち 自分 ください 教え 教えて 聞かせ 知り たい 思う について').split(' '));
const SINGLE = new Set(['金','車','家','父','母','酒','歌','街','神','愛','夢','死']);
export function japaneseContentWords(value) {
  if (!hasJapanese(value)) return [];
  return spokenWordSpans(String(value).normalize('NFKC').toLowerCase()).map(row => row.text)
    .filter(word => hasJapanese(word) && !STOP_JA.has(word) && (Array.from(word).length >= 2 || SINGLE.has(word)));
}
export const japaneseIntentWords = text => /仕事|依頼|クエスト|任務|契約|目標|次はどう|次に何|何をすれば|どこへ行|どこに行|これからどう|今後の予定|次の予定|計画/u.test(String(text ?? '')) ? ['quest','job'] : [];
export const japaneseSmallTalk = text => /^(?:こんにちは|こんばんは|おはよう(?:ございます)?|やあ|どうも|元気(?:ですか)?|調子はどう(?:ですか)?|ありがとう(?:ございます)?|よろしく(?:お願いします)?|またね|バイバイ)[。！!？?\s]*$/u.test(String(text ?? '').trim());
export const japaneseFollowUp = text => /^(?:それで|それは|じゃあ|では|あの人|彼は|彼女は|そっちは|その話|それについて|続き)/u.test(String(text ?? '').trim());
