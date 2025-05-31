from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin # 確保 cross_origin 已導入
import json
import datetime
import os

app = Flask(__name__)
CORS(app, supports_credentials=True)

# 儲存濾心資料的檔案位置（Render 通常允許 `/tmp/` 目錄）
DATA_FILE = "/tmp/filters.json"

DEFAULT_FILTERS = [
    {"name": "前置濾網", "last_replace": "2025-05-01", "lifespan": 60},
    {"name": "活性碳濾心", "last_replace": "2025-05-01", "lifespan": 90}
]

# 讀取濾心資料 - 增加錯誤處理
def load_filters():
    print(f"DEBUG: 嘗試載入濾心資料從 {DATA_FILE}")
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                filters = json.load(f)
                print(f"DEBUG: 成功載入 {len(filters)} 筆濾心資料。")
                return filters
        else:
            print(f"DEBUG: {DATA_FILE} 不存在，將使用預設濾心資料。")
            # 檔案不存在時，保存預設值以確保檔案被建立
            save_filters(DEFAULT_FILTERS)
            return DEFAULT_FILTERS
    except (FileNotFoundError, json.JSONDecodeError) as e:
        # 處理檔案不存在（如果 os.path.exists 判斷失誤）或 JSON 解析錯誤
        print(f"ERROR: 載入濾心資料時發生錯誤 ({type(e).__name__}): {e}")
        print("ERROR: 將使用預設濾心資料並嘗試寫入以修復。")
        # 嘗試用預設值覆蓋或建立檔案，避免後續崩潰
        save_filters(DEFAULT_FILTERS)
        return DEFAULT_FILTERS
    except Exception as e:
        print(f"CRITICAL ERROR: 載入濾心資料時發生未知錯誤: {e}")
        raise # 重新拋出例外，以便在 Render 日誌中看到完整的追溯

# 儲存濾心資料 - 增加錯誤處理
def save_filters(filters):
    print(f"DEBUG: 嘗試儲存濾心資料到 {DATA_FILE}")
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(filters, f, ensure_ascii=False, indent=4)
        print("DEBUG: 濾心資料成功儲存。")
    except Exception as e:
        print(f"ERROR: 儲存濾心資料時發生錯誤: {e}")
        raise # 重新拋出例外，以便在 Render 日誌中看到完整的追溯

# 新增首頁路由以避免 404 錯誤
@app.route("/")
def home():
    return jsonify({"message": "Flask 服務運行中 🚀"})

@app.route("/filters", methods=["GET"])
def get_filters():
    try:
        filters = load_filters()
        return jsonify(filters)
    except Exception as e:
        print(f"ERROR: 獲取濾心資料失敗: {e}")
        return jsonify({"message": f"獲取濾心資料失敗: {e}"}), 500

@app.route("/add", methods=["POST"])
def add_filter():
    print("DEBUG: 收到 /add 請求。")
    data = request.json
    if not data:
        print("DEBUG: 請求 JSON 數據為空。")
        return jsonify({"message": "請求必須包含 JSON 數據"}), 400

    # 增加輸入驗證
    required_fields = ["name", "last_replace", "lifespan"]
    for field in required_fields:
        if field not in data:
            print(f"DEBUG: 缺少必填欄位: {field}")
            return jsonify({"message": f"缺少必填欄位: {field}"}), 400
    
    try:
        # 嘗試轉換 lifespan 為整數，並處理錯誤
        lifespan_int = int(data["lifespan"])
    except ValueError:
        print(f"DEBUG: lifespan 無法轉換為數字: {data['lifespan']}")
        return jsonify({"message": "lifespan 必須是有效的數字"}), 400

    try:
        filters = load_filters()
        
        # 檢查濾心名稱是否已存在，避免重複新增
        if any(f.get("name") == data["name"] for f in filters): # 使用 .get() 避免如果字典中沒有 'name' 鍵時報錯
            print(f"DEBUG: 濾心名稱 '{data['name']}' 已存在。")
            return jsonify({"message": f"濾心名稱 '{data['name']}' 已存在"}), 409 # 409 Conflict

        new_filter = {
            "name": data["name"],
            "last_replace": data["last_replace"],
            "lifespan": lifespan_int
        }
        filters.append(new_filter)
        save_filters(filters)
        print(f"DEBUG: 濾心 '{data['name']}' 已成功新增。")
        return jsonify({"message": "濾心已成功新增", "added": new_filter}), 201 # 使用 201 Created

    except Exception as e:
        print(f"ERROR: 新增濾心失敗: {e}")
        return jsonify({"message": f"新增濾心失敗: {e}"}), 500

@app.route("/update", methods=["POST"])
def update_filter():
    print("DEBUG: 收到 /update 請求。")
    data = request.json
    if not data or "name" not in data:
        print("DEBUG: 更新請求缺少 'name' 欄位。")
        return jsonify({"message": "請提供要更新的濾心名稱"}), 400

    try:
        filters = load_filters()
        found = False
        for f in filters:
            if f.get("name") == data["name"]:
                f["last_replace"] = datetime.datetime.now().strftime("%Y-%m-%d")
                save_filters(filters)
                print(f"DEBUG: 濾心 '{data['name']}' 更新成功。")
                return jsonify({"message": "更新成功", "updated": f})
        
        if not found:
            print(f"DEBUG: 濾心 '{data['name']}' 未找到。")
            return jsonify({"message": "濾心未找到"}), 404

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
        return jsonify({"message": "請提供要刪除的濾心名稱"}), 400

    try:
        filters = load_filters()
        initial_len = len(filters)
        filters = [f for f in filters if f.get("name") != data["name"]]
        
        if len(filters) == initial_len:
            print(f"DEBUG: 濾心 '{data['name']}' 未找到，無法刪除。")
            return jsonify({"message": f"濾心 '{data['name']}' 未找到"}), 404
        
        save_filters(filters)
        print(f"DEBUG: 濾心 '{data['name']}' 已刪除。")
        return jsonify({"message": f"濾心 {data['name']} 已刪除"}), 200

    except Exception as e:
        print(f"ERROR: 刪除濾心失敗: {e}")
        return jsonify({"message": f"刪除濾心失敗: {e}"}), 500

if __name__ == "__main__":
    # 在應用程式啟動時，嘗試載入或建立濾心資料檔案
    # 這確保了 DATA_FILE 在服務啟動時就是有效的 JSON 格式
    try:
        load_filters()
        print("DEBUG: 服務啟動前濾心資料初始化完成。")
    except Exception as e:
        print(f"CRITICAL ERROR: 應用程式啟動時初始化資料失敗: {e}")
        # 如果這裡失敗，應用程式可能無法正常運行，可以選擇退出
        # sys.exit(1) # 如果需要更嚴格的啟動檢查，可以導入 sys
    
    app.run(debug=True) # debug=True 在開發環境使用，生產環境請關閉
