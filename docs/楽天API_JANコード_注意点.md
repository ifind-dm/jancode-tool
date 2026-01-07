# 楽天API・JANコード 注意点まとめ

> 更新日: 2026-01-07  
> 競合JANコード検索ツール開発時の知見

---

## 1. 楽天APIでJANコードは取得できない

### 問題
楽天商品検索API（IchibaItem/Search）のレスポンスに `jan` フィールドはあるが、**ほぼ空っぽ**。

```json
{
  "Item": {
    "itemName": "アイリスのお茶 緑",
    "itemPrice": 2530,
    "jan": "",           // ← 空！
    "shopName": "楽天24"
  }
}
```

### 解決策：4つの方法でJANコードを探す

| 優先度 | 方法 | 信頼度 | 説明 |
|--------|------|--------|------|
| 1 | APIのjanフィールド | ★★★★★ | あれば最も確実（ほぼない） |
| 2 | URLから抽出 | ★★★★☆ | `/shop/4901234567890/` のようなURL |
| 3 | 商品説明から抽出 | ★★★☆☆ | 説明文に「JAN: 4901234567890」など |
| 4 | ページスクレイピング | ★★★☆☆ | 商品ページから探す |

---

## 2. JANコードのバリデーション（チェックディジット）

### 問題
13桁の数字を探すと、JANコードではないものが混入する。

```
1045627221757  ← 楽天アプリIDの一部！JANではない
```

### 解決策

```python
def is_valid_jan(code: str) -> bool:
    if len(code) != 13 or not code.isdigit():
        return False
    if code.startswith('10'):  # 楽天ID対策
        return False
    
    # チェックディジット計算
    odd_sum = sum(int(code[i]) for i in range(0, 12, 2))
    even_sum = sum(int(code[i]) for i in range(1, 12, 2))
    total = odd_sum + even_sum * 3
    check_digit = (10 - (total % 10)) % 10
    
    return int(code[12]) == check_digit
```

### チェックディジットとは
JANコードの最後の1桁は、前の12桁から計算で求められる「検算用の数字」。
正しいJANコードかどうかを数学的に検証できる。

---

## 3. 商品ID検索が機能しない問題

### 問題
```
URL: https://item.rakuten.co.jp/irisplaza-r/1909734/
API検索: shopCode=irisplaza-r, keyword=1909734
結果: 0件！
```

### 理由
楽天APIは**全文検索**であり、**商品ID検索**ではない。

```
keyword=1909734 で検索
  ↓
商品名・説明文に「1909734」が含まれているか探す
  ↓
商品IDはURLにしかないのでヒットしない！
```

### 解決策：2段階検索

```python
# Step1: 商品IDでショップ内検索
items = api.search(shopCode=shop, keyword=item_id)

if not found:
    # Step2: ページタイトルから商品名を取得
    product_name = scrape_title(url)  # "マスク 美フィット..."
    
    # Step3: 商品名でショップ内検索
    items = api.search(shopCode=shop, keyword=product_name)
```

---

## 4. スクレイピングで価格が取れない問題

### 問題
楽天のページはJavaScriptで動的に価格を表示しているため、
通常のHTTPリクエストでは価格が取得できない。

```python
response = requests.get(url)
# → 価格情報がHTMLに含まれていない
```

### 解決策
- API検索で見つかった商品の価格を使用する
- スクレイピングは**JANコード抽出のみ**に使用

---

## 5. JANコードの構造

### 13桁の構成
```
4 901234 56789 0
↑ ↑      ↑     ↑
│ │      │     └─ チェックディジット（1桁）
│ │      └─────── 商品アイテムコード（3〜5桁）
│ └────────────── 事業者コード（5〜7桁）
└──────────────── 国コード
```

### 日本のJANコード
- **45** または **49** で始まる
- スクレイピングで45/49始まりを優先すると精度UP

### 注意
- 類似商品でもJANコードは似ていない（メーカー単位で付与）
- 同じメーカーなら先頭が同じ（事業者コード共通）

---

## 6. 現在の実装ロジック

### 商品情報取得フロー

```
入力: 楽天URL（例: item.rakuten.co.jp/shop/12345/）
  ↓
Step1: URL解析
  shop_code = "shop"
  item_id = "12345"
  ↓
Step2: API検索（ショップ + 商品ID）
  結果あり → URLに商品ID含む？ → YES → 使用
                              → NO → Step3へ
  結果なし → Step3へ
  ↓
Step3: フォールバック
  ページタイトルから商品名を取得（スクレイピング）
  商品名でAPI再検索
  類似商品を使用
  ↓
Step4: 競合検索
  同カテゴリ + 価格帯 で検索
  自社ショップを除外
  ↓
Step5: JAN抽出（4つの方法）
  並列スクレイピングで高速化
```

### JAN抽出フロー

```
1. API janフィールド → あれば使用
   ↓ なければ
2. URLから13桁抽出 → チェックディジット検証 → 有効なら使用
   ↓ なければ
3. 商品説明から13桁抽出 → チェックディジット検証 → 有効なら使用
   ↓ なければ
4. ページスクレイピング → "JANコード: ..." パターン検索
   → 45/49始まりを優先
```

---

## 7. パフォーマンス最適化

### 並列スクレイピング
```python
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(scrape_jan, url): item for ...}
```
- 5並列でスクレイピング
- 30件 → 約6秒（直列だと30秒）

---

## 8. 制限事項

| 項目 | 制限 |
|------|------|
| API呼び出し | 1秒1リクエスト程度 |
| 検索結果 | 最大30件/リクエスト |
| JANコード | 登録されていない商品が多い |
| 一部商品 | APIで直接検索不可（フォールバック必要） |

---

## 9. 価格帯設定

### 問題
単品商品（例: マスク1枚20円）で±30%検索すると、
箱入り商品（50枚1000円）が見つからない。

### 解決策：3つのモード
| モード | 動作 |
|--------|------|
| 自動 | 商品価格の±30% |
| カスタム | ユーザー指定の価格帯 |
| 制限なし | カテゴリのみで検索 |

---

## 参考リンク

- [楽天商品検索API](https://webservice.rakuten.co.jp/documentation/ichiba-item-search)
- [楽天商品価格ナビAPI](https://webservice.rakuten.co.jp/documentation/ichiba-product-search)
- [Qiita: 楽天の商品情報を取得する](https://qiita.com/DisneyAladdin/items/d136a04b715de59ade57)
