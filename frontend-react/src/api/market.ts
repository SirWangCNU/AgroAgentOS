import { authFetch } from "./client";
import type { ApiResponse } from "../types/api";
import type {
  MarketAnalysisData,
  MarketOverview,
  MarketPriceData,
  PolicyData,
  SupplyDemandData,
} from "../types/market";

export async function getMarketPrice(
  crop: string = "水稻",
  location: string = ""
): Promise<MarketPriceData> {
  const params = new URLSearchParams({ crop });
  if (location) params.set("location", location);
  const resp = await authFetch<ApiResponse<MarketPriceData>>(
    `/market/price?${params.toString()}`
  );
  return resp.data;
}

export async function getSupplyDemand(
  crop: string = "水稻"
): Promise<SupplyDemandData> {
  const resp = await authFetch<ApiResponse<SupplyDemandData>>(
    `/market/supply-demand?crop=${encodeURIComponent(crop)}`
  );
  return resp.data;
}

export async function getPolicySubsidies(
  location: string = ""
): Promise<PolicyData> {
  const params = new URLSearchParams();
  if (location) params.set("location", location);
  const resp = await authFetch<ApiResponse<PolicyData>>(
    `/market/policy?${params.toString()}`
  );
  return resp.data;
}

export async function getMarketAnalysis(
  crop: string = "水稻",
  location: string = ""
): Promise<MarketAnalysisData> {
  const params = new URLSearchParams({ crop });
  if (location) params.set("location", location);
  const resp = await authFetch<ApiResponse<MarketAnalysisData>>(
    `/market/analysis?${params.toString()}`
  );
  return resp.data;
}

export async function getMarketOverview(
  crop: string = "水稻",
  location: string = ""
): Promise<MarketOverview> {
  const params = new URLSearchParams({ crop });
  if (location) params.set("location", location);
  const resp = await authFetch<ApiResponse<MarketOverview>>(
    `/market/overview?${params.toString()}`
  );
  return resp.data;
}
