from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import datetime
import os

app = Flask(__name__)
CORS(app, supports_credentials=True)

# 儲存濾心資料的檔案位置（Render 通常允許 `/tmp/` 目錄）
# 請確認這條路徑是正確的
DATA_FILE = "/tmp/filters.json"

DEFAULT_FILTERS = [
    {"name": "前置濾網", "last_replace": "2025-05-01", "lifespan": 60},
    {"name": "活性碳濾心", "last_replace": "2025-05-01", "lifespan": 90}
]

# 讀取濾心資料 (應確認已恢復到此版本)
def load_filters():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            # 如果檔案不存在，使用預設值並嘗試寫入，確保檔案被建立
            save_filters(DEFAULT_FILTERS)
            return DEFAULT_FILTERS
    except (FileNotFoundError, json.JSONDecodeError) as e:
        # 處理檔案不存在或 JSON 解析錯誤的情況
        print(f"DEBUG: 讀取 filters.json 時發生錯誤: {e}. 將使用預設值。")
        save_filters(DEFAULT_FILTERS) # 嘗試寫入預設值以修復潛在的空/損壞檔案
        return DEFAULT_FILTERS
    except Exception as e:
        print(f"DEBUG: load_filters 發生未知錯誤: {e}")
        raise # 重新拋出，以便在 Render 日誌中看到詳細錯誤

# 儲存濾心資料 (應確認已恢復到此版本)
def save_filters(filters):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(filters, f, ensure_ascii=False, indent=4)
        print(f"DEBUG: 濾心資料已儲存到 {DATA_FILE}")
    except Exception as e:
        print(f"DEBUG: 儲存 filters.json 時發生錯誤: {e}")
        raise # 重新拋出，以便在 Render 日誌中看到詳細錯誤

# ... (其他路由保持不變) ...

@app.route("/add", methods=["POST"])
def add_filter():
    try:
        data = request.json
        if not data or not all(k in data for k in ["name", "last_replace", "lifespan"]):
            return jsonify({"message": "請提供完整的濾心資訊 (name, last_replace, lifespan)"}), 400

        filters = load_filters()
        # 檢查濾心名稱是否已存在，避免重複新增
        if any(f["name"] == data["name"] for f in filters):
            return jsonify({"message": f"濾心名稱 '{data['name']}' 已存在"}), 409 # 409 Conflict

        new_filter = {
            "name": data["name"],
            "last_replace": data["last_replace"],
            "lifespan": int(data["lifespan"])
        }
        filters.append(new_filter)
        save_filters(filters)
        print(f"DEBUG: 已新增濾心: {new_filter['name']}")
        return jsonify({"message": "濾心已成功新增", "added": new_filter}), 201 # 使用 201 Created

    except json.JSONDecodeError:
        return jsonify({"message": "無效的 JSON 格式"}), 400
    except ValueError:
        return jsonify({"message": "lifespan 必須是有效的數字"}), 400
    except Exception as e:
        print(f"DEBUG: add_filter 發生錯誤: {e}") # 打印到 Render 日誌
        # 返回 500 錯誤時，將錯誤訊息包含在內，方便前端調試
        return jsonify({"message": f"新增濾心時發生伺服器錯誤: {e}"}), 500


# ... (app.run 部分) ...

if __name__ == "__main__":
    # 確保在啟動時嘗試載入或建立檔案
    load_filters() # 這會確保 DATA_FILE 存在並包含預設數據
    app.run(debug=True)
