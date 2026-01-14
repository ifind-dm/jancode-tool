# GCP 基礎知識

Cloud Run デプロイやGoogle API連携で知っておくと便利な概念をまとめます。

---

## サービスアカウントとは

**プログラム（サーバー・アプリ）用のGoogleアカウント**

### 人間のアカウント vs サービスアカウント

| | 人間のアカウント | サービスアカウント |
|---|---|---|
| **例** | `s.tsukiji@ifind.co.jp` | `xxx-compute@developer.gserviceaccount.com` |
| **使う人** | あなた | プログラム・サーバー |
| **ログイン方法** | パスワード、2段階認証 | JSONキー、自動認証 |
| **用途** | GCPコンソール操作、gcloud | Cloud Run、Cloud Build などが動く |

### イメージ図

```
┌─────────────────────────────────────────────────────────┐
│  GCPプロジェクト                                         │
│                                                         │
│   👤 s.tsukiji@ifind.co.jp                              │
│      └─ あなたが gcloud コマンドを打つときに使う         │
│                                                         │
│   🤖 {番号}-compute@developer.gserviceaccount.com       │
│      └─ Cloud Run がファイルを読んだり動いたりするとき   │
│                                                         │
│   🤖 {番号}@cloudbuild.gserviceaccount.com              │
│      └─ Cloud Build が Docker イメージをビルドするとき   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### サービスアカウントの使い道

1. **GCPサービス間の連携**
   - Cloud Run → Cloud Storage を読む
   - Cloud Build → Artifact Registry にイメージを保存

2. **外部APIへのアクセス**
   - アプリ → Google Sheets API
   - アプリ → Google Drive API

---

## プロジェクトID vs プロジェクト番号

| 名前 | 例 | 決め方 |
|------|-----|--------|
| プロジェクト**ID** | `ifind-data-analysis` | 自分で決める（変更不可） |
| プロジェクト**番号** | `70665159483` | Google が自動割当 |

### 確認方法

```bash
# プロジェクト番号を確認
gcloud projects describe ifind-data-analysis --format='value(projectNumber)'
```

### サービスアカウントとの関係

サービスアカウントのメールアドレスには**プロジェクト番号**が含まれる：

```
{プロジェクト番号}-compute@developer.gserviceaccount.com
{プロジェクト番号}@cloudbuild.gserviceaccount.com
```

---

## Cloud Run ソースデプロイの仕組み

`gcloud run deploy --source .` を実行したときの流れ：

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  1. ソースコード     2. Cloud Storage      3. Cloud Build      │
│     (ローカル)          (一時保存)            (ビルド)          │
│                                                                 │
│   main.py ─────────►  gs://bucket/ ─────────► Dockerイメージ   │
│   rakuten.py           にアップロード         を作成            │
│   Dockerfile                                                    │
│                                                                 │
│                                                                 │
│  4. Artifact Registry    5. Cloud Run                          │
│     (イメージ保存)          (実行)                              │
│                                                                 │
│   イメージを保存 ─────────► コンテナ起動 🚀                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 各ステップで使われるサービスアカウント

| ステップ | サービスアカウント | 必要な権限 |
|----------|-------------------|-----------|
| 2→3 | `{番号}-compute@...` | Storage オブジェクト閲覧者 |
| 3 | `{番号}@cloudbuild...` | Cloud Build サービスアカウント |
| 4 | Cloud Build | Artifact Registry 書き込み |
| 5 | `{番号}-compute@...` | Cloud Run 呼び出し元 |

---

## IAM（権限管理）

### よく使うロール

| ロール | 説明 |
|--------|------|
| `roles/owner` | オーナー（全権限） |
| `roles/editor` | 編集者（IAM以外の全権限） |
| `roles/viewer` | 閲覧者（読み取りのみ） |
| `roles/storage.objectViewer` | Storage オブジェクト閲覧者 |
| `roles/storage.objectAdmin` | Storage オブジェクト管理者 |
| `roles/run.admin` | Cloud Run 管理者 |

### 権限付与コマンド

```bash
gcloud projects add-iam-policy-binding {プロジェクトID} \
  --member="serviceAccount:{サービスアカウント}" \
  --role="{ロール}"
```

### 例：Storage 閲覧権限を付与

```bash
gcloud projects add-iam-policy-binding ifind-data-analysis \
  --member="serviceAccount:70665159483-compute@developer.gserviceaccount.com" \
  --role="roles/storage.objectViewer"
```

---

## Cloud Run の認証

### 認証モード2種類

```
【モードA: 公開（--allow-unauthenticated）】

   誰でも ──────────────────────────► アプリ
          門番「どうぞ〜」              ✅ アクセスOK

   ※ 組織ポリシーで禁止されている場合あり


