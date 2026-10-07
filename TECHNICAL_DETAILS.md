# Technical Deep Dive

This document explains the main engineering choices behind the Surf Data Platform, what was implemented with each technology, and the practical challenges encountered while building and deploying the project.

The goal is not to describe the tools generically, but to document how they are used in this project and the trade-offs that shaped the final architecture.

## Architecture at a Glance

```text
External APIs
    ↓
Python ingestion
    ↓
PostgreSQL RAW
    ↓
dbt staging / intermediate / marts
    ↓
PostgreSQL ANALYTICS
    ↓
Streamlit

Apache Airflow orchestrates the daily workflow.
Docker Compose runs the backend stack on AWS EC2.
```

The production-oriented daily pipeline currently uses five operational data feeds:

- Open-Meteo weather
- Open-Meteo marine
- Open-Meteo previous-run forecast history
- Sunrise / sunset data
- Open Waters tides

Copernicus Marine and World Surf League connectors were also developed and remain in the repository as complementary sources, but they were deliberately removed from the critical daily Airflow path.

---

## 1. Python — Data Ingestion Layer

### Role in the platform

Python is responsible for extracting data from external APIs, normalizing provider responses and loading the results into the PostgreSQL `RAW` schema.

Each provider has its own ingestion module so that API-specific logic remains isolated from orchestration and analytical transformations.

The operational ingestion layer covers:

- weather forecasts
- marine forecasts
- historical forecast runs
- sunrise / sunset data
- tide station discovery and tide predictions

The repository also contains experimental Copernicus Marine and WSL connectors.

### What I implemented

The ingestion pattern is deliberately consistent across sources:

```text
Extract → Transform → Load
```

API calls use explicit timeouts and HTTP error handling. Source timestamps are normalized to UTC before storage, while local timezone conversion is deferred to the analytical layer.

Database loads use PostgreSQL upserts with `ON CONFLICT ... DO UPDATE`. This makes scheduled runs idempotent: rerunning the same date window refreshes existing rows instead of creating duplicates.

Examples of natural keys include:

- `(spot_id, observation_time)` for weather and marine forecasts
- `(spot_id, observation_time, forecast_horizon_days)` for historical forecast runs
- `(spot_id, observation_date)` for sunrise / sunset data
- `(tide_station_id, observation_time)` for tide observations

The ingestion orchestration wrapper also handles failures per spot. A failed API call rolls back the current transaction, logs the error and allows the task to attempt the remaining spots before raising an aggregated error.

### Tide station discovery

Tide ingestion required more than a simple API call. For each surf spot, the pipeline:

1. checks whether a tide station is already mapped,
2. searches nearby stations if no mapping exists,
3. filters for stations allowing commercial use,
4. selects the closest valid station,
5. stores the mapping in PostgreSQL,
6. reuses it on future runs.

This avoids repeatedly rediscovering the same station and makes the mapping deterministic.

### Main challenges

**Different provider structures.** Weather, marine, daylight and tide APIs expose different schemas, timestamps and granularities. I kept source-specific parsing in Python and standardized the data only after loading it into RAW.

**Retry-safe ingestion.** Because Airflow may retry a task, ingestion could not assume that a date window would only be processed once. PostgreSQL upserts made the pipeline safe to rerun.

**Partial provider failure.** A single failing spot should not hide successful processing for every other spot. The ingestion wrapper therefore records failures while still attempting all configured spots.

**Complementary sources were not reliable enough for the critical path.** Copernicus did not provide suitable coverage for all five reference spots, while the WSL source is based on event-result scraping rather than operational forecast data. Their connectors were kept for future analysis, but they were removed from the daily production DAG.

### What this demonstrates

Python in this project is used as an integration and reliability layer rather than simply for data analysis: API integration, normalization, transaction handling, logging, idempotent loading and reusable orchestration entrypoints.

---

## 2. Apache Airflow — Orchestration

### Role in the platform

