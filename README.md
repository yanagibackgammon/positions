# Backgammon Positions

解析済みのeXtreme Gammon棋譜（`.xg` / `.xgp`）から、指定したプレイヤーのエラー局面を抽出し、GitHub Pagesへ自動公開する静的ポジションデータベースです。

このREADMEは、棋譜を`imports/`へ追加した際に適用される、現在の抽出・盤面変換・表示ルールをまとめたものです。

## 1. 棋譜の読み込みと自動公開

- 読み込み対象は、`imports/`配下にある`.xg`と`.xgp`です。
- `imports/`内のサブフォルダも再帰的に検索します。
- `main`ブランチへ変更をコミットすると、GitHub Actionsの`Build and deploy positions`が自動実行されます。
- Actions画面から`workflow_dispatch`で手動実行することもできます。
- ビルド時に既存の`dist/`を削除し、現在の`imports/`、`site/`、`scripts/`、`config.json`を基にページ全体を再生成します。
- `imports/`から削除した棋譜に由来するポジションは、次回の正常なデプロイ完了後にページから消えます。
- 新しいデプロイが開始された場合、実行中の古いデプロイはキャンセルされます。
- Actionsが失敗した場合は、直前に正常公開されたページが残ります。

棋譜を入れ替える場合は、旧棋譜の削除と新棋譜の追加を同じコミットにまとめると、Actionsの実行を1回にできます。

## 2. 抽出対象

現在の`config.json`の既定設定は次のとおりです。

```json
{
  "databaseTitle": "Backgammon Error Positions",
  "targetPlayers": ["yanagi"],
  "errorThreshold": 0.02,
  "blunderThreshold": 0.08,
  "includeCheckerErrors": true,
  "includeCubeErrors": true,
  "includeTakeErrors": true,
  "anonymizeOpponents": false,
  "themeColor": "#B7924B"
}
```

### 対象プレイヤー

- `targetPlayers`に指定した名前と棋譜内のプレイヤー名を照合します。
- 大文字・小文字は区別しません。
- 名前は完全一致です。
- `targetPlayers`を空配列にすると、棋譜内の両プレイヤーを対象にします。

### エラー基準

- エラー値が`errorThreshold`以上の判断を一覧へ追加します。
- 現在の基準は`0.020以上`です。
- `blunderThreshold`以上は内部的に`Blunder`、未満は`Error`として分類します。
- 現在のBlunder基準は`0.080以上`です。

### 判断種別

表示対象は次の2分類です。

- `Checker Play`
- `Cube Action`
  - Double Decision
  - Take / Pass

次の判断は表示されません。

- エラー値が`errorThreshold`未満
- 未解析で有効なエラー値を取得できない判断
- `targetPlayers`に一致しないプレイヤーの判断
- 設定で無効にした判断種別
- `.xg`・`.xgp`以外のファイル

## 3. Checker Playの表示ルール

チェッカープレイを判断した対象プレイヤーを、常に黒側の`BK`として表示します。

- `BK`は盤面下側です。
- `BK`をオンロール側として表示します。
- 相手は白側の`WH`として盤面上側に表示します。
- 対象プレイヤーが元棋譜のPlayer 2の場合は、ポイント番号、チェッカー色、バー、スコア、キューブ所有者を表示用に反転します。
- 実際に振られたダイスを盤面へ表示します。
- キューブは実際の状態に応じて、センター、BK側、WH側のいずれかに表示します。

### 候補手

最善手セルには、評価順で上位3候補を表示します。対象プレイヤーが実際に選択したエラー手が上位3候補に含まれない場合は、その手を4番目に追加表示します。

```text
8/4(3) 6/2
8/4(2) 6/2(2)    −0.012
13/9 8/4(2)       −0.028
```

- 最善手のみ太字です。
- 次善手、3番手、および必要に応じて追加する実戦手は、最善手より小さく表示します。
- 手は左寄せ、エラー値は右寄せです。
- 4番目に追加する実戦手には、その判断で対象プレイヤーに記録されたエラー値を表示します。
- 2番手以降のエラー値は、最善手とのEquity差を小数第3位まで表示します。
- 同一の移動はまとめます。
  - 例：`8/4 8/4 8/4 6/2` → `8/4(3) 6/2`


### ポジション図

- ポジション図はセルの横幅いっぱいに表示します。
- PCでは盤面セルの余白を狭くし、盤面列自体も必要以上に広くしません。
- スマートフォンでは盤面列を画面幅いっぱいに使います。
- バー上のチェッカーは、中央キューブと外側の辺の中間を中心に配置します。

