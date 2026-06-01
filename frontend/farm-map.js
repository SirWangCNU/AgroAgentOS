// ============================================================
// 农场地图管理 - Farm Map Management
// ============================================================

let farmMap = null;
let osmLayer = null;
let satelliteLayer = null;
let roadLayer = null;
let fieldMarkers = [];
let trajectoryPointMarkers = [];

// WGS-84 转 GCJ-02 坐标转换
function wgs84ToGcj02(lat, lng) {
    const PI = Math.PI;
    const a = 6378245.0;
    const ee = 0.00669342162296594;

    function transformLat(x, y) {
        let ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
        ret += (20.0 * Math.sin(6.0 * x * PI) + 20.0 * Math.sin(2.0 * x * PI)) * 2.0 / 3.0;
        ret += (20.0 * Math.sin(y * PI) + 40.0 * Math.sin(y / 3.0 * PI)) * 2.0 / 3.0;
        ret += (160.0 * Math.sin(y / 12.0 * PI) + 320 * Math.sin(y * PI / 30.0)) * 2.0 / 3.0;
        return ret;
    }

    function transformLon(x, y) {
        let ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
        ret += (20.0 * Math.sin(6.0 * x * PI) + 20.0 * Math.sin(2.0 * x * PI)) * 2.0 / 3.0;
        ret += (20.0 * Math.sin(x * PI) + 40.0 * Math.sin(x / 3.0 * PI)) * 2.0 / 3.0;
        ret += (150.0 * Math.sin(x / 12.0 * PI) + 300.0 * Math.sin(x / 30.0 * PI)) * 2.0 / 3.0;
        return ret;
    }

    let dLat = transformLat(lng - 105.0, lat - 35.0);
    let dLng = transformLon(lng - 105.0, lat - 35.0);

    const radLat = lat / 180.0 * PI;
    let magic = Math.sin(radLat);
    magic = 1 - ee * magic * magic;
    const sqrtMagic = Math.sqrt(magic);

    dLat = (dLat * 180.0) / ((a * (1 - ee)) / (magic * sqrtMagic) * PI);
    dLng = (dLng * 180.0) / (a / sqrtMagic * Math.cos(radLat) * PI);

    return [lat + dLat, lng + dLng];
}

// 地图瓦片源配置
const MAP_CONFIG = {
    // OpenStreetMap - 无偏移，适合 WGS-84 坐标
    osm: {
        url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        options: {
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap'
        }
    },
    // 高德卫星图 - GCJ-02 坐标系
    amap_satellite: {
        url: 'https://wprd0{s}.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scl=1&style=6',
        options: {
            subdomains: ['1', '2', '3', '4'],
            maxZoom: 18,
            attribution: '&copy; 高德地图'
        }
    },
    // 高德路网 - GCJ-02 坐标系
    amap_road: {
        url: 'https://wprd0{s}.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scl=1&style=7',
        options: {
            subdomains: ['1', '2', '3', '4'],
            maxZoom: 18,
            attribution: '&copy; 高德地图'
        }
    }
};

// 当前使用的坐标系和图层
let currentCoordSystem = 'wgs84'; // 'wgs84' 或 'gcj02'
let currentLayerType = 'osm'; // 'osm', 'satellite', 'road'

// 判断当前图层是否需要坐标转换（Amap 使用 GCJ-02）
function isAmapLayer() {
    return currentLayerType === 'satellite' || currentLayerType === 'road';
}

// ============================================================
// 地图初始化
// ============================================================

function initFarmMap(center, zoom) {
    if (farmMap) {
        farmMap.remove();
    }

    const defaultCenter = center || [35.8617, 104.1954];
    const defaultZoom = zoom || 5;

    farmMap = L.map('farm-map', {
        center: defaultCenter,
        zoom: defaultZoom,
        zoomControl: false
    });

    // 添加缩放控件到右下角
    L.control.zoom({ position: 'bottomright' }).addTo(farmMap);

    // 添加图层
    osmLayer = L.tileLayer(MAP_CONFIG.osm.url, MAP_CONFIG.osm.options);
    satelliteLayer = L.tileLayer(MAP_CONFIG.amap_satellite.url, MAP_CONFIG.amap_satellite.options);
    roadLayer = L.tileLayer(MAP_CONFIG.amap_road.url, MAP_CONFIG.amap_road.options);

    // 默认显示 OpenStreetMap（无偏移，适合 GPS 数据）
    osmLayer.addTo(farmMap);

    // 更新按钮状态
    document.getElementById('btn-osm')?.classList.add('active');
    document.getElementById('btn-satellite')?.classList.remove('active');
    document.getElementById('btn-road')?.classList.remove('active');

    return farmMap;
}

