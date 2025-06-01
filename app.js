const apiBaseUrl = "https://water-2hc2.onrender.com"; // 設定 Flask API 伺服器

// --- 輔助函數：計算日期差異 ---
// 這個函數會計算兩個日期之間的天數差異
function getDaysDifference(date1, date2) {
    const oneDay = 1000 * 60 * 60 * 24; // 一天的毫秒數
    // 將日期設為午夜，避免時間部分影響天數計算
    const d1 = new Date(date1);
    d1.setHours(0, 0, 0, 0);
    const d2 = new Date(date2);
    d2.setHours(0, 0, 0, 0);

    const diffMs = Math.abs(d1.getTime() - d2.getTime()); // 毫秒差
    return Math.ceil(diffMs / oneDay); // 轉換為天數並向上取整
}

// --- 核心功能：取得濾心資料並顯示在網頁上 (已修改) ---
function fetchFilters() {
    fetch(`${apiBaseUrl}/filters`)
        .then(response => {
            // 檢查 HTTP 響應是否成功 (status code 2xx)
            if (!response.ok) {
                // 如果響應不成功，嘗試解析錯誤訊息
                return response.json().then(errorData => {
                    throw new Error(errorData.message || '網路回應不正確');
                });
            }
            return response.json();
        })
        .then(data => {
            console.log("濾心資料:", data);
            const filterList = document.getElementById("filter-list");
            filterList.innerHTML = ""; // 清空現有內容

            // 獲取當前日期 (今天的日期)，用於計算剩餘壽命
            const today = new Date();
            today.setHours(0, 0, 0, 0); // 將時間設為午夜，確保只比較日期

            // 確保 data 是一個陣列，以防 API 返回錯誤格式
            if (Array.isArray(data)) {
                data.forEach(filter => {
                    const lastReplaceDate = new Date(filter.last_replace);

                    // 計算已使用天數
                    const daysUsed = getDaysDifference(today, lastReplaceDate);

                    // 計算剩餘壽命
                    const remainingLifespan = filter.lifespan - daysUsed;

                    // 根據剩餘壽命設定顯示顏色
                    let statusColor = 'green'; // 預設綠色
                    if (remainingLifespan <= 0) {
                        statusColor = 'red'; // 壽命結束或已過期
                    } else if (remainingLifespan <= filter.lifespan * 0.2) { 
                        // 當剩餘壽命少於總壽命的 20% 時，變為橘色 (可自行調整比例)
                        statusColor = 'orange';
                    }

                    const listItem = document.createElement("li");
                    // 使用內聯樣式來設定顏色
                    listItem.innerHTML = `
                        <strong>${filter.name}</strong><br>
                        上次更換: ${filter.last_replace}<br>
                        設計壽命: ${filter.lifespan} 天<br>
                        <span style="color: ${statusColor}; font-weight: bold;">剩餘壽命: ${remainingLifespan} 天</span>
                        <button onclick="updateFilterDate('${filter.name}')">已更換</button>
                        <button onclick="deleteFilterItem('${filter.name}')" class="delete-btn">刪除</button>
                    `;
                    filterList.appendChild(listItem);
                });
            } else {
                console.error("API 回傳資料格式不正確，預期為陣列:", data);
                filterList.innerHTML = `<li style="color: red;">載入濾心資料失敗：伺服器回應格式不正確。</li>`;
            }
        })
        .catch(error => {
            console.error("API 錯誤:", error);
            const filterList = document.getElementById("filter-list");
            filterList.innerHTML = `<li style="color: red;">載入濾心資料失敗：${error.message || '請檢查網絡或伺服器。'}</li>`;
        });
}

// --- 新增濾心 (不變) ---
function addFilter() {
    const name = document.getElementById("filter-name").value;
    const lastReplace = document.getElementById("filter-date").value;
    const lifespan = document.getElementById("filter-lifespan").value;

    if (!name || !lastReplace || !lifespan) {
        alert("所有欄位都必須填寫！");
        return;
    }

    fetch(`${apiBaseUrl}/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, last_replace: lastReplace, lifespan: parseInt(lifespan) })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(errorData => {
                throw new Error(errorData.message || '新增濾心失敗');
            });
        }
        return response.json();
    })
    .then(data => {
        console.log("新增結果:", data);
        alert(data.message || "濾心已成功新增!");
        // 清空表單
        document.getElementById("filter-name").value = "";
        document.getElementById("filter-date").value = "";
        document.getElementById("filter-lifespan").value = "";
        fetchFilters(); // 更新濾心列表
    })
    .catch(error => {
        console.error("API 錯誤:", error);
        alert(`新增失敗: ${error.message}`);
    });
}

// --- 更新濾心的更換日期（設為今天）(已修改函數名以避免與 HTML input 元素 ID 混淆) ---
// 注意：這裡直接使用濾心的名字，而不是從輸入框獲取
function updateFilterDate(name) { // 接收濾心名稱作為參數
    // 如果是從輸入框獲取，請保留原本的邏輯
    // const name = document.getElementById("update-name").value; 
    
    // 如果你想讓使用者確認，可以加上 confirm
    if (!confirm(`確定要將濾心 "${name}" 的上次更換日期更新為今天嗎？`)) {
        return;
    }

    fetch(`${apiBaseUrl}/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }) // 發送要更新的濾心名稱
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(errorData => {
                throw new Error(errorData.message || '更新濾心失敗');
            });
        }
        return response.json();
    })
    .then(data => {
        console.log("更新結果:", data);
        alert(data.message || "濾心已成功更新!");
        // 如果你還有更新輸入框，可以清空它
        // document.getElementById("update-name").value = "";
        fetchFilters(); // 更新濾心列表
    })
    .catch(error => {
        console.error("API 錯誤:", error);
        alert(`更新失敗: ${error.message}`);
    });
}

// --- 刪除濾心 (已修改函數名以避免與 HTML input 元素 ID 混淆) ---
// 注意：這裡直接使用濾心的名字，而不是從輸入框獲取
function deleteFilterItem(name) { // 接收濾心名稱作為參數
    // 如果是從輸入框獲取，請保留原本的邏輯
    // const name = document.getElementById("delete-name").value; 

    if (!confirm(`確定要刪除濾心 "${name}" 嗎？此操作無法恢復。`)) {
        return;
    }

    fetch(`${apiBaseUrl}/delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }) // 發送要刪除的濾心名稱
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(errorData => {
                throw new Error(errorData.message || '刪除濾心失敗');
            });
        }
        return response.json();
    })
    .then(data => {
        console.log("刪除結果:", data);
        alert(data.message || "濾心已成功刪除!");
        // 如果你還有刪除輸入框，可以清空它
        // document.getElementById("delete-name").value = "";
        fetchFilters(); // 更新濾心列表
    })
    .catch(error => {
        console.error("API 錯誤:", error);
        alert(`刪除失敗: ${error.message}`);
    });
}

// --- 頁面載入時，先獲取濾心列表 ---
document.addEventListener("DOMContentLoaded", fetchFilters);
