# init_db_script.py
# 從 app.py 導入 app 物件、init_db 函數，以及 DATABASE 和 DEFAULT_FILTERS 變數
# 由於 DATABASE 和 DEFAULT_FILTERS 現在定義在 app.py 的頂層，可以被正確導入
from app import app, init_db, DATABASE, DEFAULT_FILTERS 

print("DEBUG: 執行 init_db_script.py 腳本...")
with app.app_context(): # 確保在應用程式上下文中執行 init_db()
    try:
        init_db()
        print("DEBUG: init_db_script.py: 資料庫初始化成功。")
    except Exception as e:
        print(f"CRITICAL ERROR: init_db_script.py: 資料庫初始化失敗: {e}")
        import sys
        sys.exit(1) # 如果初始化失敗，讓腳本退出，以便 Render 知道部署失敗
