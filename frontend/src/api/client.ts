/**
 * Typed API Client for Wind Procurement Intelligence Platform (P6-02)
 * Connects React frontend exclusively to backend API routes.
 */

export interface MetricCard {
  key: string;
  label: string;
  value: number | null;
  unit: string;
  formatted: string;
  description: string;
  sample_count: number;
  interpretation?: string | null;
}

export interface DailyTrendItem {
  date: string;
  matched_intervals: number;
  expected_intervals: number;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  wape: number | null;
  shortfall_mwh: number;
  actual_generation_mwh: number;
  forecast_generation_mwh: number;
}

export interface LargestErrorInterval {
  interval_id: string;
  start_time: string;
  settlement_date: string;
  settlement_period: number;
  actual_mw: number;
  forecast_mw: number;
  error_mw: number;
  abs_error_mw: number;
  shortfall_mwh: number;
  direction: "overforecast" | "underforecast";
}

export interface OverviewResponse {
  target_month: string;
  cutoff_time: string;
  timezone: string;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  wape: number | null;
  potential_shortfall_mwh: number | null;
  total_actual_generation_mwh: number | null;
  completeness_pct: number;
  total_expected_intervals: number;
  total_matched_intervals: number;
  missing_actual_intervals: number;
  missing_forecast_intervals: number;
  data_status: "complete" | "partial" | "stale" | "empty" | "degraded";
  cards: MetricCard[];
  daily_trends: DailyTrendItem[];
  largest_errors: LargestErrorInterval[];
}

export interface TimeseriesPoint {
  start_time: string;
  settlement_date: string;
  settlement_period: number;
  actual_mw: number | null;
  forecast_mw: number | null;
  error_mw: number | null;
  shortfall_mwh: number | null;
  forecast_publish_time: string | null;
  status: "matched" | "missing_forecast" | "missing_actual" | "missing_both";
}

export interface TimeseriesResponse {
  target_month: string;
  cutoff_time: string;
  total_points: number;
  matched_points: number;
  points: TimeseriesPoint[];
}

export interface IntervalItem {
  interval_id: string;
  start_time: string;
  settlement_date: string;
  settlement_period: number;
  actual_mw: number | null;
  forecast_mw: number | null;
  error_mw: number | null;
  shortfall_mwh: number | null;
  forecast_publish_time: string | null;
  cutoff_time_applied: string;
  status: "matched" | "missing_forecast" | "missing_actual" | "missing_both";
}

export interface IntervalsResponse {
  target_month: string;
  cutoff_time: string;
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  items: IntervalItem[];
}

export interface QualityAuditItem {
  category: string;
  status: "pass" | "warning" | "fail";
  metric: string;
  detail: string;
}

export interface QualityReportResponse {
  target_month: string;
  cutoff_time: string;
  overall_status: "complete" | "partial" | "degraded" | "stale" | "empty";
  completeness_pct: number;
  expected_intervals: number;
  actual_intervals_found: number;
  forecast_intervals_found: number;
  matched_intervals: number;
  missing_actual_count: number;
  missing_forecast_count: number;
  missing_actual_intervals: string[];
  missing_forecast_intervals: string[];
  audits: QualityAuditItem[];
  notes: string[];
}

export interface HedgingRecommendation {
  recommended_thermal_buffer_mw: number;
  strategy_rationale: string;
  risk_level: string;
  unhedged_shortfall_mwh: number;
}

export interface PeakExposureAlert {
  interval_id: string;
  settlement_date: string;
  settlement_period: number;
  forecast_mw: number;
  actual_mw: number;
  error_mw: number;
  shortfall_mwh: number;
  risk_category: string;
  mitigation_action: string;
}

export interface AiBriefingResponse {
  executive_summary: string;
  hedging_recommendation: HedgingRecommendation;
  peak_exposure_alerts: PeakExposureAlert[];
  operational_checklist: string[];
  market_context: string;
  ai_provider: string;
  model_used?: string | null;
  timestamp_utc: string;
}

export interface AiBriefingRequest {
  month?: string;
  cutoff?: string;
  risk_tolerance?: "conservative" | "balanced" | "aggressive";
  api_key?: string;
  custom_query?: string;
}

const getBaseUrl = (): string => {
  return import.meta.env.VITE_API_BASE_URL || "";
};

async function request<T>(
  endpoint: string,
  queryParams: Record<string, string | number | undefined> = {},
  options: RequestInit = {}
): Promise<T> {
  const url = new URL(`${getBaseUrl()}${endpoint}`, window.location.origin);
  Object.entries(queryParams).forEach(([key, val]) => {
    if (val !== undefined && val !== null && val !== "") {
      url.searchParams.set(key, String(val));
    }
  });

  const response = await fetch(url.toString(), {
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status} ${response.statusText}`;
    try {
      const errJson = await response.json();
      if (errJson && errJson.detail) {
        errorDetail = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // Keep fallback error string
    }
    throw new Error(errorDetail);
  }

  return response.json() as Promise<T>;
}

export const apiClient = {
  fetchOverview: (month: string = "2026-01", cutoff: string = "12:00"): Promise<OverviewResponse> => {
    return request<OverviewResponse>("/api/v1/overview", { month, cutoff });
  },

  fetchTimeseries: (month: string = "2026-01", cutoff: string = "12:00"): Promise<TimeseriesResponse> => {
    return request<TimeseriesResponse>("/api/v1/timeseries", { month, cutoff });
  },

  fetchIntervals: (params: {
    month?: string;
    cutoff?: string;
    page?: number;
    pageSize?: number;
    startDate?: string;
    endDate?: string;
    status?: string;
  }): Promise<IntervalsResponse> => {
    return request<IntervalsResponse>("/api/v1/intervals", {
      month: params.month || "2026-01",
      cutoff: params.cutoff || "12:00",
      page: params.page || 1,
      page_size: params.pageSize || 48,
      start_date: params.startDate,
      end_date: params.endDate,
      status_filter: params.status,
    });
  },

  fetchQualityReport: (month: string = "2026-01", cutoff: string = "12:00"): Promise<QualityReportResponse> => {
    return request<QualityReportResponse>("/api/v1/quality", { month, cutoff });
  },

  checkHealthLive: (): Promise<{ status: string }> => {
    return request<{ status: string }>("/health/live");
  },

  fetchAiBriefing: (body: AiBriefingRequest = {}): Promise<AiBriefingResponse> => {
    return request<AiBriefingResponse>("/api/v1/ai/briefing", {}, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        month: body.month || "2026-01",
        cutoff: body.cutoff || "12:00",
        risk_tolerance: body.risk_tolerance || "balanced",
        api_key: body.api_key || undefined,
        custom_query: body.custom_query || undefined,
      }),
    });
  },
};
