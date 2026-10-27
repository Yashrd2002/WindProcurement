import React from "react";
import { IntervalItem } from "../api/client";

interface IntervalsTableProps {
  items: IntervalItem[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  onPageChange: (newPage: number) => void;
  onPageSizeChange: (newSize: number) => void;
  statusFilter: string;
  onStatusFilterChange: (status: string) => void;
  targetMonth: string;
  cutoffTime: string;
  isLoading: boolean;
}

export const IntervalsTable: React.FC<IntervalsTableProps> = ({
  items,
  total,
  page,
  pageSize,
  totalPages,
  onPageChange,
  onPageSizeChange,
  statusFilter,
  onStatusFilterChange,
  targetMonth,
  cutoffTime,
  isLoading,
}) => {
  // Client-side CSV export generator (P6-07)
  const handleExportCsv = () => {
    if (items.length === 0) return;

    const headers = [
      "Interval ID",
      "Delivery Start Time (UTC)",
      "Settlement Date",
      "Settlement Period",
      "Actual (MW)",
      "Cutoff Forecast (MW)",
      "Forecast Error (MW)",
      "Shortfall Volume (MWh)",
      "Forecast Publish Time (UTC)",
      "Cutoff Time Applied (UTC)",
      "Status",
    ];

    const rows = items.map((i) => [
      i.interval_id,
      i.start_time,
      i.settlement_date,
      i.settlement_period,
      i.actual_mw !== null ? i.actual_mw : "",
      i.forecast_mw !== null ? i.forecast_mw : "",
      i.error_mw !== null ? i.error_mw : "",
      i.shortfall_mwh !== null ? i.shortfall_mwh : "",
      i.forecast_publish_time !== null ? i.forecast_publish_time : "",
      i.cutoff_time_applied,
      i.status,
    ]);

    const csvContent =
      "data:text/csv;charset=utf-8," +
      [headers.join(","), ...rows.map((r) => r.map((c) => `"${c}"`).join(","))].join("\n");

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute(
      "download",
      `wind_procurement_intervals_${targetMonth}_cutoff_${cutoffTime.replace(":", "")}.csv`
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <section className="table-card" aria-label="Settlement intervals tabular ledger">
      <div className="table-toolbar">
        <div>
          <h3 className="section-title">Settlement Period Intervals</h3>
          <p className="section-subtitle">
            Showing {items.length} of {total} half-hourly intervals for {targetMonth}.
          </p>
        </div>

        <div className="controls-group">
          <div className="filter-field">
            <label htmlFor="status-filter-select">Status Filter</label>
            <select
              id="status-filter-select"
              className="filter-select"
              value={statusFilter}
              onChange={(e) => onStatusFilterChange(e.target.value)}
              disabled={isLoading}
            >
              <option value="">All Statuses ({total})</option>
              <option value="matched">Matched Pairs Only</option>
              <option value="missing_forecast">Missing Forecast</option>
              <option value="missing_actual">Missing Actual</option>
            </select>
          </div>

          <div className="filter-field">
            <label htmlFor="page-size-select">Per Page</label>
            <select
              id="page-size-select"
              className="filter-select"
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              disabled={isLoading}
            >
              <option value="24">24 (12h)</option>
              <option value="48">48 (1 Day)</option>
              <option value="96">96 (2 Days)</option>
            </select>
          </div>

          <div className="filter-field" style={{ alignSelf: "flex-end" }}>
            <button
              type="button"
              className="action-btn"
              onClick={handleExportCsv}
              disabled={isLoading || items.length === 0}
              title="Download active records as CSV"
            >
              📥 Export CSV
            </button>
          </div>
        </div>
      </div>

      <div className="data-table-container">
        <table className="data-table" aria-label="Settlement intervals dataset">
          <thead>
            <tr>
              <th>Interval ID</th>
              <th>Delivery Start (UTC)</th>
              <th>Period</th>
              <th>Actual (MW)</th>
              <th>Forecast (MW)</th>
              <th>Error (MW)</th>
              <th>Shortfall (MWh)</th>
              <th>Forecast Released</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <tr key={i}>
                  <td colSpan={9} style={{ padding: "14px" }}>
                    <div className="skeleton" style={{ height: "20px" }} />
                  </td>
                </tr>
              ))
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={9} style={{ textAlign: "center", padding: "40px", color: "var(--text-muted)" }}>
                  No settlement intervals matched the active filter.
                </td>
              </tr>
            ) : (
              items.map((row) => (
                <tr key={row.interval_id}>
                  <td>
                    <strong style={{ color: "#ffffff" }}>{row.interval_id}</strong>
                  </td>
                  <td>{row.start_time.replace("T", " ").replace("+00:00", "Z")}</td>
                  <td>P{row.settlement_period}</td>
                  <td style={{ color: "var(--color-actual)" }}>
                    {row.actual_mw !== null ? `${row.actual_mw.toLocaleString()} MW` : "—"}
                  </td>
                  <td style={{ color: "var(--color-forecast)" }}>
                    {row.forecast_mw !== null ? `${row.forecast_mw.toLocaleString()} MW` : "—"}
                  </td>
                  <td
                    style={{
                      color:
                        row.error_mw === null
                          ? "var(--text-muted)"
                          : row.error_mw > 0
                          ? "var(--color-overforecast)"
                          : "var(--color-underforecast)",
                      fontWeight: 700,
                    }}
                  >
                    {row.error_mw !== null ? `${row.error_mw > 0 ? "+" : ""}${row.error_mw.toLocaleString()} MW` : "—"}
                  </td>
                  <td style={{ color: row.shortfall_mwh && row.shortfall_mwh > 0 ? "#fb7185" : "var(--text-muted)" }}>
                    {row.shortfall_mwh && row.shortfall_mwh > 0 ? `${row.shortfall_mwh.toLocaleString()} MWh` : "—"}
                  </td>
                  <td style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                    {row.forecast_publish_time
                      ? row.forecast_publish_time.replace("T", " ").replace("+00:00", "")
                      : "—"}
                  </td>
                  <td>
                    {row.status === "matched" ? (
                      <span className="status-chip chip-matched">MATCHED</span>
                    ) : (
                      <span className="status-chip chip-missing">{row.status.replace("_", " ")}</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="pagination-bar">
        <div>
          Showing page <strong>{page}</strong> of <strong>{totalPages || 1}</strong> ({total} total intervals)
        </div>

        <nav className="pagination-nav" aria-label="Table pagination">
          <button
            type="button"
            className="nav-btn"
            onClick={() => onPageChange(1)}
            disabled={page <= 1 || isLoading}
          >
            « First
          </button>
          <button
            type="button"
            className="nav-btn"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1 || isLoading}
          >
            ‹ Prev
          </button>
          <span style={{ padding: "0 8px", fontWeight: 700 }}>{page}</span>
          <button
            type="button"
            className="nav-btn"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages || isLoading}
          >
            Next ›
          </button>
          <button
            type="button"
            className="nav-btn"
            onClick={() => onPageChange(totalPages)}
            disabled={page >= totalPages || isLoading}
          >
            Last »
          </button>
        </nav>
      </div>
    </section>
  );
};
