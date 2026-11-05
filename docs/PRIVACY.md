# データ送信・保存・使用量 / Privacy and service usage

## 日本語

**Codex CLIを使っても、文章生成はクラウドです。** ローカルで動くbridgeとCLIが、本人のChatGPTログインで外部サービスへ要求を送ります。このbridgeはAPIキー認証を拒否し、環境変数のAPIキーも暗黙に継承しません。「APIキーを貼らなくてよい」と「通信も費用もない」は別です。利用できるモデル、上限、料金、保持条件は契約と選んだサービスに従います。別アカウントの共有や制限回避を目的とする機能ではありません。

会話生成に送る材料には、入力文、人物設定、関係する会話記憶、場所・時刻・体調・所持金・クエスト等の取得済みゲーム状況が含まれます。利用者が人物設定やVのプロフィールに書いた内容も送信対象になります。必要のない実名、住所、連絡先、秘密を書かないでください。

本体の **Companion vision** を有効にした場合はゲーム画面の画像も、選んだ文章プロバイダーへ送られます。この追加Modは、画像送信を勝手にオンにしません。クラウド音声では生成台詞や参照音声がそのサービスへ送られます。マイク入力の送信先と処理方法も、本体で選んだ認識・会話方式に従います。

### 追加の自動処理

- 掛け合いやVの自動返答は、それぞれ文章生成の要求を増やします。
- **関係更新**は会話後の評価にもAIを使います。新規の設定ではオフです。以前から明示的に有効にしていた人の設定は保持します。
- 高い発話頻度は目標値です。戦闘、メニュー、利用可能な相手、待機時間、生成速度で実際の回数は変わります。60回/時を選んでも、正確に60回の生成や再生を保証しません。
- Vの自動返答は新規設定でオフ、自動音声もオフです。有効にする場合も、1ラウンドの返答上限・待機時間・打ち切り条件があります。
- Vが返答するかをAIに判断させた場合、最終的に発話しない判定でも要求を消費することがあります。字幕や発話の回数と、サービスへの要求数は同じではありません。

Dynamic infoでオフにした種別は、自動取得する状況、掛け合いの参照情報、Vの返答判定でも除外します。絶対ゲーム秒は時刻と前回会話の両方の共有がオンの場合だけ扱います。保存済みの構造化された自動観測は送信時に同じ設定で絞ります。旧版の種別を分離できない自動観測は、該当種別にオフがあれば送信しません。保存ファイル自体は削除しません。実際に発言した会話や手動の記憶は別であり、この設定は過去に送信済みの情報を取り消したり、会話本文から意味を推測して消したりする機能ではありません。

### PC内に保存するもの

本体の利用者データ領域と追加Modの利用者データ領域に、設定、人物編集、必要な認証設定、会話・関係の記憶を保存します。Windowsでは本体が `%LOCALAPPDATA%\AiNpcCyberpunkMod\data`、Codex bridgeが `%LOCALAPPDATA%\AiNpcCodexBridge` を使います。インストール先ドライブと利用者名は固定していません。

追加の社会的記憶はV1～V4の手動スロットで分けます。聞いた会話は最大600件、Vの出来事は最大500件で、各700文字・全体2MiBの上限があり、これらの出来事は最大90日で整理します。関係の記録は別に最大256件を更新順で保持し、同じ90日の期限ではありません。これは本体の全記憶・全ログを一括削除する機能ではありません。プレイスルーを変えるときはスロットを選んでください。機能をオフにすることと、すでに保存した内容を消すことも別です。

Codex用のローカル接続トークンは利用者のPC内で生成します。アップロード用ZIPにトークンや本人のCodex認証は入れません。公開版の専用Codex設定領域は、一般の作業用Codexに保存した指示がNPCへ混ざるのを避けるために使用します。本人が一度だけ専用領域でログインする手順はCodex導入ガイドにあります。

本追加Modは独自のテレメトリ送信先を追加しません。**元Modの自動エラーレポート等は別機能**です。本体のPrivacy and helpで確認してください。サポートにログを共有する際は、APIキー・認証・ローカルトークン・会話本文・個人パスが含まれていないか確認してください。

## English

Codex CLI is a cloud client, not a local language model. This bridge uses your own ChatGPT login, rejects API-key authentication and does not silently inherit environment API keys. Model access, quotas, charges and provider retention depend on your account. This is not an account-sharing or quota-bypass tool.

Requests can contain player text, character profiles, relevant memories and observed game state such as location, time, health, money and quests. Personal text entered in character or V profiles can also be sent. Companion vision, when enabled in the original mod, adds game-window images. Cloud voice services receive generated speech text and reference audio according to the selected engine. This add-on does not silently enable vision.

Automatic chatter, automatic V replies and relationship review can add model requests. Relationship review and V's automatic replies/voice default off for new settings; explicit existing choices are preserved. A high frequency is a target, not a guarantee of an exact number of calls or spoken lines.

A model-assisted decision about whether V should reply can consume a request even when the result is silence. Caption or speech counts are not request counts. Dynamic info exclusions also apply to automatically observed state, party context and V planning. Absolute game-time values require both time and last-talk sharing. Stored structured observations are filtered again before sending; legacy observations that cannot be separated by kind are withheld when a relevant kind is off. Files remain intact. Spoken dialogue and manually entered memories are separate: these switches do not retract past transmissions or infer and erase information from conversation text.

Local social memory uses manually selected V1–V4 slots. Heard/player events are bounded at 600/500 entries, 700 characters per entry, a 2 MiB total budget and 90 days. Relationship records instead retain up to 256 entries by update order; they do not share the event expiry. These bounds do not delete every original-mod log or memory. Disabling a feature does not erase previous data.

The bridge uses a per-user local connection token and a dedicated Codex home. Authentication is not copied into distribution files. Dedicated login is performed by the player. The CLI is run with an isolated work area and a read-only sandbox; this does not protect against malicious software running as the same Windows account, nor remove provider policies.

This add-on adds no separate telemetry destination. Original-mod error reporting and provider policies are separate. Before sharing diagnostics, remove keys, credentials, connection tokens, dialogue content and personal paths.
