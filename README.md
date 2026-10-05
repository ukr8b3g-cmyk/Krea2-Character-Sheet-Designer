# Krea2 Character Sheet Designer

ComfyUI用のキャラクターシートDesignerです。既存H3 / Qwen版の操作を再利用し、内部プロンプトとワークフローを **Krea2 Identity Edit** 用にしました。

**どちらの版も人物・キャラクターのリファレンス画像が必要です。** 標準版は配置を文章で指示し、試験版はDesigner内のマネキンから配置画像を作って追加参照へ渡します。外部のレイアウト画像を用意する必要はありません。

## 2つの版

| ノード / workflow | 人物参照 | レイアウト例 | 用途 |
|---|---|---|---|
| `Krea2CharacterSheetDesigner` / `Krea2_Character_Sheet_Designer.json` | 必須・1枚 | 使用しない | 推奨の標準版。配置はプロンプトで指定 |
| `Krea2LayoutImageSheetDesigner` / `Krea2_Layout_Reference_Designer_Experimental.json` | 必須・1枚 | Designerが自動出力 | 試験版。画像1＝内蔵配置画像、画像2＝人物 |

試験版の「レイアウトだけ参照」はプロンプト上の役割です。モデル内部で外観と構図を完全分離する機能はなく、灰色のマネキン形状や質感が残る可能性があります。正確な配置や人物保持を保証しません。混ざる場合は標準版へ戻してください。

## インストール

