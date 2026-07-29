export type FieldStatus = "idle" | "planting" | "fallow";

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
  current_crop: string;
  status: FieldStatus;
  notes: string;
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
  area_mu: number;
  current_crop: string;
  status: FieldStatus;
  notes: string;
}
