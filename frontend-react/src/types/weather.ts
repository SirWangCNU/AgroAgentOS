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
