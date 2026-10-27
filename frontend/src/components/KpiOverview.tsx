import React from "react";
import { MetricCard } from "../api/client";

interface KpiOverviewProps {
  cards: MetricCard[];
  dataStatus: string;
  completenessPct: number;
  totalMatched: number;
  totalExpected: number;
  isLoading: boolean;
}

export const KpiOverview: React.FC<KpiOverviewProps> = ({
  cards,
  dataStatus,
  completenessPct,
  totalMatched,
  totalExpected,
  isLoading,
}) => {
  const getStatusBadge = () => {
    switch (dataStatus) {
      case "complete":
        return <span className="kpi-tag tag-green">COMPLETE (100%)</span>;
      case "partial":
        return <span className="kpi-tag tag-amber">PARTIAL COVERAGE</span>;
      case "stale":
        return <span className="kpi-tag tag-red">STALE PUBLICATION</span>;
      default:
        return <span className="kpi-tag tag-blue">{dataStatus.toUpperCase()}</span>;
    }
  };

  if (isLoading) {
    return (
      <section className="kpi-grid" aria-label="KPI overview loading">
        {[1, 2, 3, 4, 5, 6].map((idx) => (
          <div key={idx} className="kpi-card skeleton" style={{ height: "140px" }} />
        ))}
      </section>
    );
  }

  return (
    <section className="kpi-grid" aria-label="Key performance indicators">
      {cards.map((card) => {
        let tag = null;
        if (card.key === "bias") {
          tag = (card.value || 0) > 0 ? (
            <span className="kpi-tag tag-red">OVERFORECAST (F &gt; A)</span>
          ) : (card.value || 0) < 0 ? (
            <span className="kpi-tag tag-blue">UNDERFORECAST (F &lt; A)</span>
          ) : (
            <span className="kpi-tag tag-green">BALANCED</span>
          );
        } else if (card.key === "completeness") {
          tag = getStatusBadge();
        } else if (card.key === "shortfall") {
          tag = <span className="kpi-tag tag-amber">PHYSICAL MWh</span>;
        }

        return (
          <div key={card.key} className="kpi-card" tabIndex={0} role="article" aria-label={`${card.label}: ${card.formatted}`}>
            <div>
              <div className="kpi-card-header">
                <span className="kpi-label">{card.label}</span>
                {tag}
              </div>
              <div className="kpi-value">{card.formatted}</div>
              <div className="kpi-meta">{card.description}</div>
            </div>

            {card.interpretation && (
              <div className="kpi-interpretation">
                {card.interpretation}
              </div>
            )}
          </div>
        );
      })}
    </section>
  );
};
