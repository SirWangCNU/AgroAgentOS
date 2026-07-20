import { useEffect, useRef } from "react";
import {
  MapContainer,
  TileLayer,
  LayersControl,
  Marker,
  Popup,
  CircleMarker,
  Polygon,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Field, TrajectoryPoint } from "../../types/farm";

// Fix Leaflet default marker icons in bundlers
const iconDefaultProto = L.Icon.Default.prototype as unknown as {
  _getIconUrl?: string;
};
delete iconDefaultProto._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const farmIcon = new L.Icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

const selectedIcon = new L.Icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [30, 49],
  iconAnchor: [15, 49],
  popupAnchor: [1, -40],
  shadowSize: [49, 49],
});

// Work status colors
const STATUS_COLORS: Record<string, string> = {
  working: "#22c55e",     // green
  transporting: "#3b82f6", // blue
  idle: "#94a3b8",        // gray
};

const STATUS_LABELS: Record<string, string> = {
  working: "作业中",
  transporting: "运输中",
  idle: "空闲",
};

interface FarmMarker {
  id: number;
  name: string;
  location: string;
  area_mu: number;
  latitude: number;
  longitude: number;
}

interface FarmMapProps {
  farms: FarmMarker[];
  fields?: Field[];
  selectedFarmId?: number | null;
  selectedFieldId?: number | null;
  trajectoryPoints?: TrajectoryPoint[];
  onFarmClick?: (farmId: number) => void;
}

interface FieldBoundary {
  field: Field;
  positions: [number, number][];
}

function parseBoundary(field: Field): FieldBoundary | null {
  if (!field.boundary_json) return null;
  try {
    const boundary = JSON.parse(field.boundary_json) as {
      type?: string;
      coordinates?: unknown;
    };
    if (boundary.type !== "Polygon" || !Array.isArray(boundary.coordinates)) {
      return null;
    }
    const ring = boundary.coordinates[0];
    if (!Array.isArray(ring)) return null;
    const positions = ring
      .map((point) => {
        if (!Array.isArray(point) || point.length < 2) return null;
        const lon = Number(point[0]);
        const lat = Number(point[1]);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
        return [lat, lon] as [number, number];
      })
      .filter((point): point is [number, number] => point !== null);
    return positions.length >= 3 ? { field, positions } : null;
  } catch {
    return null;
  }
}

/** Fly to selected farm */
function FlyToFarm({ farm }: { farm: FarmMarker | undefined }) {
  const map = useMap();
  const prevId = useRef<number | null>(null);

  useEffect(() => {
    if (farm && farm.latitude && farm.longitude && farm.id !== prevId.current) {
      map.flyTo([farm.latitude, farm.longitude], 13, { duration: 1 });
      prevId.current = farm.id;
    }
  }, [farm, map]);

  return null;
}

/** Fit bounds to trajectory points */
function FitTrajectory({ points }: { points: TrajectoryPoint[] }) {
  const map = useMap();
  const prevLen = useRef(0);

  useEffect(() => {
    if (points.length > 0 && points.length !== prevLen.current) {
      const bounds = L.latLngBounds(
        points.map((p) => [p.latitude, p.longitude] as [number, number])
      );
      map.fitBounds(bounds, { padding: [30, 30], maxZoom: 16 });
      prevLen.current = points.length;
    }
  }, [points, map]);

  return null;
}

