from flask import Flask, request, jsonify, g
from flask_cors import CORS, cross_origin
import json
import datetime
import os
import sqlite3

app = Flask(__name__)
CORS(app, supports_credentials=True)

# 為了持久性儲存，現在使用 SQLite 資料庫檔案
# 注意：在 Render 免費版中，/tmp/ 是非持久性的。每次服務重啟資料會重置。
DATABASE = "/tmp/filters.db"

# 預設濾心資料，用於資料庫初始化
DEFAULT_FILTERS = [
    {"name": "前置濾網", "last_replace": "2025-05-01", "lifespan": 60},
    {"name": "活性碳濾心", "last_replace": "2025-05-01", "lifespan": 90}
]

# --- 資料庫操作函式 ---

# 獲取資料庫連接
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

# 初始化資料庫：建立表格並插入預設資料 (如果資料庫為空)
def init_db():
    print("DEBUG: 嘗試初始化資料庫...")
    # 注意：這裡我們不再需要 with app.app_context()
    # 因為這個函數會在 Flask app 載入時被調用，那時上下文已經可用
    db = get_db() # 直接獲取 db 連接
    cursor = db.cursor()
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS filters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                last_replace TEXT NOT NULL,
                lifespan INTEGER NOT NULL
            )
        ''')
        db.commit()
        print("DEBUG: 資料表 'filters' 檢查/建立成功。")

        cursor.execute("SELECT COUNT(*) FROM filters")
        if cursor.fetchone()[0] == 0:
            print("DEBUG: 資料庫為空，開始插入預設濾心資料。")
            for f in DEFAULT_FILTERS:
                cursor.execute(
                    "INSERT INTO filters (name, last_replace, lifespan) VALUES (?, ?, ?)",
                    (f["name"], f["last_replace"], f["lifespan"])
                )
            db.commit()
            print("DEBUG: 資料庫已初始化並載入預設濾心資料。")
        else:
            print("DEBUG: 資料庫已存在資料，跳過預設資料插入。")
    except sqlite3.Error as e:
        print(f"ERROR: 初始化資料庫時發生 SQLite 錯誤: {e}")
        raise
    except Exception as e:
        print(f"CRITICAL ERROR: 初始化資料庫時發生未知錯誤: {e}")
        raise

# 在應用程式載入時立即調用 init_db()
# Gunicorn 會載入整個 app.py 檔案，因此這會在服務啟動時執行
try:
    init_db()
    print("DEBUG: 應用程式載入時資料庫初始化完成。")
except Exception as e:
    print(f"CRITICAL ERROR: 應用程式啟動時資料庫初始化失敗: {e}")
    # 如果這裡失敗，應用程式可能無法正常運行，可以選擇讓它崩潰
    # import sys
    # sys.exit(1)


# 在每次請求結束後關閉資料庫連接
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
        print("DEBUG: 資料庫連接已關閉。")

# --- 路由 (以下部分保持不變) ---

@app.route("/")
def home():
    return jsonify({"message": "Flask 服務運行中 🚀"})

@app.route("/filters", methods=["GET"])
def get_filters():
    print("DEBUG: 收到 /filters 請求。")
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT name, last_replace, lifespan FROM filters")
        filters = [dict(row) for row in cursor.fetchall()]
        print(f"DEBUG: 成功獲取 {len(filters)} 筆濾心資料。")
        return jsonify(filters)
    except Exception as e:
        print(f"ERROR: 在 get_filters 中發生錯誤: {e}")
        return jsonify({"message": f"伺服器錯誤: {e}"}), 500

@app.route("/add", methods=["POST"])
def add_filter():
    print("DEBUG: 收到 /add 請求。")
    data = request.json
    if not data:
        print("DEBUG: 請求 JSON 數據為空。")
        return jsonify({"message": "請求必須包含 JSON 數據"}), 400

    required_fields = ["name", "last_replace", "lifespan"]
    for field in required_fields:
        if field not in data:
            print(f"DEBUG: 缺少必填欄位: {field}")
            return jsonify({"message": f"缺少必填欄位: {field}"}), 400
    
    try:
        lifespan_int = int(data["lifespan"])
    except ValueError:
        print(f"DEBUG: lifespan 無法轉換為數字: {data['lifespan']}")
        return jsonify({"message": "lifespan 必須是有效的數字"}), 400

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM filters WHERE name = ?", (data["name"],))
        if cursor.fetchone()[0] > 0:
            print(f"DEBUG: 濾心名稱 '{data['name']}' 已存在。")
            return jsonify({"message": f"濾心名稱 '{data['name']}' 已存在"}), 409
        cursor.execute(
            "INSERT INTO filters (name, last_replace, lifespan) VALUES (?, ?, ?)",
            (data["name"], data["last_replace"], lifespan_int)
        )
        db.commit()
        print(f"DEBUG: 濾心 '{data['name']}' 已成功新增。")
        return jsonify({"message": "濾心已成功新增", "filter": {"name": data["name"], "last_replace": data["last_replace"], "lifespan": lifespan_int}}), 201
    except sqlite3.Error as e:
        print(f"ERROR: 新增濾心時發生 SQLite 錯誤: {e}")
        return jsonify({"message": f"新增濾心時發生錯誤: {e}"}), 500
    except Exception as e:
        print(f"ERROR: 新增濾心時發生未知錯誤: {e}")
        return jsonify({"message": f"新增濾心時發生錯誤: {e}"}), 500


@app.route("/update", methods=["POST"])
def update_filter():
    print("DEBUG: 收到 /update 請求。")
    data = request.json
    
    if not data or "name" not in data:
        print("DEBUG: 更新請求缺少 'name' 欄位。")
        return jsonify({"message": "請提供濾心名稱 (name) 以進行更新"}), 400

    db = get_db()
    cursor = db.cursor()
    
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    
    try:
        cursor.execute(
            "UPDATE filters SET last_replace = ? WHERE name = ?",
            (current_date, data["name"])
        )
        db.commit()

        if cursor.rowcount == 0:
            print(f"DEBUG: 濾心 '{data['name']}' 未找到，無法更新。")
            return jsonify({"message": "濾心未找到"}), 404
        
        cursor.execute("SELECT name, last_replace, lifespan FROM filters WHERE name = ?", (data["name"],))
        updated_filter = cursor.fetchone()
        if updated_filter:
            print(f"DEBUG: 濾心 '{data['name']}' 更新成功。")
            return jsonify({"message": "更新成功", "updated": dict(updated_filter)})
        else:
            print("ERROR: 更新成功但無法重新查詢濾心資訊。")
            return jsonify({"message": "更新成功但無法重新查詢濾心資訊"}), 200
    except Exception as e:
        print(f"ERROR: 更新濾心失敗: {e}")
        return jsonify({"message": f"更新濾心失敗: {e}"}), 500

@app.route("/delete", methods=["POST", "OPTIONS"])
@cross_origin()
def delete_filter():
    if request.method == "OPTIONS":
        print("DEBUG: 收到 /delete OPTIONS 預檢請求。")
        return jsonify({"message": "OK"}), 200
        
    print("DEBUG: 收到 /delete POST 請求。")
    data = request.json
    if not data or "name" not in data:
        print("DEBUG: 刪除請求缺少 'name' 欄位。")
        return jsonify({"message": "請提供要刪除的濾心名稱 (name)"}), 400

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM filters WHERE name = ?", (data["name"],))
        db.commit()

        if cursor.rowcount == 0:
            print(f"DEBUG: 濾心 '{data['name']}' 未找到，無法刪除。")
            return jsonify({"message": f"濾心 '{data['name']}' 未找到"}), 404
        
        print(f"DEBUG: 濾心 '{data['name']}' 已刪除。")
        return jsonify({"message": f"濾心 '{data['name']}' 已刪除"}), 200
    except Exception as e:
        print(f"ERROR: 刪除濾心失敗: {e}")
        return jsonify({"message": f"刪除濾心失敗: {e}"}), 500

if __name__ == "__main__":
    # 如果是直接運行此腳本 (例如: python app.py)，app.run() 會提供自己的應用程式上下文
    # 因此這裡不需要額外的 init_db() 調用，因為上面已經在檔案頂層調用過了
    print("DEBUG: 正在直接運行 app.py 腳本。")
    app.run(debug=True)