Airflow coordinates the daily execution of the platform.

The `surf_pipeline` DAG currently runs five ingestion tasks in parallel:

```text
ingest_weather ───────────┐
ingest_marine ────────────┤
ingest_forecast ──────────┤
ingest_sunrise_sunset ────┼──→ dbt_build
ingest_tides ──────────────┘
```

The dbt transformation step runs only after every core ingestion task succeeds.

### Reliability configuration

The DAG uses:

- daily scheduling with `@daily`
- two retries
- a five-minute retry delay
- `catchup=False`
- `max_active_runs=1`

The last setting prevents overlapping executions from writing the same forecast window simultaneously.

### Retry-stable date windows

A subtle orchestration issue was making API windows reproducible across retries.

Using the current wall-clock time inside a task would mean a retry on another day could request a different dataset. Instead, the DAG derives `start_date` and `end_date` from the Airflow DAG run data interval.

A retry therefore receives exactly the same seven-day window as the original attempt.

### Regression tests

The DAG has an offline regression test suite that validates:

- the exact task set
- dependencies between ingestion and dbt
- absence of cycles
- schedule and retry configuration
- retry-stable date windows
- dbt dependency on all ingestion tasks
- direct mapping between Airflow tasks and Python callables
- absence of external side effects during DAG import

The current suite contains seven passing DAG tests.

### Main challenges

**Non-critical tasks blocked the whole pipeline.** The first version of the DAG also contained WSL and Copernicus ingestion. A Copernicus timeout caused the task to fail, which made `dbt_build` upstream-failed and left the analytics mart stale even though the core forecast sources had succeeded.

The solution was architectural rather than simply increasing the timeout: WSL and Copernicus were removed from the critical DAG because they are complementary, not required for the operational forecast.

**Testing the DAG without performing real API/database calls.** The regression tests load the DAG with Airflow operator stubs and mock external side effects. This allows structural testing without requiring a running Airflow metadata database or external API connectivity.

**Python environment confusion during debugging.** The custom image contains both the Airflow Python environment and a separate dbt virtual environment. Because the dbt venv is added to `PATH`, the interactive `python` command resolves to the dbt interpreter, while the `airflow` executable uses the system Airflow Python interpreter. This was identified while running the DAG tests and is now understood as an intentional environment separation rather than a missing dependency.

### What this demonstrates

The Airflow layer shows orchestration design, task dependency management, reproducible scheduling, retry behavior, failure isolation and regression testing.

---

## 3. AWS EC2 — Cloud Runtime

### Role in the platform

The backend is deployed on a single AWS EC2 instance in `eu-west-3` (Paris).

The current architecture uses:

- Ubuntu 26.04 LTS
- an `m7i-flex.large` instance
- Docker Compose for service management
- persistent Docker volumes for databases and Airflow state

The EC2 instance hosts the backend only. Streamlit is deployed separately on Streamlit Community Cloud.

### Why a single EC2 instance

For a portfolio project, the objective was to demonstrate a real cloud deployment while keeping the architecture understandable and operating costs low.

A single Dockerized EC2 instance avoids introducing managed services only for architectural complexity. It also makes the whole backend reproducible from the repository.

This is an intentional trade-off: the platform demonstrates deployment and service separation, but it is not designed as a highly available multi-node production cluster.

### Security choices

The deployment follows a least-privilege approach:

- SSH access is restricted through the EC2 security group
- PostgreSQL is only exposed where required for the external Streamlit application
- Streamlit uses a dedicated read-only PostgreSQL account
- that account can access the `ANALYTICS` schema but not the `RAW` schema
- Airflow metadata remains in its own database
- secrets are stored outside Git

### Main challenges

**Turning a local project into a persistent cloud service.** The project originally ran locally. Moving it to EC2 required separating local host assumptions from container networking, persistent database storage and external application access.

**Cost versus architecture.** Managed PostgreSQL, Kubernetes or multiple EC2 nodes would have increased complexity and cost without materially improving the portfolio objective. The final design intentionally favors a small but complete platform.

