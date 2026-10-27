import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiClient } from "../api/client";

describe("apiClient (P6-02)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchOverview queries /api/v1/overview with default parameters", async () => {
    const mockOverview = {
      target_month: "2026-01",
      cutoff_time: "12:00",
      timezone: "UTC",
      mae: 2020.64,
      rmse: 2481.38,
      bias: 1806.23,
      wape: 17.45,
      potential_shortfall_mwh: 1423598.0,
      total_actual_generation_mwh: 8156000.0,
      completeness_pct: 100.0,
      total_expected_intervals: 1488,
      total_matched_intervals: 1488,
      missing_actual_intervals: 0,
      missing_forecast_intervals: 0,
      data_status: "complete",
      cards: [],
      daily_trends: [],
      largest_errors: [],
    };

    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockOverview,
    } as Response);

    const result = await apiClient.fetchOverview("2026-01", "12:00");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const calledUrl = fetchSpy.mock.calls[0][0].toString();
    expect(calledUrl).toContain("/api/v1/overview");
    expect(calledUrl).toContain("month=2026-01");
    expect(calledUrl).toContain("cutoff=12%3A00");
    expect(result.mae).toBe(2020.64);
    expect(result.data_status).toBe("complete");
  });

  it("fetchTimeseries queries /api/v1/timeseries", async () => {
    const mockTimeseries = {
      target_month: "2026-01",
      cutoff_time: "12:00",
      total_points: 1488,
      matched_points: 1488,
      points: [
        {
          start_time: "2026-01-01T00:00:00Z",
          settlement_date: "2026-01-01",
          settlement_period: 1,
          actual_mw: 9500.0,
          forecast_mw: 11000.0,
          error_mw: 1500.0,
          shortfall_mwh: 750.0,
          forecast_publish_time: "2025-12-31T11:45:00Z",
          status: "matched",
        },
      ],
    };

    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockTimeseries,
    } as Response);

    const result = await apiClient.fetchTimeseries("2026-01", "12:00");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(result.points).toHaveLength(1);
    expect(result.points[0].status).toBe("matched");
  });

  it("fetchIntervals formats query parameters for pagination, status filter, and dates", async () => {
    const mockIntervals = {
      target_month: "2026-01",
      cutoff_time: "12:00",
      total: 48,
      page: 1,
      page_size: 48,
      total_pages: 1,
      items: [],
    };

    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockIntervals,
    } as Response);

    await apiClient.fetchIntervals({
      month: "2026-01",
      cutoff: "12:00",
      page: 2,
      pageSize: 24,
      startDate: "2026-01-10",
      endDate: "2026-01-15",
      status: "matched",
    });

    const calledUrl = fetchSpy.mock.calls[0][0].toString();
    expect(calledUrl).toContain("page=2");
    expect(calledUrl).toContain("page_size=24");
    expect(calledUrl).toContain("start_date=2026-01-10");
    expect(calledUrl).toContain("end_date=2026-01-15");
    expect(calledUrl).toContain("status_filter=matched");
  });

  it("throws formatted error message on non-200 HTTP response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 400,
      statusText: "Bad Request",
      json: async () => ({
        detail: "Unsupported analysis month '2025-12'. This pilot is strictly scoped to January 2026.",
      }),
    } as Response);

    await expect(apiClient.fetchOverview("2025-12", "12:00")).rejects.toThrow(
      "Unsupported analysis month '2025-12'"
    );
  });

  it("checkHealthLive returns backend live status", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok" }),
    } as Response);

    const res = await apiClient.checkHealthLive();
    expect(res.status).toBe("ok");
  });
});
