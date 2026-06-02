// ============================================================
// 农场与地块管理 - Farm & Field Management
// ============================================================

const FARM_API = "/api/v1";

// 状态
let farmsData = [];
let currentFarmId = null;
let currentFieldId = null;
let currentFarmFields = [];
let currentTrajectories = [];

// ============================================================
// 初始化
// ============================================================
function initFarmsPage() {
    loadFarms();
    setupTrajectoryDropZone();
}

// ============================================================
// 加载农场列表
// ============================================================
async function loadFarms() {
    const select = document.getElementById("farm-select");
    if (!select) return;

    try {
        const resp = await safeFetch(`${FARM_API}/farms?page=1&page_size=100`);
        const data = await resp.json();
        if (data.code === "SUCCESS") {
            farmsData = data.data.farms || [];
            renderFarmSelect();
        }
    } catch (e) {
        console.error("加载农场失败:", e);
    }
}

function renderFarmSelect() {
    const select = document.getElementById("farm-select");
    select.innerHTML = '<option value="">选择农场</option>' +
        farmsData.map(f => `<option value="${f.id}">${escapeHtml(f.name)}</option>`).join('');

    // 如果有农场，默认选中第一个
    if (farmsData.length > 0 && !currentFarmId) {
        select.value = farmsData[0].id;
        onFarmChange(farmsData[0].id);
    }
}

// ============================================================
// 农场切换
// ============================================================
async function onFarmChange(farmId) {
    currentFarmId = farmId ? parseInt(farmId) : null;
    currentFieldId = null;
    currentFarmFields = [];

    // 更新地块下拉框
    const fieldSelect = document.getElementById("field-select");
    const btnAddField = document.getElementById("btn-add-field");
    const btnUploadTraj = document.getElementById("btn-upload-traj");

    if (!currentFarmId) {
        fieldSelect.innerHTML = '<option value="">选择地块</option>';
        document.getElementById("trajectory-select").innerHTML = '<option value="">选择轨迹</option>';
        btnAddField.style.display = "none";
        btnUploadTraj.style.display = "none";
        return;
    }

    // 显示新建地块按钮
    btnAddField.style.display = "";

    // 加载地块
    try {
        const resp = await safeFetch(`${FARM_API}/farms/${currentFarmId}`);
        const data = await resp.json();
        if (data.code === "SUCCESS") {
            currentFarmFields = data.data.fields || [];
            renderFieldSelect();
            // 在地图上显示地块
            showFieldsOnMap(currentFarmFields);
        }
    } catch (e) {
        console.error("加载地块失败:", e);
    }
}

function renderFieldSelect() {
    const select = document.getElementById("field-select");
    select.innerHTML = '<option value="">选择地块</option>' +
        currentFarmFields.map(f => `<option value="${f.id}">${escapeHtml(f.name)}</option>`).join('');

    // 清空轨迹选择
    document.getElementById("trajectory-select").innerHTML = '<option value="">选择轨迹</option>';
    document.getElementById("btn-upload-traj").style.display = "none";
}

// ============================================================
// 地块切换
// ============================================================
async function onFieldChange(fieldId) {
    currentFieldId = fieldId ? parseInt(fieldId) : null;
    currentTrajectories = [];

    const trajSelect = document.getElementById("trajectory-select");
    const btnUploadTraj = document.getElementById("btn-upload-traj");

    if (!currentFieldId) {
        trajSelect.innerHTML = '<option value="">选择轨迹</option>';
        btnUploadTraj.style.display = "none";
        return;
    }

    // 显示导入轨迹按钮
    btnUploadTraj.style.display = "";

    // 定位到地块
    const field = currentFarmFields.find(f => f.id === currentFieldId);
    if (field && field.latitude && field.longitude) {
        flyToLocation(field.latitude, field.longitude, 16);
    }

    // 加载轨迹列表
    try {
        const resp = await safeFetch(`${FARM_API}/fields/${currentFieldId}/trajectories`);
        const data = await resp.json();
        if (data.code === "SUCCESS") {
            currentTrajectories = data.data.trajectories || [];
            renderTrajectorySelect();
        }
    } catch (e) {
        console.error("加载轨迹失败:", e);
    }
}

