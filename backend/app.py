import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime

app = Flask(__name__)
CORS(app)

# 🔹 使用 Render 可持久存儲的檔案路徑，而不是 `/tmp/`
DB_FILE = "filters.db"

# 🔹 建立資料表（只執行一次）
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS filters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            last_replace TEXT NOT NULL,
            lifespan INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()

# ✅ 讀取濾心資料
def load_filters():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT name, last_replace, lifespan FROM filters")
    filters = [{"name": row[0], "last_replace": row[1], "lifespan": row[2]} for row in cursor.fetchall()]
    conn.close()
    return filters

# ✅ API: 取得濾心資料
@app.route("/filters", methods=["GET"])
def get_filters():
    return jsonify(load_filters())

# ✅ API: 新增濾心
@app.route("/add", methods=["POST"])
def add_filter():
    data = request.json
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO filters (name, last_replace, lifespan) VALUES (?, ?, ?)",
                   (data["name"], data["last_replace"], int(data["lifespan"])))
    conn.commit()
    conn.close()
    return jsonify({"message": "濾心已成功新增"})

# ✅ API: 更新濾心
@app.route("/update", methods=["POST"])
def update_filter():
    data = request.json
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE filters SET last_replace = ? WHERE name = ?",
                   (datetime.datetime.now().strftime("%Y-%m-%d"), data["name"]))
    conn.commit()
    conn.close()
    return jsonify({"message": "更新成功"})

# ✅ API: 刪除濾心
@app.route("/delete", methods=["POST"])
def delete_filter():
    data = request.json
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM filters WHERE name = ?", (data["name"],))
    conn.commit()
    conn.close()
    return jsonify({"message": f"濾心 {data['name']} 已刪除"})

if __name__ == "__main__":
    init_db()  # ✅ 應用啟動時執行一次，確保資料庫表格存在
    app.run(debug=True)