## 4. Cube Actionの表示ルール

Double DecisionとTake / Passは、画面上ではすべて`Cube Action`へ集約します。

### Double Decision

キューブ判断を行った側を`BK`として表示します。

最上段には最善アクションだけを太字で表示し、その下へXGと同じ考え方で3つのキューブ結果を固定順で表示します。

```text
最善アクション（太字）
No Double      −0.156
Double/Take    +0.262
Double/Pass
```

- XGと同様に、最善判断に対応する行を比較基準とし、他の結果との差を小数第3位まで表示します。
- `Double/Take`が最善の場合は`Double/Take`を基準にします。
- `Double/Pass`が最善の場合は`Double/Pass`を基準にします。
- `No Double`または`Too Good/...`が最善の場合は`No Double`を基準にします。
- 基準行は`+0.000`を表示せず、数値欄を空欄にします。
- 正の差には`+`、負の差には`−`を付けます。
- 最善アクションは`Double/Take`、`Double/Pass`、`No Double`、`Too Good/Take`、`Too Good/Pass`のいずれかです。
- `Too Good/...`は最上段の最善アクションとして表示し、下の3結果は比較用として`No Double / Double/Take / Double/Pass`を維持します。この場合、`No Double`が基準行になります。

キューブがすでにBK側にあり、リダブル判断となる場合はXGに合わせて次の表記へ切り替えます。

```text
最善アクション（太字）
No Redouble       符号付き差
Redouble/Take     符号付き差
Redouble/Pass
```

### Take / Pass

Take / Passのエラー対象者は応手側ですが、表示はキューブを打った側の視点へ統一します。

- ダブラーを`BK`として表示します。
- Take / Passを判断した側を`WH`として表示します。
- 盤面、チェッカー色、スコア、PIP、勝率をダブラー側の視点へ反転します。
- ダブラーが元棋譜のPlayer 2の場合も、盤面そのものを反転します。
- 最上段は応手だけではなく、局面全体の最善キューブ判断を表示します。`No Double`、`Double/Take`、`Double/Pass`、`Too Good/Take`、`Too Good/Pass`のいずれかになります。
- その下にはDouble Decisionと同様に、`No Double / Double/Take / Double/Pass`の3結果を固定順で表示し、最善判断に対応する行を基準とした差を併記します。
- `Too Good`判定は、No DoubleのEquityがDouble/PassのEquityを上回るかで判定します。相手の最適応手を組み合わせるため、通常の`Too Good/Pass`だけでなく、まれな`Too Good/Take`も表示します。
- リダブルへのTake / Pass判断では、`No Redouble / Redouble/Take / Redouble/Pass`と表示します。

### Cube Actionのキューブ位置

Cube Actionでは、キューブを必ず次のいずれかへ表示します。

- センター
- BK側

WH側には表示しません。

## 5. スコア、Away、Crawford、キューブ表記

スコアは次の形式です。

```text
BK  0 (7a)
WH  1 (6a)
```

- 通常の残りポイントは`(7a)`のようにAway表記します。
- Crawford Gameの1-away側は`(Cr)`と表示します。
- Post-Crawford Gameの1-away側は`(PC)`と表示します。

CrawfordとPost-Crawfordのルールは次のとおりです。

- Crawford：キューブは使用不可
- Post-Crawford：キューブは再び使用可能
- Crawford時の中央表示：`CB Cr`
- Post-Crawford時の中央表示：通常のキューブ値
- 通常時の中央表示：`CB 1`、`CB 2`、`CB 4`など
- 盤面内のキューブは、Crawford時のみ小文字の`c`を表示します。

## 6. 統合セル内の情報

盤面・候補手の右側に、BK情報、マッチ情報、WH情報を1セルへ統合して表示します。

```text
BK側              中央              WH側

BK  スコア(Away)   ML  マッチ長      WH  スコア(Away)
PIP ピップ数       CB  キューブ値     PIP ピップ数
W   勝率                              W   勝率
GW  ギャモン勝率                      GW  ギャモン勝率
```

### BK側

- BKスコアとAway
- BK PIP
- BK勝率：`W`
- BKギャモン勝率：`GW`

### 中央

- マッチ長：`ML`
- キューブ状態：`CB`

### WH側

- WHスコアとAway
- WH PIP
- WH勝率：`W`（BKの負率）
- WHギャモン勝率：`GW`（BKのギャモン負け率）

