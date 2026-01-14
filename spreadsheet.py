"""
Google スプレッドシート連携モジュール

認証方式:
- OAuth: テスト用（初回ブラウザ認証が必要）
- サービスアカウント: 本番用（JSONキーのみ）

環境変数:
- SPREADSHEET_AUTH_TYPE: "oauth" or "service_account"
- SPREADSHEET_ID: スプレッドシートID
- GOOGLE_CREDENTIALS_PATH: 認証情報ファイルのパス
"""

import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class SpreadsheetClient:
    def __init__(self):
        self.auth_type = os.environ.get("SPREADSHEET_AUTH_TYPE", "oauth")
        self.spreadsheet_id = os.environ.get("SPREADSHEET_ID")
        self.creds_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        self.client = None
        self.spreadsheet = None
    
    def connect(self) -> bool:
        """スプレッドシートに接続"""
        try:
            import gspread
        except ImportError:
            print("❌ gspread がインストールされていません")
            print("   pip install gspread google-auth google-auth-oauthlib")
            return False
        
        if not self.spreadsheet_id:
            print("❌ SPREADSHEET_ID が設定されていません")
            return False
        
        try:
            if self.auth_type == "service_account":
                self.client = self._auth_service_account()
            else:
                self.client = self._auth_oauth()
            
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            print(f"✅ スプレッドシート接続成功: {self.spreadsheet.title}")
            return True
            
        except Exception as e:
            print(f"❌ 接続エラー: {e}")
            return False
    
    def _auth_service_account(self):
        """サービスアカウント認証"""
        import gspread
        from google.oauth2.service_account import Credentials
        
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_file(self.creds_path, scopes=scopes)
        return gspread.authorize(creds)
    
    def _auth_oauth(self):
        """OAuth認証（初回はブラウザ認証が必要）"""
        import gspread
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        import json
        
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        token_path = "token.json"
        creds = None
        
        # 保存済みトークンがあれば読み込み
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, scopes)
        
        # トークンがないか期限切れの場合
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # OAuth クライアント設定ファイルから認証
                if not os.path.exists(self.creds_path):
                    print(f"❌ OAuth設定ファイルが見つかりません: {self.creds_path}")
                    print("\n📋 設定手順:")
                    print("1. Google Cloud Console → 認証情報")
                    print("2. 「OAuthクライアントIDを作成」→「デスクトップアプリ」")
                    print("3. JSONをダウンロードして credentials.json として保存")
                    raise FileNotFoundError(self.creds_path)
                
                flow = InstalledAppFlow.from_client_secrets_file(self.creds_path, scopes)
                creds = flow.run_local_server(port=0)
            
            # トークンを保存
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
            print("✅ 認証トークンを保存しました")
        
        return gspread.authorize(creds)
    
    def get_sheets(self) -> list[str]:
        """シート一覧を取得"""
        if not self.spreadsheet:
            return []
        return [sheet.title for sheet in self.spreadsheet.worksheets()]
    
    def append_jan_data(self, sheet_name: str, data: list[dict]) -> int:
        """JANコードデータをシートに追記
        
        Args:
            sheet_name: シート名
            data: [{"jan": "xxx", "name": "xxx", "shop": "xxx", "price": 123, "url": "xxx"}, ...]
        
        Returns:
            追加した行数
        """
        if not self.spreadsheet:
            raise Exception("スプレッドシートに接続されていません")
        
        try:
            sheet = self.spreadsheet.worksheet(sheet_name)
        except:
            # シートがなければ作成
            sheet = self.spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=10)
            # ヘッダーを追加
            headers = ["JANコード", "商品名", "ショップ", "価格", "URL", "取得日時"]
            sheet.update('A1', [headers])
            print(f"✅ 新しいシート「{sheet_name}」を作成しました")
        
        # 既存データを確認
        existing = sheet.get_all_values()
        
        # ヘッダーがなければ追加
        expected_headers = ["JANコード", "商品名", "ショップ", "価格", "URL", "取得日時"]
        if not existing or existing[0] != expected_headers:
            sheet.update('A1', [expected_headers])
            existing = [expected_headers]
        
        # データを行形式に変換
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = []
        for item in data:
            row = [
                item.get("jan", ""),
                item.get("name", ""),
                item.get("shop", ""),
                str(item.get("price", "")),
                item.get("url", ""),
                now
            ]
            rows.append(row)
        
        # 最終行の次に追加
        next_row = len(existing) + 1
        if rows:
            sheet.update(f'A{next_row}', rows)
            print(f"✅ {len(rows)}件のデータを追加しました（{next_row}行目〜）")
        
        return len(rows)
    
    def find_existing_jans(self, sheet_name: str) -> set[str]:
        """既存のJANコードを取得（重複チェック用）"""
        if not self.spreadsheet:
            return set()
        
        try:
            sheet = self.spreadsheet.worksheet(sheet_name)
            values = sheet.col_values(1)  # A列（JANコード）
            # ヘッダーを除外
            return set(values[1:]) if len(values) > 1 else set()
        except:
            return set()


# テスト用
if __name__ == "__main__":
    print("=" * 50)
    print("スプレッドシート接続テスト")
    print("=" * 50)
    
    client = SpreadsheetClient()
    
    if client.connect():
        print(f"\n📊 シート一覧: {client.get_sheets()}")
        
        response = input("\nテストデータを書き込みますか？ (y/n): ")
        if response.lower() == 'y':
            sheet_name = input("シート名（空欄で「JANマスタ」）: ").strip() or "JANマスタ"
            
            test_data = [
                {"jan": "4901234567890", "name": "テスト商品A", "shop": "テストショップ", "price": 1980, "url": "https://example.com/a"},
                {"jan": "4901234567891", "name": "テスト商品B", "shop": "テストショップ", "price": 2480, "url": "https://example.com/b"},
            ]
            
            count = client.append_jan_data(sheet_name, test_data)
            print(f"\n✅ {count}件追加完了！スプレッドシートを確認してください")


