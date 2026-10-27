import React from "react";

interface HeaderProps {
  apiStatus: "connected" | "connecting" | "error";
  targetMonth: string;
  cutoffTime: string;
}

export const Header: React.FC<HeaderProps> = ({ apiStatus, targetMonth, cutoffTime }) => {
  return (
    <header className="header-banner" role="banner">
      <div>
        <div className="brand-eyebrow">
          <span className="dot-indicator" aria-hidden="true" />
          <span>UK Wholesale Power Desk · Day-Ahead Renewable Balancing</span>
        </div>
        <h1 className="brand-title">Wind Procurement Intelligence</h1>
        <p className="brand-subtitle">
          Statistically evaluates national wind forecasts available at the decision cutoff against observed delivery to optimize thermal power procurement and prevent costly imbalance penalties.
        </p>
      </div>

      <div className="header-badges" aria-label="Operational status metadata">
        <div className="badge badge-blue">
          <span>📅 Window:</span>
          <strong>{targetMonth}</strong>
        </div>
        <div className="badge badge-amber">
          <span>⏱️ Decision Cutoff:</span>
          <strong>{cutoffTime} D-1 (UK)</strong>
        </div>
        <div className="badge badge-green">
          <span className="dot-indicator" aria-hidden="true" />
          <span>Elexon BMRS:</span>
          <strong>{apiStatus === "connected" ? "Live Stream" : apiStatus === "connecting" ? "Syncing..." : "Offline Fallback"}</strong>
        </div>
      </div>
    </header>
  );
};
