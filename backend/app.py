from flask import Flask, request, jsonify, g
from flask_cors import CORS, cross_origin
import json
import datetime
import os
import psycopg2 # 導入 psycopg2
from flask_jwt_extended import create_access_token, jwt_required, JWTManager, get_jwt_identity

# --- 全局變數定義 ---
DEFAULT_FILTERS = [
    {"name": "UF-591", "last_replace": "2024-06-01", "lifespan": 90},
    {"name": "UF-592", "last_replace": "2024-06-01", "lifespan": 180}
]
# --- 全局變數定義結束 ---

app = Flask(__name__)
CORS(app, supports_credentials=True)

# --- JWT 設定 ---
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "your-super-secret-jwt-key-PLEASE-CHANGE-ME-IN-RENDER") # <-- **非常重要**：請在 Render 環境變數中設定
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(days=7) # JWT 存活時間，例如 7 天
jwt = JWTManager(app)

# 用於簡單認證的預設使用者 (僅供演示，實際應用不應硬編碼)
USERS = {
    "admin": "hxcs04water" # **請務必使用更複雜且只有您知道的密碼**
}

# --- 資料庫操作函式 ---
# 從環境變數獲取資料庫 URL (Render 為連結的資料庫提供此變數)
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("CRITICAL ERROR: DATABASE_URL 環境變數未設定！如果是在本地運行，請確保已設置環境變數或在代碼中提供本地DB連接字串。")
    # 如果您需要在本地測試，可以在這裡設定一個本地 PostgreSQL URL
    # DATABASE_URL = "postgresql://user:password@localhost:5432/your_db_name"


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        if not DATABASE_URL:
            raise Exception("DATABASE_URL 未設定！無法連接到資料庫。")
        db = g._database = psycopg2.connect(DATABASE_URL)
    return db

def init_db():
    print("DEBUG: 嘗試初始化資料庫 (PostgreSQL)...")
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        try:
            # 建立資料表時，移除 display_order 欄位
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS filters (
                    id SERIAL PRIMARY KEY,
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
                        "INSERT INTO filters (name, last_replace, lifespan) VALUES (%s, %s, %s)",
                        (f["name"], f["last_replace"], f["lifespan"])
                    )
                db.commit()
                print("DEBUG: 資料庫已初始化並載入預設濾心資料。")
            else:
                print("DEBUG: 資料庫已存在資料，跳過預設資料插入。")
        except psycopg2.Error as e: 
            print(f"ERROR: 初始化資料庫時發生 PostgreSQL 錯誤: {e}")
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

# 確保 init_db 在應用程式啟動時被呼叫
with app.app_context():
    init_db()

# --- 認證路由 ---
@app.route("/login", methods=["POST", "OPTIONS"])
@cross_origin()
def login():
    if request.method == "OPTIONS":
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

@app.route("/")
def home():
    return jsonify({"message": "Flask 服務運行中 🚀"})

@app.route("/filters", methods=["GET"])
@jwt_required() # 保護這個路由
def get_filters():
    current_user = get_jwt_identity()
    print(f"DEBUG: 用戶 '{current_user}' 收到 /filters 請求。")
    try:
        db = get_db()
        cursor = db.cursor()
        # 這裡不再按 display_order 排序，預設按 id 排序
        cursor.execute("SELECT name, last_replace, lifespan FROM filters") 
        filters = []
        for row in cursor.fetchall():
            filters.append({
                "name": row[0],
                "last_replace": row[1],
                "lifespan": row[2]
            })
        print(f"DEBUG: 成功獲取 {len(filters)} 筆濾心資料。")
        return jsonify(filters)
    except Exception as e:
        print(f"ERROR: 在 get_filters 中發生錯誤: {e}")
        return jsonify({"message": f"伺服器錯誤: {e}"}), 500

