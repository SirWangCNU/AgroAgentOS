export interface WeatherCurrent {
  location: string;
  temperature: number;
  condition: string;
  humidity: number;
  wind_level: string;
  rain_probability: number;
  icon?: string;
}

export interface WeatherForecast {
  date: string;
  icon: string;
  temp_max: number;
  temp_min: number;
  rain_probability: number;
}

export interface WeatherData {
  current: WeatherCurrent;
  forecast: WeatherForecast[];
  agriculture_advice: string;
  source: string;
}

export interface WeatherLocationConfig {
  location_enabled: boolean;
  default_city: string;
  timeout_ms: number;
  high_accuracy: boolean;
}

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

export interface FarmWeatherSummary {
  available: boolean;
  reason: "FARM_LOCATION_REQUIRED" | "WEATHER_SERVICE_UNAVAILABLE" | null;
  current: FarmWeatherCurrent | null;
  alerts: FarmWeatherAlert[];
  source: string | null;
}
