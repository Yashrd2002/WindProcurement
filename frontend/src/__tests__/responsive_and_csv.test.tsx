import React from "react";
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { IntervalsTable } from "../components/IntervalsTable";
import { FilterControls } from "../components/FilterControls";
import { IntervalItem } from "../api/client";

describe("Responsive and CSV Behavior (P7-05)", () => {
  describe("CSV Export Functionality", () => {
    const mockItems: IntervalItem[] = [
      {
        interval_id: "2026-01-01-01",
        start_time: "2026-01-01T00:00:00Z",
        settlement_date: "2026-01-01",
        settlement_period: 1,
        actual_mw: 9240.5,
        forecast_mw: 11050.0,
        error_mw: 1809.5,
        shortfall_mwh: 904.75,
        forecast_publish_time: "2025-12-31T11:45:00Z",
        cutoff_time_applied: "2025-12-31T12:00:00Z",
        status: "matched",
      },
      {
        interval_id: "2026-01-01-02",
        start_time: "2026-01-01T00:30:00Z",
        settlement_date: "2026-01-01",
        settlement_period: 2,
        actual_mw: null,
        forecast_mw: null,
        error_mw: null,
        shortfall_mwh: null,
        forecast_publish_time: null,
        cutoff_time_applied: "2025-12-31T12:00:00Z",
        status: "missing_both",
      },
    ];

    it("triggers CSV download with proper URI encoding and formatted filename", () => {
      // Spy on document.createElement and click
      const clickSpy = vi.fn();
      let createdLink: HTMLAnchorElement | null = null;

      const originalCreateElement = document.createElement.bind(document);
      vi.spyOn(document, "createElement").mockImplementation((tagName: string) => {
        const el = originalCreateElement(tagName);
        if (tagName.toLowerCase() === "a") {
          createdLink = el as HTMLAnchorElement;
          createdLink.click = clickSpy;
        }
        return el;
      });

      render(
        <IntervalsTable
          items={mockItems}
          total={2}
          page={1}
          pageSize={48}
          totalPages={1}
          onPageChange={vi.fn()}
          onPageSizeChange={vi.fn()}
          statusFilter=""
          onStatusFilterChange={vi.fn()}
          targetMonth="2026-01"
          cutoffTime="12:00"
          isLoading={false}
        />
      );

      const exportBtn = screen.getByText(/Export CSV/);
      fireEvent.click(exportBtn);

      expect(clickSpy).toHaveBeenCalledTimes(1);
      const targetLink = createdLink as HTMLAnchorElement | null;
      expect(targetLink).not.toBeNull();
      expect(targetLink?.getAttribute("download")).toBe(
        "wind_procurement_intervals_2026-01_cutoff_1200.csv"
      );

      const href = targetLink?.getAttribute("href") || "";
      expect(href).toContain("data:text/csv;charset=utf-8,");

      const decodedContent = decodeURI(href);
      // Check headers
      expect(decodedContent).toContain("Interval ID");
      expect(decodedContent).toContain("Delivery Start Time (UTC)");
      expect(decodedContent).toContain("Actual (MW)");
      expect(decodedContent).toContain("Shortfall Volume (MWh)");

      // Check row values
      expect(decodedContent).toContain("2026-01-01-01");
      expect(decodedContent).toContain("9240.5");
      expect(decodedContent).toContain("11050");
      expect(decodedContent).toContain("1809.5");
      expect(decodedContent).toContain("904.75");

      // Check null row handling (empty string, not 'null')
      expect(decodedContent).toContain("2026-01-01-02");
      expect(decodedContent).toContain("missing_both");
    });
  });

  describe("Filter Controls & Presets Coordination", () => {
    it("enforces January 2026 date bounds on HTML date inputs", () => {
      render(
        <FilterControls
          cutoffTime="12:00"
          onCutoffChange={vi.fn()}
          startDate="2026-01-01"
          endDate="2026-01-31"
          onDateRangeChange={vi.fn()}
          onRefresh={vi.fn()}
          isLoading={false}
        />
      );

      const startInput = screen.getByLabelText("Start Date") as HTMLInputElement;
      const endInput = screen.getByLabelText("End Date") as HTMLInputElement;

      expect(startInput.min).toBe("2026-01-01");
      expect(startInput.max).toBe("2026-01-31");
      expect(endInput.max).toBe("2026-01-31");
    });

    it("highlights active preset button", () => {
      const { rerender } = render(
        <FilterControls
          cutoffTime="12:00"
          onCutoffChange={vi.fn()}
          startDate="2026-01-01"
          endDate="2026-01-31"
          onDateRangeChange={vi.fn()}
          onRefresh={vi.fn()}
          isLoading={false}
        />
      );

      const fullMonthBtn = screen.getByText("Full Month");
      expect(fullMonthBtn.className).toContain("active");

      // Change to Peak Storm Miss (Jan 10-15)
      rerender(
        <FilterControls
          cutoffTime="12:00"
          onCutoffChange={vi.fn()}
          startDate="2026-01-10"
          endDate="2026-01-15"
          onDateRangeChange={vi.fn()}
          onRefresh={vi.fn()}
          isLoading={false}
        />
      );

      const stormBtn = screen.getByText("⚡ Peak Storm Miss (Jan 10-15)");
      expect(stormBtn.className).toContain("active");
      expect(screen.getByText("Full Month").className).not.toContain("active");
    });
  });
});
