// Japanese topic/subject hints for the existing English selector. No claim, trust,
// audience, quest prerequisite or automatic/group gate is added or bypassed.
const TERMS = [
 [/コーヒー|エスプレッソ/u,'coffee'],[/初期のライブ|初期のバンド|昔のライブ|最初のライブ|カリエンテ/u,'early gigs caliente'],
 [/サムライ|音楽活動|音楽の仕事|ソロ活動|ソロにな/u,'samurai solo career'],[/フィリピン/u,'filipino'],[/ルーツ|出自/u,'heritage roots'],
 [/ナイトシティ/u,'night city'],[/レコード会社|楽曲の権利|曲の権利|音楽の権利|芸術的な独立/u,'record label song rights'],
 [/ブレインダンス|バーチャル|\bBD\b/iu,'braindance'],[/食べ物|料理|食事|食材/u,'food cooking'],[/フィクサー/u,'fixer'],
 [/口の堅さ|口が堅|守秘|プライバシー|内密/u,'discretion privacy'],[/仕事仲間|同業者|仕事相手|評判|プロ意識/u,'professional colleagues reputation'],
 [/権力|支配/u,'power control'],[/警察|刑事|バッジ|NCPD/iu,'police detective ncpd'],[/ジャンバラヤ|レシピ/u,'cooking jambalaya recipe'],
 [/ジョス/u,'joss'],[/近所|住みやす|街の眺め/u,'neighborhood city view'],[/統一戦争|諜報網|諜報組織|昔の組織/u,'unification war spy network'],
 [/人質|誘拐犯|暗殺|護衛任務|要人警護/u,'hostage kidnappers protective operations'],[/生き延び|生き残|生還/u,'survival survived'],
 [/新合衆国|新アメリカ合衆国|愛国心|国への奉仕|忠誠|FIA/iu,'nusa fia service patriotism'],
 [/ソン・ソミ|ソンソミ/u,'song so mi'],[/コードネーム/u,'codename'],[/本名|名前/u,'name'],[/フリーランス|独立したランナー|データ要塞|データフォート/u,'freelance datafort'],
 [/装備|機材|稼いだ金/u,'gear equipment freelance earnings'],[/チームワーク|命令に従|宣誓/u,'teamwork taking orders service oath'],[/ブルックリン/u,'brooklyn'],
 [/ジョニー/u,'johnny'],[/オルト(?:・カニンガム)?/u,'alt cunningham'],[/エングラム|人格コンストラクト/u,'engram'],[/本当のオルト/u,'real alt'],
 [/ソウルキラー/u,'soulkiller'],[/神輿|ミコシ|ブラックアイス|ブラックICE/u,'mikoshi black ice'],[/ネットウォッチ/u,'netwatch'],
 [/怖い|恐れ|恐怖|不死|死すべき|夢を見る/u,'fear mortality dreams'],[/ネットランナー|ブラックウォール|不良AI/iu,'netrunner blackwall'],
 [/ラグナ・ベンド|ラグナベンド/u,'laguna bend'],[/子供時代|子ども時代|幼少期|育った|故郷/u,'childhood hometown'],
 [/祖父母|祖父|祖母|おじい|おばあ/u,'grandparents grandfather grandmother'],[/スキャンウェア|工房|ハードウェア/u,'scanware workshop hardware'],
 [/アート|芸術|編集/u,'art artistic editing'],[/モックス/u,'mox'],[/企業|コーポ|スタジオ|独立/u,'corporate corporation studio independence'],
 [/カリフォルニア/u,'california'],[/ソウル|クランを離|クランから離|クランを抜/u,'saul leaving the clan'],[/ミッチ|スコーピオン/u,'mitch scorpion'],
 [/路上生活|ノーマッドの生活|ノーマッドとして|野宿|旅の暮らし/u,'nomad life road life sleeping outside'],[/政府|大統領|元首/u,'government president'],
 [/コール/u,'cole'],[/ドッグタグ|認識票/u,'dog tags'],[/脱走|脱走兵|ピスティス・ソフィア|ピスティスソフィア/u,'desertion pistis sophia'],
 [/スパイダー・マーフィー|スパイダーマーフィー/u,'spider murphy'],[/アラサカ(?:・)?タワー/u,'arasaka tower'],[/アラサカ/u,'arasaka'],
 [/核爆弾|核兵器|核攻撃|爆弾|爆破/u,'nuclear bomb'],[/軍歴|軍隊|従軍|入隊|兵役|兵士|戦争/u,'military army war'],
 [/メキシコ/u,'mexico'],[/ローグ/u,'rogue'],[/トンプソン/u,'thompson'],[/サンティアゴ/u,'santiago'],[/ケリー/u,'kerry'],
 [/音楽|ギター|楽器|バンド|昔のシングル/u,'music guitar instruments band'],[/父親|親父|父さん|お父さん|(?<![祖義養])父(?!権|性|系)/u,'father'],[/ベルト/u,'belt'],
 [/虐待|殴ら|殴る|暴力/u,'abuse beating violent'],[/撃たれ|銃撃|入院|負傷|けが/u,'shot injury hospital'],[/カミラ/u,'camila'],
 [/ミスティ/u,'misty'],[/ガレージ|鍵|プライベートな空間/u,'garage key privacy'],[/マンダラ|曼荼羅|砂絵/u,'mandala sand spiritual'],
 [/守ると約束|弾丸|身を挺/u,'bullet protect promise devotion'],[/母親|母さん|お母さん|オフクロ|(?<![祖義養])母(?!国|語|体|系|性)/u,'mother'],[/ママ・ウェルズ|ママウェルズ/u,'mama welles'],
 [/ヘミングウェイ|誰がために鐘は鳴る|読書/u,'hemingway book'],[/テキーラ/u,'tequila'],[/センツォン/u,'centzon'],[/幸運のボトル/u,'lucky bottle'],
 [/ヴァレンティーノズ|ヘイウッド|ギャング/u,'valentinos heywood gang'],[/後悔|罪悪感|なぜ|理由/u,'why reason regret'],
 [/スマッシャー/u,'smasher'],[/サブロウ/u,'saburo'],[/捕ま|捕虜|尋問/u,'captured interrogation'],[/脱出|逃げ|生きてい|生存/u,'escape alive survived'],
];
const SUBJECT = {
 'johnny-silverhand':/ジョニー(?:・シルヴァーハンド)?/u,'jackie-welles':/ジャッキー(?:・ウェルズ)?/u,
 'judy-alvarez':/ジュディ(?:・アルヴァレス)?/u,'panam-palmer':/パナム(?:・パーマー)?/u,
 'kerry-eurodyne':/ケリー(?:・ユーロダイン)?/u,'river-ward':/リバー(?:・ウォード)?/u,
 'evelyn-parker':/エヴリン(?:・パーカー)?/u,'solomon-reed':/リード|ソロモン(?:・リード)?/u,
 songbird:/ソングバード|ソン・ソミ/u,'alt-cunningham':/オルト(?:・カニンガム)?/u,
};
export function intrinsicQueryJa(value, profileKey) {
 const raw=String(value ?? '').trim().normalize('NFKC').toLowerCase();
 if(!/[\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}]/u.test(raw))return raw;
 if(/渡して|渡せ|持ってき|取ってき|呼んで|呼べ|ついてき|運転して|運転しろ|座って|座れ|立って/u.test(raw))return raw;
 const family=/父親|父さん|お父さん|親父|(?<![祖義養])父(?!権|性|系)|母親|母さん|お母さん|オフクロ|(?<![祖義養])母(?!国|語|体|系|性)|祖父母|祖父|祖母|家族|軍歴|兵役|認識票|ドッグタグ|ルーツ|出自|子供時代|子ども時代|幼少期|故郷/u.test(raw);
 const name=SUBJECT[profileKey];
 const own=/(?:あなた|あんた|お前|君|そっち)(?:自身)?の/u.test(raw)
   || !!(name && new RegExp('(?:'+name.source+')(?:自身)?の','u').test(raw));
 const ownAct=/(?:あなた|あんた|お前|君)(?:自身)?(?:が|は)/u.test(raw)
   || !!(name && new RegExp('(?:'+name.source+')(?:自身)?(?:が|は)','u').test(raw));
 const explicitOther=/(?:私|わたし|俺|僕|あたし|うち|V|v|彼|彼女|あの人|友人|友達|知人)(?:たち)?の(?:父|親父|母|祖父|祖母|家族|軍歴|兵役|ドッグタグ|認識票)/u.test(raw);
 const otherNamedFamily=family && !own && /[^\s]{1,18}の(?:父|親父|母|祖父|祖母|家族|軍歴|兵役|認識票|ドッグタグ)/u.test(raw);
 // A Japanese ambiguous family question is held rather than silently assigning it
 // to the NPC. This is stricter than, and never weakens, the English gates.
 if(family && (explicitOther || otherNamedFamily || !own))return raw+' my father';
 const hints=TERMS.filter(([pattern])=>pattern.test(raw)).map(([,english])=>english);
 const question=/教え|聞かせ|話して|語って|知りたい|何|誰|なぜ|どう|いつ|どこ|どんな|好き|嫌い|思う|感じ|覚え|について|の話|[?？]/u.test(raw);
 if(own){
  if(/父親|父さん|お父さん|親父|(?<![祖義養])父(?!権|性|系)/u.test(raw))hints.unshift('your father');
  if(/母親|母さん|お母さん|オフクロ|(?<![祖義養])母(?!国|語|体|系|性)/u.test(raw))hints.unshift('your mother');
  if(/祖父母|祖父|祖母/u.test(raw))hints.unshift('your grandparents');
  if(/子供時代|子ども時代|幼少期|故郷/u.test(raw))hints.unshift('your childhood hometown');
  if(/ルーツ|出自/u.test(raw))hints.unshift('your heritage');
  if(/ドッグタグ|認識票/u.test(raw))hints.unshift('your dog tags');
  if(/軍歴|軍隊|兵役|従軍|入隊/u.test(raw))hints.unshift('your military service');
  if(/脱走/u.test(raw))hints.unshift('your desertion');
  if(/生き残|生き延び|生還/u.test(raw))hints.unshift('you survived');
  if(/名前|本名/u.test(raw))hints.unshift('your name');
 }
 if(ownAct){
  hints.unshift('you');
  if(/生き残|生き延び|生還/u.test(raw))hints.unshift('you survived');
  if(/何者|誰なの|誰です/u.test(raw))hints.unshift('who are you');
 }
 if(/マーフィーの法則/u.test(raw))hints.push("murphy's law");
 if(/スパイダー(?:ボット|タンク|ドローン)|蜘蛛|クモ/u.test(raw))hints.push('spider bot');
 if(/(?:alt|オルト)(?:キー|ショートカット)|キーボード/iu.test(raw))hints.push('alt key keyboard');
 if(/ギャングの抗争|縄張り争い|ストリートの抗争/u.test(raw))hints.push('gang war');
 const historic=/2023|当時|昔|かつて|生前|過去|あのとき|あの時|だった|した時|したの|した理由/u.test(raw);
 if(historic)hints.push('back then');
 if(!historic && /今日|今夜|明日|これから|予定|計画|警備|侵入|潜入|強襲|襲撃|ヘイスト/u.test(raw))hints.push('plan for today security');
 return raw+' '+(question?'tell me about ':'')+hints.join(' ');
}