function renderTrajectorySelect() {
    const select = document.getElementById("trajectory-select");
    if (currentTrajectories.length === 0) {
        select.innerHTML = '<option value="">暂无轨迹</option>';
    } else {
        select.innerHTML = '<option value="">选择轨迹</option>' +
            currentTrajectories.map(t =>
                `<option value="${t.id}">${escapeHtml(t.filename)} (${t.point_count}点)</option>`
            ).join('');
    }
}

// ============================================================
// 轨迹切换
// ============================================================
async function onTrajectoryChange(fileId) {
    const btnAnalysis = document.getElementById("btn-analysis");

    if (!fileId) {
        clearTrajectoryPoints();
        btnAnalysis.style.display = "none";
        return;
    }

    // 显示数据分析按钮
    btnAnalysis.style.display = "";

    // 加载轨迹点并在地图上显示
    try {
        const resp = await safeFetch(`${FARM_API}/trajectories/${fileId}/points`);
        const data = await resp.json();
        if (data.code === "SUCCESS" && data.data.points) {
            clearTrajectoryPoints();
            renderTrajectoryPoints(data.data.points);
        }
    } catch (e) {
        console.error("加载轨迹点失败:", e);
    }
}

// ============================================================
// 上传轨迹模态框
// ============================================================
function showUploadModal() {
    if (!currentFieldId) {
        alert("请先选择地块");
        return;
    }
    document.getElementById("trajectory-modal").classList.add("show");
}

function closeTrajectoryModal() {
    document.getElementById("trajectory-modal").classList.remove("show");
}

function handleTrajectoryUpload(input) {
    const file = input.files[0];
    if (!file) return;

    if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
        alert('仅支持 .xlsx / .xls 格式');
        input.value = '';
        return;
    }

    uploadTrajectory(file);
    input.value = '';
}

async function uploadTrajectory(file) {
    const formData = new FormData();
    formData.append('file', file);

    const coordSystem = document.getElementById("coord-system")?.value || "auto";
    formData.append('coord_system', coordSystem);

    const statusEl = document.getElementById("trajectory-upload-status");
    statusEl.textContent = '上传中...';
    statusEl.className = "upload-status";

    try {
        const resp = await safeFetch(`${FARM_API}/fields/${currentFieldId}/trajectories/upload`, {
            method: "POST",
            body: formData,
        });
        const data = await resp.json();
        if (data.code === "SUCCESS") {
            statusEl.textContent = data.message;
            statusEl.className = "upload-status success";
            // 刷新轨迹列表
            onFieldChange(currentFieldId);
        } else {
            statusEl.textContent = data.message;
            statusEl.className = "upload-status error";
        }
    } catch (e) {
        statusEl.textContent = '上传失败';
        statusEl.className = "upload-status error";
    }
}

// 拖拽上传
function setupTrajectoryDropZone() {
    const dropZone = document.getElementById("trajectory-drop-zone");
    if (!dropZone) return;

    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("dragover");
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        const file = e.dataTransfer.files[0];
        if (file && (file.name.endsWith('.xlsx') || file.name.endsWith('.xls'))) {
            uploadTrajectory(file);
        } else {
            alert('仅支持 .xlsx / .xls 格式');
        }
    });
}

// ============================================================
// 农场/地块 CRUD（保留原有功能）
// ============================================================

function showFarmModal(farmId) {
    const farm = farmId ? farmsData.find(f => f.id === farmId) : null;
    const modal = document.getElementById("farm-modal");
    const title = document.getElementById("farm-modal-title");
    const form = document.getElementById("farm-form");

    title.textContent = farm ? "编辑农场" : "创建农场";
    form.dataset.farmId = farmId || "";

    document.getElementById("farm-name").value = farm?.name || "";
    document.getElementById("farm-location").value = farm?.location || "";
    document.getElementById("farm-area").value = farm?.area_mu || "";
    document.getElementById("farm-lat").value = farm?.latitude || "";
    document.getElementById("farm-lng").value = farm?.longitude || "";
    document.getElementById("farm-desc").value = farm?.description || "";

    modal.classList.add("show");
}

