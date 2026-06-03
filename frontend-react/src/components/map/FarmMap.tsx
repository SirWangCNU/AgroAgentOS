import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

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
  className: "selected-marker",
});

interface FarmMarker {
  id: number;
  name: string;
  location: string;
  area_mu: number;
  latitude: number;
  longitude: number;
}

interface TrajectoryLine {
  points: [number, number][];
  color: string;
}

interface FarmMapProps {
  farms: FarmMarker[];
  selectedFarmId?: number | null;
  trajectories?: TrajectoryLine[];
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

export default function FarmMap({
  farms,
  selectedFarmId,
  trajectories = [],
  onFarmClick,
}: FarmMapProps) {
  const selectedFarm = farms.find((f) => f.id === selectedFarmId);

  // Default center: China
  const center: [number, number] = selectedFarm
    ? [selectedFarm.latitude, selectedFarm.longitude]
    : [35.86, 104.19];

  const zoom = selectedFarm ? 13 : 4;

  return (
    <div className="w-full h-full rounded-xl overflow-hidden border border-border">
      <MapContainer
        center={center}
        zoom={zoom}
        className="w-full h-full"
        scrollWheelZoom={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <FlyToFarm farm={selectedFarm} />

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

        {/* Trajectory lines */}
        {trajectories.map((traj, i) => (
          <Polyline
            key={i}
            positions={traj.points}
            pathOptions={{
              color: traj.color,
              weight: 3,
              opacity: 0.8,
            }}
          />
        ))}
      </MapContainer>
    </div>
  );
}
