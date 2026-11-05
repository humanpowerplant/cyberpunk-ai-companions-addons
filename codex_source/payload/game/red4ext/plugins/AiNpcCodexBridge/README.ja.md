Codex Bridge 1.2.2-rc.2 — backend 1.2.0-rc.2 / AI Companions 0.4.6用

Vortexで導入・有効化・Deployしてください。Apply.cmdの実行は不要です。元Modと作者指定の依存Modは別途必要です。賑やかな会話などの追加機能はGemini等でも利用でき、Codexを選ぶ場合だけ公式Codex CLIが必要です。

Codexを初めて使うとき:
1. 公式Codex CLIを別途インストールしてください。公開版0.166.0を基準に必要な隔離オプションと機能制御を確認し、未対応CLIでは起動を拒否します。ご自身の対応ChatGPTアカウントを使います。利用枠・モデルの提供状況はアカウント次第です。CLI・Python本体・契約・認証情報は同梱していません。
2. このフォルダーのLogin.cmdを一度だけ手動実行してください。これは公式CLIへの対話ログインで、導入やApply処理とは別です。専用領域 %LOCALAPPDATA%/AiNpcCodexBridge/codex-home を使い、別のログインのauthファイルはコピーしません。旧共有領域から移行する場合だけ、確認後にconfig.jsonをバックアップしてcodex_homeをisolatedに変更します。
3. 元ModのConversation providerをCustom、Base URLをhttp://127.0.0.1:17865/v1、モデルをcodex-defaultにします。API key欄は空にしてください。ローカル通信用の認証情報は自動設定されるため、ゲームへの貼り付けや他人への共有は不要です。
4. Content packs > Codex Bridgeで「CLIの既定モデル（推奨）」「Auto（CLI既定）」を選べます。新規既定は開発者のモデルに固定しません。旧model/effortの保存番号はその意味を維持し、Legacy・アカウント依存と表示します。非対応の組み合わせは拒否し、前の反映済み設定を維持してエラーを表示します。

任意モデルはユーザー側 %LOCALAPPDATA%/AiNpcCodexBridge/config.json のmodel欄にCLIで利用可能な識別子を設定し、「config.jsonの任意モデル」を選びます。識別子に使用できるのは英数字・_・.・-のみです。ポート変更にも対応します。初期Codex URLだけを設定ポートへ読み替え、無関係なCustom URLは変更しません。hostは127.0.0.1に限定します。host/port/home変更前に所有するbackendを停止してください。

Codexへの会話要求、またはモデル設定の明示変更時にのみbackendを準備します。Gemini利用時にこのZIPを入れただけでCodexを起動したり、未導入CLIの確認を繰り返したりしません。ゲームの会話サービスが所有するbackendは親サービス終了時に停止します。手動起動した認証対応backendはPIDの所有権を取得せず再利用し、自動停止しません。旧未認証backendは手動停止・再起動を案内し、勝手に借用・停止しません。別サービスがポートを使用していても操作しません。Start.cmd/Stop.cmd/status.ps1/check.ps1は任意の診断用です。

既存config.json/selection.jsonは保持します。旧設定でcodex_homeが未指定の場合は共有領域のまま警告します。Login.cmdで専用領域に移行できます。選択領域のAGENTS.md/AGENTS.override.mdは内容を読まず検出して拒否します。専用領域に個人指示やskillsを追加しないでください。Login.cmdは自動実行せず、ゲーム起動でログイン画面を勝手に開きません。

要求ごとに専用の一時作業フォルダー、ephemeralセッション、read-only sandbox、承認しない設定、shell/web/MCP/skill/subagent機能の制限、環境変数の限定を使います。ただし公式CLIがapply_patchや時計など一部のnative toolを登録する場合があり、「全toolが存在しない」「一切のファイル読取機能がない」とは保証しません。上流のread-only/never設定は書込patchを拒否し、予期しないtoolイベントを検出したら要求を中止します。ゲームの会話・状況情報・任意の場面画像は、ご自身のCLI認証を通じOpenAIに送信されます。実在の秘密を会話に含めないでください。OpenAI公式のModや、無制限・無料のサービスではありません。

ローカルHTTPはIPv4 loopbackのみです。生成・設定・モデル一覧・停止操作にはユーザー専用の乱数tokenを要求します。Node/PowerShellはBearerを渡す前に、新しい乱数と実ポートを使ったHMACでサーバー側のtoken所持を検証します。異なるOrigin/Host、redirectは拒否します。tokenはWindowsユーザー領域のlocal-token.jsonに保存し、URL・プロンプト・状態ログ・配布物には入れません。同じWindowsユーザーで動く悪意あるソフト、不適切なプロファイル権限、あらゆるローカル競合を完全に隔離するものではありません。

既定上限はHTTP処理8本、同時生成1本、1分30要求です。本文・画像・出力サイズ・待機時間も制限します。会話本文・回答・画像bytes・CLIイベント・APIキー・認証tokenをbridgeログに書きません。固定診断と機密を含まない稼働情報だけを記録します。不具合報告でstateフォルダーを丸ごと公開しないでください。

検証は合成データと使い捨てサービスを使用します。ゲーム内互換性・音声品質・実アカウントのモデル利用可否を保証する試験ではありません。公式資料: https://learn.chatgpt.com/docs/auth ; https://learn.chatgpt.com/docs/non-interactive-mode ; https://learn.chatgpt.com/docs/cli/reference
