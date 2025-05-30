@echo off
echo 啟動 Flask 後端...
cd backend
call ..\env\Scripts\activate
start python app.py

echo 啟動前端伺服器...
cd ../frontend
start python -m http.server 8000

echo ✅ Flask API 運行於 http://127.0.0.1:5000/
echo ✅ 前端運行於 http://127.0.0.1:8000/
echo 🎯 請在瀏覽器開啟前端網址！