// ============================================================
// 图层切换
// ============================================================

function switchMapLayer(type) {
    if (!farmMap) return;

    // 移除所有图层
    if (osmLayer) farmMap.removeLayer(osmLayer);
    if (satelliteLayer) farmMap.removeLayer(satelliteLayer);
    if (roadLayer) farmMap.removeLayer(roadLayer);

    // 重置按钮状态
    document.getElementById('btn-osm')?.classList.remove('active');
    document.getElementById('btn-satellite')?.classList.remove('active');
    document.getElementById('btn-road')?.classList.remove('active');

    // 更新当前图层类型
    currentLayerType = type;

    // 添加选择的图层
    if (type === 'osm') {
        osmLayer.addTo(farmMap);
        document.getElementById('btn-osm')?.classList.add('active');
    } else if (type === 'satellite') {
        satelliteLayer.addTo(farmMap);
        document.getElementById('btn-satellite')?.classList.add('active');
    } else if (type === 'road') {
        roadLayer.addTo(farmMap);
        document.getElementById('btn-road')?.classList.add('active');
    }

    // 切换图层后重新渲染所有标记（坐标系可能不同）
    reRenderAllMarkers();
}

// ============================================================
// 地图视图控制
// ============================================================

function fitMapBounds() {
    if (!farmMap) return;

    const allMarkers = [...fieldMarkers, ...trajectoryPointMarkers];
    if (allMarkers.length > 0) {
        const group = L.featureGroup(allMarkers);
        farmMap.fitBounds(group.getBounds().pad(0.2));
    }
}

function flyToLocation(lat, lng, zoom) {
    if (!farmMap) return;
    // 根据当前图层转换坐标
    const [cLat, cLng] = convertCoord(lat, lng);
    farmMap.flyTo([cLat, cLng], zoom || 15);
}

// ============================================================
// 地块标记
// ============================================================

// 保存原始数据用于重新渲染
let fieldData = [];
let trajectoryPointsData = [];

function clearFieldMarkers() {
    fieldMarkers.forEach(marker => farmMap.removeLayer(marker));
    fieldMarkers = [];
}

// 坐标转换：WGS-84 -> 当前图层坐标系
function convertCoord(lat, lng) {
    if (isAmapLayer()) {
        return wgs84ToGcj02(lat, lng);
    }
    return [lat, lng];
}

