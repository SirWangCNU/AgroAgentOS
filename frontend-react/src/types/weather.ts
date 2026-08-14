export interface FarmWeatherCurrent {
  condition: string;
  temperature: number;
  humidity: number;
  wind_speed: number;
  wind_level: number;
  update_time: string;
}

export interface FarmWeatherAlert {
  alert_type: string;
  date: string;
  severity: string;
}

export interface FarmWeatherDaily {
  date: string;
  min_temp: number;
  max_temp: number;
  precipitation_mm: number;
  condition: string;
  wind_level: number;
}

export interface FarmWeatherSummary {
  available: boolean;
  reason:
    | "FARM_LOCATION_REQUIRED"
    | "FIELD_BOUNDARY_REQUIRED"
    | "WEATHER_SERVICE_UNAVAILABLE"
    | null;
  current: FarmWeatherCurrent | null;
  daily: FarmWeatherDaily[];
  alerts: FarmWeatherAlert[];
  source: string | null;
}
