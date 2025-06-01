from flask import Flask, request, jsonify, g
from flask_cors import CORS, cross_origin
import json
import datetime
import os
import sqlite3
from flask import Flask, request, jsonify, g
from flask_cors import CORS, cross_origin
import json
import datetime
import os
import sqlite3
# 新增 JWT 相關導入
from flask_jwt_extended import create_access_token, jwt_required, JWTManager, get_jwt_identity

# --- 全局變數定義 ---
DATABASE = "/tmp/filters.db"
DEFAULT_FILTERS = [
    {"name": "UF-591", "last_replace": "2024-06-01", "lifespan": 90}, # 使用實際的型號名稱
    {"name": "UF-592", "last_replace": "2024-06-01", "lifespan": 180}
]
# --- 全局變數定義結束 ---

app = Flask(__name__)
CORS(app, supports_credentials=True)

# --- JWT 設定 ---
# 設定一個秘密金鑰，用於簽名 JWT
# 建議從環境變數中讀取，而不是硬編碼！
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "your-super-secret-jwt-key") # <-- 這裡非常重要！在 Render 設定環境變數！
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(days=7) # JWT 存活時間，例如 7 天
jwt = JWTManager(app)

# 用於簡單認證的預設使用者（未來可從資料庫讀取）
# 這裡只是範例，實際應用中不應該這樣硬編碼帳密！
USERS = {
    "admin": "hxcs04water" # 範例帳號密碼，請務必更換！
}

# --- 資料庫操作函式 ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
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

# --- 新增的認證路由 ---
@app.route("/login", methods=["POST"])
@cross_origin()
def login():
    # 下面這個 if 區塊通常在 @cross_origin() 存在時可以省略，
    # 但為了明確性，保留它也無妨。Flask-CORS 理論上會自動處理 OPTIONS 請求。
    if request.method == "OPTIONS":
        print("DEBUG: 收到 /login OPTIONS 預檢請求。")
        return jsonify({"message": "OK"}), 200 # 回應 200 OK
        
    username = request.json.get("username", None)
    password = request.json.get("password", None)

    # 這裡的帳號密碼驗證邏輯：
    # 確保是檢查 USERS 字典中是否存在該用戶名，並且密碼匹配。
    # 原始程式碼的 `username != USERS.get(username)` 這部分可能有點問題。
    # 更正後的判斷：
    if username not in USERS or USERS[username] != password:
        print(f"DEBUG: 無效登入嘗試 - 用戶: {username}")
        return jsonify({"message": "錯誤的使用者名稱或密碼"}), 401
    
    access_token = create_access_token(identity=username)
    print(f"DEBUG: 用戶 '{username}' 登入成功，發送 JWT。")
    return jsonify(access_token=access_token)

# --- 路由 (現在需要 JWT 保護) ---
@app.route("/")
# home 路由可以選擇是否需要認證，如果不需要，就不加 @jwt_required()
def home():
    # current_user = get_jwt_identity() # 如果 home 路由也想知道當前用戶
    return jsonify({"message": "Flask 服務運行中 🚀"})


@app.route("/filters", methods=["GET"])
@jwt_required() # <--- 加上這個裝飾器來保護路由
def get_filters():
    current_user = get_jwt_identity() # 可以獲取當前登入的使用者名稱
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
@jwt_required() # <--- 加上這個裝飾器來保護路由
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
@jwt_required() # <--- 加上這個裝飾器來保護路由
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
@cross_origin()
@jwt_required() # <--- 加上這個裝飾器來保護路由
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
# --- 全局變數定義 (非常重要：請確保它們在檔案頂層) ---
# DATABASE 變數定義在 app 物件建立之前，確保在導入時可見
DATABASE = "/tmp/filters.db" # 在 Render 上，/tmp/ 是唯一可寫且持久的目錄

# DEFAULT_FILTERS 變數定義在 app 物件建立之前，確保在導入時可見
DEFAULT_FILTERS = [
    {"name": "前置濾網", "last_replace": "2025-05-01", "lifespan": 60},
    {"name": "活性碳濾心", "last_replace": "2025-05-01", "lifespan": 90}
]
# --- 全局變數定義結束 ---

app = Flask(__name__)
CORS(app, supports_credentials=True)

# --- 資料庫操作函式 ---

# 獲取資料庫連接
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row # 讓查詢結果以字典形式返回
    return db

# 初始化資料庫：建立表格並插入預設資料 (如果資料庫為空)
def init_db():
    print("DEBUG: 嘗試初始化資料庫...")
    # 使用 app.app_context() 確保在執行資料庫操作時，Flask 應用程式上下文是激活的
    # 這是因為 get_db() 內部使用了 g 對象，它需要上下文
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        try:
            # 建立 'filters' 表格，如果它不存在的話
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

            # 檢查資料庫是否為空，如果為空則插入預設資料
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
            # 捕獲 SQLite 相關的錯誤
            print(f"ERROR: 初始化資料庫時發生 SQLite 錯誤: {e}")
            raise # 重新拋出錯誤，讓 Render 日誌顯示詳細追溯
        except Exception as e:
            # 捕獲任何其他未知錯誤
            print(f"CRITICAL ERROR: 初始化資料庫時發生未知錯誤: {e}")
            raise # 重新拋出錯誤

# 在每次請求結束後關閉資料庫連接
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
        print("DEBUG: 資料庫連接已關閉。")

# --- 路由 ---

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
        filters = [dict(row) for row in cursor.fetchall()] # 將 SQLite Row 物件轉換為字典
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
        return jsonify({"message": "濾心已成功新增", "filter": {"name": data["name"], "last_replace": data["last_replace"], "lifespan": lifespan_int}}), 201 # 使用 201 Created
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
@cross_origin() # 確保 CORS 預檢請求被正確處理
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
    # 這個區塊僅用於本地開發環境直接運行 app.py 時
    # 在 Render 上，我們將通過 init_db_script.py 來處理初始化
    print("DEBUG: 正在直接運行 app.py 腳本 (本地開發模式)。")
    with app.app_context(): # 確保在本地運行時也有應用程式上下文
        try:
            init_db()
            print("DEBUG: 本地開發模式下資料庫初始化完成。")
        except Exception as e:
            print(f"CRITICAL ERROR: 本地開發模式下資料庫初始化失敗: {e}")
    app.run(debug=True) # debug=True 僅用於開發，生產環境請設定為 False
