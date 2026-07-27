# positions

解析済みの eXtreme Gammon 棋譜（`.xg` / `.xgp`）から、指定選手のエラー局面を自動抽出し、GitHub Pagesで一覧表示する静的データベースです。

## 主な機能

- `imports/` に解析済み棋譜を追加するとGitHub Actionsが自動実行
- Checker Play、Double、Take / Passのエラーを抽出
- bgLogのMinstrelsを参考にした独自SVG盤面を生成
- 実戦アクション、最善アクション、エクイティロスを表示
- 勝率、ギャモン勝率、敗率、ギャモン負け率を表示
- 全表示列を昇順・降順でソート
- 判断種別、判定、棋譜、キーワードによる絞り込み
- XGIDの表示とコピー
- 候補手一覧の展開表示

## 最初の設定

1. この一式を、GitHubリポジトリ `positions` のルートへアップロードします。
2. GitHubで `positions` リポジトリを開きます。
3. `Settings` → `Pages` を開きます。
4. `Build and deployment` の `Source` を **GitHub Actions** にします。
5. `Actions` タブで `Build and deploy positions` が成功することを確認します。
6. `Settings` → `Pages` に表示されたURLを開きます。

ZIP内の `positions` フォルダ自体をアップロードするのではなく、フォルダ内のファイルとフォルダがリポジトリ直下に並ぶようにしてください。

## 日常の使い方

1. eXtreme Gammonでマッチを解析した状態で保存します。
2. GitHubの `imports/` フォルダを開きます。
3. `Add file` → `Upload files` を選択します。
4. `.xg` または `.xgp` をアップロードし、`Commit changes` を押します。
5. GitHub Actions完了後、Pagesの一覧が自動更新されます。

同じ棋譜を再解析して差し替えた場合も、棋譜内容から生成されるMatch IDと局面情報を使って一覧を再構築します。

## 抽出対象を変更する

`config.json` を編集します。

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

### `targetPlayers`

棋譜内の表記と同じプレイヤー名を指定します。大文字・小文字は区別しません。

```json
"targetPlayers": ["yanagi", "別のユーザー名"]
```

空配列にすると、棋譜に含まれる両選手を抽出します。

```json
"targetPlayers": []
```

### エラー基準

```json
"errorThreshold": 0.02,
"blunderThreshold": 0.08
```

`errorThreshold`以上を一覧へ追加し、`blunderThreshold`以上をBlunderとして表示します。

### 対戦相手の匿名化

```json
"anonymizeOpponents": true
```

対戦相手名を公開したくない場合は `true` にします。ただし、アップロードした元の`.xg`ファイル自体はリポジトリ内に残ります。リポジトリがPublicの場合、元ファイルも閲覧可能です。

## フォルダ構成

```text
positions/
├─ imports/                 解析済み.xg / .xgpのアップロード先
├─ scripts/build.py         抽出・SVG生成・サイト構築
├─ site/                    GitHub Pagesの画面
├─ vendor/xgread/           XGファイル解析ライブラリ
├─ .github/workflows/       自動構築・公開設定
├─ config.json              抽出条件
└─ README.md
```

`dist/` はGitHub Actions実行時に自動生成され、Pagesへ直接デプロイされます。リポジトリへの自動コミットは行いません。

## 数値の扱い

Checker Playの確率は、実戦で選択した候補手のXG解析値です。

- 勝率：ゲームに勝つ確率
- G勝率：ギャモン以上で勝つ確率
- 敗率：ゲームに負ける確率
- G負率：ギャモン以上で負ける確率

Double後にPassした局面など、確率ベクトルを表示できないアクションは `—` と表示します。詳細画面ではバックギャモン率と候補手ごとのEquityも確認できます。

## ライセンス・出典

XGファイル解析には、公式XGファイル仕様を実装した `gtback/xgread` を同梱しています。ライセンスは `LICENSES/xgread-LICENSE.txt` を参照してください。

盤面SVGは本プロジェクト独自の描画であり、bgLogの画像やプログラムを複製していません。


## 自動公開

`main` ブランチへ変更をコミットすると、`.xg`、HTML、CSS、JavaScript、設定、解析スクリプトなど、更新したファイルの種類にかかわらず `Build and deploy positions` が自動実行されます。処理完了後、GitHub Pagesへ自動反映されます。
