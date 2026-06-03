import { useEffect, useRef } from "react";
import {
  MapContainer,
  TileLayer,
  LayersControl,
  Marker,
  Popup,
  Polyline,
  CircleMarker,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { TrajectoryPoint } from "../../types/farm";

// Fix Leaflet default marker icons in bundlers
delete (L.Icon.Default.prototype as any)._getIconUrl;
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
  selectedFarmId?: number | null;
  trajectoryPoints?: TrajectoryPoint[];
  onFarmClick?: (farmId: number) => void;
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
  selectedFarmId,
  trajectoryPoints = [],
  onFarmClick,
}: FarmMapProps) {
  const selectedFarm = farms.find((f) => f.id === selectedFarmId);

  const center: [number, number] = selectedFarm
    ? [selectedFarm.latitude, selectedFarm.longitude]
    : [35.86, 104.19];

  const zoom = selectedFarm ? 13 : 4;

  // Build trajectory segments by work_status
  const segments = buildSegments(trajectoryPoints);

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

        {/* Trajectory segments — colored by work_status */}
        {segments.map((seg, i) => (
          <Polyline
            key={`seg-${i}`}
            positions={seg.points}
            pathOptions={{
              color: seg.color,
              weight: 3,
              opacity: 0.85,
            }}
          />
        ))}

        {/* Trajectory points — small dots with popups */}
        {trajectoryPoints.length > 0 &&
          trajectoryPoints.map((pt, i) => {
            const isFirst = i === 0;
            const isLast = i === trajectoryPoints.length - 1;
            // Only show markers for first, last, and every Nth point
            if (!isFirst && !isLast && i % 5 !== 0) return null;

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

/** Build colored segments from trajectory points */
function buildSegments(points: TrajectoryPoint[]) {
  if (points.length < 2) return [];

  const segments: { points: [number, number][]; color: string }[] = [];
  let currentStatus = points[0].work_status;
  let currentPoints: [number, number][] = [
    [points[0].latitude, points[0].longitude],
  ];

  for (let i = 1; i < points.length; i++) {
    const pt = points[i];
    if (pt.work_status !== currentStatus) {
      // End current segment, start new one
      currentPoints.push([pt.latitude, pt.longitude]);
      segments.push({
        points: currentPoints,
        color: STATUS_COLORS[currentStatus] || STATUS_COLORS.idle,
      });
      currentStatus = pt.work_status;
      currentPoints = [[pt.latitude, pt.longitude]];
    } else {
      currentPoints.push([pt.latitude, pt.longitude]);
    }
  }

  // Push last segment
  if (currentPoints.length > 1) {
    segments.push({
      points: currentPoints,
      color: STATUS_COLORS[currentStatus] || STATUS_COLORS.idle,
    });
  }

  return segments;
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  } catch {
    return iso;
  }
}
