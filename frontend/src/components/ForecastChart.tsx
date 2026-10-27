import React, { useState, useMemo, useRef } from "react";
import { TimeseriesPoint } from "../api/client";

interface ForecastChartProps {
  points: TimeseriesPoint[];
  startDate: string;
  endDate: string;
  cutoffTime: string;
  isLoading: boolean;
}

export const ForecastChart: React.FC<ForecastChartProps> = ({
  points,
  startDate,
  endDate,
  cutoffTime,
  isLoading,
}) => {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [showForecast, setShowForecast] = useState(true);
  const [showActual, setShowActual] = useState(true);
  const [showDifference, setShowDifference] = useState(true);

  const containerRef = useRef<HTMLDivElement>(null);

  // Filter points according to active date range
  const filteredPoints = useMemo(() => {
    return points.filter((p) => {
      if (!startDate && !endDate) return true;
      const d = p.settlement_date;
      if (startDate && d < startDate) return false;
      if (endDate && d > endDate) return false;
      return true;
    });
  }, [points, startDate, endDate]);

  // Chart dimensions & scaling
  const width = 1000;
  const height = 350;
  const padding = { top: 20, right: 25, bottom: 40, left: 65 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  const { maxVal, yTicks, xTicks } = useMemo(() => {
    let max = 1000;
    filteredPoints.forEach((p) => {
      if (p.forecast_mw && p.forecast_mw > max) max = p.forecast_mw;
      if (p.actual_mw && p.actual_mw > max) max = p.actual_mw;
    });
    // Round up to nearest 2,500 MW
    const roundedMax = Math.ceil(max / 2500) * 2500;
    const ticksCount = 5;
    const yTicksArr = Array.from({ length: ticksCount + 1 }, (_, i) => (roundedMax / ticksCount) * i);

    // X-axis ticks (sample 6 evenly spaced dates)
    const xTicksArr: { index: number; label: string }[] = [];
    if (filteredPoints.length > 0) {
      const step = Math.max(1, Math.floor(filteredPoints.length / 6));
      for (let i = 0; i < filteredPoints.length; i += step) {
        const pt = filteredPoints[i];
        xTicksArr.push({
          index: i,
          label: `${pt.settlement_date.slice(5)} P${pt.settlement_period}`,
        });
      }
    }

    return { maxVal: roundedMax, yTicks: yTicksArr, xTicks: xTicksArr };
  }, [filteredPoints]);

  const getX = (index: number) => {
    if (filteredPoints.length <= 1) return padding.left;
    return padding.left + (index / (filteredPoints.length - 1)) * plotWidth;
  };

  const getY = (val: number | null) => {
    if (val === null || isNaN(val)) return height - padding.bottom;
    const clamped = Math.max(0, Math.min(maxVal, val));
    return padding.top + plotHeight - (clamped / maxVal) * plotHeight;
  };

  // Generate SVG path strings
  const { forecastPath, actualPath, differencePath } = useMemo(() => {
    if (filteredPoints.length === 0) return { forecastPath: "", actualPath: "", differencePath: "" };

    let fPath = "";
    let aPath = "";

    filteredPoints.forEach((p, idx) => {
      const x = getX(idx);
      const fy = getY(p.forecast_mw);
      const ay = getY(p.actual_mw);

      if (idx === 0) {
        fPath = `M ${x} ${fy}`;
        aPath = `M ${x} ${ay}`;
      } else {
        fPath += ` L ${x} ${fy}`;
        aPath += ` L ${x} ${ay}`;
      }
    });

    // Difference polygon: forecast line forward, then actual line backward
    let diffPath = "";
    if (filteredPoints.length > 1) {
      diffPath = fPath;
      for (let i = filteredPoints.length - 1; i >= 0; i--) {
        const x = getX(i);
        const ay = getY(filteredPoints[i].actual_mw);
        diffPath += ` L ${x} ${ay}`;
      }
      diffPath += " Z";
    }

    return { forecastPath: fPath, actualPath: aPath, differencePath: diffPath };
  }, [filteredPoints, maxVal]);

  // Mouse hover event handler
  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!containerRef.current || filteredPoints.length === 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const svgX = (mouseX / rect.width) * width;

    if (svgX < padding.left || svgX > width - padding.right) {
      setHoverIndex(null);
      return;
    }

    const relativeX = (svgX - padding.left) / plotWidth;
    const idx = Math.min(
      filteredPoints.length - 1,
      Math.max(0, Math.round(relativeX * (filteredPoints.length - 1)))
    );
    setHoverIndex(idx);
  };

  const handleMouseLeave = () => {
    setHoverIndex(null);
  };

  const activePoint = hoverIndex !== null && filteredPoints[hoverIndex] ? filteredPoints[hoverIndex] : null;

  if (isLoading) {
    return (
      <section className="chart-card">
        <div className="chart-header">
          <div>
            <div className="section-title">Day-Ahead Forecast vs Realized Generation</div>
            <div className="section-subtitle">Loading Elexon time series stream...</div>
          </div>
        </div>
        <div className="chart-container skeleton" />
      </section>
    );
  }

  if (filteredPoints.length === 0) {
    return (
      <section className="chart-card">
        <div className="chart-header">
          <div className="section-title">Day-Ahead Forecast vs Realized Generation</div>
        </div>
        <div className="empty-state">
          <div className="empty-icon">📊</div>
          <h3>No settlement intervals found</h3>
          <p>No data matched the active filters for {startDate} to {endDate}.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="chart-card" aria-label="Forecast vs actual time series chart">
      <div className="chart-header">
        <div>
          <h2 className="section-title">Day-Ahead Forecast vs Realized Generation</h2>
          <p className="section-subtitle">
            Showing {filteredPoints.length} half-hourly settlement periods at <strong>{cutoffTime} D-1</strong> decision cutoff.
          </p>
        </div>

        <div className="chart-legend" role="group" aria-label="Chart line toggles">
          <div
            className="legend-item"
            onClick={() => setShowForecast(!showForecast)}
            style={{ opacity: showForecast ? 1 : 0.4 }}
          >
            <span className="legend-line line-forecast" />
            <span>Forecast (MW)</span>
          </div>

          <div
            className="legend-item"
            onClick={() => setShowActual(!showActual)}
            style={{ opacity: showActual ? 1 : 0.4 }}
          >
            <span className="legend-line line-actual" />
            <span>Actual Realized (MW)</span>
          </div>

          <div
            className="legend-item"
            onClick={() => setShowDifference(!showDifference)}
            style={{ opacity: showDifference ? 1 : 0.4 }}
          >
            <span className="legend-swatch swatch-shortfall" />
            <span>Overforecast Shortfall (MWh)</span>
          </div>
        </div>
      </div>

      <div className="chart-container" ref={containerRef}>
        <svg
          className="chart-svg"
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="none"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          <defs>
            <linearGradient id="shortfallGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.05" />
            </linearGradient>
          </defs>

          {/* Gridlines & Y-Axis Ticks */}
          <g className="chart-axis" aria-hidden="true">
            {yTicks.map((tickVal) => {
              const y = getY(tickVal);
              return (
                <g key={tickVal}>
                  <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} />
                  <text x={padding.left - 10} y={y + 4} textAnchor="end">
                    {(tickVal / 1000).toFixed(1)} GW
                  </text>
                </g>
              );
            })}
          </g>

          {/* X-Axis Ticks */}
          <g className="chart-axis" aria-hidden="true">
            {xTicks.map((tick) => {
              const x = getX(tick.index);
              return (
                <g key={tick.index}>
                  <line x1={x} y1={height - padding.bottom} x2={x} y2={height - padding.bottom + 6} />
                  <text x={x} y={height - padding.bottom + 20} textAnchor="middle">
                    {tick.label}
                  </text>
                </g>
              );
            })}
          </g>

          {/* Difference Area Fill */}
          {showDifference && differencePath && (
            <path d={differencePath} fill="url(#shortfallGradient)" pointerEvents="none" />
          )}

          {/* Lines */}
          {showForecast && forecastPath && (
            <path d={forecastPath} className="chart-line-forecast" pointerEvents="none" />
          )}
          {showActual && actualPath && (
            <path d={actualPath} className="chart-line-actual" pointerEvents="none" />
          )}

          {/* Crosshair & Data Points on Hover */}
          {activePoint && hoverIndex !== null && (
            <g pointerEvents="none">
              <line
                x1={getX(hoverIndex)}
                y1={padding.top}
                x2={getX(hoverIndex)}
                y2={height - padding.bottom}
                className="chart-crosshair"
              />
              {showForecast && activePoint.forecast_mw !== null && (
                <circle
                  cx={getX(hoverIndex)}
                  cy={getY(activePoint.forecast_mw)}
                  r={5}
                  fill="#f59e0b"
                  stroke="#ffffff"
                  strokeWidth={2}
                />
              )}
              {showActual && activePoint.actual_mw !== null && (
                <circle
                  cx={getX(hoverIndex)}
                  cy={getY(activePoint.actual_mw)}
                  r={5}
                  fill="#06b6d4"
                  stroke="#ffffff"
                  strokeWidth={2}
                />
              )}
            </g>
          )}
        </svg>

        {/* Hover Tooltip Popup */}
        {activePoint && hoverIndex !== null && (
          <div
            className="chart-tooltip"
            style={{
              left: `${(getX(hoverIndex) / width) * 100}%`,
              top: `${(Math.min(getY(activePoint.forecast_mw), getY(activePoint.actual_mw)) / height) * 100}%`,
            }}
          >
            <div className="tooltip-time">
              {activePoint.settlement_date} · Period {activePoint.settlement_period}
            </div>
            <div className="tooltip-row">
              <span style={{ color: "var(--color-forecast)" }}>● Forecast:</span>
              <strong>{activePoint.forecast_mw ? `${activePoint.forecast_mw.toLocaleString()} MW` : "N/A"}</strong>
            </div>
            <div className="tooltip-row">
              <span style={{ color: "var(--color-actual)" }}>● Actual:</span>
              <strong>{activePoint.actual_mw ? `${activePoint.actual_mw.toLocaleString()} MW` : "N/A"}</strong>
            </div>
            <div className="tooltip-row">
              <span style={{ color: activePoint.error_mw && activePoint.error_mw > 0 ? "var(--color-overforecast)" : "var(--color-underforecast)" }}>
                Error (F-A):
              </span>
              <strong>
                {activePoint.error_mw
                  ? `${activePoint.error_mw > 0 ? "+" : ""}${activePoint.error_mw.toLocaleString()} MW`
                  : "N/A"}
              </strong>
            </div>
            {activePoint.shortfall_mwh ? (
              <div className="tooltip-row" style={{ color: "#fb7185", borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: "4px", marginTop: "4px" }}>
                <span>Shortfall:</span>
                <strong>{activePoint.shortfall_mwh.toLocaleString()} MWh</strong>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </section>
  );
};
