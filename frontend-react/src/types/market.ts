// 市场行情相关类型定义

export interface MarketPriceItem {
  crop: string;
  market: string;
  price: number;
  price_unit: string;
  change: number;
  change_percent: number;
  date: string;
}

export interface MarketPriceData {
  crop: string;
  location: string;
  items: MarketPriceItem[];
  average_price: number;
  trend: string; // up / down / stable
  source: string;
  update_time: string;
}

export interface SupplyDemandData {
  crop: string;
  production: number;
  consumption: number;
  import_volume: number;
  export_volume: number;
  stock: number;
  supply_demand_ratio: number;
  analysis: string;
  source: string;
}

export interface PolicySubsidy {
  title: string;
  category: string;
  subsidy_amount: string;
  target: string;
  conditions: string;
  deadline: string;
  region: string;
  source_url: string;
}

export interface PolicyData {
  location: string;
  policies: PolicySubsidy[];
  source: string;
  update_time: string;
}

export interface MarketAnalysisData {
  crop: string;
  location: string;
  price_summary: string;
  trend_forecast: string;
  supply_demand_summary: string;
  policy_summary: string;
  sales_advice: string;
  risk_warning: string;
  source: string;
}

export interface MarketOverview {
  crop: string;
  location: string;
  price: MarketPriceData | null;
  supply_demand: SupplyDemandData | null;
  policy: PolicyData | null;
  analysis: MarketAnalysisData | null;
}
