# Python 3.12 slim image
FROM python:3.12-slim

# 作業ディレクトリ
WORKDIR /app

# 依存関係をコピー＆インストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# Cloud Runは8080ポートを使用
EXPOSE 8080

# Uvicornでアプリを起動
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