function closeFarmModal() {
    document.getElementById("farm-modal").classList.remove("show");
}

async function saveFarm() {
    const form = document.getElementById("farm-form");
    const farmId = form.dataset.farmId;
    const name = document.getElementById("farm-name").value.trim();
    if (!name) { alert("请输入农场名称"); return; }

    const body = {
        name,
        location: document.getElementById("farm-location").value.trim(),
        area_mu: parseFloat(document.getElementById("farm-area").value) || null,
        latitude: parseFloat(document.getElementById("farm-lat").value) || null,
        longitude: parseFloat(document.getElementById("farm-lng").value) || null,
        description: document.getElementById("farm-desc").value.trim(),
    };

    try {
        const url = farmId ? `${FARM_API}/farms/${farmId}` : `${FARM_API}/farms`;
        const method = farmId ? "PUT" : "POST";
        const resp = await safeFetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        const data = await resp.json();
        if (data.code === "SUCCESS") {
            closeFarmModal();
            loadFarms();
        } else {
            alert(data.message || "操作失败");
        }
    } catch (e) {
        alert("网络错误");
    }
}

function confirmDeleteFarm(farmId, name) {
    if (!confirm(`删除农场"${name}"？地块将一并删除。`)) return;
    deleteFarm(farmId);
}

async function deleteFarm(farmId) {
    try {
        const resp = await safeFetch(`${FARM_API}/farms/${farmId}`, { method: "DELETE" });
        const data = await resp.json();
        if (data.code === "SUCCESS") {
            loadFarms();
        } else {
            alert(data.message || "删除失败");
        }
    } catch (e) {
        alert("网络错误");
    }
}

function showFieldModal(fieldId) {
    const field = fieldId ? currentFarmFields.find(f => f.id === fieldId) : null;
    const modal = document.getElementById("field-modal");
    const title = document.getElementById("field-modal-title");
    const form = document.getElementById("field-form");

    title.textContent = field ? "编辑地块" : "添加地块";
    form.dataset.fieldId = fieldId || "";

    document.getElementById("field-name").value = field?.name || "";
    document.getElementById("field-area").value = field?.area_mu || "";
    document.getElementById("field-soil").value = field?.soil_type || "";
    document.getElementById("field-crop").value = field?.current_crop || "";
    document.getElementById("field-planting-date").value = field?.planting_date || "";
    document.getElementById("field-harvest-date").value = field?.expected_harvest || "";
    document.getElementById("field-stage").value = field?.growth_stage || "";
    document.getElementById("field-status").value = field?.status || "idle";
    document.getElementById("field-notes").value = field?.notes || "";

    modal.classList.add("show");
}

function closeFieldModal() {
    document.getElementById("field-modal").classList.remove("show");
}

async function saveField() {
    const form = document.getElementById("field-form");
    const fieldId = form.dataset.fieldId;
    const name = document.getElementById("field-name").value.trim();
    if (!name) { alert("请输入地块名称"); return; }

    const body = {
        name,
        area_mu: parseFloat(document.getElementById("field-area").value) || null,
        soil_type: document.getElementById("field-soil").value.trim(),
        current_crop: document.getElementById("field-crop").value.trim(),
        planting_date: document.getElementById("field-planting-date").value || null,
        expected_harvest: document.getElementById("field-harvest-date").value || null,
        growth_stage: document.getElementById("field-stage").value.trim(),
        status: document.getElementById("field-status").value,
        notes: document.getElementById("field-notes").value.trim(),
    };

    try {
        let url, method;
        if (fieldId) {
            url = `${FARM_API}/fields/${fieldId}`;
            method = "PUT";
        } else {
            url = `${FARM_API}/farms/${currentFarmId}/fields`;
            method = "POST";
        }
        const resp = await safeFetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        const data = await resp.json();
        if (data.code === "SUCCESS") {
            closeFieldModal();
            onFarmChange(currentFarmId);
        } else {
            alert(data.message || "操作失败");
        }
    } catch (e) {
        alert("网络错误");
    }
}

