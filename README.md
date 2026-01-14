# 競合JANコード検索ツール

楽天の商品URLを入力すると、同カテゴリ・同価格帯の競合商品を一覧表示し、JANコードをCSVでエクスポートできるツールです。

## 機能

- 🔍 楽天URLから商品情報を自動取得
- 📊 同カテゴリ・価格帯の競合商品を検索
- 🏷️ JANコード自動抽出（4つの方法で探索）
- ✅ チェックボックスで競合を選択
- 📥 選択した商品をCSVエクスポート
- 💰 価格帯のカスタム指定対応

## セットアップ

### 1. 楽天APIアプリIDを取得

1. https://webservice.rakuten.co.jp/ にアクセス
2. 楽天会員でログイン
3. 「アプリID発行」からアプリを登録
4. 発行されたアプリIDをメモ

### 2. 環境構築

```bash
# venv作成
python -m venv venv

# 有効化（Mac/Linux/WSL）
source venv/bin/activate

# 有効化（Windows PowerShell）
venv\Scripts\Activate.ps1

# パッケージインストール
pip install -r requirements.txt
```

### 3. 環境変数設定

`.env` ファイルを作成：

```
RAKUTEN_APP_ID=あなたのアプリID
```

### 4. 起動

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

ブラウザで http://localhost:8000 にアクセス

## 使い方

1. 自社商品の楽天URLを入力
2. 価格帯を設定（自動/カスタム/制限なし）
3. 「競合を検索」をクリック
4. 同カテゴリ・価格帯の商品が一覧表示
5. 競合だと思う商品にチェック
6. 「CSVエクスポート」でダウンロード

## 技術スタック

- **バックエンド**: FastAPI
- **テンプレート**: Jinja2
- **非同期通信**: htmx
- **スタイル**: Tailwind CSS
- **API**: 楽天商品検索API
- **スクレイピング**: BeautifulSoup4

## ディレクトリ構成

```
jancode-tool/
├── main.py              # FastAPIアプリ
├── rakuten.py           # 楽天API・スクレイピング
├── templates/
│   ├── base.html        # ベーステンプレート
│   ├── index.html       # メイン画面
│   ├── results.html     # 検索結果
│   └── error.html       # エラー画面
├── docs/
│   └── 楽天API_JANコード_注意点.md
├── requirements.txt
├── .env                 # 環境変数（要作成）
└── README.md
```

## 処理フロー

```
1. URL入力 → ショップID・商品ID抽出
2. 楽天API検索（ショップ + 商品ID）
   ├─ 見つかった → 商品情報取得
   └─ 見つからない → ページタイトルから商品名取得
                    → 商品名でAPI再検索
3. 競合検索（同カテゴリ + 価格帯）
4. JANコード抽出（4つの方法）
   ├─ API janフィールド
   ├─ URLから正規表現
   ├─ 商品説明から正規表現
   └─ ページスクレイピング
5. 結果表示（JANあり優先）
```

## Cloud Runへのデプロイ

### 前提条件

- Google Cloud SDK (gcloud) がインストール済み
- GCPプロジェクトが作成済み

### デプロイ手順

```bash
# 1. ログイン
gcloud auth login

# 2. プロジェクト設定
gcloud config set project ifind-data-analysis

# 3. デプロイ
gcloud run deploy jancode-tool --source . --region asia-northeast1 --allow-unauthenticated
```

### 環境変数の設定

楽天APIキーなどはCloud Runの環境変数で設定：

```bash
gcloud run deploy jancode-tool \
  --source . \
  --region asia-northeast1 \
  --allow-unauthenticated \
  --set-env-vars "RAKUTEN_APP_ID=your_app_id"
```

### コード変更後の再デプロイ

同じコマンドを再実行するだけ：

```bash
gcloud run deploy jancode-tool --source . --region asia-northeast1 --allow-unauthenticated
```

## 制限事項

- 楽天の商品のみ対象（Amazon等は非対応）
- JANコードがない商品もあります
- 楽天API呼び出し制限あり（1秒1リクエスト程度）
- 一部商品はAPIで直接検索できない場合があります

## 関連ドキュメント

- [デプロイ手順](docs/デプロイ手順.md)
- [GCP基礎知識](docs/GCP基礎知識.md)
- [楽天API・JANコード注意点](docs/楽天API_JANコード_注意点.md)
