# 互換性と確認範囲 / Compatibility and scope

## 対象

| 項目 | 対象・扱い |
| --- | --- |
| 本体 | AI Companions using Large Language Models **0.4.6 Full install** |
| ゲーム | Cyberpunk 2077 **2.5** |
| OS・導入 | Windows、VortexでのZIP導入・有効化・Deploy |
| ゲームの場所 | 実際のゲームrootから解決。GOG/Steamの既定パスやCドライブに固定しない |
| 本体の依存Mod | 元Modページの指定に従う |
| 日本語単独 | 利用可。Codex/掛け合い拡張は任意 |
| Codex/掛け合い単独 | 利用可。日本語拡張は任意 |
| 両方 | 日本語 **1.0.4-rc.2** とCodex/掛け合い **1.2.2-rc.2** の組 |
| 旧版との混在 | 同一追加Modの重複は無効化。旧世代との組は適用診断の対象 |
| 他バージョン・環境 | 本体0.4.4/0.4.5/将来版、ゲーム2.31、MO2、Linux/Protonは未確認 |

この追加Modの小さなZIPは、元ModのFull installの代わりにはなりません。必要なRuntime・音声処理・本体コードは元Mod側が提供します。

## 上書き順と更新

両方使う場合は **本体 → Codex/掛け合い → 日本語**。共有ローダーは同じ公開世代の2本で同じ内容です。片方だけを古い版へ戻す操作は避けてください。新しいローダーが配置されている場合、対応しない組を検出すると診断を出し、元のコード選択へ戻します。旧版のローダーを別のModが上書きしている状態まで検出を保証するものではありません。

無効化・更新はゲーム終了後のDeployと次回通常起動で反映します。起動中の差し替えには対応しません。配布ファイルが持つ既定値と、利用者が保存した設定は区別し、明示された既存設定を保持します。

## 確認と未確認を区別する

公開用の自動確認は、読み込み・単独/併用/解除・混在診断・日本語/空白を含むパス・通信境界・設定の保持等を対象にします。公式のコピー処理を実行するfixtureでも、最後の会話サービス起動はstubに置き換えます。ゲームをプレイした試験ではありません。

実ゲームでの以下の項目は、各公開版の実プレイ記録が必要です。

- 街中での通常会話、仲間同士の会話、条件を満たしたVの応答と音声。
- セーブ読込み、ファストトラベル、イベント後のメニュー復帰。
- 他Modを大量に入れた構成、特定のカメラ/衣装/車両/世界編集Modとの相互作用。
- 様々なPC・音声機器・契約モデルでの応答時間と声の再現度。

過去の開発環境で会話機能が動いたことと、この公開候補の全項目が実プレイ済みであることは区別します。公開候補はRCとして扱い、[リリース前確認](TESTING.md)を参照してください。

## English

Supported target: Windows, Vortex, Cyberpunk 2077 **2.5**, and AI Companions **0.4.6 Full install** with its original requirements. The game path is resolved relative to the installation, not pinned to one storefront or drive.

Use either add-on or the matching pair **Japanese 1.0.4-rc.2 / Party Conversations and Codex Bridge 1.2.2-rc.2**. Recommended conflict order is base → Party/Codex → Japanese. Disable old duplicates. Mixing release generations can cause the new loaders to fall back to original code with a diagnostic. An old loader winning a file conflict cannot be assumed to detect new rules.

Other base versions, game 2.31, MO2 and Proton are unverified. Automated source, installer and protocol fixtures are not gameplay, cross-PC, performance or voice-quality proof. The release candidate needs the manual checks in [Testing](TESTING.md).