function confirmDeleteField(fieldId, name) {
    if (!confirm(`删除地块"${name}"？`)) return;
    deleteField(fieldId);
}

async function deleteField(fieldId) {
    try {
        const resp = await safeFetch(`${FARM_API}/fields/${fieldId}`, { method: "DELETE" });
        const data = await resp.json();
        if (data.code === "SUCCESS") {
            onFarmChange(currentFarmId);
        } else {
            alert(data.message || "删除失败");
        }
    } catch (e) {
        alert("网络错误");
    }
}

// ============================================================
// 数据分析
// ============================================================

function showAnalysisModal() {
    const trajSelect = document.getElementById("trajectory-select");
    const fileId = trajSelect.value;

    if (!fileId) {
        alert("请先选择轨迹");
        return;
    }

    // 显示模态框
    document.getElementById("analysis-modal").classList.add("show");
    document.getElementById("analysis-loading").style.display = "";
    document.getElementById("analysis-content").style.display = "none";

    // 加载分析数据
    loadAnalysisData(fileId);
}

function closeAnalysisModal() {
    document.getElementById("analysis-modal").classList.remove("show");
}

async function loadAnalysisData(fileId) {
    try {
        const resp = await safeFetch(`${FARM_API}/trajectories/${fileId}/analysis`);
        const data = await resp.json();

        if (data.code === "SUCCESS") {
            renderAnalysisData(data.data);
        } else {
            alert(data.message || "分析失败");
            closeAnalysisModal();
        }
    } catch (e) {
        console.error("加载分析数据失败:", e);
        alert("网络错误");
        closeAnalysisModal();
    }
}

function renderAnalysisData(analysis) {
    // 隐藏加载状态，显示内容
    document.getElementById("analysis-loading").style.display = "none";
    document.getElementById("analysis-content").style.display = "";

    // 作业量指标
    const volume = analysis.work_volume;
    document.getElementById("metric-duration").textContent = volume.work_duration_hours.toFixed(1);
    document.getElementById("metric-distance").textContent = volume.work_distance_km.toFixed(2);
    document.getElementById("metric-area").textContent = volume.work_area_mu.toFixed(1);
    document.getElementById("metric-speed").textContent = volume.avg_field_speed_kmh.toFixed(1);

    // 作业效率指标
    const efficiency = analysis.work_efficiency;
    document.getElementById("metric-compliance").textContent = efficiency.compliance_rate.toFixed(1);
    document.getElementById("metric-productivity").textContent = efficiency.productivity_mu_per_hour.toFixed(1);
    document.getElementById("metric-time-util").textContent = efficiency.time_utilization_rate.toFixed(1);

    // 详细指标
    document.getElementById("detail-depth-compliance").textContent = efficiency.depth_compliance.toFixed(1) + "%";
    document.getElementById("detail-speed-compliance").textContent = efficiency.speed_compliance.toFixed(1) + "%";
    document.getElementById("detail-total-points").textContent = efficiency.total_points;
    document.getElementById("detail-compliant-points").textContent = efficiency.compliant_points;

    // 图表
    const volumeChart = document.getElementById("work-volume-chart");
    const efficiencyChart = document.getElementById("work-efficiency-chart");

    if (analysis.work_volume_chart) {
        volumeChart.src = "data:image/png;base64," + analysis.work_volume_chart;
        volumeChart.style.display = "";
    } else {
        volumeChart.style.display = "none";
    }

    if (analysis.work_efficiency_chart) {
        efficiencyChart.src = "data:image/png;base64," + analysis.work_efficiency_chart;
        efficiencyChart.style.display = "";
    } else {
        efficiencyChart.style.display = "none";
    }
}