**Operational debugging.** Once the project was remote, diagnosing issues required distinguishing Git state, host filesystem state, container state, database state and Airflow state. This led to a more disciplined deployment workflow: inspect first, modify only the layer that is actually responsible.

### What this demonstrates

The EC2 deployment shows that the project was not limited to local development: it includes Linux administration, networking, cloud security, persistent runtime services and deployment trade-offs.

---

## 4. Docker & Docker Compose — Runtime Isolation

### Role in the platform

Docker Compose packages the backend into independent services:

- PostgreSQL 18 for surf data
- PostgreSQL 16 for Airflow metadata
- Airflow API server
- Airflow scheduler
- Airflow DAG processor

The Airflow services use the same custom image.

### Custom Airflow image

The image is based on:

```text
apache/airflow:3.3.2-python3.14
```

It contains:

- Airflow ingestion dependencies
- the Python ingestion source code
- the Airflow DAG
- the dbt project
- a dedicated dbt virtual environment

dbt is intentionally installed in `/home/airflow/dbt-venv` so dbt dependencies remain separated from Airflow's Python dependency set.

### Local versus AWS networking

The Compose configuration supports two environments:

- local development, where containers may reach PostgreSQL through `host.docker.internal`
- AWS, where services reach the surf database through the Docker service name `surf-db`

This avoided hard-coding one networking assumption into application code.

### Persistent volumes

Named volumes persist:

- surf PostgreSQL data
- Airflow metadata
- Airflow logs
- Airflow authentication state

This allows containers to be recreated without losing database state.

### Main challenge: bind-mount permissions

One of the most useful deployment incidents involved dbt.

The project directory `./surf_dbt` is bind-mounted into the Airflow containers. Although the Dockerfile runs `chown` while building the image, a bind mount replaces those image-layer files at runtime with the host filesystem.

The host had created:

- `surf_dbt/logs/`
- `surf_dbt/target/`

with ownership incompatible with the Airflow container user (UID 50000).

The result was two successive dbt failures:

```text
PermissionError: ... surf_dbt/logs/dbt.log
PermissionError: ... surf_dbt/target/partial_parse.msgpack
```

The fix was to set ownership of the generated dbt directories to the Airflow UID/group. After that, dbt successfully recreated its artifacts as `50000:root`.

Both directories are ignored by Git, so normal `git pull` operations do not overwrite the corrected runtime ownership.

### What this demonstrates

Docker is used here for service isolation, reproducible dependencies, persistent state and environment portability. The permissions incident also demonstrates understanding of the difference between image-layer ownership and runtime bind-mount ownership.

---

## 5. PostgreSQL — Operational and Analytical Storage

### Two separate PostgreSQL services

The project deliberately uses two PostgreSQL instances:

**PostgreSQL 18 — surf data**

Database: `surf_data`

Main schemas:

```text
RAW
ANALYTICS
```

**PostgreSQL 16 — Airflow metadata**

This stores scheduler and DAG execution state separately from the application data.

Separating them prevents orchestration metadata from becoming mixed with the analytical model.

### RAW and ANALYTICS separation

The `RAW` schema stores source-level data loaded by Python.

The `ANALYTICS` schema contains dbt-generated staging/intermediate views and analytical marts.

This creates a clear ownership boundary:

```text
Python owns RAW writes
dbt owns analytical transformations
Streamlit reads ANALYTICS
```

### Idempotent writes

Python ingestion relies on PostgreSQL constraints and `ON CONFLICT` upserts.

This was important for scheduled automation because the same forecast horizon is intentionally refreshed every day and Airflow retries must not create duplicate rows.

### Read-only application access

Streamlit does not connect with the ingestion/database owner account.

A dedicated role was created with:

- permission to connect to `surf_data`
- `USAGE` on `ANALYTICS`
- `SELECT` on current and future analytical objects
- no RAW access
- no INSERT privileges
- no CREATE privileges in ANALYTICS
- a restricted connection limit

