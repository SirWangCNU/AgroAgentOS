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
  planting_date?: string | null;
  expected_harvest?: string | null;
  growth_stage: string;
  status: "idle" | "planting" | "fallow";
  latitude?: number | null;
  longitude?: number | null;
  notes: string;
  boundary_json?: string;
  current_season_id?: number | null;
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
  operation_type?: string;
  season_id?: number | null;
  related_task_id?: string | null;
  operator?: string;
  event_time?: string | null;
  coverage_rate?: number | null;
  quality_summary?: Record<string, unknown>;
}

export interface TrajectoryPoint {
  id?: number;
  seq: number;
  latitude: number;
  longitude: number;
  gps_time?: string;
  work_status: "working" | "idle" | "transporting";
  speed: number;
  depth: number;
  depth_std?: number;
}

export interface TrajectoryStats {
  total_points: number;
  work_duration_hours: number;
  work_distance_km: number;
  work_area_mu: number;
  avg_depth: number;
  depth_std: number;
  avg_speed: number;
  max_speed: number;
  compliance_rate: number;
  depth_compliance: number;
  speed_compliance: number;
}

export interface TrajectoryAnalysis {
  work_volume: Record<string, unknown>;
  work_efficiency: Record<string, unknown>;
  work_volume_chart: string;
  work_efficiency_chart: string;
}

export interface TrajectoryUploadOptions {
  coordSystem?: string;
  operationType?: string;
  seasonId?: number | null;
  relatedTaskId?: string | null;
  operator?: string;
  eventTime?: string | null;
}
