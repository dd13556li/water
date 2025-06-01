from flask import Flask, request, jsonify, g
from flask_cors import CORS, cross_origin # 確保 cross_origin 已導入
import json
import datetime
import os
import sqlite3
from flask_jwt_extended import create_access_token, jwt_required, JWTManager, get_jwt_identity

# --- 全局變數定義 ---
# 確保這些變數在檔案頂層且只定義一次
DATABASE = "/tmp/filters.db" # 在 Render 上，/tmp/ 是唯一可寫且持久的目錄
DEFAULT_FILTERS = [
    {"name": "UF-591", "last_replace": "2024-06-01", "lifespan": 90},
    {"name": "UF-592", "last_replace": "2024-06-01", "lifespan": 180}
    # 這裡的預設濾心名稱，如果您有實際使用的名稱，請在這裡更新，
    # 例如："UF-591 - 5微米PP濾芯", "UF-592 - 塊狀活性碳濾芯"
]
# --- 全局變數定義結束 ---

app = Flask(__name__)
# 確保 CORS 設定只出現一次，並且 supports_credentials=True
CORS(app, supports_credentials=True)

# --- JWT 設定 ---
# 確保 JWT 設定只出現一次
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "your-super-secret-jwt-key-PLEASE-CHANGE-ME-IN-RENDER") # <-- **非常重要**：請在 Render 環境變數中設定
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(days=7) # JWT 存活時間，例如 7 天
jwt = JWTManager(app)

# 用於簡單認證的預設使用者
# **注意**：這只是一個範例！在實際應用中，帳號密碼不應硬編碼！
# 如果您已在 Render 環境變數中設定了 JWT_SECRET_KEY，請確保這裡的密碼是您要使用的。
USERS = {
    "admin": "hxcs04water" # **請務必使用更複雜且只有您知道的密碼**
}

# --- 資料庫操作函式 ---
# 確保這些函式只定義一次

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row # 讓查詢結果以字典形式返回
    return db

def init_db():
    print("DEBUG: 嘗試初始化資料庫...")
    with app.app_context():
        db = get_db()
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

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
        print("DEBUG: 資料庫連接已關閉。")

# --- 認證路由 ---
# 確保 /login 路由只定義一次，並正確設定 methods 和 @cross_origin()
@app.route("/login", methods=["POST", "OPTIONS"]) # <--- **這裡必須同時有 POST 和 OPTIONS**
@cross_origin() # <--- **這裡必須要有 @cross_origin()**
def login():
    if request.method == "OPTIONS":
        # 如果是 OPTIONS 預檢請求，直接返回 200 OK
        print("DEBUG: 收到 /login OPTIONS 預檢請求。")
        return jsonify({"message": "CORS preflight successful"}), 200

    username = request.json.get("username", None)
    password = request.json.get("password", None)

    # 驗證使用者名稱和密碼
    if username not in USERS or USERS[username] != password:
        print(f"DEBUG: 無效登入嘗試 - 用戶: {username}")
        return jsonify({"message": "錯誤的使用者名稱或密碼"}), 401
    
    # 登入成功，建立 JWT
    access_token = create_access_token(identity=username)
    print(f"DEBUG: 用戶 '{username}' 登入成功，發送 JWT。")
    return jsonify(access_token=access_token)

# --- 其他應用程式路由 ---
# 確保這些路由也只定義一次，並在需要保護的路由上加上 @jwt_required()

@app.route("/")
def home():
    return jsonify({"message": "Flask 服務運行中 🚀"})

@app.route("/filters", methods=["GET"])
@jwt_required() # <--- 保護這個路由
def get_filters():
    current_user = get_jwt_identity()
    print(f"DEBUG: 用戶 '{current_user}' 收到 /filters 請求。")
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
@jwt_required() # <--- 保護這個路由
def add_filter():
    current_user = get_jwt_identity()
    print(f"DEBUG: 用戶 '{current_user}' 收到 /add 請求。")
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
@jwt_required() # <--- 保護這個路由
def update_filter():
    current_user = get_jwt_identity()
    print(f"DEBUG: 用戶 '{current_user}' 收到 /update 請求。")
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
@cross_origin() # <--- 確保這裡也有 @cross_origin()
@jwt_required() # <--- 保護這個路由
def delete_filter():
    if request.method == "OPTIONS":
        print("DEBUG: 收到 /delete OPTIONS 預檢請求。")
        return jsonify({"message": "OK"}), 200
        
    current_user = get_jwt_identity()
    print(f"DEBUG: 用戶 '{current_user}' 收到 /delete POST 請求。")
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
    print("DEBUG: 正在直接運行 app.py 腳本 (本地開發模式)。")
    with app.app_context():
        try:
            init_db()
            print("DEBUG: 本地開發模式下資料庫初始化完成。")
        except Exception as e:
            print(f"CRITICAL ERROR: 本地開發模式下資料庫初始化失敗: {e}")
    app.run(debug=True)
