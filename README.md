# End-to-End Data Engineering & Analytics Platform

> A production-oriented data platform that ingests, stores, transforms and analyzes multi-source marine and weather data, using **surf forecasting** as the use case.

**Stack:** Python · Apache Airflow · PostgreSQL · dbt · Docker Compose · AWS EC2 · Streamlit · Caddy

### 🔗 [Live Demo — Streamlit Dashboard](https://surf-project.duckdns.org/)

![End-to-End Data Engineering Architecture: Python ingestion, Airflow orchestration, PostgreSQL RAW and ANALYTICS, dbt transformations, Streamlit dashboard and Caddy HTTPS reverse proxy, deployed with Docker on AWS EC2](Surf_Data_TA-1.png)

## Overview

This project brings together data engineering, analytical modeling and cloud deployment to turn marine and weather forecasts into local surf insights.

It demonstrates:

- **End-to-end pipeline** — ingestion, storage, transformation, data quality checks and consumption
- **API integration** — five operational data feeds, with additional experimental WSL and Copernicus connectors
- **Orchestration** — a scheduled Airflow DAG with retries and overlap protection
- **Data modeling** — layered dbt models (staging → intermediate → marts) with automated tests
- **Cloud deployment** — Data pipeline and Streamlit dashboard on AWS EC2, with HTTPS served by Caddy
- **Security** — least-privilege, read-only database access and externalized secrets
- **Analytics** — a transparent, parameter-driven, spot-specific Surf Index

## Architecture

```text
Data Sources
    ↓
Python Ingestion
    ↓
PostgreSQL RAW
    ↓
dbt Transformations
    ↓
PostgreSQL ANALYTICS
    ↓
Streamlit
```

| Layer | Technology | Responsibility |
|-------|------------|----------------|
| Orchestration | Apache Airflow | Schedules ingestion, then triggers `dbt build` |
| Ingestion | Python | Retrieves, validates, normalizes and loads source data |
| Storage | PostgreSQL 18 | `RAW` and `ANALYTICS` schemas (surf data) |
| Transformation | dbt | Staging, intermediate and mart models, plus tests |
| Application | Streamlit | User-facing analytics layer |
| Runtime | Docker Compose on AWS EC2 | Airflow, PostgreSQL, dbt environment, Streamlit and Caddy |
| Airflow metadata | PostgreSQL 16 | Separate database for Airflow state |
| Web access | Caddy | HTTPS termination, automatic certificates and reverse proxy to Streamlit |
| DNS | DuckDNS | Free subdomain pointing to the EC2 public IPv4 address |

Each layer has a defined responsibility, allowing ingestion, modeling and presentation to evolve independently.

## Data Sources & Ingestion

| Source | Data | Role |
|--------|------|------|
| Open-Meteo Weather API | Wind, temperature, atmospheric conditions | Weather conditions |
| Open-Meteo Marine API | Wave and swell height, period, direction | Wave and swell conditions |
| Open-Meteo Historical Forecast API | Archived weather forecasts | Forecast history and analysis |
| Open Waters Tides API | Tide levels, high/low tide predictions | Tidal conditions |
| Sunrise / sunset data | Local sunrise and sunset times | Surfable-hour filtering |
| Copernicus Marine Service | Global in-situ oceanographic observations | Experimental marine observation source |
| World Surf League (WSL) | Events, heats, competition results | Experimental surf event context source |

Open Waters supplies tide predictions through the open-source Neaps harmonic prediction engine. Copernicus Marine and WSL remain experimental connectors outside the daily pipeline.

Each source is handled by a dedicated Python module:

```text
External Source → Python Connector → Validation & Normalization → PostgreSQL RAW
```

The `RAW` layer preserves source-level data before any transformation. Connectors can therefore be maintained or replaced without affecting downstream dbt models.

A dedicated historical forecast feed supports future analysis of how predictions evolve with forecast lead time.

## Orchestration with Apache Airflow

Airflow coordinates the ingestion jobs and ensures that the transformation runs only after source data has been collected. The pipeline is a single DAG, `surf_pipeline`, scheduled daily:

```text
Scheduled Run → Parallel Ingestion Tasks → dbt build → Analytics Dataset
```

The DAG coordinates five ingestion feeds before running `dbt build`, so analytical models are refreshed only after ingestion succeeds.

**Reliability settings**

| Setting | Purpose |
|---------|---------|
| `@daily` schedule | Daily refresh |
| 2 retries, 5-minute delay | Recover from temporary API or network failures |
| `catchup=False` | Avoid automatically processing historical scheduled runs |
| `max_active_runs=1` | Prevent overlapping executions |
| Date windows from the Airflow data interval | Reproducible ingestion runs |

Airflow uses `LocalExecutor` and a custom Docker image containing the ingestion code, dbt environment and required dependencies.

## Transformation & Data Modeling with dbt

dbt organizes SQL transformations into three layers with explicit dependencies and automated data quality checks.

```text
RAW → STAGING → INTERMEDIATE → MARTS
```

| Layer | Materialization | Responsibility |
|-------|-----------------|----------------|
| Staging | Views | Rename and standardize columns, cast types, normalize timestamps and units, light source-specific transformations |
| Intermediate | Views | Combine weather, marine and tide data; convert to local timezones; prepare daylight and surfable hours; compute intermediate indicators; join spot characteristics and scoring parameters |
| Marts | Tables | Final datasets consumed by Streamlit |

**Main fact tables**

