export type FieldStatus = "idle" | "planting" | "fallow";

export interface GeoJSONPolygon {
  type: "Polygon";
  coordinates: number[][][];
}

export interface Farm {
  id: number;
  name: string;
  location: string;
  latitude: number | null;
  longitude: number | null;
  area_mu: number;
  description: string;
  field_count?: number;
  fields?: Field[];
}

export interface Field {
  id: number;
  farm_id: number;
  name: string;
  area_mu: number;
  soil_type: string;
  current_crop: string;
  planting_date: string | null;
  expected_harvest: string | null;
  growth_stage: string;
  status: FieldStatus;
  latitude: number | null;
  longitude: number | null;
  notes: string;
  boundary: GeoJSONPolygon | null;
}

export interface FarmInput {
  name: string;
  location: string;
  latitude: number | null;
  longitude: number | null;
  area_mu: number;
  description: string;
}

export interface FieldInput {
  name: string;
  area_mu?: number;
  soil_type?: string;
  current_crop: string;
  planting_date?: string | null;
  expected_harvest?: string | null;
  growth_stage?: string;
  status: FieldStatus;
  notes: string;
  boundary?: GeoJSONPolygon | null;
}