This reduces the impact of a frontend compromise and keeps the presentation layer read-only by design.

### Main challenges

**Exposing a database safely to an external frontend.** Streamlit Community Cloud runs outside the EC2 Docker network, so PostgreSQL must be reachable externally while still remaining restricted. This required combining PostgreSQL roles with AWS Security Group rules rather than relying on database credentials alone.

**Keeping operational and analytical concerns separate.** Using distinct schemas and a separate Airflow metadata database makes it easier to reason about permissions, ownership and troubleshooting.

### What this demonstrates

PostgreSQL is used as more than simple storage: relational constraints, upserts, schema boundaries, access control, service separation and persistent cloud storage are all part of the design.

---

## 6. dbt — Transformation, Modeling and Data Quality

### Role in the platform

dbt owns the SQL transformation layer.

The project follows a layered structure:

```text
RAW
 ↓
STAGING
 ↓
INTERMEDIATE
 ↓
MARTS
```

Materialization strategy:

- staging → views
- intermediate → views
- marts → tables

The final marts are stable datasets optimized for dashboard consumption.

### Main models

Key analytical models include:

- `int_surf_conditions`
- `fct_surf_hourly`
- `fct_surf_daily`

The hourly mart is the main source consumed by Streamlit.

### Timezone handling

The source APIs are stored as UTC instants.

Surfing decisions, however, are local: sunrise, sunset and the selected calendar day depend on the surf spot timezone.

The transformation layer therefore keeps the original UTC `observation_time` and derives:

- `local_observation_time`
- `local_date`
- localized sunrise / sunset values
- `is_daylight`
- `is_surfable_light`

The five configured spots span multiple timezones, including Europe/Paris, Asia/Makassar, Australia/Melbourne, Pacific/Fiji and Pacific/Honolulu.

### Surf scoring

The Surf Index is intentionally transparent rather than machine-learning based.

```text
Surf Index = 60% Swell + 25% Wind + 15% Tide
```

The swell component combines:

- height
- period
- direction

Wind scoring combines:

- direction relative to the spot orientation
- wind speed

Tide scoring uses the position within the local tidal cycle and spot-specific parameters.

Spot preferences are stored as data rather than hard-coded globally, so different surf locations can use different swell, wind and tide characteristics.

### Data quality

The dbt project includes schema tests, custom generic tests and singular SQL tests covering areas such as:

- uniqueness
- non-null critical fields
- accepted values
- relationships
- physical value ranges
- angular ranges
- model grain
- tide score consistency

The validated build used in the deployed pipeline completed with:

```text
PASS=213
WARN=0
ERROR=0
SKIP=0
TOTAL=213
```

### Main challenges

**Timezone correctness.** Initially, UTC and local civil time could easily be mixed when joining solar data and filtering surfable hours. The solution was to preserve UTC as the canonical instant and derive explicit local-time columns using each spot's timezone.

**Tide availability at the forecast edge.** Tide calculations require surrounding turning points. At the edge of the available observation window, the next turning point may be missing, which makes the tide score unreliable. The mart therefore tracks the last reliable tide observation per spot and excludes later hours.

**A score that looked too optimistic.** Early scoring produced many Optimal / Very Good hours. Instead of hiding this, the scoring logic was kept parameter-driven and interpretable so it can be calibrated iteratively with historical evidence later.

**Experimental data sources inside dbt.** WSL and Copernicus models remain in the project because they represent completed exploration work, even though their ingestion is no longer on the critical daily path. This keeps the work reusable without making operational refresh reliability depend on those sources.

### What this demonstrates

The dbt layer shows dimensional thinking, layered SQL modeling, data quality testing, timezone-aware analytics, parameter-driven business logic and an explicit separation between forecast conditions and future forecast-reliability analysis.

---

## 7. Streamlit — Analytical Presentation Layer

### Role in the platform

