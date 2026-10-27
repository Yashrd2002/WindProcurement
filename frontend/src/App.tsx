import React, { useState, useEffect, useCallback } from "react";
import {
  apiClient,
  OverviewResponse,
  TimeseriesResponse,
  IntervalsResponse,
  QualityReportResponse,
} from "./api/client";
import { Header } from "./components/Header";
import { FilterControls } from "./components/FilterControls";
import { KpiOverview } from "./components/KpiOverview";
import { ForecastChart } from "./components/ForecastChart";
import { ErrorAnalysisView } from "./components/ErrorAnalysisView";
import { IntervalsTable } from "./components/IntervalsTable";
import { QualityAuditSection } from "./components/QualityAuditSection";
import { AiCopilotBriefing } from "./components/AiCopilotBriefing";

export function App() {
  // Application Filter States (P6-06)
  const [cutoffTime, setCutoffTime] = useState<string>("12:00");
  const [startDate, setStartDate] = useState<string>("2026-01-01");
  const [endDate, setEndDate] = useState<string>("2026-01-31");
  const [targetMonth] = useState<string>("2026-01");

  // Pagination & Table Filter States (P6-07)
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(48);
  const [statusFilter, setStatusFilter] = useState<string>("");

  // Data Store
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [timeseries, setTimeseries] = useState<TimeseriesResponse | null>(null);
  const [intervals, setIntervals] = useState<IntervalsResponse | null>(null);
  const [quality, setQuality] = useState<QualityReportResponse | null>(null);

  // Status & Error Management (P6-08)
  const [apiHealth, setApiHealth] = useState<"connected" | "connecting" | "error">("connecting");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // 1. Fetch Overview, Timeseries, and Quality Report
  const loadGlobalAnalytics = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const [overviewData, timeseriesData, qualityData] = await Promise.all([
        apiClient.fetchOverview(targetMonth, cutoffTime),
        apiClient.fetchTimeseries(targetMonth, cutoffTime),
        apiClient.fetchQualityReport(targetMonth, cutoffTime),
      ]);

      setOverview(overviewData);
      setTimeseries(timeseriesData);
      setQuality(qualityData);
      setApiHealth("connected");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to connect to backend analytics API";
      setErrorMessage(msg);
      setApiHealth("error");
    } finally {
      setIsLoading(false);
    }
  }, [targetMonth, cutoffTime]);

  // 2. Fetch Paginated Intervals Table
  const loadIntervalsTable = useCallback(async () => {
    try {
      const intervalsData = await apiClient.fetchIntervals({
        month: targetMonth,
        cutoff: cutoffTime,
        page,
        pageSize,
        startDate,
        endDate,
        status: statusFilter,
      });
      setIntervals(intervalsData);
    } catch (err: unknown) {
      console.error("Failed to load intervals table:", err);
    }
  }, [targetMonth, cutoffTime, page, pageSize, startDate, endDate, statusFilter]);

  // Trigger global data load on cutoff change
  useEffect(() => {
    loadGlobalAnalytics();
  }, [loadGlobalAnalytics]);

  // Trigger intervals load when pagination, date range, or status filter changes
  useEffect(() => {
    loadIntervalsTable();
  }, [loadIntervalsTable]);

  // Date range change handler
  const handleDateRangeChange = (start: string, end: string) => {
    setStartDate(start);
    setEndDate(end);
    setPage(1); // Reset to page 1 on filter change
  };

  // Quick filter from daily trend click
  const handleSelectDay = (selectedDate: string) => {
    setStartDate(selectedDate);
    setEndDate(selectedDate);
    setPage(1);
  };

  return (
    <div className="app-container">
      {/* Header Banner */}
      <Header
        apiStatus={apiHealth}
        targetMonth={targetMonth}
        cutoffTime={cutoffTime}
      />

      {/* Global Error Banner (P6-08) */}
      {errorMessage && (
        <aside className="error-banner" role="alert">
          <div>
            <strong>⚠️ Analytics Service Communication Warning:</strong> {errorMessage}
          </div>
          <button
            type="button"
            className="action-btn"
            onClick={loadGlobalAnalytics}
            style={{ background: "#ffffff", color: "#e11d48", padding: "6px 14px" }}
          >
            Retry Connection
          </button>
        </aside>
      )}

      {/* Controls & Policy Filter Bar (P6-06) */}
      <FilterControls
        cutoffTime={cutoffTime}
        onCutoffChange={(newCutoff) => {
          setCutoffTime(newCutoff);
          setPage(1);
        }}
        startDate={startDate}
        endDate={endDate}
        onDateRangeChange={handleDateRangeChange}
        onRefresh={() => {
          loadGlobalAnalytics();
          loadIntervalsTable();
        }}
        isLoading={isLoading}
      />

      {/* KPI Cards Overview (P6-03) */}
      <KpiOverview
        cards={overview?.cards || []}
        dataStatus={overview?.data_status || "complete"}
        completenessPct={overview?.completeness_pct || 100.0}
        totalMatched={overview?.total_matched_intervals || 1488}
        totalExpected={overview?.total_expected_intervals || 1488}
        isLoading={isLoading}
      />

      {/* AI Trading Desk Copilot (Morning Briefing & Thermal Sizing) */}
      <AiCopilotBriefing
        month={targetMonth}
        cutoff={cutoffTime}
      />

      {/* Time Series Forecast vs Actual Chart (P6-04) */}
      <ForecastChart
        points={timeseries?.points || []}
        startDate={startDate}
        endDate={endDate}
        cutoffTime={cutoffTime}
        isLoading={isLoading}
      />

      {/* Accuracy & Operational Risk Views: Daily Trends & Top 5 Errors (P6-05) */}
      <ErrorAnalysisView
        dailyTrends={overview?.daily_trends || []}
        largestErrors={overview?.largest_errors || []}
        onSelectDate={handleSelectDay}
        isLoading={isLoading}
      />

      {/* Settlement Period Intervals Ledger with CSV Export (P6-07) */}
      <IntervalsTable
        items={intervals?.items || []}
        total={intervals?.total || 0}
        page={page}
        pageSize={pageSize}
        totalPages={intervals?.total_pages || 1}
        onPageChange={setPage}
        onPageSizeChange={(newSize) => {
          setPageSize(newSize);
          setPage(1);
        }}
        statusFilter={statusFilter}
        onStatusFilterChange={(newStatus) => {
          setStatusFilter(newStatus);
          setPage(1);
        }}
        targetMonth={targetMonth}
        cutoffTime={cutoffTime}
        isLoading={isLoading}
      />

      {/* Data Quality & Look-Ahead Audit Disclosure (P6-08 / P5-05) */}
      <QualityAuditSection
        report={quality}
        isLoading={isLoading}
      />
    </div>
  );
}
export default App;
