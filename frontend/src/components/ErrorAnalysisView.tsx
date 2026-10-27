import React, { useState } from "react";
import { DailyTrendItem, LargestErrorInterval } from "../api/client";

interface ErrorAnalysisViewProps {
  dailyTrends: DailyTrendItem[];
  largestErrors: LargestErrorInterval[];
  onSelectDate: (date: string) => void;
  isLoading: boolean;
}

export const ErrorAnalysisView: React.FC<ErrorAnalysisViewProps> = ({
  dailyTrends,
  largestErrors,
  onSelectDate,
  isLoading,
}) => {
  const [hoveredDay, setHoveredDay] = useState<DailyTrendItem | null>(null);

  // Maximum MAE across all days for scaling
  const maxMae = Math.max(1000, ...dailyTrends.map((d) => d.mae || 0));

  if (isLoading) {
    return (
      <div className="analytics-grid">
        <div className="analytics-card skeleton" style={{ height: "300px" }} />
        <div className="analytics-card skeleton" style={{ height: "300px" }} />
      </div>
    );
  }

  return (
    <div className="analytics-grid">
      {/* Pane 1: Daily Forecast Accuracy Trend */}
      <section className="analytics-card" aria-label="Daily accuracy trend">
        <div className="chart-header" style={{ marginBottom: "10px" }}>
          <div>
            <h3 className="section-title">Daily Forecast Error Trends</h3>
            <p className="section-subtitle">
              Daily MAE and systematic bias across all 31 days in January 2026.
            </p>
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
            Click bar to filter date
          </div>
        </div>

        <div className="daily-bars-container" role="figure" aria-label="Daily MAE bar chart">
          {dailyTrends.map((day) => {
            const heightPct = Math.min(100, Math.max(8, ((day.mae || 0) / maxMae) * 100));
            const isOver = (day.bias || 0) >= 0;

            return (
              <div
                key={day.date}
                className="daily-bar-column"
                onClick={() => onSelectDate(day.date)}
                onMouseEnter={() => setHoveredDay(day)}
                onMouseLeave={() => setHoveredDay(null)}
                title={`${day.date}: MAE ${day.mae?.toFixed(0)} MW, Bias ${day.bias && day.bias > 0 ? "+" : ""}${day.bias?.toFixed(0)} MW`}
              >
                <div
                  className={`daily-bar-fill ${isOver ? "bar-overforecast" : "bar-underforecast"}`}
                  style={{ height: `${heightPct}%` }}
                />
                <span className="daily-date-label">{day.date.slice(8)}</span>
              </div>
            );
          })}
        </div>

        {/* Hovered Day Details */}
        <div style={{ marginTop: "12px", minHeight: "36px", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
          {hoveredDay ? (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "16px", alignItems: "center" }}>
              <strong style={{ color: "#ffffff" }}>📅 {hoveredDay.date}:</strong>
              <span>MAE: <strong style={{ color: "var(--text-primary)" }}>{hoveredDay.mae?.toLocaleString()} MW</strong></span>
              <span>
                Bias: <strong style={{ color: (hoveredDay.bias || 0) > 0 ? "var(--color-overforecast)" : "var(--color-underforecast)" }}>
                  {(hoveredDay.bias || 0) > 0 ? "+" : ""}{hoveredDay.bias?.toLocaleString()} MW
                </strong>
              </span>
              <span>Shortfall: <strong style={{ color: "#fb7185" }}>{hoveredDay.shortfall_mwh.toLocaleString()} MWh</strong></span>
              <span>WAPE: <strong>{hoveredDay.wape ? `${hoveredDay.wape}%` : "N/A"}</strong></span>
            </div>
          ) : (
            <span style={{ color: "var(--text-muted)" }}>
              Hover over a daily bar to inspect MAE, bias, and shortfall for that trading day.
            </span>
          )}
        </div>
      </section>

      {/* Pane 2: Top 5 Largest Error Settlement Intervals */}
      <section className="analytics-card" aria-label="Peak forecast errors">
        <div className="chart-header" style={{ marginBottom: "10px" }}>
          <div>
            <h3 className="section-title">Peak Operational Risk Periods</h3>
            <p className="section-subtitle">
              Top 5 largest forecasting misses in January 2026 requiring emergency thermal dispatch.
            </p>
          </div>
          <span className="kpi-tag tag-red">TOP 5 SWINGS</span>
        </div>

        <table className="dense-table" aria-label="Top 5 largest error intervals">
          <thead>
            <tr>
              <th>Interval</th>
              <th>Forecast</th>
              <th>Actual</th>
              <th>Deviation</th>
              <th>Shortfall</th>
            </tr>
          </thead>
          <tbody>
            {largestErrors.map((item) => (
              <tr key={item.interval_id}>
                <td>
                  <strong style={{ color: "#ffffff" }}>{item.settlement_date}</strong> P{item.settlement_period}
                </td>
                <td style={{ color: "var(--color-forecast)" }}>
                  {item.forecast_mw.toLocaleString()} MW
                </td>
                <td style={{ color: "var(--color-actual)" }}>
                  {item.actual_mw.toLocaleString()} MW
                </td>
                <td style={{ color: item.direction === "overforecast" ? "var(--color-overforecast)" : "var(--color-underforecast)", fontWeight: 700 }}>
                  {item.error_mw > 0 ? "+" : ""}{item.error_mw.toLocaleString()} MW
                </td>
                <td style={{ color: "#fb7185" }}>
                  {item.shortfall_mwh > 0 ? `${item.shortfall_mwh.toLocaleString()} MWh` : "—"}
                </td>
              </tr>
            ))}
            {largestErrors.length === 0 && (
              <tr>
                <td colSpan={5} style={{ textAlign: "center", color: "var(--text-muted)", padding: "20px" }}>
                  No error intervals available.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
};
