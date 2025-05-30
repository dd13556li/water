#!/bin/bash
echo "🚀 啟動 Flask 後端..."
cd backend
source ../env/bin/activate  # 啟動虛擬環境
python app.py &             # 以背景模式啟動 Flask

echo "🌍 啟動前端伺服器..."
cd ../frontend
python -m http.server 8000  # 啟動前端伺服器

echo "✅ 後端：http://127.0.0.1:5000/"
echo "✅ 前端：http://127.0.0.1:8000/"
