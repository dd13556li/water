from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import datetime

app = Flask(__name__)
CORS(app, supports_credentials=True)  # ✅ 確保允許跨域請求


DATA_FILE = "filters.json"

DEFAULT_FILTERS = [
    {"name": "前置濾網", "last_replace": "2025-05-01", "lifespan": 60},
    {"name": "活性碳濾心", "last_replace": "2025-05-01", "lifespan": 90}
]

# 讀取濾心資料
def load_filters():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return DEFAULT_FILTERS

# 儲存濾心資料
def save_filters(filters):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(filters, f, ensure_ascii=False, indent=4)

@app.route("/filters", methods=["GET"])
def get_filters():
    return jsonify(load_filters())

@app.route("/add", methods=["POST"])
def add_filter():
    data = request.json
    filters = load_filters()
    filters.append({
        "name": data["name"],
        "last_replace": data["last_replace"],
        "lifespan": int(data["lifespan"])
    })
    save_filters(filters)
    return jsonify({"message": "濾心已成功新增"})

@app.route("/update", methods=["POST"])
def update_filter():
    data = request.json
    filters = load_filters()
    for f in filters:
        if f["name"] == data["name"]:
            f["last_replace"] = datetime.datetime.now().strftime("%Y-%m-%d")
            save_filters(filters)
            return jsonify({"message": "更新成功", "updated": f})
    return jsonify({"message": "濾心未找到"}), 404

from flask_cors import cross_origin

@app.route("/delete", methods=["POST", "OPTIONS"])  # ✅ 確保支持 OPTIONS 預檢請求
@cross_origin()
def delete_filter():
    if request.method == "OPTIONS":  # ✅ 處理預檢請求
        return jsonify({"message": "OK"}), 200
    
    data = request.json
    filters = load_filters()
    filters = [f for f in filters if f["name"] != data["name"]]
    save_filters(filters)
    return jsonify({"message": f"濾心 {data['name']} 已刪除"}), 200


if __name__ == "__main__":
    app.run(debug=True)