勝率はすべて小数第1位まで表示します。

```text
W   62.7%
GW  16.7%
W   37.3%
GW  11.5%
```

Checker Playでは、実戦で選択した候補手の解析値を表示します。Cube Actionでも、原則として実際に選択されたアクションの解析値を使用します。XGでは終端アクションであるPass自体に勝率ベクトルが付かないため、Pass時は同一局面の`Double/Take`解析からW・GW・L・GLを補完します。これにより、公開される全ポジションで勝率とギャモン率を表示します。利用可能な解析ベクトルが局面内に一つもない場合は、空欄を公開せずビルドをエラー終了します。

## 7. 勝率バー

統合セルの最下部に、BKとWHの勝率を表す横棒グラフを表示します。

- 左側：BK勝率
- 右側：WH勝率
- BK・WHそれぞれのギャモン勝率部分を金色で同じ高さに重ねます。
- 背景へ10％刻みの目盛を表示します。
- グラフ直上に小さく`30% / 50% / 70%`を表示します。
- BKとWHの勝率境界の直上に、小さな金色の`▼`を表示します。
- 境界自体には追加の太い線を入れず、黒と白の切り替わりで表現します。

## 8. 初期表示順、絞り込み、ソート

### 初期表示順

ビルド時に次の優先順で並べます。

1. エラー値の大きい順
2. ファイル名
3. ゲーム番号
4. ムーブ番号

### 絞り込み

プルダウンには次の項目があります。

- `All`
- `Checker Play`
- `Cube Action`

### ソートボタン

ソートボタンは次の順で1行に並べます。

```text
BK  PIP  W  GW ｜ ML  CB ｜ WH  PIP  W  GW
```

- BK側のボタンは黒色です。
- `ML / CB`は金色です。
- WH側のボタンは白色です。
- すべてのボタンは`BK`と同じ幅です。
- 未ソート時はボタン文字を左右中央揃えにします。
- クリックすると、その項目の昇順で並べます。
- 同じボタンを再度クリックすると降順へ切り替えます。
- 選択中のボタンには昇順・降順の矢印を表示します。

## 9. タイトル、拡大表示、スマートフォン対応

### タイトル

- ブラウザーの`<title>`は`Backgammon Positions`で固定です。
- 画面上の見出しは、表示件数に応じて更新します。
- 見出しの基礎文字列は`config.json`の`databaseTitle`から末尾の`Positions`を除いて生成します。
- 現在の設定では、例として`Backgammon Error 13 Positions`の形式になります。
- `databaseTitle`を`Backgammon Positions`へ変更すると、`Backgammon 13 Positions`の形式になります。

### ポジション拡大

- 盤面をクリックすると、画面内に収まるサイズで拡大表示します。
- 拡大盤面の下に、元の棋譜ファイル名を小さく表示します。
- 長いファイル名は1行で省略表示します。

### スマートフォン対応

- 表はスマートフォンの画面幅に収まるレイアウトへ切り替えます。
- ソートボタン行は横スクロールできます。
- 下方向へスクロールするとタイトルを隠し、上方向へ戻すスクロールではタイトルを再表示します。ソートボタン行は常に画面上部へ固定します。
- PC・スマートフォンとも、画面タイトルをクリックまたはタップするとページ最上部へ戻ります。
- PC・スマートフォンとも、盤面を見やすいサイズで表示します。
- ページのダブルタップやピンチ操作による意図しない拡大・縮小を抑止します。

### アイコン

- Apple Touch Icon：`180×180px` PNG
- ファビコン：`16×16px`、`32×32px` PNG
- 互換性用ICO：`16 / 32 / 48px`

## フォルダ構成

```text
positions/
├─ imports/                 解析済み.xg / .xgpのアップロード先
├─ scripts/build.py         抽出・盤面SVG生成・サイト構築
├─ site/                    GitHub Pagesの画面とアイコン
├─ vendor/xgread/           XGファイル解析ライブラリ
├─ .github/workflows/       GitHub Actions設定
├─ config.json              抽出条件と表示設定
└─ README.md                現在のルール
```

`dist/`はGitHub Actions実行時に自動生成され、GitHub Pagesへ直接デプロイされます。リポジトリへ自動コミットはしません。

## ライセンス・出典

XGファイル解析には、公式XGファイル仕様を実装した`gtback/xgread`を同梱しています。ライセンスは`LICENSES/xgread-LICENSE.txt`を参照してください。

盤面SVGは本プロジェクト独自の描画です。
