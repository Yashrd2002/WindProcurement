import React, { useState, useEffect } from "react";
import { apiClient, AiBriefingResponse } from "../api/client";

interface AiCopilotBriefingProps {
  month: string;
  cutoff: string;
}

export function AiCopilotBriefing({ month, cutoff }: AiCopilotBriefingProps) {
  const [briefing, setBriefing] = useState<AiBriefingResponse | null>(null);
  const [riskTolerance, setRiskTolerance] = useState<"conservative" | "balanced" | "aggressive">("balanced");
  const [customQuery, setCustomQuery] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean>(false);

  const fetchBriefing = async (tolerance = riskTolerance, query = customQuery) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiClient.fetchAiBriefing({
        month,
        cutoff,
        risk_tolerance: tolerance,
        custom_query: query.trim() || undefined,
      });
      setBriefing(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to generate AI trading briefing";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  // Automatically load initial briefing on mount or cutoff change
  useEffect(() => {
    fetchBriefing();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [month, cutoff]);

  const handleToleranceChange = (newTolerance: "conservative" | "balanced" | "aggressive") => {
    setRiskTolerance(newTolerance);
    fetchBriefing(newTolerance, customQuery);
  };

  const handleCopyClipboard = () => {
    if (!briefing) return;
    const text = `
=== UK WIND PROCUREMENT INTEL · TRADING DESK BRIEFING ===
Evaluation Month: ${month} | Day-Ahead Cutoff: ${cutoff} UTC
Provider: ${briefing.ai_provider} (${briefing.model_used || "standard"})

[EXECUTIVE SUMMARY]
${briefing.executive_summary}

[THERMAL HEDGE SIZING DIRECTIVE]
• Recommended Buffer: +${briefing.hedging_recommendation.recommended_thermal_buffer_mw.toLocaleString()} MW
• Desk Exposure: ${briefing.hedging_recommendation.risk_level}
• Rationale: ${briefing.hedging_recommendation.strategy_rationale}
• Total Unhedged Shortfall: ${briefing.hedging_recommendation.unhedged_shortfall_mwh.toLocaleString()} MWh

[TOP EXPOSURE ALERTS]
${briefing.peak_exposure_alerts.map(a => `• ${a.settlement_date} SP${a.settlement_period}: Error ${a.error_mw > 0 ? "+" : ""}${a.error_mw.toLocaleString()} MW | ${a.risk_category} -> ${a.mitigation_action}`).join("\n")}

[SHIFT OPERATIONAL CHECKLIST]
${briefing.operational_checklist.map(c => `• ${c}`).join("\n")}
=========================================================
`.trim();

    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    });
  };

  return (
    <section className="dashboard-card ai-copilot-card" style={{ marginBottom: "24px" }} aria-label="AI Trading Desk Copilot">
      {/* Top Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px", marginBottom: "16px" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
            <h2 style={{ fontSize: "1.25rem", fontWeight: 700, margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
              <span>🤖</span> AI Trading Desk Copilot
            </h2>
            {briefing && (
              <span
                style={{
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  padding: "3px 10px",
                  borderRadius: "9999px",
                  background: briefing.ai_provider === "openai" ? "rgba(16, 185, 129, 0.15)" : "rgba(56, 189, 248, 0.15)",
                  color: briefing.ai_provider === "openai" ? "#10b981" : "#38bdf8",
                  border: `1px solid ${briefing.ai_provider === "openai" ? "rgba(16, 185, 129, 0.3)" : "rgba(56, 189, 248, 0.3)"}`,
                }}
              >
                {briefing.ai_provider === "openai" ? `⚡ OpenAI ${briefing.model_used || "GPT-4o-mini"}` : "🛡️ Quant Heuristic Engine"}
              </span>
            )}
          </div>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: "4px" }}>
            Executive Day-Ahead Risk Briefing & Thermal Sizing Recommendations (Strict 12:00 D-1 Cutoff)
          </p>
        </div>

        {/* Action Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          <div style={{ display: "inline-flex", background: "rgba(15, 23, 42, 0.6)", borderRadius: "8px", padding: "3px", border: "1px solid var(--border-subtle)" }}>
            {(["conservative", "balanced", "aggressive"] as const).map((tol) => (
              <button
                key={tol}
                type="button"
                onClick={() => handleToleranceChange(tol)}
                disabled={isLoading}
                style={{
                  background: riskTolerance === tol ? "var(--color-brand)" : "transparent",
                  color: riskTolerance === tol ? "#020617" : "var(--text-secondary)",
                  border: "none",
                  padding: "5px 12px",
                  borderRadius: "6px",
                  fontSize: "0.8rem",
                  fontWeight: riskTolerance === tol ? 700 : 500,
                  cursor: "pointer",
                  textTransform: "capitalize",
                  transition: "all 0.15s ease",
                }}
              >
                {tol}
              </button>
            ))}
          </div>

          <button
            type="button"
            className="action-btn"
            onClick={() => fetchBriefing()}
            disabled={isLoading}
            style={{
              background: "var(--color-brand)",
              color: "#020617",
              fontWeight: 600,
              padding: "6px 14px",
              fontSize: "0.82rem",
              borderRadius: "8px",
              cursor: isLoading ? "not-allowed" : "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            {isLoading ? "Generating..." : "⚡ Refresh Briefing"}
          </button>

          {briefing && (
            <button
              type="button"
              className="action-btn"
              onClick={handleCopyClipboard}
              style={{
                background: "rgba(148, 163, 184, 0.1)",
                color: copied ? "#10b981" : "var(--text-primary)",
                border: "1px solid var(--border-subtle)",
                fontWeight: 500,
                padding: "6px 12px",
                fontSize: "0.82rem",
                borderRadius: "8px",
                cursor: "pointer",
              }}
            >
              {copied ? "✓ Copied!" : "📋 Copy Briefing"}
            </button>
          )}
        </div>
      </div>

      {/* Trader Custom Prompt Input */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
        <input
          type="text"
          value={customQuery}
          onChange={(e) => setCustomQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") fetchBriefing();
          }}
          placeholder="Ask Copilot a question (e.g. 'What is the exposure risk during evening peak hours?')"
          style={{
            flex: 1,
            background: "rgba(15, 23, 42, 0.5)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "8px",
            padding: "8px 12px",
            color: "var(--text-primary)",
            fontSize: "0.85rem",
          }}
        />
        <button
          type="button"
          onClick={() => fetchBriefing()}
          disabled={isLoading || !customQuery.trim()}
          style={{
            background: isLoading ? "rgba(56, 189, 248, 0.4)" : "rgba(56, 189, 248, 0.2)",
            color: "var(--color-brand)",
            border: "1px solid rgba(56, 189, 248, 0.4)",
            padding: "8px 18px",
            borderRadius: "8px",
            fontSize: "0.85rem",
            fontWeight: 600,
            cursor: !customQuery.trim() || isLoading ? "not-allowed" : "pointer",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            transition: "all 0.2s ease",
          }}
        >
          {isLoading ? (
            <>
              <span
                style={{
                  display: "inline-block",
                  width: "12px",
                  height: "12px",
                  border: "2px solid rgba(56, 189, 248, 0.3)",
                  borderTopColor: "var(--color-brand)",
                  borderRadius: "50%",
                  animation: "aiSpin 0.7s linear infinite",
                }}
              />
              Thinking...
            </>
          ) : (
            "Ask"
          )}
        </button>
      </div>

      {error && (
        <div style={{ padding: "10px 14px", background: "rgba(244, 63, 94, 0.1)", border: "1px solid rgba(244, 63, 94, 0.3)", borderRadius: "8px", color: "#f43f5e", fontSize: "0.85rem", marginBottom: "16px" }}>
          ⚠️ {error}
        </div>
      )}

      {/* Prominent Active Processing Banner during LLM Generation */}
      {isLoading && (
        <div
          style={{
            background: "linear-gradient(90deg, rgba(56, 189, 248, 0.12) 0%, rgba(16, 185, 129, 0.12) 100%)",
            border: "1px solid rgba(56, 189, 248, 0.4)",
            borderRadius: "10px",
            padding: "12px 16px",
            marginBottom: "16px",
            display: "flex",
            alignItems: "center",
            gap: "14px",
            animation: "aiPulse 1.8s ease-in-out infinite",
          }}
        >
          <div
            style={{
              width: "22px",
              height: "22px",
              border: "2.5px solid rgba(56, 189, 248, 0.2)",
              borderTopColor: "var(--color-brand)",
              borderRadius: "50%",
              animation: "aiSpin 0.8s linear infinite",
              flexShrink: 0,
            }}
          />
          <div style={{ flex: 1 }}>
            <div style={{ color: "var(--color-brand)", fontSize: "0.88rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "6px" }}>
              <span>⚡</span> Querying OpenAI GPT-4o-mini & Analyzing Elexon Data...
            </div>
            <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginTop: "2px" }}>
              Evaluating desk sizing directives against 1,488 January 2026 settlement periods and 12:00 D-1 auction gate closure.
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes aiSpin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes aiPulse {
          0%, 100% { opacity: 1; border-color: rgba(56, 189, 248, 0.5); }
          50% { opacity: 0.75; border-color: rgba(16, 185, 129, 0.5); }
        }
      `}</style>

      {/* Main Intelligence Body */}
      {briefing ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "16px", opacity: isLoading ? 0.6 : 1, transition: "opacity 0.2s ease" }}>
          {/* Column 1: Thermal Sizing Directive & Rationale */}
          <div style={{ background: "rgba(15, 23, 42, 0.4)", padding: "16px", borderRadius: "10px", border: "1px solid var(--border-subtle)" }}>
            <div style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-muted)", fontWeight: 700 }}>
              Day-Ahead Procurement Directive
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: "8px", marginTop: "8px", marginBottom: "8px" }}>
              <span style={{ fontSize: "2rem", fontWeight: 800, color: "var(--color-forecast)", fontFamily: "var(--font-mono)" }}>
                +{briefing.hedging_recommendation.recommended_thermal_buffer_mw.toLocaleString()} MW
              </span>
              <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                thermal hedge buffer
              </span>
            </div>

            <div style={{ display: "flex", gap: "8px", marginBottom: "12px" }}>
              <span style={{ fontSize: "0.75rem", fontWeight: 700, padding: "2px 8px", borderRadius: "4px", background: "rgba(244, 63, 94, 0.15)", color: "#f43f5e" }}>
                Exposure: {briefing.hedging_recommendation.risk_level}
              </span>
              <span style={{ fontSize: "0.75rem", fontWeight: 600, padding: "2px 8px", borderRadius: "4px", background: "rgba(245, 158, 11, 0.15)", color: "#f59e0b" }}>
                Shortfall: {briefing.hedging_recommendation.unhedged_shortfall_mwh.toLocaleString()} MWh
              </span>
            </div>

            <p style={{ fontSize: "0.85rem", lineHeight: 1.5, color: "var(--text-secondary)", margin: 0 }}>
              {briefing.hedging_recommendation.strategy_rationale}
            </p>
          </div>

          {/* Column 2: Executive Summary & Shift Checklist */}
          <div style={{ background: "rgba(15, 23, 42, 0.4)", padding: "16px", borderRadius: "10px", border: "1px solid var(--border-subtle)", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-muted)", fontWeight: 700, marginBottom: "8px" }}>
                Commercial Regime Summary
              </div>
              <p style={{ fontSize: "0.85rem", lineHeight: 1.5, color: "var(--text-primary)", marginBottom: "12px" }}>
                {briefing.executive_summary}
              </p>
            </div>

            <div>
              <div style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-muted)", fontWeight: 700, marginBottom: "6px" }}>
                Trading Shift Checklist
              </div>
              <ul style={{ paddingLeft: "16px", margin: 0, fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.4 }}>
                {briefing.operational_checklist.map((item, idx) => (
                  <li key={idx} style={{ marginBottom: "4px" }}>{item}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Column 3: Peak Danger Intervals */}
          {briefing.peak_exposure_alerts.length > 0 && (
            <div style={{ gridColumn: "1 / -1", background: "rgba(15, 23, 42, 0.3)", padding: "14px 16px", borderRadius: "10px", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-muted)", fontWeight: 700, marginBottom: "10px" }}>
                ⚠️ High-Volatility Exposure Alerts
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "10px" }}>
                {briefing.peak_exposure_alerts.map((alert, idx) => (
                  <div key={idx} style={{ background: "rgba(244, 63, 94, 0.08)", border: "1px solid rgba(244, 63, 94, 0.2)", borderRadius: "8px", padding: "10px 12px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", fontWeight: 700, color: "#f43f5e", marginBottom: "4px" }}>
                      <span>{alert.settlement_date} SP{alert.settlement_period}</span>
                      <span>Error: {alert.error_mw > 0 ? "+" : ""}{alert.error_mw.toLocaleString()} MW</span>
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: "4px" }}>
                      <strong>Driver:</strong> {alert.risk_category} | <strong>Shortfall:</strong> {alert.shortfall_mwh.toLocaleString()} MWh
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--color-brand)" }}>
                      <strong>Action:</strong> {alert.mitigation_action}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : isLoading ? (
        <div style={{ textAlign: "center", padding: "30px", color: "var(--text-secondary)", fontSize: "0.9rem" }}>
          ⏳ Computing AI trading desk risk assessment and sizing directives...
        </div>
      ) : null}
    </section>
  );
}
export default AiCopilotBriefing;
