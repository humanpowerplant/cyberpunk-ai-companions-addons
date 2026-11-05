# 困ったとき / Troubleshooting

まず、ゲーム・本体・追加Modの版、利用プロバイダーを確認してください。セーブ・人物編集・認証をまとめて消す方法から始める必要はありません。

| 症状 | 最初に確認すること |
| --- | --- |
| Full installが必要と出る | 本体0.4.6のFull install・ゲーム2.5用があるか。Update用ZIPだけでは不足。ZIPを二重のフォルダーへ展開していないか |
| 追加項目がない | Vortexで有効・Deploy済みか、旧版が同時に有効でないか、本体より後か。ゲームを完全終了してから再起動したか |
| メニューや入力欄が反応しない | セーブ読込み後の街中でも同じかを区別。キーはCET Bindingsで確認。イベント後の症状は保存後に通常再起動し、同じ操作で再現するかを記録 |
| 日本語拡張なのに英語になる | Voice AI and microphone → **Voice language = Japanese**。Interface languageや字幕言語だけを変えていないか。個人の人物編集が古い英語を優先していないか |
| NPCの例文が英語のまま | 52プロフィールは元の英語例を保持。紹介・話し方の日本語設定とは別。自分の編集で保存した例も優先される |
| 所持金を答えない | Dynamic infoのmoney設定、会話方式と情報の対象範囲を確認。取得できない値は未知として扱う。電話や通行人へ無条件に残高を送る機能ではない |
| 仲間同士の会話が起きない | 実際に招待した仲間がいるか、本体の発話頻度・反応設定、利用可能性、待機時間を確認。頻度は保証回数ではない |
| Vが応答しない | Vの自動返答は新規設定でオフ。質問されたとき/状況に応じてを選び、Vへ向けた話題があるか、上限・待機中でないか確認 |
| Vの字幕はあるが音声がない | 自動音声は別スイッチ。V本人の参照と、言語に対応した音声エンジンが必要。音声未準備では字幕を維持する |
| Codexが使えない | 公式CLI、必要な機能、専用領域での本人のログイン、選んだモデルへのアクセスを確認。普段のデスクトップCodexのログインと専用領域は別 |
| Codexが401/認証不一致になる | 両追加Modを同じ公開世代へ揃え、旧サーバー/旧手動版を終了して通常再起動。ローカルトークンを公開投稿しない |
| ローカルポートの競合・検証失敗 | 別サービスが使っていないか確認。必要ならbridgeとCustom endpointのポートを両方変更。認証を無効にしたりLANへ公開したりしない |
| モデル/推論量のエラー | まずCLI default/automaticへ。旧プリセットや任意IDが本人の契約で使えるとは限らない。CLI側のエラー表示を確認 |
| invalid_saved_selection | ゲームとbridgeを終了し、`%LOCALAPPDATA%\AiNpcCodexBridge\selection.json`だけを別名で保管してから起動し、モデルを選び直す。config.jsonやcodex-home・認証をまとめて消す必要はない |
| 429、使用上限、遅い | サービスの使用状況を確認し、発話頻度・関係更新・V自動返答を減らす。高頻度の再試行で解決しようとしない |
| ゲーム終了後にhelperが残る | 少し待って状態確認。自動起動したものと以前に手動起動したものを区別し、手動サーバーはその起動元/同梱の停止手順で終了する。全Node/Pythonを一括終了しない |

`startup.lock`という空ファイルが残ること自体は正常です。排他は開いているファイルハンドルで管理し、終了時に解放します。ファイルの存在をプロセスの残留と判断せず、起動中に削除しないでください。

## 報告に必要な最小情報

ゲーム・本体・両追加Modのバージョン、Vortexでの有効状態、プロバイダー名、CodexならCLI版と選んだモデル、音声ならエンジン、再現する短い操作手順、エラーの必要部分を添えてください。APIキー、認証JSON、ローカルトークン、セーブ、全会話履歴は投稿しないでください。

まず追加Mod側で切り分けてください。元Modだけでも再現する問題と分かった場合に、その情報を添えて元作者の案内へ進みます。

## English quick checks

- Missing base/full-install message: install the original **0.4.6 Full install for game 2.5**, not only an Update ZIP.
- No options: check enabled status, Deploy, conflict order, old duplicates and a complete game restart.
- Japanese not used: set **Voice language → Japanese**; interface/subtitle language and saved character edits are separate.
- No V response: automatic V replies default off, and eligible replies are bounded. Voice is a separate opt-in and requires V's own reference.
- Codex unavailable: check CLI capabilities, dedicated-home login, model access and the matching add-on pair. Never share authentication or the local token.
- Port/auth/proof failure: stop an old manually launched server and restart normally, or configure an unused matching port. Do not disable authentication or expose loopback services.
- `invalid_saved_selection`: close the game and bridge, keep a backup of only `%LOCALAPPDATA%\AiNpcCodexBridge\selection.json`, then restart and select the model again. Keep config, the Codex home and authentication intact. An empty `startup.lock` is normal and does not indicate a running process; do not delete it during startup.
- Report only versions, selected options, a short reproduction and necessary sanitized errors. Do not upload saves, complete conversations or keys.
