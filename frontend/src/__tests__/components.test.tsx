import React from "react";
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Header } from "../components/Header";
import { KpiOverview } from "../components/KpiOverview";
import { ForecastChart } from "../components/ForecastChart";
import { ErrorAnalysisView } from "../components/ErrorAnalysisView";
import { FilterControls } from "../components/FilterControls";
import { IntervalsTable } from "../components/IntervalsTable";
import { QualityAuditSection } from "../components/QualityAuditSection";
import { MetricCard, DailyTrendItem, LargestErrorInterval, IntervalItem, QualityReportResponse } from "../api/client";

describe("Frontend Dashboard Components (Phase 6)", () => {
  describe("Header Component (P6-01)", () => {
    it("renders branding title and operational badges", () => {
      render(
        <Header apiStatus="connected" targetMonth="2026-01" cutoffTime="12:00" />
      );

      expect(screen.getByText("Wind Procurement Intelligence")).toBeInTheDocument();
      expect(screen.getByText("2026-01")).toBeInTheDocument();
      expect(screen.getByText("12:00 D-1 (UK)")).toBeInTheDocument();
      expect(screen.getByText("Live Stream")).toBeInTheDocument();
    });
  });

  describe("KpiOverview Component (P6-03)", () => {
    const mockCards: MetricCard[] = [
      {
        key: "mae",
        label: "Mean Absolute Error (MAE)",
        value: 2020.64,
        unit: "MW",
        formatted: "2,020.6 MW",
        description: "Mean magnitude of interval forecast errors.",
        sample_count: 1488,
        interpretation: "Average procurement uncertainty per half-hour.",
      },
      {
        key: "bias",
        label: "Systematic Forecast Bias",
        value: 1806.23,
        unit: "MW",
        formatted: "+1,806.2 MW",
        description: "Mean signed error (Forecast - Actual).",
        sample_count: 1488,
        interpretation: "Persistent day-ahead overforecast pattern.",
      },
      {
        key: "shortfall",
        label: "Potential Shortfall Volume",
        value: 1423598.0,
        unit: "MWh",
        formatted: "1,423,598.0 MWh",
        description: "Cumulative energy deficit from overforecasts.",
        sample_count: 1488,
      },
      {
        key: "completeness",
        label: "Data Completeness",
        value: 100.0,
        unit: "%",
        formatted: "100.0% Complete",
        description: "1,488 of 1,488 expected periods matched.",
        sample_count: 1488,
      },
    ];

    it("renders all metric cards with proper values and tags", () => {
      render(
        <KpiOverview
          cards={mockCards}
          dataStatus="complete"
          completenessPct={100.0}
          totalMatched={1488}
          totalExpected={1488}
          isLoading={false}
        />
      );

      expect(screen.getByText("Mean Absolute Error (MAE)")).toBeInTheDocument();
      expect(screen.getByText("2,020.6 MW")).toBeInTheDocument();
      expect(screen.getByText("+1,806.2 MW")).toBeInTheDocument();
      expect(screen.getByText("1,423,598.0 MWh")).toBeInTheDocument();
      expect(screen.getByText("OVERFORECAST (F > A)")).toBeInTheDocument();
      expect(screen.getByText("PHYSICAL MWh")).toBeInTheDocument();
      expect(screen.getByText("COMPLETE (100%)")).toBeInTheDocument();
    });

    it("renders skeleton placeholders when loading", () => {
      const { container } = render(
        <KpiOverview
          cards={[]}
          dataStatus="complete"
          completenessPct={100.0}
          totalMatched={1488}
          totalExpected={1488}
          isLoading={true}
        />
      );

      const skeletons = container.querySelectorAll(".skeleton");
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  describe("ForecastChart Component (P6-04)", () => {
    const mockPoints = [
      {
        start_time: "2026-01-01T00:00:00Z",
        settlement_date: "2026-01-01",
        settlement_period: 1,
        actual_mw: 8000,
        forecast_mw: 10000,
        error_mw: 2000,
        shortfall_mwh: 1000,
        forecast_publish_time: "2025-12-31T11:45:00Z",
        status: "matched" as const,
      },
      {
        start_time: "2026-01-01T00:30:00Z",
        settlement_date: "2026-01-01",
        settlement_period: 2,
        actual_mw: 8500,
        forecast_mw: 9500,
        error_mw: 1000,
        shortfall_mwh: 500,
        forecast_publish_time: "2025-12-31T11:45:00Z",
        status: "matched" as const,
      },
    ];

    it("renders chart SVG and legend toggles", () => {
      render(
        <ForecastChart
          points={mockPoints}
          startDate="2026-01-01"
          endDate="2026-01-31"
          cutoffTime="12:00"
          isLoading={false}
        />
      );

      expect(screen.getByText("Day-Ahead Forecast vs Realized Generation")).toBeInTheDocument();
      expect(screen.getByText("Forecast (MW)")).toBeInTheDocument();
      expect(screen.getByText("Actual Realized (MW)")).toBeInTheDocument();
      expect(screen.getByText("Overforecast Shortfall (MWh)")).toBeInTheDocument();
    });

    it("renders empty state message when points array is empty", () => {
      render(
        <ForecastChart
          points={[]}
          startDate="2026-01-01"
          endDate="2026-01-02"
          cutoffTime="12:00"
          isLoading={false}
        />
      );

      expect(screen.getByText("No settlement intervals found")).toBeInTheDocument();
    });
  });

  describe("ErrorAnalysisView Component (P6-05)", () => {
    const mockTrends: DailyTrendItem[] = [
      {
        date: "2026-01-01",
        matched_intervals: 48,
        expected_intervals: 48,
        mae: 1500.0,
        rmse: 1800.0,
        bias: 1200.0,
        wape: 15.0,
        shortfall_mwh: 28800.0,
        actual_generation_mwh: 200000.0,
        forecast_generation_mwh: 228800.0,
      },
    ];

    const mockErrors: LargestErrorInterval[] = [
      {
        interval_id: "2026-01-12-03",
        start_time: "2026-01-12T01:00:00Z",
        settlement_date: "2026-01-12",
        settlement_period: 3,
        actual_mw: 2000.0,
        forecast_mw: 8885.0,
        error_mw: 6885.0,
        abs_error_mw: 6885.0,
        shortfall_mwh: 3442.5,
        direction: "overforecast",
      },
    ];

    it("renders daily trends bar chart and top 5 risk table", () => {
      const handleSelectDate = vi.fn();
      render(
        <ErrorAnalysisView
          dailyTrends={mockTrends}
          largestErrors={mockErrors}
          onSelectDate={handleSelectDate}
          isLoading={false}
        />
      );

      expect(screen.getByText("Daily Forecast Error Trends")).toBeInTheDocument();
      expect(screen.getByText("Peak Operational Risk Periods")).toBeInTheDocument();
      expect(screen.getByText("2026-01-12")).toBeInTheDocument();
      expect(screen.getByText("+6,885 MW")).toBeInTheDocument();
      expect(screen.getByText("3,442.5 MWh")).toBeInTheDocument();

      // Click daily bar
      const bar = screen.getByTitle(/2026-01-01/);
      fireEvent.click(bar);
      expect(handleSelectDate).toHaveBeenCalledWith("2026-01-01");
    });
  });

  describe("FilterControls Component (P6-06)", () => {
    it("fires callbacks when cutoff time and presets change", () => {
      const handleCutoffChange = vi.fn();
      const handleDateRangeChange = vi.fn();
      const handleRefresh = vi.fn();

      render(
        <FilterControls
          cutoffTime="12:00"
          onCutoffChange={handleCutoffChange}
          startDate="2026-01-01"
          endDate="2026-01-31"
          onDateRangeChange={handleDateRangeChange}
          onRefresh={handleRefresh}
          isLoading={false}
        />
      );

      // Change cutoff
      const select = screen.getByLabelText("Decision Cutoff (Day D-1)");
      fireEvent.change(select, { target: { value: "09:30" } });
      expect(handleCutoffChange).toHaveBeenCalledWith("09:30");

      // Click preset pill
      const peakStormBtn = screen.getByText("⚡ Peak Storm Miss (Jan 10-15)");
      fireEvent.click(peakStormBtn);
      expect(handleDateRangeChange).toHaveBeenCalledWith("2026-01-10", "2026-01-15");

      // Click refresh
      const refreshBtn = screen.getByText("↻ Recompute");
      fireEvent.click(refreshBtn);
      expect(handleRefresh).toHaveBeenCalled();
    });
  });

  describe("IntervalsTable Component (P6-07)", () => {
    const mockItems: IntervalItem[] = [
      {
        interval_id: "2026-01-01-01",
        start_time: "2026-01-01T00:00:00Z",
        settlement_date: "2026-01-01",
        settlement_period: 1,
        actual_mw: 9000,
        forecast_mw: 11000,
        error_mw: 2000,
        shortfall_mwh: 1000,
        forecast_publish_time: "2025-12-31T11:45:00Z",
        cutoff_time_applied: "2025-12-31T12:00:00Z",
        status: "matched",
      },
    ];

    it("renders tabular ledger and handles pagination / export clicks", () => {
      const handlePageChange = vi.fn();
      const handlePageSizeChange = vi.fn();
      const handleStatusFilterChange = vi.fn();

      render(
        <IntervalsTable
          items={mockItems}
          total={1488}
          page={1}
          pageSize={48}
          totalPages={31}
          onPageChange={handlePageChange}
          onPageSizeChange={handlePageSizeChange}
          statusFilter=""
          onStatusFilterChange={handleStatusFilterChange}
          targetMonth="2026-01"
          cutoffTime="12:00"
          isLoading={false}
        />
      );

      expect(screen.getByText("Settlement Period Intervals")).toBeInTheDocument();
      expect(screen.getByText("2026-01-01-01")).toBeInTheDocument();
      expect(screen.getByText("+2,000 MW")).toBeInTheDocument();
      expect(screen.getByText("1,000 MWh")).toBeInTheDocument();
      expect(screen.getByText("MATCHED")).toBeInTheDocument();

      // Pagination click
      const nextBtn = screen.getByText("Next ›");
      fireEvent.click(nextBtn);
      expect(handlePageChange).toHaveBeenCalledWith(2);

      // Status filter change
      const filterSelect = screen.getByLabelText("Status Filter");
      fireEvent.change(filterSelect, { target: { value: "matched" } });
      expect(handleStatusFilterChange).toHaveBeenCalledWith("matched");
    });
  });

  describe("QualityAuditSection Component (P6-08)", () => {
    const mockReport: QualityReportResponse = {
      target_month: "2026-01",
      cutoff_time: "12:00",
      overall_status: "complete",
      completeness_pct: 100.0,
      expected_intervals: 1488,
      actual_intervals_found: 1488,
      forecast_intervals_found: 1488,
      matched_intervals: 1488,
      missing_actual_count: 0,
      missing_forecast_count: 0,
      missing_actual_intervals: [],
      missing_forecast_intervals: [],
      audits: [
        {
          category: "Coverage",
          status: "pass",
          metric: "Settlement Period Coverage",
          detail: "1,488 / 1,488 half-hour settlement periods matched with zero omissions.",
        },
      ],
      notes: ["Audited against January 2026 calendar."],
    };

    it("renders regulatory audit metrics", () => {
      render(<QualityAuditSection report={mockReport} isLoading={false} />);
      expect(screen.getByText("Elexon Ingestion & Regulatory Audit")).toBeInTheDocument();
      expect(screen.getByText("Settlement Period Coverage")).toBeInTheDocument();
      expect(screen.getByText("PASS")).toBeInTheDocument();
    });
  });
});
