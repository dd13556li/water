from flask import Flask, request, jsonify, g
from flask_cors import CORS, cross_origin
import json
import datetime
import os
from flask_jwt_extended import create_access_token, jwt_required, JWTManager, get_jwt_identity
import pytz # <-- 新增導入 pytz

# --- 全局變數定義 ---
# 注意：預設濾心日期也建議改為 UTC，但為簡化，這裡暫時保留 YYYY-MM-DD 格式
DEFAULT_FILTERS = [
    {"name": "UF-591", "last_replace": "2024-06-01", "lifespan": 90},
    {"name": "UF-592", "last_replace": "2024-06-01", "lifespan": 180}
]

# JSON 檔案路徑
FILTERS_FILE = "filters.json" 

app = Flask(__name__)
CORS(app, supports_credentials=True)

# --- JWT 設定 ---
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "your-super-secret-jwt-key-PLEASE-CHANGE-ME-IN-RENDER")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(days=7)
jwt = JWTManager(app)

# 用於簡單認證的預設使用者
USERS = {
    "admin": "hxcs04water"
}

# --- JSON 檔案操作函式 (保持不變) ---
# ... (load_filters 和 save_filters 保持不變) ...

def load_filters():
    """從 JSON 檔案載入濾心資料"""
    if not os.path.exists(FILTERS_FILE) or os.stat(FILTERS_FILE).st_size == 0:
        print(f"DEBUG: {FILTERS_FILE} 不存在或為空，將載入預設濾心。")
        return DEFAULT_FILTERS[:] # 返回副本以避免修改預設列表
    try:
        with open(FILTERS_FILE, 'r', encoding='utf-8') as f:
            filters = json.load(f)
            # 確保載入的 filters 是一個列表，以防檔案被損壞
            if not isinstance(filters, list):
                print(f"ERROR: {FILTERS_FILE} 內容無效，將使用預設濾心。")
                return DEFAULT_FILTERS[:]
            return filters
    except json.JSONDecodeError as e:
        print(f"ERROR: 解碼 {FILTERS_FILE} 失敗: {e}。將使用預設濾心。")
        return DEFAULT_FILTERS[:]
    except Exception as e:
        print(f"ERROR: 讀取 {FILTERS_FILE} 時發生錯誤: {e}。將使用預設濾心。")
        return DEFAULT_FILTERS[:]

