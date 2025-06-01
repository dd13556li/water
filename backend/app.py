from flask import Flask, request, jsonify, g # 導入 g 用於應用程式上下文
from flask_cors import CORS, cross_origin
import json
import datetime
import os
import sqlite3 # 導入 sqlite3 模組

app = Flask(__name__)
CORS(app, supports_credentials=True)

# 為了持久性儲存，現在使用 SQLite 資料庫檔案
DATABASE = "/tmp/filters.db" # 將資料庫檔案放在 /tmp/ 以符合 Render 環境

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
        db.row_factory = sqlite3.Row # 讓查詢結果以字典形式返回，方便操作
    return db

# 初始化資料庫
def init_db():
    print("DEBUG: 嘗試初始化資料庫。") # 添加日誌
    with app.app_context(): # 確保在應用程式上下文中執行
        db = get_db()
        cursor = db.cursor()
        try:
            # 檢查表格是否存在，如果不存在則建立
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS filters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    last_replace TEXT NOT NULL,
                    lifespan INTEGER NOT NULL
                )
            ''')
            db.commit()
            print("DEBUG: 資料表 'filters' 檢查/建立成功。") # 添加日誌

            # 如果資料庫是空的，則插入預設資料
            cursor.execute("SELECT COUNT(*) FROM filters")
            if cursor.fetchone()[0] == 0:
                print("DEBUG: 資料庫為空，開始插入預設濾心資料。") # 添加日誌
                for f in DEFAULT_FILTERS:
                    cursor.execute(
                        "INSERT INTO filters (name, last_replace, lifespan) VALUES (?, ?, ?)",
                        (f["name"], f["last_replace"], f["lifespan"])
                    )
                db.commit()
                print("DEBUG: 資料庫已初始化並載入預設濾心資料。")
            else:
                print("DEBUG: 資料庫已存在，無需初始化預設資料。")
        except sqlite3.Error as e:
            print(f"ERROR: 初始化資料庫時發生 SQLite 錯誤: {e}") # 添加日誌
            raise # 重新拋出，讓 Render 日誌能看到完整錯誤
        except Exception as e:
            print(f"CRITICAL ERROR: 初始化資料庫時發生未知錯誤: {e}") # 添加日誌
            raise

# 關閉資料庫連接
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
        print("DEBUG: 資料庫連接已關閉。") # 添加日誌

# --- 路由 ---

@app.route("/")
def home():
    return jsonify({"message": "Flask 服務運行中 🚀"})

@app.route("/filters", methods=["GET"])
def get_filters():
    print("DEBUG: 收到 /filters 請求。") # 添加日誌
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT name, last_replace, lifespan FROM filters")
        filters = [dict(row) for row in cursor.fetchall()] # 將 SQLite Row 物件轉換為字典
        print(f"DEBUG: 成功獲取 {len(filters)} 筆濾心資料。") # 添加日誌
        return jsonify(filters)
    except Exception as e:
        print(f"ERROR: 在 get_filters 中發生錯誤: {e}") # 添加日誌
        return jsonify({"message": f"伺服器錯誤: {e}"}), 500

@app.route("/add", methods=["POST"])
def add_filter():
    print("DEBUG: 收到 /add 請求。") # 添加日誌
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
        # 檢查是否已存在相同的 name
        cursor.execute("SELECT COUNT(*) FROM filters WHERE name = ?", (data["name"],))
        if cursor.fetchone()[0] > 0:
            print(f"DEBUG: 濾心名稱 '{data['name']}' 已存在。")
            return jsonify({"message": f"濾心名稱 '{data['name']}' 已存在"}), 409 # 409 Conflict

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
    print("DEBUG: 收到 /update 請求。") # 添加日誌
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
        
        # 重新查詢更新後的資料以返回
        cursor.execute("SELECT name, last_replace, lifespan FROM filters WHERE name = ?", (data["name"],))
        updated_filter = cursor.fetchone()
        if updated_filter:
            print(f"DEBUG: 濾心 '{data['name']}' 更新成功。")
            return jsonify({"message": "更新成功", "updated": dict(updated_filter)})
        else:
            print("ERROR: 更新成功但無法重新查詢濾心資訊。")
            return jsonify({"message": "更新成功但無法重新查詢濾心資訊"}), 200 # 理論上不應該發生
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
    # 在應用程式啟動時，初始化資料庫
    # 這是確保 'filters' 表格被建立的關鍵一步
    try:
        init_db() 
        print("DEBUG: 應用程式啟動前資料庫初始化完成。")
    except Exception as e:
        print(f"CRITICAL ERROR: 應用程式啟動時資料庫初始化失敗: {e}")
        # 如果這裡失敗，應用程式可能無法正常運行，可以選擇退出
        # import sys
        # sys.exit(1)
    
    app.run(debug=True) # debug=True 在開發環境使用，生產環境請關閉
