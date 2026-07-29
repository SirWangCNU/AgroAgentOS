import { useEffect, useRef } from "react";
import { LocateFixed, MapPin } from "lucide-react";
import {
  LayersControl,
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  useMap,
  useMapEvents,
} from "react-leaflet";
import L, { type LatLngLiteral } from "leaflet";
import "leaflet/dist/leaflet.css";
import { gcj02ToWgs84, wgs84ToGcj02 } from "../../lib/coordinates";

const defaultIcon = new L.Icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

const selectedIcon = new L.DivIcon({
  className: "",
  html: '<span style="display:block;width:32px;height:32px;border-radius:999px;background:#1d6b45;border:4px solid #e4f3e7;box-shadow:0 5px 14px rgba(29,107,69,.35)"></span>',
  iconSize: [32, 32],
  iconAnchor: [16, 16],
});

function toMapCoordinate(position: LatLngLiteral): LatLngLiteral {
  return wgs84ToGcj02(position);
}

function toStoredCoordinate(position: LatLngLiteral): LatLngLiteral {
  return gcj02ToWgs84(position);
}

export interface FarmMapMarker {
  id: number;
  name: string;
  location: string;
  area_mu: number;
  latitude: number | null;
  longitude: number | null;
}

interface FarmMapProps {
  farms: FarmMapMarker[];
  selectedFarmId: number | null;
  isEditing: boolean;
  draftPosition: LatLngLiteral | null;
  onFarmClick: (farmId: number) => void;
  onDraftPositionChange: (position: LatLngLiteral) => void;
}

function FlyToFarm({ farm }: { farm: FarmMapMarker | undefined }) {
  const map = useMap();
  const previousFarmId = useRef<number | null>(null);

  useEffect(() => {
    if (
      farm &&
      farm.latitude !== null &&
      farm.longitude !== null &&
      farm.id !== previousFarmId.current
    ) {
      const position = toMapCoordinate({ lat: farm.latitude, lng: farm.longitude });
      map.flyTo([position.lat, position.lng], 14, { duration: 0.65 });
      previousFarmId.current = farm.id;
    }
  }, [farm, map]);

  return null;
}

function DraftLocationHandler({
  enabled,
  onChange,
}: {
  enabled: boolean;
  onChange: (position: LatLngLiteral) => void;
}) {
  useMapEvents({
    click(event) {
      if (enabled) onChange(toStoredCoordinate(event.latlng));
    },
  });
  return null;
}

export default function FarmMap({
  farms,
  selectedFarmId,
  isEditing,
  draftPosition,
  onFarmClick,
  onDraftPositionChange,
}: FarmMapProps) {
  const selectedFarm = farms.find((farm) => farm.id === selectedFarmId);
  const selectedFarmPosition =
    selectedFarm?.latitude != null && selectedFarm?.longitude != null
      ? toMapCoordinate({ lat: selectedFarm.latitude, lng: selectedFarm.longitude })
      : null;
  const center: [number, number] = selectedFarmPosition
    ? [selectedFarmPosition.lat, selectedFarmPosition.lng]
    : [35.86, 104.19];
  const mapDraftPosition = draftPosition ? toMapCoordinate(draftPosition) : null;

  return (
    <div className="relative h-full min-h-[560px] overflow-hidden rounded-2xl border border-emerald-900/10 bg-[#eaf1e7] shadow-[0_18px_50px_rgba(41,71,48,0.12)] map-isolation">
      <MapContainer
        center={center}
        zoom={selectedFarm?.latitude != null ? 14 : 4}
        maxZoom={18}
        className="h-full w-full"
        scrollWheelZoom
      >
        <LayersControl position="topright">
          <LayersControl.BaseLayer checked name="高德地图">
            <TileLayer
              attribution="&copy; 高德地图"
              url="https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}"
              subdomains={["1", "2", "3", "4"]}
              maxZoom={18}
            />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="高德卫星">
            <TileLayer
              attribution="&copy; 高德地图"
              url="https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}"
              subdomains={["1", "2", "3", "4"]}
              maxZoom={18}
            />
          </LayersControl.BaseLayer>
        </LayersControl>

        <FlyToFarm farm={selectedFarm} />
        <DraftLocationHandler enabled={isEditing} onChange={onDraftPositionChange} />

        {farms.map((farm) => {
          if (farm.latitude === null || farm.longitude === null) return null;
          const selected = farm.id === selectedFarmId;
          return (
            <Marker
              key={farm.id}
              position={toMapCoordinate({ lat: farm.latitude, lng: farm.longitude })}
              icon={selected ? selectedIcon : defaultIcon}
              eventHandlers={{ click: () => onFarmClick(farm.id) }}
            >
              <Popup>
                <div className="min-w-40 text-sm text-slate-800">
                  <div className="font-semibold">{farm.name}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    {farm.location || "位置待补充"} · {farm.area_mu} 亩
                  </div>
                </div>
              </Popup>
            </Marker>
          );
        })}

        {isEditing && mapDraftPosition && (
          <Marker
            position={mapDraftPosition}
            icon={selectedIcon}
            draggable
            eventHandlers={{
              dragend: (event) => onDraftPositionChange(toStoredCoordinate(event.target.getLatLng())),
            }}
          >
            <Popup>拖动标记或点击地图，确定农场位置</Popup>
          </Marker>
        )}
      </MapContainer>

      <div className="pointer-events-none absolute left-4 top-4 z-[500] max-w-[250px] rounded-xl border border-white/70 bg-white/90 px-3 py-2.5 shadow-sm backdrop-blur">
        <div className="flex items-center gap-2 text-sm font-semibold text-emerald-950">
          <MapPin className="h-4 w-4 text-emerald-700" />
          {isEditing ? "正在调整农场位置" : "农场位置总览"}
        </div>
        <p className="mt-1 text-xs leading-5 text-slate-600">
          {isEditing ? "点击地图或拖动圆点，确认后再保存。" : "点击标记即可切换当前农场。"}
        </p>
      </div>

      {isEditing && (
        <div className="pointer-events-none absolute bottom-4 left-4 z-[500] flex items-center gap-2 rounded-lg bg-emerald-950 px-3 py-2 text-xs text-white shadow-lg">
          <LocateFixed className="h-3.5 w-3.5" />
          位置尚未保存
        </div>
      )}
    </div>
  );
}