Streamlit is the public-facing layer of the platform.

It is intentionally thin: the application does not reproduce the scoring logic in Python. It reads the final analytical mart produced by dbt and focuses on filtering, presentation and explanation.

### What the dashboard provides

Users can:

- select a surf spot
- select an available local forecast day
- view only surfable daylight hours
- see the daily average Surf Index
- identify the best hour and best hourly quality
- compare wave and swell height
- inspect hourly Surf Index evolution
- understand swell, wind and tide contributions
- inspect detailed hourly data

Queries are cached for 15 minutes to reduce repeated database load.

### Timezone-aware display

The database stores UTC timestamps, but Streamlit displays the dbt-generated local timestamps.

A useful edge case appeared with Pipeline in Hawaii: a UTC forecast window beginning on the current UTC day can legitimately contain hours belonging to the previous local calendar day.

The dashboard therefore respects the spot's actual `local_date` instead of forcing every location to begin on the same calendar date.

### Incomplete final-day handling

The opposite edge occurs at the end of the seven-day UTC forecast window. Depending on timezone, a final local calendar day may exist with only a few hours of data.

Rather than exposing a selectable day that appears incomplete to the user, the dashboard checks the maximum local hour for the final date and removes that date from the selector if the local day does not reach the end of the day.

### Security

The app is deployed separately on Streamlit Community Cloud and connects to PostgreSQL using the dedicated read-only account.

Secrets are provided through Streamlit's secrets configuration, with environment-variable fallback for local development.

### Portfolio role

The dashboard is deliberately more than a charting layer. Its explanations describe:

- how the Surf Index is built
- how wave and swell differ
- how timezones are handled
- how the backend is structured
- what the model intentionally does not attempt to predict

This allows the application to act as a live demonstration of the wider data platform.

### What this demonstrates

Streamlit shows analytical application development, secure database consumption, caching, timezone-aware UX and the ability to translate technical data products into an understandable interface.

---

## Cross-Cutting Engineering Lessons

### 1. Reliability is often an architecture problem

When Copernicus failures blocked dbt, the best fix was not a larger timeout. The dependency itself was wrong: a complementary source should not determine whether core forecast analytics refresh successfully.

### 2. UTC storage and local business time should be separate concepts

UTC is the right canonical timestamp for storage and joins, while local civil time is the right concept for surfable hours and user-facing dates.

Keeping both explicitly avoids hidden timezone assumptions.

### 3. Idempotence is essential for orchestration

Scheduled workflows retry. Reprocessing the same window must therefore be safe. Natural keys and PostgreSQL upserts were designed into the ingestion layer rather than added as an afterthought.

### 4. Container images do not control bind-mounted filesystem ownership

The dbt permission incident demonstrated that runtime mounts can override image-layer ownership. Debugging containerized systems requires checking the host filesystem as well as the Dockerfile.

### 5. Presentation should consume modeled data, not reimplement business logic

Surf scoring, timezone logic and data-quality decisions belong in dbt. Streamlit should consume the analytical contract and present it.

This keeps the scoring reusable by any future consumer, not only the current dashboard.

### 6. Simplicity was an explicit design constraint

The project could have used managed databases, Kubernetes, distributed workers or a much larger cloud architecture.

For this scope, a single EC2 instance with Docker Compose demonstrates the complete lifecycle while keeping the system understandable, affordable and maintainable.

---

## Current Limitations and Next Steps

The current platform is intentionally a V1.

The most valuable future improvements are:

- calibrating the Surf Index against historical observed conditions
- measuring forecast error by forecast horizon
- separating experimental WSL / Copernicus models into optional dbt selections
- adding automated CI for Python, Airflow and dbt validation
- adding pipeline monitoring and alerting
- extending the number of surf spots
- improving spot-specific tide modeling
- evaluating machine learning only once enough historical ground-truth data exists

The objective is to keep each future improvement evidence-driven rather than adding complexity only for the sake of the technology stack.