@app.route("/add", methods=["POST"])
@jwt_required() # 保護這個路由
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
        cursor.execute("SELECT COUNT(*) FROM filters WHERE name = %s", (data["name"],))
        if cursor.fetchone()[0] > 0:
            print(f"DEBUG: 濾心名稱 '{data['name']}' 已存在。")
            return jsonify({"message": f"濾心名稱 '{data['name']}' 已存在"}), 409
        
        # 不再設定 display_order
        cursor.execute(
            "INSERT INTO filters (name, last_replace, lifespan) VALUES (%s, %s, %s)",
            (data["name"], data["last_replace"], lifespan_int)
        )
        db.commit()
        print(f"DEBUG: 濾心 '{data['name']}' 已成功新增。")
        return jsonify({"message": "濾心已成功新增", "filter": {"name": data["name"], "last_replace": data["last_replace"], "lifespan": lifespan_int}}), 201
    except psycopg2.Error as e: 
        print(f"ERROR: 新增濾心時發生 PostgreSQL 錯誤: {e}")
        return jsonify({"message": f"新增濾心時發生錯誤: {e}"}), 500
    except Exception as e:
        print(f"ERROR: 新增濾心時發生未知錯誤: {e}")
        return jsonify({"message": f"新增濾心時發生錯誤: {e}"}), 500


@app.route("/update", methods=["POST"])
@jwt_required() # 保護這個路由
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
            "UPDATE filters SET last_replace = %s WHERE name = %s",
            (current_date, data["name"])
        )
        db.commit()

        if cursor.rowcount == 0:
            print(f"DEBUG: 濾心 '{data['name']}' 未找到，無法更新。")
            return jsonify({"message": "濾心未找到"}), 404
        
        cursor.execute("SELECT name, last_replace, lifespan FROM filters WHERE name = %s", (data["name"],))
        updated_filter_row = cursor.fetchone() 
        if updated_filter_row:
            updated_filter = {
                "name": updated_filter_row[0],
                "last_replace": updated_filter_row[1],
                "lifespan": updated_filter_row[2]
            }
            print(f"DEBUG: 濾心 '{data['name']}' 更新成功。")
            return jsonify({"message": "更新成功", "updated": updated_filter})
        else:
            print("ERROR: 更新成功但無法重新查詢濾心資訊。")
            return jsonify({"message": "更新成功但無法重新查詢濾心資訊"}), 200
    except psycopg2.Error as e: 
        print(f"ERROR: 更新濾心失敗: {e}")
        return jsonify({"message": f"更新濾心失敗: {e}"}), 500
    except Exception as e:
        print(f"ERROR: 更新濾心失敗: {e}")
        return jsonify({"message": f"更新濾心失敗: {e}"}), 500

@app.route("/delete", methods=["POST", "OPTIONS"])
@cross_origin()
@jwt_required() # 保護這個路由
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
        cursor.execute("DELETE FROM filters WHERE name = %s", (data["name"],))
        db.commit()

        if cursor.rowcount == 0:
            print(f"DEBUG: 濾心 '{data['name']}' 未找到，無法刪除。")
            return jsonify({"message": f"濾心 '{data['name']}' 未找到"}), 404
        
        print(f"DEBUG: 濾心 '{data['name']}' 已刪除。")
        return jsonify({"message": f"濾心 '{data['name']}' 已刪除"}), 200
    except psycopg2.Error as e: 
        print(f"ERROR: 刪除濾心失敗: {e}")
        return jsonify({"message": f"刪除濾心失敗: {e}"}), 500
    except Exception as e:
        print(f"ERROR: 刪除濾心失敗: {e}")
        return jsonify({"message": f"刪除濾心失敗: {e}"}), 500

# 移除 /reorder-filters 端點

if __name__ == "__main__":
    print("DEBUG: 正在直接運行 app.py 腳本 (本地開發模式)。")
    with app.app_context():
        try:
            init_db()
            print("DEBUG: 本地開發模式下資料庫初始化完成。")
        except Exception as e:
            print(f"CRITICAL ERROR: 本地開發模式下資料庫初始化失敗: {e}")
    app.run(debug=True, port=5000)
