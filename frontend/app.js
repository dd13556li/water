// 獲取濾心資訊並更新網頁內容
async function fetchFilters() {
    const response = await fetch("http://127.0.0.1:5000/filters");
    const filters = await response.json();
    const tbody = document.getElementById("filterTable");
    tbody.innerHTML = "";

    filters.forEach(filter => {
        let lastDate = new Date(filter.last_replace);
        let nextDate = new Date(lastDate);
        nextDate.setDate(lastDate.getDate() + filter.lifespan);
        let remainingDays = Math.ceil((nextDate - new Date()) / (1000 * 60 * 60 * 24));

        let row = `<tr>
            <td>${filter.name}</td>
            <td>${filter.last_replace}</td>
            <td>${nextDate.toISOString().split('T')[0]}</td>
            <td class="${remainingDays <= 7 ? 'low-days' : ''}">${remainingDays}</td>
            <td><button onclick="updateFilter('${filter.name}')"><i class="fas fa-sync-alt icon"></i> 更新</button></td>
            <td><button onclick="confirmDelete('${filter.name}')"><i class="fas fa-trash-alt icon"></i> 刪除</button></td>
        </tr>`;
        tbody.innerHTML += row;
    });
}


// 新增濾心
document.getElementById("filterForm").addEventListener("submit", async function(event) {
    event.preventDefault();
    
    const name = document.getElementById("name").value;
    const lastReplace = document.getElementById("lastReplace").value;
    const lifespan = document.getElementById("lifespan").value;

    await fetch("http://127.0.0.1:5000/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, last_replace: lastReplace, lifespan })
    });

    alert("濾心已新增！");
    fetchFilters();
});

// 更新濾心更換日期
async function updateFilter(name) {
    await fetch("http://127.0.0.1:5000/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name })
    });
    alert("濾心已更新！");
    fetchFilters();
}

// 執行刪除濾心
async function deleteFilter(name) {
    await fetch("http://127.0.0.1:5000/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name })
    });

    alert(`已刪除濾心：${name}`);
    fetchFilters(); // 重新載入濾心清單
}

// 確認是否刪除濾心
function confirmDelete(name) {
    if (confirm(`確定要刪除 ${name} 嗎？`)) {
        deleteFilter(name);
    }
}

// 確認是否刪除濾心
function confirmDelete(name) {
    if (confirm(`確定要刪除 ${name} 嗎？`)) {
        deleteFilter(name);
    }
}

// 當頁面載入時，獲取濾心資訊
document.addEventListener("DOMContentLoaded", fetchFilters);
