# Krea2 Character Sheet Designer

ComfyUI用のキャラクターシートDesignerです。人物リファレンス1枚と、Designerが作るマネキン配置画像を **Krea2 Identity Edit** へ渡します。外部のレイアウト画像は不要です。

## 配布workflow / Download

**[Krea2_Layout_Reference_Designer.json をダウンロード](workflows/Krea2_Layout_Reference_Designer.json?raw=1)**

配布テンプレートはこの1本です。ユーザー提供の最新workflowをバイト単位で保持し、ファイル名だけ統一しています。`Krea2LayoutImageSheetDesigner` を使い、画像1＝内蔵レイアウト、画像2＝人物リファレンスの順です。

## クイックスタート

1. このリポジトリを `ComfyUI/custom_nodes/Krea2-Character-Sheet-Designer/` へ配置
2. 別途 [comfyui-krea2edit](https://github.com/lbouaraba/comfyui-krea2edit) と [Identity Edit v1.2 LoRA](https://huggingface.co/conradlocke/krea2-identity-edit)、対応するKrea2モデル・CLIP・VAEを用意
3. Krea2とサブグラフに対応したComfyUIを再起動し、ブラウザーを再読込
4. 上のJSONを読み込み、`Image 2: CHARACTER IDENTITY / required` で自分の人物画像を選択
5. サブグラフの公開コントロールで、手元のUNET・CLIP・VAE・LoRAを選び直してQueue

**保存されている画像名・モデル名は提供者の環境のものです。画像や重みは同梱していません。** `krea2\...` という保存パスや、内部ノードに残る `SELECT_...` は、そのまま使えることを保証しません。内部の保存値だけで判断せず、サブグラフの公開コントロールを確認してください。

Designer用に追加のpip/npmインストールは不要です。配置画像はComfyUI環境のPillow・NumPy・torch、プレビューAPIはaiohttpを使用します。画像用ライブラリは画像出力時だけ読み込みます。H3版・Qwen版のインストールは不要で、既存のノードやルートも変更しません。

### English quickstart

1. Place this repository in `ComfyUI/custom_nodes/Krea2-Character-Sheet-Designer/`
2. Install [comfyui-krea2edit](https://github.com/lbouaraba/comfyui-krea2edit), the [Identity Edit v1.2 LoRA](https://huggingface.co/conradlocke/krea2-identity-edit), and compatible Krea2 / CLIP / VAE weights separately
3. Restart a Krea2- and subgraph-capable ComfyUI, refresh the browser, then import the **[single distributed workflow](workflows/Krea2_Layout_Reference_Designer.json?raw=1)**
4. Select your character image in `Image 2: CHARACTER IDENTITY / required`; reselect installed models and LoRA in the subgraph's exposed controls before queuing

The saved filenames belong to the supplied workflow, not bundled assets. Layout is reference image 1; character identity is reference image 2. Defaults are five views, Manual 1696×768. This exact attachment has not been executed in ComfyUI or on a GPU in this verification environment.

## 保存設定と配線

初期配置は **5ビュー・Manual 1696×768**（body_height 672、約1.30MP）：正面胸像 → 画面左向き胸像 → 正面全身 → 画面左向き全身 → 背面全身。

最新添付のサブグラフに保存された公開コントロールは次の値です。

- UNET：`krea2\krea2_turbo_int8_convrot.safetensors`
- CLIP：`qwen3vl_4b_fp8_scaled.safetensors`（内部typeは `krea2`）
- VAE：`qwen_image_vae.safetensors`
- LoRA：`krea2\krea2_identity_edit_v1_2.safetensors`（内部強度1.0）
- seed：`1088049369132323`、steps：10、CFG：1
- 内部設定：fixed seed / euler / simple / denoise 1 / grounding 768 / fit

内部UNET・LoRAノードには別の `SELECT_...` 仮名が保存されていますが、モデル選択はサブグラフ境界から接続されています。公開コントロールの保存値と内部の予備値を混同しないでください。

カテゴリは `Krea2/CharacterSheet`。`Krea2LayoutImageSheetDesigner` の出力順は `prompt: STRING`、`width: INT`、`height: INT`、`layout_image: IMAGE` です。

- prompt → positiveの `Krea2EditGroundedEncode.prompt`
- width / height → `EmptySD3LatentImage`
- 同じEmpty latent → `KSampler.latent_image` と `Krea2EditModelPatch.target_latent`
- layout_image → 画像1のconditioning・VAEEncode・pixel path
- 人物画像 → 画像2の `image_b`・VAEEncode・`source_image_b` / `source_latent_b`

positive・negative・VAE・pixel pathの全経路で同じ画像順です。`ref_boost=4` は最後の人物参照、`ref_boost_a=1` は配置参照に対応します。negativeは空文で、CFG 1ではnegativeの抑制に頼らずpositiveへ制約を書きます。`ModelSamplingFlux` は追加していません。

配置画像は同梱マネキンPNGから選択ビューを白背景RGBへ合成し、出力寸法と一致させます。UIのラベル・補助線・枠は含みません。衣装などの部位変更は画像へ描かずpromptに反映します。配布グラフには独立した `PreviewImage` ノードはありません。

## Designerの操作と互換性

- 7ビュー：正面胸像、画面左向き胸像、全身正面、画面左向き全身、全身背面、両手詳細、足・履物詳細
- 8部位：頭・髪、顔、上半身の服、背面の服、下半身、手・手袋、足・履物、全体・その他
- Auto / Manual、高解像度の手入力、日本語 / 英語UI、保存・復元、Undo連携を維持
- ビューと部位入力は即時保存。数値の手入力はEnterまたはフォーカスを外すと確定
- 手足の詳細をOFFにしても、手袋や靴の指示は全身へ適用。背面の服の指示は後ろ側の衣服表面だけに適用
- 部位入力は原文を保持し、自動翻訳しない。英語の静止画promptへ各指示を一度ずつ入れる
- 左向きの胸像・全身はUIと配置画像の両方で反転。元PNGと配置座標は変更しない
- UIのプレビューは配置ガイドで、生成結果や衣装変更の見た目は表示しない
- `Comfy.Locale` がja系なら日本語、それ以外は英語

`state_json` が唯一の保存入力で、既存schema v1/v2を受理します。v1は読込だけでは移行せず、実際の部位編集時にv2へ進みます。64KiB上限、32以上の32倍数、ComfyUI `MAX_RESOLUTION`、部位ごと1000 UTF-16単位などを検証し、不正JSONを黙って初期化しません。

Autoは基準高を保って寸法を算出し、32単位へ切り上げます。Manualは指定キャンバスへ縦横比を保って配置し、ビュー変更で寸法を変えません。既存の高解像度stateを自動縮小しません。

**テンプレートの一本化でノード機能は削除していません。** `Krea2CharacterSheetDesigner` とLegacyの `Krea2LayoutReferenceSheetDesigner` は登録と従来の3出力・prompt動作を維持し、保存済みworkflowを引き続き扱えます。新しい配布テンプレートは4出力の `Krea2LayoutImageSheetDesigner` だけを使用します。

## 検証と限界

確認対象のIdentity Editは `1.2.5` / [commit 86f886da](https://github.com/lbouaraba/comfyui-krea2edit/tree/86f886dac23013d88996e3a2e99093ba44d322fb) です。`target_latent`、pixel path、`image_b` を持つ版が必要です。任意のComfyUI・frontend・将来版との互換性を保証しません。

[検証記録](docs/VERIFICATION.md)は、今回の添付JSONの確認と過去のノード回帰検証を分けて記録しています。**今回の環境では実torch・実ComfyUI frontend・Queue・GPU生成を未検証です。** 保存PNG、速度、VRAM、画質、人物保持の実測はありません。

レイアウトと人物の役割分離はpromptによる誘導です。マスクやControlNetのような配置強制ではなく、灰色の残存や顔・服・画風・人数・向きのずれが起こり得ます。高解像度ではVRAMに加え、CPU配置画像のRAMも増えます。UIの `Experimental` 表示は引き継いだ1,032,192画素の注意閾値であり、Krea固有の品質・VRAM上限ではありません。Krea社公式workflowではありません。

## 開発用テスト

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/js/*.test.js
KREA2_JSDOM_PATH=/path/to/jsdom/lib/api.js node --test tests/dom/*.test.js
python tools/validate_workflows.py
```

jsdomと `tests/browser/` のChromium harnessは任意の開発用ツールで、ノード実行には不要です。模擬UIテストは実ComfyUIやgraphToPromptの代わりにはなりません。

## 出典

UI/state/geometry：[Qwen 604ec0c6](https://github.com/ukr8b3g-cmyk/Qwen-Image-2.1-Character-Sheet-Designer/tree/604ec0c6ea4046a3460e2c662d41f564870c15d8)、元の[H3 bf792c65](https://github.com/ukr8b3g-cmyk/H3-Character-Sheet-Designer/tree/bf792c652a9f50e895409e49fce667fef0f73c25)。配置画像：[Qwen f6274130](https://github.com/ukr8b3g-cmyk/Qwen-Image-2.1-Character-Sheet-Designer/tree/f627413028f2c2e05b75ed2b09a30947dea1fec6)を基に左向き・枠なしへ調整。

Identity Edit：[作者コード 86f886da](https://github.com/lbouaraba/comfyui-krea2edit/tree/86f886dac23013d88996e3a2e99093ba44d322fb)。ライセンスとworkflowの来歴は [NOTICE.md](NOTICE.md)。重みは別配布・別ライセンスです。Qwen版のGPU報告や過去の参考画像は、この添付workflowの実行証拠ではありません。
