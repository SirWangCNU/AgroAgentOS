export interface Farm {
  id: number;
  name: string;
  location: string;
  latitude: number;
  longitude: number;
  area_mu: number;
  description: string;
  fields?: Field[];
}

export interface Field {
  id: number;
  farm_id: number;
  name: string;
  area_mu: number;
  soil_type: string;
  current_crop: string;
  planting_date: string;
  expected_harvest: string;
  growth_stage: string;
  status: "idle" | "planting" | "fallow";
  notes: string;
}

export interface TrajectoryFile {
  id: number;
  field_id: number;
  filename: string;
  machine_id: string;
  point_count: number;
  start_time: string;
  end_time: string;
  total_distance_m: number;
  work_distance_m: number;
  work_area_mu: number;
  avg_depth: number;
  avg_speed: number;
}

export interface TrajectoryPoint {
  seq: number;
  latitude: number;
  longitude: number;
  work_status: number;
  speed: number;
  depth: number;
}
