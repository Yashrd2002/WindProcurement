import React from "react";
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AiCopilotBriefing } from "../components/AiCopilotBriefing";
import { apiClient, AiBriefingResponse } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: {
    fetchAiBriefing: vi.fn(),
  },
}));

describe("AiCopilotBriefing Component", () => {
  const mockBriefing: AiBriefingResponse = {
    executive_summary: "Severe systematic overforecasting during January 2026.",
    hedging_recommendation: {
      recommended_thermal_buffer_mw: 1806.2,
      strategy_rationale: "Size day-ahead CCGT buffer at +1,806 MW to neutralize overforecast bias.",
      risk_level: "Elevated",
      unhedged_shortfall_mwh: 1423598.0,
    },
    peak_exposure_alerts: [
      {
        interval_id: "2026-01-12-SP03",
        settlement_date: "2026-01-12",
        settlement_period: 3,
        forecast_mw: 14200.0,
        actual_mw: 7315.0,
        error_mw: 6885.0,
        shortfall_mwh: 3442.5,
        risk_category: "Storm Cut-Out Ramp",
        mitigation_action: "Trigger Fast Reserve",
      },
    ],
    operational_checklist: [
      "1. Submit day-ahead thermal purchase bids with a +1,806 MW hedge buffer.",
      "2. Flag settlement periods with forecasted wind >14,000 MW.",
      "3. Monitor SBP cashout prices.",
    ],
    market_context: "UK wholesale day-ahead 12:00 D-1 auction gate closure context.",
    ai_provider: "openai",
    model_used: "gpt-4o-mini",
    timestamp_utc: "2026-10-26T12:00:00Z",
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders AI Copilot header and provider badge upon loading data", async () => {
    vi.mocked(apiClient.fetchAiBriefing).mockResolvedValueOnce(mockBriefing);

    render(<AiCopilotBriefing month="2026-01" cutoff="12:00" />);

    expect(screen.getByText("AI Trading Desk Copilot")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("⚡ OpenAI gpt-4o-mini")).toBeInTheDocument();
      expect(screen.getByText("+1,806.2 MW")).toBeInTheDocument();
      expect(screen.getByText("Severe systematic overforecasting during January 2026.")).toBeInTheDocument();
      expect(screen.getByText("Exposure: Elevated")).toBeInTheDocument();
      expect(screen.getByText("2026-01-12 SP3")).toBeInTheDocument();
    });
  });

  it("allows switching risk tolerance to conservative and triggers fetch", async () => {
    vi.mocked(apiClient.fetchAiBriefing).mockResolvedValue(mockBriefing);

    render(<AiCopilotBriefing month="2026-01" cutoff="12:00" />);

    await waitFor(() => {
      expect(screen.getByText("+1,806.2 MW")).toBeInTheDocument();
    });

    const consButton = screen.getByRole("button", { name: /conservative/i });
    fireEvent.click(consButton);

    await waitFor(() => {
      expect(apiClient.fetchAiBriefing).toHaveBeenCalledWith(
        expect.objectContaining({
          risk_tolerance: "conservative",
        })
      );
    });
  });
});
