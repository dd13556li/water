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
    with app.app_context(): # 確保在應用程式上下文中執行
        db = get_db()
        cursor = db.cursor()
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

        # 如果資料庫是空的，則插入預設資料
        cursor.execute("SELECT COUNT(*) FROM filters")
        if cursor.fetchone()[0] == 0:
            for f in DEFAULT_FILTERS:
                cursor.execute(
                    "INSERT INTO filters (name, last_replace, lifespan) VALUES (?, ?, ?)",
                    (f["name"], f["last_replace"], f["lifespan"])
                )
            db.commit()
            print("資料庫已初始化並載入預設濾心資料。")
        else:
            print("資料庫已存在，無需初始化預設資料。")


# 關閉資料庫連接
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# --- 路由 ---

@app.route("/")
def home():
    return jsonify({"message": "Flask 服務運行中，使用 SQLite 資料庫 🚀"})

@app.route("/filters", methods=["GET"])
def get_filters():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT name, last_replace, lifespan FROM filters")
    filters = [dict(row) for row in cursor.fetchall()] # 將 SQLite Row 物件轉換為字典
    return jsonify(filters)

@app.route("/add", methods=["POST"])
def add_filter():
    data = request.json
    name = data.get("name")
    last_replace = data.get("last_replace")
    lifespan = data.get("lifespan")

    if not all([name, last_replace, lifespan]):
        return jsonify({"message": "請提供完整的濾心資訊 (name, last_replace, lifespan)"}), 400

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "INSERT INTO filters (name, last_replace, lifespan) VALUES (?, ?, ?)",
            (name, last_replace, int(lifespan))
        )
        db.commit()
        return jsonify({"message": "濾心已成功新增", "filter": {"name": name, "last_replace": last_replace, "lifespan": int(lifespan)}}), 201
    except sqlite3.IntegrityError:
        return jsonify({"message": f"濾心名稱 '{name}' 已存在"}), 409 # 409 Conflict
    except Exception as e:
        return jsonify({"message": f"新增濾心時發生錯誤: {str(e)}"}), 500


@app.route("/update", methods=["POST"])
def update_filter():
    data = request.json
    name = data.get("name")
    
    if not name:
        return jsonify({"message": "請提供濾心名稱 (name) 以進行更新"}), 400

    db = get_db()
    cursor = db.cursor()
    
    # 這裡只更新 last_replace 為當前日期，如果需要更新其他欄位，請修改 SQL
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    
    cursor.execute(
        "UPDATE filters SET last_replace = ? WHERE name = ?",
        (current_date, name)
    )
    db.commit()

    if cursor.rowcount == 0:
        return jsonify({"message": "濾心未找到"}), 404
    
    # 重新查詢更新後的資料以返回
    cursor.execute("SELECT name, last_replace, lifespan FROM filters WHERE name = ?", (name,))
    updated_filter = cursor.fetchone()
    if updated_filter:
        return jsonify({"message": "更新成功", "updated": dict(updated_filter)})
    else:
        return jsonify({"message": "更新成功但無法重新查詢濾心資訊"}), 200 # 理論上不應該發生

@app.route("/delete", methods=["POST", "OPTIONS"])
@cross_origin()
def delete_filter():
    if request.method == "OPTIONS":
        return jsonify({"message": "OK"}), 200
        
    data = request.json
    name = data.get("name")

    if not name:
        return jsonify({"message": "請提供要刪除的濾心名稱 (name)"}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM filters WHERE name = ?", (name,))
    db.commit()

    if cursor.rowcount == 0:
        return jsonify({"message": f"濾心 '{name}' 未找到"}), 404
    
    return jsonify({"message": f"濾心 '{name}' 已刪除"}), 200

if __name__ == "__main__":
    init_db() # 在應用程式啟動時初始化資料庫
    app.run(debug=True)
