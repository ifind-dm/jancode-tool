from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from typing import Optional
import re
import csv
import io
from rakuten import RakutenAPI

# .envファイルから環境変数を読み込み
load_dotenv()

app = FastAPI(title="競合JANコード検索ツール")
templates = Jinja2Templates(directory="templates")
rakuten = RakutenAPI()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """メインページ"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/search", response_class=HTMLResponse)
async def search(
    request: Request, 
    url: str = Form(...),
    price_mode: str = Form(default="auto"),
    price_min: Optional[int] = Form(default=None),
    price_max: Optional[int] = Form(default=None)
):
    """楽天URLから競合商品を検索"""
    # 1. URLからショップIDと商品IDを抽出
    parsed = extract_ids_from_url(url)
    if not parsed:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "message": "URLが不正です。楽天の商品URLを入力してください。"
        })
    
    shop_code, item_id = parsed
    
    # 2. 商品詳細取得（API使用）
    product = rakuten.get_item(shop_code, item_id)
    if not product:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "message": "商品が見つかりません。URLを確認してください。"
        })
    
    # 3. 価格帯の決定
    if price_mode == "custom" and price_min is not None and price_max is not None:
        # カスタム指定
        search_price_min = price_min
        search_price_max = price_max
        price_mode_label = "カスタム"
    elif price_mode == "none":
        # 価格制限なし
        search_price_min = 0
        search_price_max = 999999999
        price_mode_label = "制限なし"
    else:
        # 自動（±30%）
        search_price_min = int(product["price"] * 0.7)
        search_price_max = int(product["price"] * 1.3)
        price_mode_label = "自動（±30%）"
    
    print(f"[価格帯] {price_mode_label}: ¥{search_price_min:,} 〜 ¥{search_price_max:,}")
    
    # 4. 同カテゴリ商品検索
    competitors = rakuten.search_competitors(
        category_id=product["categoryId"],
        price_min=search_price_min,
        price_max=search_price_max,
        exclude_shop=product["shopId"]
    )
    
    return templates.TemplateResponse("results.html", {
        "request": request,
        "product": product,
        "competitors": competitors,
        "price_min": search_price_min,
        "price_max": search_price_max,
        "price_mode_label": price_mode_label
    })


def extract_ids_from_url(url: str) -> tuple[str, str] | None:
    """楽天URLからショップIDと商品IDを抽出"""
    # パターン: item.rakuten.co.jp/shop/item-id/
    pattern = r"item\.rakuten\.co\.jp/([^/]+)/([^/?]+)"
    match = re.search(pattern, url)
    if match:
        return (match.group(1), match.group(2))
    return None


@app.post("/export", response_class=StreamingResponse)
async def export_csv(selected: list[str] = Form(default=[])):
    """選択した商品をCSVエクスポート"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["JANコード", "商品名", "ショップ", "価格", "URL"])
    
    # selectedの形式: "jan|name|shop|price|url"
    for item in selected:
        parts = item.split("|")
        if len(parts) == 5:
            writer.writerow(parts)
    
    output.seek(0)
    
    # BOM付きUTF-8でExcelでも文字化けしない
    bom = '\ufeff'
    content = bom + output.getvalue()
    
    return StreamingResponse(
        iter([content.encode('utf-8')]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=competitors.csv"}
    )
