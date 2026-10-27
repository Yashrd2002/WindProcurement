import React from "react";

interface FilterControlsProps {
  cutoffTime: string;
  onCutoffChange: (cutoff: string) => void;
  startDate: string;
  endDate: string;
  onDateRangeChange: (start: string, end: string) => void;
  onRefresh: () => void;
  isLoading: boolean;
}

export const FilterControls: React.FC<FilterControlsProps> = ({
  cutoffTime,
  onCutoffChange,
  startDate,
  endDate,
  onDateRangeChange,
  onRefresh,
  isLoading,
}) => {
  const handlePreset = (start: string, end: string) => {
    onDateRangeChange(start, end);
  };

  const isFullMonth = startDate === "2026-01-01" && endDate === "2026-01-31";
  const isWeek1 = startDate === "2026-01-01" && endDate === "2026-01-07";
  const isWeek2 = startDate === "2026-01-08" && endDate === "2026-01-14";
  const isStormPeak = startDate === "2026-01-10" && endDate === "2026-01-15";

  return (
    <section className="controls-card" aria-label="Analysis policy and filter controls">
      <div className="controls-group">
        <div className="filter-field">
          <label htmlFor="cutoff-select">Decision Cutoff (Day D-1)</label>
          <select
            id="cutoff-select"
            className="filter-select"
            value={cutoffTime}
            onChange={(e) => onCutoffChange(e.target.value)}
            disabled={isLoading}
          >
            <option value="12:00">12:00 UK (Standard Day-Ahead Commit)</option>
            <option value="09:30">09:30 UK (Early Morning Gate)</option>
            <option value="11:00">11:00 UK (Pre-Auction Sizing)</option>
            <option value="17:00">17:00 UK (Late Afternoon Revision)</option>
          </select>
        </div>

        <div className="filter-field">
          <label htmlFor="start-date-input">Start Date</label>
          <input
            id="start-date-input"
            type="date"
            className="filter-input"
            min="2026-01-01"
            max="2026-01-31"
            value={startDate}
            onChange={(e) => onDateRangeChange(e.target.value, endDate)}
            disabled={isLoading}
          />
        </div>

        <div className="filter-field">
          <label htmlFor="end-date-input">End Date</label>
          <input
            id="end-date-input"
            type="date"
            className="filter-input"
            min={startDate || "2026-01-01"}
            max="2026-01-31"
            value={endDate}
            onChange={(e) => onDateRangeChange(startDate, e.target.value)}
            disabled={isLoading}
          />
        </div>
      </div>

      <div className="controls-group">
        <div className="preset-pills" role="group" aria-label="Date range quick presets">
          <button
            type="button"
            className={`pill-btn ${isFullMonth ? "active" : ""}`}
            onClick={() => handlePreset("2026-01-01", "2026-01-31")}
          >
            Full Month
          </button>
          <button
            type="button"
            className={`pill-btn ${isWeek1 ? "active" : ""}`}
            onClick={() => handlePreset("2026-01-01", "2026-01-07")}
          >
            Week 1
          </button>
          <button
            type="button"
            className={`pill-btn ${isWeek2 ? "active" : ""}`}
            onClick={() => handlePreset("2026-01-08", "2026-01-14")}
          >
            Week 2
          </button>
          <button
            type="button"
            className={`pill-btn ${isStormPeak ? "active" : ""}`}
            onClick={() => handlePreset("2026-01-10", "2026-01-15")}
          >
            ⚡ Peak Storm Miss (Jan 10-15)
          </button>
        </div>

        <button
          type="button"
          className="action-btn action-btn-outline"
          onClick={onRefresh}
          disabled={isLoading}
          title="Refresh analytics data"
        >
          {isLoading ? "Refreshing..." : "↻ Recompute"}
        </button>
      </div>
    </section>
  );
};
