const apiBaseUrl = "https://water-2hc2.onrender.com"; // 設定 Flask API 伺服器

// ✅ 取得濾心資料並顯示在網頁上
function fetchFilters() {
    fetch(`${apiBaseUrl}/filters`)
        .then(response => response.json())
        .then(data => {
            console.log("濾心資料:", data);
            const filterList = document.getElementById("filter-list");
            filterList.innerHTML = "";
            data.forEach(filter => {
                const listItem = document.createElement("li");
                listItem.innerText = `${filter.name} - 上次更換: ${filter.last_replace} - 壽命: ${filter.lifespan} 天`;
                filterList.appendChild(listItem);
            });
        })
        .catch(error => console.error("API 錯誤:", error));
}

// ✅ 新增濾心
function addFilter() {
    const name = document.getElementById("filter-name").value;
    const lastReplace = document.getElementById("filter-date").value;
    const lifespan = document.getElementById("filter-lifespan").value;

    fetch(`${apiBaseUrl}/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, last_replace: lastReplace, lifespan: parseInt(lifespan) })
    })
    .then(response => response.json())
    .then(data => {
        console.log("新增結果:", data);
        fetchFilters(); // 更新濾心列表
    })
    .catch(error => console.error("API 錯誤:", error));
}

// ✅ 更新濾心的更換日期（設為今天）
function updateFilter() {
    const name = document.getElementById("update-name").value;

    fetch(`${apiBaseUrl}/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name })
    })
    .then(response => response.json())
    .then(data => {
        console.log("更新結果:", data);
        fetchFilters(); // 更新濾心列表
    })
    .catch(error => console.error("API 錯誤:", error));
}

// ✅ 刪除濾心
function deleteFilter() {
    const name = document.getElementById("delete-name").value;

    fetch(`${apiBaseUrl}/delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name })
    })
    .then(response => response.json())
    .then(data => {
        console.log("刪除結果:", data);
        fetchFilters(); // 更新濾心列表
    })
    .catch(error => console.error("API 錯誤:", error));
}

// ✅ 頁面載入時，先獲取濾心列表
document.addEventListener("DOMContentLoaded", fetchFilters);