export default function FarmMap({
  farms,
  fields = [],
  selectedFarmId,
  selectedFieldId,
  trajectoryPoints = [],
  onFarmClick,
}: FarmMapProps) {
  const selectedFarm = farms.find((f) => f.id === selectedFarmId);
  const fieldBoundaries = fields
    .map(parseBoundary)
    .filter((item): item is FieldBoundary => item !== null);

  const center: [number, number] = selectedFarm
    ? [selectedFarm.latitude, selectedFarm.longitude]
    : [35.86, 104.19];

  const zoom = selectedFarm ? 13 : 4;

  return (
    <div className="w-full h-full rounded-xl overflow-hidden border border-border map-isolation">
      <MapContainer
        center={center}
        zoom={zoom}
        className="w-full h-full"
        scrollWheelZoom={true}
      >
        <LayersControl position="topright">
          {/* Standard map */}
          <LayersControl.BaseLayer checked name="地图">
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
          </LayersControl.BaseLayer>

          {/* Satellite (Gaode) */}
          <LayersControl.BaseLayer name="卫星">
            <TileLayer
              attribution='&copy; 高德地图'
              url="https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}"
              subdomains={["1", "2", "3", "4"]}
              maxZoom={18}
            />
          </LayersControl.BaseLayer>

          {/* Satellite + labels (hybrid) */}
          <LayersControl.BaseLayer name="混合">
            <>
              <TileLayer
                attribution='&copy; 高德地图'
                url="https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}"
                subdomains={["1", "2", "3", "4"]}
                maxZoom={18}
              />
              <TileLayer
                attribution='&copy; 高德地图'
                url="https://webst0{s}.is.autonavi.com/appmaptile?style=8&x={x}&y={y}&z={z}"
                subdomains={["1", "2", "3", "4"]}
                maxZoom={18}
              />
            </>
          </LayersControl.BaseLayer>
        </LayersControl>

        <FlyToFarm farm={selectedFarm} />
        <FitTrajectory points={trajectoryPoints} />

        {/* Field boundaries */}
        {fieldBoundaries.map(({ field, positions }) => {
          const selected = field.id === selectedFieldId;
          return (
            <Polygon
              key={`field-${field.id}`}
              positions={positions}
              pathOptions={{
                color: selected ? "#f59e0b" : "#16a34a",
                fillColor: selected ? "#fbbf24" : "#22c55e",
                fillOpacity: selected ? 0.22 : 0.12,
                weight: selected ? 3 : 2,
              }}
            >
              <Popup>
                <div className="text-xs space-y-1 min-w-[150px]">
                  <div className="text-sm font-semibold">{field.name}</div>
                  <div className="text-gray-500">{field.area_mu} 亩</div>
                  {field.current_crop && (
                    <div>
                      {field.current_crop}
                      {field.growth_stage ? ` · ${field.growth_stage}` : ""}
                    </div>
                  )}
                </div>
              </Popup>
            </Polygon>
          );
        })}

        {/* Farm markers */}
        {farms.map((farm) => {
          if (!farm.latitude || !farm.longitude) return null;
          const isSelected = farm.id === selectedFarmId;
          return (
            <Marker
              key={farm.id}
              position={[farm.latitude, farm.longitude]}
              icon={isSelected ? selectedIcon : farmIcon}
              eventHandlers={{
                click: () => onFarmClick?.(farm.id),
              }}
            >
              <Popup>
                <div className="text-sm">
                  <div className="font-semibold">{farm.name}</div>
                  <div className="text-gray-500 text-xs mt-0.5">
                    {farm.location} · {farm.area_mu} 亩
                  </div>
                </div>
              </Popup>
            </Marker>
          );
        })}

        {/* Trajectory points — small dots with popups */}
        {trajectoryPoints.length > 0 &&
          trajectoryPoints.map((pt, i) => {
            const isFirst = i === 0;
            const isLast = i === trajectoryPoints.length - 1;
            // 只显示起点、终点以及每第 3 个点，避免过密连成线
            if (!isFirst && !isLast && i % 3 !== 0) return null;

            const color = STATUS_COLORS[pt.work_status] || STATUS_COLORS.idle;

            return (
              <CircleMarker
                key={`pt-${i}`}
                center={[pt.latitude, pt.longitude]}
                radius={isFirst || isLast ? 6 : 3}
                pathOptions={{
                  color: isFirst ? "#16a34a" : isLast ? "#ef4444" : color,
                  fillColor: isFirst ? "#22c55e" : isLast ? "#f87171" : color,
                  fillOpacity: 0.9,
                  weight: isFirst || isLast ? 2 : 1,
                }}
              >
                <Popup>
                  <div className="text-xs space-y-1 min-w-[160px]">
                    <div className="font-semibold text-sm">
                      {isFirst ? "🟢 起点" : isLast ? "🔴 终点" : `📍 轨迹点 #${pt.seq}`}
                    </div>
                    <div className="grid grid-cols-2 gap-x-2 gap-y-1">
                      <span className="text-gray-500">经度</span>
                      <span className="font-mono">{pt.longitude.toFixed(6)}</span>
                      <span className="text-gray-500">纬度</span>
                      <span className="font-mono">{pt.latitude.toFixed(6)}</span>
                      <span className="text-gray-500">状态</span>
                      <span style={{ color }}>{STATUS_LABELS[pt.work_status] || pt.work_status}</span>
                      <span className="text-gray-500">速度</span>
                      <span>{pt.speed.toFixed(1)} km/h</span>
                      {pt.depth > 0 && (
                        <>
                          <span className="text-gray-500">深度</span>
                          <span>{pt.depth.toFixed(1)} cm</span>
                        </>
                      )}
                      {pt.gps_time && (
                        <>
                          <span className="text-gray-500">时间</span>
                          <span>{formatTime(pt.gps_time)}</span>
                        </>
                      )}
                    </div>
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
      </MapContainer>
    </div>
  );
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  } catch {
    return iso;
  }
}