- `fct_surf_hourly` — hourly surf conditions, forecasts and calculated surf scores
- `fct_surf_daily` — daily aggregated conditions and quality indicators

### Data Quality & Testing

Automated dbt tests cover primary-key uniqueness, non-null critical fields, referential integrity, accepted values and model-level consistency. A validated `dbt build` completed with **189 data tests and 24 seed/model executions passing**, with no errors or warnings.

Tests run alongside model builds to detect data issues in the analytical layer.

### Why dbt?

- **Modular** — transformations are split into focused models
- **Testable** — data quality checks are automated
- **Traceable** — model dependencies form a clear transformation graph
- **Maintainable** — ingestion logic stays separate from analytical logic

## Surf Quality Scoring

The Surf Index is a rule-based score from 0 to 100, combining swell, wind and tide suitability. It is an interpretable heuristic rather than a machine learning model.

```text
Surf Index = 60% Swell + 25% Wind + 15% Tide
```

| Component | Weight | Breakdown |
|-----------|--------|-----------|
| Swell | 60% | 50% height, 25% period, 25% direction |
| Wind | 25% | 60% direction, 40% speed |
| Tide | 15% | Spot-specific tidal suitability (simplified in V1) |

Each component is normalized to a 0–100 score before being combined, and the result is converted into qualitative quality bands used by the dashboard.

**Spot-specific parameters.** A single set of global thresholds cannot represent different spots. Rather than hard-coding rules in SQL, parameter tables define, for each spot:

- preferred swell and wind directions
- wave-height ranges and preferred wave periods
- wind-speed thresholds
- tide preferences

Parameters can be calibrated without rewriting the scoring logic. Daily summaries use local time and surfable daylight hours.

### Design Process

The scoring methodology was developed through five steps:

1. **Exploration** — assessed coverage and consistency of wave, swell, wind, tide and daylight variables across the five spots.
2. **Unified conditions layer** — built `int_surf_conditions` to align timestamps, standardize units and combine source data before scoring.
3. **Simplification** — grouped indicators into swell, wind and tide components to balance explanatory value and complexity.
4. **Validation** — inspected scores across spots and forecast periods, supported by duplicate, null and range checks. Tide scoring remains simplified and requires further calibration.
5. **Forecast reliability** — kept condition suitability separate from forecast uncertainty; historical forecast-error analysis is a planned extension.

## Streamlit Dashboard

Streamlit is the user-facing analytics layer. It reads `fct_surf_hourly` from the PostgreSQL `ANALYTICS` schema through a dedicated read-only user, and caches queries to reduce database load.

The dashboard allows users to:

- select a surf spot and local date
- view the daily Surf Index and overall quality
- identify the best surf window
- explore wave, swell and wind conditions
- visualize the hourly Surf Index and see how swell, wind and tide contribute to it

Forecasts are displayed in each spot's local timezone, with primary results limited to surfable daylight hours.

## Deployment & Infrastructure

The platform runs on a single **AWS EC2 m7i-flex.large** instance (2 vCPU, 8 GiB RAM) in `eu-west-3` (Paris), managed with **Docker Compose**:

- Apache Airflow — pipeline orchestration
- PostgreSQL 18 — surf data (`RAW` and `ANALYTICS`)
- PostgreSQL 16 — Airflow metadata
- dbt — transformation environment within the Airflow image
- Streamlit — dashboard in a separate application container
- Caddy — public HTTPS reverse proxy

Persistent Docker volumes preserve PostgreSQL data across container restarts and deployments.

The dashboard connects to PostgreSQL over the internal Docker network. Streamlit and Caddy have automatic restart policies, and the application remains active while the instance and services are running.

### HTTPS with Caddy

Caddy provides the public HTTPS entry point, redirects HTTP traffic and proxies browser requests and WebSocket connections to Streamlit. It automatically obtains and renews TLS certificates, with certificate state stored in persistent Docker volumes. Streamlit's application port is accessible only within the Docker network.

DuckDNS supplies the free public subdomain mapped to the EC2 instance.

## Security

The security model is simple and based on least privilege:

- Public web access uses ports 80/443, controlled by AWS Security Groups
- Streamlit uses a dedicated PostgreSQL user with read-only access to the `ANALYTICS` schema only
- Database credentials are kept outside the Git repository; Streamlit secrets are mounted read-only from a protected server-side TOML file
- AWS credentials and private keys are excluded from version control

## Engineering Decisions

The main technical choices balance maintainability, interpretability and operating costs.

| Decision | Rationale |
|----------|-----------|
| PostgreSQL for both `RAW` and `ANALYTICS` | Simple, low-cost storage with clear schema separation |
| Airflow for orchestration, dbt for transformation | Each tool does one job; ingestion and analytics logic stay decoupled |
| Single Dockerized EC2 instance | Reproducible deployment without managed-service cost |
| Streamlit in a separate container on the same EC2 instance | Simple deployment with internal database access and no inactivity-based dashboard suspension |
| Caddy in front of Streamlit | Automatic HTTPS and a single public web entry point |
| Parameter-driven scoring instead of machine learning | Transparent, explainable and easy to calibrate |
| Free or open-source technologies | Minimize recurring infrastructure cost |

## Future Improvements

- Calibrate the Surf Index using historical observed surf conditions
- Integrate forecast-error analysis to estimate forecast reliability
- Expand the number of surf spots and data sources
- Improve tide modeling with more detailed spot-specific rules
- Introduce automated monitoring and alerting for pipeline failures
- Explore machine learning models once sufficient historical data is available

These extensions are planned and are not part of the current implementation.