【モードB: 認証必須（デフォルト）】

   誰か ──────► 門番「認証トークン見せて」
                      │
         ┌────────────┼────────────┐
         │            │            │
         ▼            ▼            ▼
     トークン      トークン      トークン
       なし         無効          有効
         │            │            │
         ▼            ▼            ▼
    ❌ 403        ❌ 403       ✅ 通過 ──► アプリ
    Forbidden     Forbidden
```

### 認証トークンとは

```
┌──────────────────────────────────────────────────────────────┐
│  認証トークン = 「私は〇〇です」という証明書                    │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodH... │ │
│  │  （めっちゃ長い暗号文字列）                               │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  中身:                                                       │
│   - 誰か: s.tsukiji@ifind.co.jp                             │
│   - 発行者: Google                                          │
│   - 有効期限: 1時間                                          │
└──────────────────────────────────────────────────────────────┘
```

### 誰がアクセスできるか（IAM）

```
Cloud Run サービス jancode-tool
         │
         │  roles/run.invoker（起動権限）を持ってる人だけ通す
         │
         ├─► allUsers         → 誰でもOK（❌ 会社ポリシーで禁止）
         │
         ├─► user:xxx@ifind.co.jp        → この人だけOK
         │
         ├─► domain:ifind.co.jp          → 会社の人全員OK
         │
         └─► group:team@ifind.co.jp      → このグループの人OK
```

### アクセス方法の比較

```
【方法A: gcloud proxy】

   あなたのPC
   ┌─────────────────────────────┐
   │  localhost:8080             │
   │       │                     │
   │       ▼                     │
   │  ┌─────────┐                │
   │  │ proxy   │ ← gcloudが自動でトークン付ける
   │  └────┬────┘                │
   └───────┼─────────────────────┘
           │ + トークン
           ▼
       Cloud Run ──► ✅ OK

   コマンド:
   $ gcloud run services proxy jancode-tool --region=asia-northeast1 --port=8080


【方法B: curl + トークン】

   $ gcloud auth print-identity-token
         │
         ▼
   トークン取得（eyJhbG...）
         │
         ▼
   $ curl -H "Authorization: Bearer トークン" URL
         │
         ▼
   Cloud Run ──► ✅ OK


【方法C: IAP 経由】← 会社推奨

   ブラウザ ──► IAP（Googleログイン画面）──► Cloud Run
                      │
                Googleアカウントで
                ログインすると
                自動でトークン付く
```

### 組織ポリシーについて

```
┌─────────────────────────────────────────────────────────────┐
│  組織ポリシー                                                │
│                                                             │
│  「Cloud Run を allUsers に公開してはダメ」                   │
│                                                             │
│       ↓ つまり                                              │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  --allow-unauthenticated は使えない                  │   │
│  │  必ず認証が必要な状態にすること                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  理由: セキュリティ（社内ツールを外部に公開しない）           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 認証方式の比較（Google API用）

Google API（Sheets, Drive など）にアクセスする方法：

| 方式 | 用途 | 特徴 |
|------|------|------|
| **OAuth 2.0** | 個人・テスト | 初回ブラウザ認証、ユーザーごとに許可 |
| **サービスアカウント** | サーバー・本番 | JSONキーで自動認証、審査不要 |
| **APIキー** | 公開データのみ | 読み取り専用、書き込み不可 |

### OAuth vs サービスアカウント

```
【OAuth】
ユーザー ──(ブラウザログイン)──► アプリ ──► Google API
                                  │
                             ユーザーの権限で動く

【サービスアカウント】
アプリ ──(JSONキー)──► Google API
    │
サービスアカウントの権限で動く
（スプシ等は共有設定が必要）
```

---

## トラブルシューティング

### よくあるエラーと対処

| エラー | 原因 | 対処 |
|--------|------|------|
| `does not have storage.objects.get access` | Storage 読み取り権限なし | `roles/storage.objectViewer` を付与 |
| `does not have permission to access projects instance` | IAM確認権限なし | プロジェクト管理者に依頼 |
| `Spreadsheet not found` | スプシが共有されていない | サービスアカウントに共有 |

### 権限確認コマンド

```bash
# 自分のアカウント確認
gcloud config get-value account

# 自分の権限確認（権限があれば）
gcloud projects get-iam-policy {プロジェクトID} \
  --flatten="bindings[].members" \
  --filter="bindings.members:{メールアドレス}" \
  --format="table(bindings.role)"
```

---

## 参考リンク

- [GCP IAM ドキュメント](https://cloud.google.com/iam/docs)
- [Cloud Run ドキュメント](https://cloud.google.com/run/docs)
- [サービスアカウントについて](https://cloud.google.com/iam/docs/service-accounts)


