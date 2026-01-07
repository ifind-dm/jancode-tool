import os
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

class RakutenAPI:
    def __init__(self):
        self.app_id = os.environ.get("RAKUTEN_APP_ID")
        self.base_url = "https://app.rakuten.co.jp/services/api"
    
    def _is_valid_jan(self, code: str) -> bool:
        """JANコード（EAN-13）のチェックディジットを検証"""
        if not code or len(code) != 13 or not code.isdigit():
            return False
        if code.startswith('10'):
            return False
        odd_sum = sum(int(code[i]) for i in range(0, 12, 2))
        even_sum = sum(int(code[i]) for i in range(1, 12, 2))
        total = odd_sum + even_sum * 3
        check_digit = (10 - (total % 10)) % 10
        return int(code[12]) == check_digit
    
    def _extract_jan_full(self, item: dict, scrape_if_missing: bool = False) -> tuple[str, str]:
        """4つの方法でJANコードを探す"""
        item_url = item.get("itemUrl", "") or item.get("url", "")
        caption = item.get("itemCaption", "")
        
        api_jan = item.get("jan", "")
        if api_jan and self._is_valid_jan(api_jan):
            return (api_jan, "API")
        
        jan_in_url = re.findall(r'[0-9]{13}', item_url)
        for jan in jan_in_url:
            if self._is_valid_jan(jan):
                return (jan, "URL")
        
        jan_in_caption = re.findall(r'[0-9]{13}', caption)
        for jan in jan_in_caption:
            if self._is_valid_jan(jan):
                return (jan, "説明文")
        
        if scrape_if_missing and item_url:
            scraped_jan = self._scrape_jan_from_page(item_url)
            if scraped_jan:
                return (scraped_jan, "スクレイピング")
        
        return ("", "")
    
    def _scrape_jan_from_page(self, url: str) -> str:
        """商品ページをスクレイピングしてJANコードを取得"""
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            page_text = soup.get_text()
            
            jan_patterns = [
                r'JAN[コード：:\s]*([0-9]{13})',
                r'JANコード[：:\s]*([0-9]{13})',
                r'EAN[：:\s]*([0-9]{13})',
            ]
            for pattern in jan_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match and self._is_valid_jan(match.group(1)):
                    return match.group(1)
            
            all_13_digits = re.findall(r'[0-9]{13}', page_text)
            for jan in all_13_digits:
                if self._is_valid_jan(jan) and (jan.startswith('45') or jan.startswith('49')):
                    return jan
            for jan in all_13_digits:
                if self._is_valid_jan(jan):
                    return jan
        except:
            pass
        return ""
    
    def _get_product_name_from_page(self, shop_code: str, item_id: str) -> str:
        """ページタイトルから商品名を取得"""
        url = f"https://item.rakuten.co.jp/{shop_code}/{item_id}/"
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.text
                # 【楽天市場】商品名:ショップ名 のパターン
                if '【楽天市場】' in title:
                    product_name = title.replace('【楽天市場】', '').split(':')[0].strip()
                    # 最初の数単語を取得（検索キーワード用）
                    words = product_name.split()[:5]
                    return ' '.join(words)
        except:
            pass
        return ""
    
    def get_item(self, shop_code: str, item_id: str) -> dict | None:
        """ショップコードと商品IDで商品を検索"""
        url = f"{self.base_url}/IchibaItem/Search/20220601"
        
        # 方法1: ショップ + 商品ID でキーワード検索
        params = {
            "applicationId": self.app_id,
            "shopCode": shop_code,
            "keyword": item_id,
            "hits": 10
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            items = data.get("Items", [])
            
            print(f"[API検索1] ショップ:{shop_code} キーワード:{item_id} → {len(items)}件")
            
            if items:
                # URLに商品IDが含まれるものを探す
                for item_data in items:
                    item = item_data["Item"]
                    item_url = item.get("itemUrl", "")
                    if item_id in item_url:
                        print(f"[API] ✓ URLマッチ: {item.get('itemName', '')[:40]}...")
                        return self._parse_item(item, scrape_jan=True)
        except requests.RequestException as e:
            print(f"[API] エラー: {e}")
        
        # 方法2: ページタイトルから商品名を取得 → キーワード検索
        print(f"[フォールバック] ページタイトルから商品名を取得...")
        product_name = self._get_product_name_from_page(shop_code, item_id)
        
        if product_name:
            print(f"[フォールバック] 商品名: {product_name}")
            params = {
                "applicationId": self.app_id,
                "shopCode": shop_code,
                "keyword": product_name,
                "hits": 10
            }
            
            try:
                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                items = data.get("Items", [])
                
                print(f"[API検索2] キーワード:「{product_name[:20]}...」→ {len(items)}件")
                
                if items:
                    # 最初の商品を使用（同ショップなので類似商品）
                    first_item = items[0]["Item"]
                    print(f"[API] ✓ 類似商品: {first_item.get('itemName', '')[:40]}...")
                    return self._parse_item(first_item, scrape_jan=True)
            except requests.RequestException as e:
                print(f"[API] エラー: {e}")
        
        print(f"[結果] 商品が見つかりませんでした")
        return None
    
    def _parse_item(self, item: dict, scrape_jan: bool = False) -> dict:
        """APIレスポンスから商品情報を抽出"""
        jan, jan_source = self._extract_jan_full(item, scrape_if_missing=scrape_jan)
        if jan:
            print(f"[JAN取得] {jan} ← {jan_source}")
        
        return {
            "name": item.get("itemName", ""),
            "price": item.get("itemPrice", 0),
            "categoryId": str(item.get("genreId", "")),
            "shopId": item.get("shopCode", ""),
            "shopName": item.get("shopName", ""),
            "image": item.get("mediumImageUrls", [{}])[0].get("imageUrl", "") if item.get("mediumImageUrls") else "",
            "jan": jan,
            "janSource": jan_source,
            "url": item.get("itemUrl", ""),
            "categoryName": ""
        }
    
    def search_competitors(self, category_id: str, price_min: int, 
                          price_max: int, exclude_shop: str) -> list:
        """同カテゴリの競合商品を検索"""
        url = f"{self.base_url}/IchibaItem/Search/20220601"
        params = {
            "applicationId": self.app_id,
            "genreId": category_id,
            "minPrice": price_min,
            "maxPrice": price_max,
            "hits": 30
        }
        
        print(f"\n=== 競合検索 ===")
        print(f"カテゴリID: {category_id}")
        print(f"価格帯: ¥{price_min:,} 〜 ¥{price_max:,}")
        print(f"除外ショップ: {exclude_shop}")
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            items = data.get("Items", [])
            
            print(f"検索結果: {len(items)}件")
            
            competitors = []
            items_to_scrape = []
            
            for item_data in items:
                item = item_data["Item"]
                if item.get("shopCode", "") != exclude_shop:
                    jan, jan_source = self._extract_jan_full(item, scrape_if_missing=False)
                    if jan:
                        print(f"[JAN取得] {jan} ← {jan_source}")
                    
                    competitor = {
                        "name": item.get("itemName", ""),
                        "price": item.get("itemPrice", 0),
                        "image": item.get("mediumImageUrls", [{}])[0].get("imageUrl", "") if item.get("mediumImageUrls") else "",
                        "jan": jan,
                        "janSource": jan_source,
                        "url": item.get("itemUrl", ""),
                        "shop": item.get("shopName", "")
                    }
                    competitors.append(competitor)
                    if not jan:
                        items_to_scrape.append(competitor)
            
            if items_to_scrape:
                print(f"\n[スクレイピング] {len(items_to_scrape)}件のページをスキャン中...")
                with ThreadPoolExecutor(max_workers=5) as executor:
                    future_to_item = {
                        executor.submit(self._scrape_jan_from_page, item["url"]): item 
                        for item in items_to_scrape
                    }
                    for future in as_completed(future_to_item):
                        item = future_to_item[future]
                        try:
                            jan = future.result()
                            if jan:
                                item["jan"] = jan
                                item["janSource"] = "スクレイピング"
                                print(f"[JAN取得] {jan} ← スクレイピング")
                        except:
                            pass
            
            jan_count = sum(1 for c in competitors if c["jan"])
            print(f"\n=== 結果: {jan_count}/{len(competitors)}件 でJAN取得成功 ===\n")
            
            competitors.sort(key=lambda x: (x["jan"] == "", x["name"]))
            return competitors
            
        except requests.RequestException as e:
            print(f"API Error: {e}")
        return []