def save_filters(filters):
    """將濾心資料儲存到 JSON 檔案"""
    try:
        with open(FILTERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(filters, f, indent=4, ensure_ascii=False)
        print(f"DEBUG: 濾心資料已成功寫入到 {FILTERS_FILE}。")
    except Exception as e:
        print(f"ERROR: 寫入 {FILTERS_FILE} 失敗: {e}")

def init_data_file():
    """在應用程式啟動時初始化資料檔案 (如果不存在或為空)"""
    print(f"DEBUG: 檢查並初始化 {FILTERS_FILE}...")
    if not os.path.exists(FILTERS_FILE) or os.stat(FILTERS_FILE).st_size == 0:
        print(f"DEBUG: {FILTERS_FILE} 不存在或為空，創建並寫入預設濾心。")
        save_filters(DEFAULT_FILTERS)
    else:
        # 嘗試載入並驗證檔案內容
        try:
            with open(FILTERS_FILE, 'r', encoding='utf-8') as f:
                filters = json.load(f)
                if not isinstance(filters, list):
                    print(f"WARNING: {FILTERS_FILE} 內容無效，將用預設濾心覆蓋。")
                    save_filters(DEFAULT_FILTERS)
                else:
                    print(f"DEBUG: {FILTERS_FILE} 存在且有效。")
        except json.JSONDecodeError:
            print(f"WARNING: {FILTERS_FILE} 格式錯誤，將用預設濾心覆蓋。")
            save_filters(DEFAULT_FILTERS)
        except Exception as e:
            print(f"WARNING: 讀取 {FILTERS_FILE} 時發生錯誤 {e}，將用預設濾心覆蓋。")
            save_filters(DEFAULT_FILTERS)

# 確保資料檔案在應用程式啟動時被初始化
with app.app_context():
    init_data_file()

# --- 認證路由 (保持不變) ---
# ... (login 函數保持不變) ...

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
    # 診斷用代碼，可以保留或刪除
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    try:
        # 台灣時區
        taipei_tz = pytz.timezone('Asia/Taipei')
        now_taipei = now_utc.astimezone(taipei_tz)
        taipei_time_str = now_taipei.strftime("%Y-%m-%d %H:%M:%S %Z%z")
    except Exception as e:
        taipei_time_str = f"轉換台灣時間失敗: {e}"

    server_local_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return jsonify({
        "message": "Flask 服務運行中 🚀",
        "server_local_time": server_local_time_str, # 服務器在運行時的本地時間
        "server_utc_time": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "server_taipei_time": taipei_time_str # 轉換到台灣時間
    })

@app.route("/filters", methods=["GET"])
@jwt_required()
def get_filters():
    current_user = get_jwt_identity()
    print(f"DEBUG: 用戶 '{current_user}' 收到 /filters 請求。")
    try:
        filters = load_filters()
        print(f"DEBUG: 成功獲取 {len(filters)} 筆濾心資料。")
        return jsonify(filters)
    except Exception as e:
        print(f"ERROR: 在 get_filters 中發生錯誤: {e}")
        return jsonify({"message": f"伺服器錯誤: {e}"}), 500

@app.route("/add", methods=["POST"])
@jwt_required()
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

    filters = load_filters()
    # 檢查濾心名稱是否已存在
    if any(f['name'] == data['name'] for f in filters):
        print(f"DEBUG: 濾心名稱 '{data['name']}' 已存在。")
        return jsonify({"message": f"濾心名稱 '{data['name']}' 已存在"}), 409
    
    new_filter = {
        "name": data["name"],
        "last_replace": data["last_replace"], # 前端傳過來的日期字符串 (應該是 YYYY-MM-DD 格式)
        "lifespan": lifespan_int
    }
    filters.append(new_filter)
    save_filters(filters)
    
    print(f"DEBUG: 濾心 '{data['name']}' 已成功新增。")
    return jsonify({"message": "濾心已成功新增", "filter": new_filter}), 201
    

@app.route("/update", methods=["POST"])
@jwt_required()
def update_filter():
    current_user = get_jwt_identity()
    print(f"DEBUG: 用戶 '{current_user}' 收到 /update 請求。")
    data = request.json
    
    if not data or "name" not in data:
        print("DEBUG: 更新請求缺少 'name' 欄位。")
        return jsonify({"message": "請提供濾心名稱 (name) 以進行更新"}), 400

    filters = load_filters()
    filter_name_to_update = data["name"]
    found = False
    updated_filter = None
    
    # 獲取當前 UTC 日期作為更新日期
    current_date_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d") 
    print(f"DEBUG: 伺服器更新日期 (UTC) 為: {current_date_utc}")

    for i, f in enumerate(filters):
        if f['name'] == filter_name_to_update:
            filters[i]['last_replace'] = current_date_utc # 更新為 UTC 日期字串
            updated_filter = filters[i]
            found = True
            break
    
    if found:
        save_filters(filters)
        print(f"DEBUG: 濾心 '{filter_name_to_update}' 更新成功。")
        return jsonify({"message": "更新成功", "updated": updated_filter})
    else:
        print(f"DEBUG: 濾心 '{filter_name_to_update}' 未找到，無法更新。")
        return jsonify({"message": "濾心未找到"}), 404

@app.route("/delete", methods=["POST", "OPTIONS"])
@cross_origin()
@jwt_required()
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

    filters = load_filters()
    filter_name_to_delete = data["name"]
    original_count = len(filters)
    
    filters = [f for f in filters if f['name'] != filter_name_to_delete]

    if len(filters) < original_count:
        save_filters(filters)
        print(f"DEBUG: 濾心 '{filter_name_to_delete}' 已刪除。")
        return jsonify({"message": f"濾心 '{filter_name_to_delete}' 已刪除"}), 200
    else:
        print(f"DEBUG: 濾心 '{filter_name_to_delete}' 未找到，無法刪除。")
        return jsonify({"message": f"濾心 '{filter_name_to_delete}' 未找到"}), 404

if __name__ == "__main__":
    print("DEBUG: 正在直接運行 app.py 腳本 (本地開發模式)。")
    init_data_file() 
    app.run(debug=True, port=5000)