1. このリポジトリを `ComfyUI/custom_nodes/Krea2-Character-Sheet-Designer/` へ配置
2. 別途 [comfyui-krea2edit](https://github.com/lbouaraba/comfyui-krea2edit) と、作者配布の [Identity Edit v1.2 LoRA](https://huggingface.co/conradlocke/krea2-identity-edit) を用意
3. Krea2対応ComfyUIを再起動し、ブラウザーを再読込
4. `workflows/` の標準版JSONを読み込み、画像・LoRA・モデルを手元のファイルから選択

Designer用に追加のpip/npmインストールは不要です。配置画像はComfyUI同梱のPillow・NumPy・torch、プレビューAPIはaiohttpを使用します。画像用ライブラリは画像出力を実行する時だけ読み込みます。モデル、LoRA、人物参照画像のダウンロードやインストールは行いません。H3版やQwen版のインストールは不要で、それぞれのノードやルートも変更しません。

確認したIdentity Editノードは `1.2.5` / commit `86f886dac23013d88996e3a2e99093ba44d322fb` です。`Krea2EditModelPatch.target_latent`、pixel path、`Krea2EditGroundedEncode.image_b` を持つ版を前提にします。将来版・旧版の互換性を保証するものではありません。

### 使用するモデル

- UNET: 標準版 `krea2_turbo_fp8_scaled.safetensors`、添付workflowを基にした試験版 `krea2_turbo_int8_convrot.safetensors`
- CLIP: `qwen3vl_4b_fp8_scaled.safetensors`、type `krea2`
- VAE: `qwen_image_vae.safetensors`
- LoRA: `krea2_identity_edit_v1_2.safetensors`、強度1.0

`SELECT_...` は選択前の仮名です。実ファイルに変更しないと実行できません。モデル名は作者のテンプレートに従ったもので、重みはこの配布に含みません。Krea社公式のキャラクターシートworkflowではありません。

## 使い方

カテゴリは `Krea2/CharacterSheet`。標準版は `prompt: STRING`、`width: INT`、`height: INT` の3出力です。新しい試験版はその後に `layout_image: IMAGE` が付きます。

- prompt → `Krea2EditGroundedEncode.prompt`（positive）
- width / height → `EmptySD3LatentImage`
- 同じEmpty latent → `KSampler.latent_image` と `Krea2EditModelPatch.target_latent`
- 参照画像 → VAEEncode、GroundedEncode、ModelPatchのpixel path

新規ノードと同梱workflowは **5ビュー・1696×768・Manual** から開始します。正面胸像 → 画面左向き胸像 → 正面全身 → 画面左向き全身 → 背面全身。人物参照を入れてQueueし、その後同じseedで部位やビューを比較してください。

### 既存Designerの操作を維持

7ビュー、8部位入力、Auto / Manual、高解像度の手入力、日本語 / 英語UI、保存・復元、Undo連携を引き継いでいます。

- 7ビュー：正面胸像、画面左向き胸像、全身正面、画面左向き全身、全身背面、両手詳細、足・履物詳細
- 8部位：頭・髪、顔、上半身の服、背面の服、下半身、手・手袋、足・履物、全体・その他
- ビューと部位入力は即時保存。数値の手入力はEnterまたはフォーカスを外すと確定
- 手足の詳細をOFFにしても、手袋や靴の指示は全身へ適用
- 背面の服の指示は後ろ側の衣服表面だけに適用。背面で顔を見せる振り向きは要求しない
- 部位入力は原文のまま保持し、自動翻訳しない。英語の定型文に各指示を一度ずつ入れる
- 左向きの胸像・全身はUIと生成用配置画像の両方で左右反転して、画面左向きの指示と一致。元マネキンPNGと配置座標は変更しない
- UIのプレビューは配置ガイド。人物の生成結果や部位変更の見た目は表示しない
- UI言語はComfyUIの `Comfy.Locale` がja系なら日本語、それ以外は英語

Krea用コンパイラーは英語の静止画指示を直接作ります。H3の動画・音声指示やQwenのレイアウトJSONは出力しません。標準版はビュー位置を自然言語と割合で指示します。新しい試験版は配置画像を一対一で人物へ置換する指示を使い、割合の再指定はしません。どちらもマスクやControlNetのような配置強制ではありません。

### 保存互換性とサイズ

`state_json` だけが保存入力で、既存schema v1/v2をそのまま受理します。参照モードをstateへ追加せず、ノード型で区別します。旧 `Krea2LayoutReferenceSheetDesigner` はLegacy扱いで登録を残し、保存済みの外部レイアウトworkflowと3出力を維持します。新規の同梱試験版では使いません。v1は読込だけで移行せず、実際の部位編集時にv2へ進みます。高解像度の既存stateを黙って縮小しません。

64KiB上限、32以上の32倍数、ComfyUI `MAX_RESOLUTION`、部位ごと1000 UTF-16単位などを検証します。不正JSONを勝手に初期値へ置き換えません。

Autoは基準高を保って幅・高さを算出し、32単位へ切り上げます。Manualは指定キャンバスに縦横比を保って配置し、ビューを変更しても寸法を変えません。寸法計算は既存H3 / Qwen版と同じです。

作者の目安は約1MPから、まず2MP以下での確認です。1696×768は約1.30MPです。高解像度は編集可能ですが、VRAM・速度・品質を保証しません。UIの `Experimental` 表示は引き継いだ1,032,192画素の注意閾値であり、Krea固有の品質・VRAM上限ではありません。

### Identity Edit設定

10 steps / CFG 1 / euler / simple / denoise 1 / LoRA 1.0 / fixed seed `1088049369132323` / grounding 768 / fit。

- `ref_boost=4`：最後の参照を強める。標準版では人物、試験版でも2枚目の人物
- `ref_boost_a=1`：試験版の1枚目（レイアウト）に対応。標準版の1枚参照では効果なし
- negativeは空文＋同じ画像順。CFG 1ではnegativeによる抑制が効かないため、必要な制約はpositiveに記述
- `vae` と生の参照画像を接続し、pixel pathを使用
- 同じlatentをtarget_latentへ接続してsampling前に参照をencode。出力寸法と別のlatentを接続しない

通常のKrea Core用に追加した `ModelSamplingFlux` をこのIdentity Editグラフへ独断で挿入していません。作者のモデル経路を維持しています。

## 内蔵レイアウト画像を使う試験版

[試験版workflow](workflows/Krea2_Layout_Reference_Designer_Experimental.json)を差し替えました。ユーザー提供のサブグラフ構成を基に、Designerの4番目の出力から選択ビューの配置画像を渡します。

1. `layout_image` → 画像1の `image` / `source_latent` / `source_image`
2. 人物リファレンス1枚 → 画像2の `image_b` / `source_latent_b` / `source_image_b`

positive、negative、VAE、pixel pathのすべてで同じ順序です。作者のscene-first / subject-second順序を維持し、最後の参照を強める `ref_boost=4` は人物、`ref_boost_a=1` は配置に対応します。

- 生成用の配置画像は同梱マネキンPNGを切り出して合成するため、追加の生成モデルや画像アップロードは不要
- `width` / `height` と同寸の白背景RGB。選択したビューのみ、同じ配置計算・縦横比・左向きで描画
- UIのラベル・背景グラデーション・足元の補助線・枠線は生成用画像に含めない
- 配置画像を `PreviewImage` でも確認可能。部位指示による衣装などの変更は配置画像には描かず、生成時のpromptへ反映
- サブグラフ内のモデル・LoRA・seed・steps・CFGなどは、添付workflowの構成と値を保持。画像やモデルの個人環境のパスは配布用の選択名へ置換
- 最初の3出力の順番を維持。標準版workflowは変更しない

新しいノードを使う前にComfyUIを再起動し、ブラウザーも再読込してから、新しい試験版JSONを読み込んでください。既存の外部レイアウト版が自動で新ノードへ変わることはありません。

2画像をモデルが厳密に分離する保証はありません。灰色の残存、顔・服・画風の変化、人数や配置・向きのずれを確認し、標準版と同じseedで比較してください。高解像度は自動縮小せず、その寸法の配置画像をCPU上で作るため、大きいサイズほどRAMも消費します。

## 検証と限界

[検証記録](docs/VERIFICATION.md)を参照してください。CPUコンパイラー、実際の配置画像の画素、JavaScript、模擬UI、workflowの静的構造を検証します。実torchテンソルを使うテストは環境にtorchがないため未実行です。

**実ComfyUI frontendへの読込、実Queue、GPU生成、保存PNGの寸法・メタデータ、画質・人物保持・速度・VRAMは未検証です。** ユーザーが提示した従来の5ビュー結果は、この新しいコンパイラーや2画像版の合格証拠ではありません。

## 開発用テスト

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/js/*.test.js
KREA2_JSDOM_PATH=/path/to/jsdom/lib/api.js node --test tests/dom/*.test.js
python tools/build_workflows.py
python tools/validate_workflows.py
```

jsdomは任意の開発用依存で、ComfyUI実行には不要です。Chromium用の独立UI harnessも `tests/browser/` にありますが、この環境ではブラウザー起動制約により未実行です。ComfyUI本体やPinia、実際のgraphToPromptは模擬テストの対象外です。

## 出典

配置画像の描画手法: [Qwen版 f6274130](https://github.com/ukr8b3g-cmyk/Qwen-Image-2.1-Character-Sheet-Designer/tree/f627413028f2c2e05b75ed2b09a30947dea1fec6)。Krea向けに左向き・枠なしへ調整。Qwen版で報告されたGPU検証は、このKrea版の実測ではありません。

UI/state/geometry: [Qwen版 604ec0c6](https://github.com/ukr8b3g-cmyk/Qwen-Image-2.1-Character-Sheet-Designer/tree/604ec0c6ea4046a3460e2c662d41f564870c15d8)、元の[H3版 bf792c65](https://github.com/ukr8b3g-cmyk/H3-Character-Sheet-Designer/tree/bf792c652a9f50e895409e49fce667fef0f73c25)。

Identity Edit: [作者workflowとコード 86f886da](https://github.com/lbouaraba/comfyui-krea2edit/tree/86f886dac23013d88996e3a2e99093ba44d322fb)。詳細は [NOTICE.md](NOTICE.md)。新しいライセンスを上流素材へ割り当てません。モデル重みは別配布・別ライセンスです。
