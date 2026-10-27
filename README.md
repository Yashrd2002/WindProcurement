# Wind Procurement Intelligence Platform

[![Build Status](https://img.shields.io/badge/Build-Passing-brightgreen.svg)](#)
[![Tests](https://img.shields.io/badge/Tests-137%2F137%20Passed-brightgreen.svg)](#)
[![Stack](https://img.shields.io/badge/Stack-React%2019%20%7C%20FastAPI%20%7C%20OpenAI%20%7C%20Docker-blue.svg)](#)
[![Target Window](https://img.shields.io/badge/Target%20Window-January%202026-orange.svg)](#)
[![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)](#)

A production-grade decision-support platform designed for UK wholesale power procurement desks. It enables power traders to visualize operational day-ahead wind forecasts, strictly enforce gate-closure decision cutoffs to eliminate look-ahead bias, quantitatively assess forecast accuracy against realized Elexon BMRS generation, and leverage an **AI Trading Desk Copilot** for risk-adjusted thermal procurement sizing.

---

## 🌐 Live Application Deployment & Demonstration

| Resource | Link | Description |
| :--- | :--- | :--- |
| **🌐 Live Application** | [http://54.226.35.22:8000/](http://54.226.35.22:8000/) | Live deployed platform on AWS ECS Fargate |
| **🎥 Video Walkthrough** | [https://youtu.be/cy0MacEeEW8](https://youtu.be/cy0MacEeEW8) | Two-part presentation (&le;10 min: Pitch + Technical Walkthrough) |
| **📑 Interactive API Docs** | [http://54.226.35.22:8000/docs](http://54.226.35.22:8000/docs) | Swagger / OpenAPI 3.1 interactive specification |
| **🩺 Liveness Health Check** | [http://54.226.35.22:8000/health/live](http://54.226.35.22:8000/health/live) | Container runtime probe (`{"status":"ok"}`) |
| **🩺 Readiness Health Check** | [http://54.226.35.22:8000/health/ready](http://54.226.35.22:8000/health/ready) | Upstream Elexon ingestion & cache readiness probe |

---

## ⚡ Executive Problem & Business Context

UK energy utilities must procure power in the wholesale day-ahead market to serve fluctuating consumer demand. Thermal and dispatchable generation must be contracted in advance to cover whatever portion of demand is not met by weather-dependent renewables like wind:

1. **Gate Closure Constraint:** Day-ahead auction bids close at **12:00 D-1** (noon the day before delivery). Any forecast published *after* 12:00 D-1 represents hindsight knowledge and cannot be used in real procurement decisions.
2. **Look-Ahead Bias Elimination:** This platform deterministically filters forecasts using the rule:
   $$\text{publishTime} \le \text{targetDeliveryDate} - 1 \text{ day at } 12:00\text{ UTC}$$
3. **Quantified Asymmetric Risk:** Overforecasting renewable generation leaves the utility short of power, forcing reliance on punitive balancing market cashout prices. Underforecasting results in excessive committed thermal capacity.

---

## 🤖 AI Trading Desk Copilot (OpenAI GPT-4o-mini Integration)

The platform features an embedded **AI Trading Desk Copilot** that bridges quantitative metrics with real-time trading decisions:
- **Executive Morning Briefing:** Synthesizes month-long forecast dynamics into commercially astute morning dispatches.
- **Risk-Adjusted Thermal Buffer Sizing:** Computes specific MW thermal procurement recommendations for the day-ahead wholesale auction based on desk risk tolerance:
  - **Conservative:** High buffer (+2,400 MW) to eliminate punitive cashout price exposure.
  - **Balanced:** Exactly neutralizes the +1,806 MW systematic overforecast bias.
  - **Aggressive:** Lower buffer (+1,350 MW) to reduce committed thermal capacity premiums.
- **High-Volatility Risk Alerts:** Flags extreme danger intervals (e.g. Storm Gorel on Jan 12 P3 with +6,885 MW overforecast) and prescribes immediate desk countermeasures.
- **Trader Shift Checklist & Q&A:** Generates 3-point operational protocols and accepts natural-language trader inquiries with one-click clipboard export.
- **Dual Engine Architecture:** Transparently executes against live **OpenAI GPT-4o-mini** when an API key is configured, with an automatic zero-latency fallback to an internal quantitative heuristic engine.

---

## 📊 January 2026 Quantitative Baseline Benchmarks

Evaluated across all 1,488 settlement periods (31 days × 48 half-hour intervals) of January 2026:

| Metric | Formula | Value (Jan 2026) | Operational Interpretation |
| :--- | :--- | :---: | :--- |
| **Mean Absolute Error (MAE)** | $\frac{1}{N}\sum \|F_i - A_i\|$ | **2,020.64 MW** | Average sizing error per half-hour period |
| **Root Mean Squared Error (RMSE)**| $\sqrt{\frac{1}{N}\sum (F_i - A_i)^2}$ | **2,481.38 MW** | Penalizes severe forecast misses |
| **Systematic Bias** | $\frac{1}{N}\sum (F_i - A_i)$ | **+1,806.23 MW** | Chronic **overforecast** tendency (forecast > actual) |
| **Weighted Absolute Percentage Error (WAPE)** | $\frac{\sum \|F_i - A_i\|}{\sum A_i}$ | **17.45%** | Volume-weighted national relative forecast error |
| **Potential Shortfall Volume** | $\sum \max(0, F_i - A_i) \times 0.5\,\text{h}$ | **1,423,598.0 MWh** | Cumulative generation deficit requiring thermal cover |
| **Data Completeness** | $\frac{N_{\text{valid}}}{N_{\text{expected}}}$ | **100.0%** | Zero missing half-hourly settlement intervals |

---

## 🏗️ Architecture & Technology Stack

```mermaid
flowchart LR
    User([Procurement Trader]) -->|Browser| UI[React 19 + TypeScript + Vite]
    UI -->|REST / JSON| API[FastAPI Application]
    API -->|In-Process| Cache[(In-Memory TTL Cache<br/>TTL: 3600s)]
    API -->|HTTPS| Elexon[Elexon BMRS Streams<br/>FUELHH: Actual Wind<br/>WINDFOR: Forecasts]
    API -.->|HTTPS (Optional)| OpenAI[OpenAI API<br/>GPT-4o-mini Copilot]
```

- **Frontend:** React 19, TypeScript, Vite, Vanilla CSS design tokens (responsive glassmorphic UI, custom accessible SVG time-series charts, zero heavyweight UI bloat).
- **Backend:** Python 3.12, FastAPI, Pydantic v2 data validation, Uvicorn ASGI server.
- **Data Integration:** Resilient HTTP client streaming half-hourly generation (`FUELHH`, fuelType `WIND`) and operational day-ahead forecasts (`WINDFOR`) from Elexon BMRS.
- **Containerization:** Multi-stage Docker image packaging the compiled React bundle into FastAPI's static mount for single-port (`8000`) production deployment.

---

## 📁 Repository Directory Structure

```text
├── Dockerfile                   # Multi-stage production container build (Vite + FastAPI)
├── README.md                    # Root documentation and project overview
├── compose.yaml                 # Multi-service local development stack (Vite :5173 + API :8000)
├── .env.example                 # Environment configuration template
├── .gitignore                   # Version control exclusion rules
│
├── backend/                     # FastAPI Backend Application
│   ├── app/
│   │   ├── main.py              # Application entrypoint, CORS, lifespan, SPA static mount
│   │   ├── core/
│   │   │   ├── config.py        # Typed application settings (Pydantic Settings)
│   │   │   └── cache.py         # Thread-safe in-memory TTL caching layer
│   │   ├── clients/
│   │   │   └── elexon.py        # Resilient Elexon BMRS API client with exponential backoff
│   │   ├── models/
│   │   │   └── schemas.py       # Pydantic domain models, requests, and metric responses
│   │   ├── routers/
│   │   │   ├── health.py        # /health/live and /health/ready endpoints
│   │   │   └── wind.py          # /api/v1/wind/timeseries, /metrics, and /quality endpoints
│   │   └── services/
│   │       ├── analytics.py     # Deterministic computation of MAE, RMSE, Bias, WAPE, Shortfall
│   │       └── wind_service.py  # Orchestration service applying 12:00 D-1 cutoff policy
│   ├── tests/                   # 113 Pytest unit, integration, and property tests
│   │   ├── test_analytics.py    # Mathematical correctness of metric formulations
│   │   ├── test_client.py       # Elexon HTTP client error handling and retry tests
│   │   ├── test_cutoff.py       # Gate-closure cutoff filtering verification
│   │   ├── test_endpoints.py    # FastAPI HTTP contract and schema tests
│   │   └── test_resilience.py   # Circuit breaker, upstream 5xx, and empty-set safety
│   ├── pyproject.toml           # Python package definitions and test configuration
│   └── verify_client.py         # Standalone Elexon API connectivity probe
│
├── frontend/                    # React + TypeScript + Vite Application
│   ├── src/
│   │   ├── App.tsx              # Main dashboard view with KPI scorecards, charts, and table
│   │   ├── App.css              # Custom styling, responsive layouts, glassmorphic palette
│   │   ├── index.css            # CSS custom properties, resets, typography
│   │   ├── components/
│   │   │   ├── MetricCards.tsx  # KPI cards with positive/negative color-coded indicators
│   │   │   ├── TimeSeriesChart.tsx # Custom SVG time-series visualization with tooltips
│   │   │   ├── ErrorAnalysis.tsx   # Peak error inspector & distribution analysis
│   │   │   └── SettlementTable.tsx # Paginated settlement period table with CSV export
│   │   ├── services/
│   │   │   └── api.ts           # Typed API client with graceful error handling
│   │   └── __tests__/           # 17 Vitest UI and component test suites
│   ├── package.json             # Frontend dependencies and npm scripts
│   ├── tsconfig.json            # Strict TypeScript configuration
│   └── vite.config.ts           # Vite bundler configuration with backend proxy
│
└── docs/                        # Complete Engineering Documentation
    ├── README.md                # Comprehensive master documentation hub
    ├── RELEASE_CANDIDATE_NOTES.md # Release verification notes and test evidence
    ├── AWS_CONSOLE_SETUP_GUIDE.txt # Step-by-step AWS Fargate deployment walkthrough
    ├── chat-summary.md          # Architectural decisions and trade-offs log
    ├── phase-0-decision-record.md # Baseline scope, cutoff definition, and ADRs
    ├── phase-2-discovery-notes.md # Real Elexon BMRS endpoint audit & payload schemas
    ├── wind_procurement_platform_plan.xlsx # 10-phase delivery roadmap, ADRs, risk register
    └── Wind Procurement Intelligence Architecture.png # System architecture diagram
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.12+**
- **Node.js 20+**
- **Docker Desktop** (optional, for containerized run)

### Method A: Run via Docker (Recommended)

1. **Build and run the unified container:**
   ```bash
   docker build -t wind-procurement-platform .
   docker run -p 8000:8000 wind-procurement-platform
   ```

2. **Access the application:**
   - **Web Dashboard:** [http://localhost:8000](http://localhost:8000)
   - **Interactive API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Liveness Probe:** [http://localhost:8000/health/live](http://localhost:8000/health/live)

---

### Method B: Run Locally for Development

1. **Configure Environment:**
   ```bash
   cp .env.example .env
   ```

2. **Backend Setup:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e 'backend[dev]'
   uvicorn app.main:app --app-dir backend --reload --port 8000
   ```

3. **Frontend Setup (in a separate terminal):**
   ```bash
   npm install --prefix frontend
   npm run dev --prefix frontend
   ```
   Open [http://localhost:5173](http://localhost:5173) (Vite proxies API calls to port 8000).

---

## 🧪 Test Suite Execution

The repository enforces complete test coverage across both backend and frontend:

### Backend Tests (118 Passing Tests)
```bash
.venv/bin/pytest backend/tests/ -v
```
- Validates mathematical correctness of MAE, RMSE, Bias, and WAPE.
- Tests strict 12:00 D-1 cutoff enforcement and rejection of look-ahead records.
- Verifies upstream HTTP timeout handling, retries, and in-memory TTL caching.
- Validates AI Trading Desk Copilot service, OpenAI integration, and deterministic fallback.

### Frontend Tests (19 Passing Tests)
```bash
npm test --prefix frontend
```
- Validates KPI scorecard rendering and numeric formatting.
- Verifies SVG chart rendering, tooltip interactivity, and date range filters.
- Verifies CSV export file generation and paginated table navigation.
- Validates AI Copilot briefing UI, risk tolerance toggles, and clipboard export.

### Production Build Verification
```bash
npm run build --prefix frontend
```
- Compiles TypeScript and builds minified production assets with zero warnings or errors.

---

## 🤖 AI Tool Disclosure

In accordance with Section 3.2 of the challenge brief, this project was developed with the assistance of AI agentic coding tooling (Google DeepMind Antigravity IDE). AI assistance was utilized for:
- Accelerating boilerplate generation for FastAPI routes and Pydantic schemas.
- Drafting initial mathematical metric calculation routines and property-based test matrices.
- Formatting comprehensive documentation, Architecture Decision Records (ADRs), and delivery tracking workbooks.

All architectural decisions, mathematical formulas, look-ahead bias cutoff logic, Elexon BMRS endpoint integrations, and test verifications were explicitly reviewed, validated, and verified against the challenge specification and live data.

---

## 📄 License

This project is licensed under the MIT License.