function addFieldMarker(field) {
    if (!farmMap || !field.latitude || !field.longitude) return;

    const statusColors = {
        idle: '#6b8a6b',
        planting: '#16a34a',
        fallow: '#d97706'
    };

    const color = statusColors[field.status] || '#6b8a6b';

    const icon = L.divIcon({
        className: 'field-marker-icon',
        html: `<div class="field-marker" style="background-color: ${color}"></div>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10]
    });

    // 根据当前图层转换坐标
    const [lat, lng] = convertCoord(field.latitude, field.longitude);

    const marker = L.marker([lat, lng], { icon })
        .addTo(farmMap)
        .bindPopup(`
            <div style="font-size:12px;padding:4px">
                <div style="font-weight:600;margin-bottom:4px">${escapeHtml(field.name)}</div>
                <div>${field.area_mu || 0} 亩 · ${escapeHtml(field.current_crop || '未种植')}</div>
            </div>
        `);

    fieldMarkers.push(marker);
    return marker;
}

function showFieldsOnMap(fields) {
    clearFieldMarkers();
    clearTrajectoryPoints();

    // 保存原始数据
    fieldData = fields;
    trajectoryPointsData = [];

    const validFields = fields.filter(f => f.latitude && f.longitude);

    validFields.forEach(field => {
        addFieldMarker(field);
    });

    if (fieldMarkers.length > 0) {
        fitMapBounds();
    }
}

// ============================================================
// 轨迹点显示（散点）
// ============================================================

function clearTrajectoryPoints() {
    trajectoryPointMarkers.forEach(marker => {
        if (farmMap) farmMap.removeLayer(marker);
    });
    trajectoryPointMarkers = [];
}

function renderTrajectoryPoints(points) {
    if (!farmMap || !points || points.length === 0) return;

    // 保存原始数据用于重新渲染
    trajectoryPointsData = points;

    console.log('[地图] 渲染轨迹点数量:', points.length);
    console.log('[地图] 第一个点坐标:', points[0].latitude, points[0].longitude);
    console.log('[地图] 当前图层:', currentLayerType, '(需要坐标转换:', isAmapLayer(), ')');

    const statusColors = {
        working: '#16a34a',
        idle: '#9ca3af',
        transporting: '#2563eb'
    };

    const bounds = [];

    points.forEach(point => {
        const color = statusColors[point.work_status] || statusColors.idle;

        // 根据当前图层转换坐标
        const [lat, lng] = convertCoord(point.latitude, point.longitude);

        const circleMarker = L.circleMarker([lat, lng], {
            radius: 3,
            fillColor: color,
            color: color,
            weight: 1,
            opacity: 0.8,
            fillOpacity: 0.6
        }).addTo(farmMap);

        // 弹出框显示原始 WGS-84 坐标
        circleMarker.bindPopup(`
            <div style="font-size:12px">
                <div><b>序号:</b> ${point.seq}</div>
                <div><b>坐标:</b> ${point.latitude.toFixed(6)}, ${point.longitude.toFixed(6)}</div>
                <div><b>状态:</b> ${point.work_status || '未知'}</div>
                <div><b>速度:</b> ${point.speed?.toFixed(1) || 0} km/h</div>
                <div><b>深度:</b> ${point.depth?.toFixed(1) || 0} cm</div>
            </div>
        `);

        trajectoryPointMarkers.push(circleMarker);
        bounds.push([lat, lng]);
    });

    // 自动调整视图
    if (bounds.length > 0) {
        farmMap.fitBounds(bounds, { padding: [30, 30] });
        console.log('[地图] 视图已调整到轨迹范围');
    }
}

// ============================================================
// 切换图层后重新渲染所有标记
// ============================================================

function reRenderAllMarkers() {
    if (!farmMap) return;

    // 重新渲染地块标记
    if (fieldData.length > 0) {
        clearFieldMarkers();
        fieldData.forEach(field => {
            if (field.latitude && field.longitude) {
                addFieldMarker(field);
            }
        });
    }

    // 重新渲染轨迹点
    if (trajectoryPointsData.length > 0) {
        clearTrajectoryPoints();
        const statusColors = {
            working: '#16a34a',
            idle: '#9ca3af',
            transporting: '#2563eb'
        };

        trajectoryPointsData.forEach(point => {
            const color = statusColors[point.work_status] || statusColors.idle;
            const [lat, lng] = convertCoord(point.latitude, point.longitude);

            const circleMarker = L.circleMarker([lat, lng], {
                radius: 3,
                fillColor: color,
                color: color,
                weight: 1,
                opacity: 0.8,
                fillOpacity: 0.6
            }).addTo(farmMap);

            circleMarker.bindPopup(`
                <div style="font-size:12px">
                    <div><b>序号:</b> ${point.seq}</div>
                    <div><b>坐标:</b> ${point.latitude.toFixed(6)}, ${point.longitude.toFixed(6)}</div>
                    <div><b>状态:</b> ${point.work_status || '未知'}</div>
                    <div><b>速度:</b> ${point.speed?.toFixed(1) || 0} km/h</div>
                    <div><b>深度:</b> ${point.depth?.toFixed(1) || 0} cm</div>
                </div>
            `);

            trajectoryPointMarkers.push(circleMarker);
        });

        console.log('[地图] 已重新渲染所有标记，当前图层:', currentLayerType);
    }
}

// ============================================================
// 页面加载时初始化地图
// ============================================================

document.addEventListener('DOMContentLoaded', function() {
    const mapContainer = document.getElementById('farm-map');
    if (mapContainer) {
        initFarmMap();
    }
});
