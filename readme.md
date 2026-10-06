End-to-End Data Engineering & Analytics Platform

An end-to-end data engineering project designed to collect, process, transform and analyze surf conditions from multiple external data sources.

The project demonstrates how to build a production-oriented data pipeline combining Python, Apache Airflow, PostgreSQL, dbt, Docker and AWS, with a Streamlit analytics application consuming the resulting analytical data.

Live Demo

Streamlit Dashboard:
https://surfproject-7lqwunii9pg4f4wvqeqyot.streamlit.app/

The dashboard provides surf forecasts for several spots around the world, with local timezone handling, surfable daylight filtering, wave and wind conditions, and a spot-specific Surf Index.

Project Overview

The platform follows an end-to-end data engineering architecture:

Data Sources → Python Ingestion → PostgreSQL RAW → dbt → PostgreSQL ANALYTICS → Streamlit

Apache Airflow orchestrates the ingestion and transformation workflow, while Docker provides a reproducible execution environment deployed on AWS EC2.

The architecture separates data ingestion, storage, transformation and visualization, making the platform easier to maintain and extend.

Cost optimization was also a key design criterion: the technology stack and infrastructure were deliberately selected around free-tier and free-to-use solutions, allowing the entire project to operate with no recurring infrastructure cost.

Architecture

The platform is deployed on AWS EC2 using Docker Compose.

At the backend level:

Apache Airflow orchestrates the pipeline.

Python handles source-specific data ingestion.

PostgreSQL 18 stores surf data in both RAW and ANALYTICS schemas.

dbt transforms raw data through staging, intermediate and mart models.

PostgreSQL 16 stores Airflow metadata.

Docker Compose provides the containerized execution environment.

The Streamlit application is deployed separately on Streamlit Community Cloud and connects to the analytical PostgreSQL layer using a dedicated read-only database user.

<!-- Add the final architecture diagram here. -->

Data Sources & Ingestion

The platform combines multiple external sources to build a comprehensive view of surf conditions.

Source

Data

Role

Open-Meteo Weather API

Wind, temperature and atmospheric conditions

Weather conditions

Open-Meteo Marine API

Wave height, swell height, period and direction

Wave and swell conditions

Open-Meteo Historical Forecast API

Archived weather forecasts

Forecast history and analysis

Open Waters Tides API

Tide levels and high/low tide predictions

Tidal conditions

Sunrise / Sunset data

Local sunrise and sunset times

Surfable-hour filtering

Copernicus Marine Service

Oceanographic observations

Marine observation data

World Surf League (WSL)

Events, heats and competition results

Surf event context

Data Sources

Open-Meteo provides the main weather and marine forecast layer, including hourly weather variables and wave and swell conditions such as height, direction and period. Its Historical Forecast API is also used to support forecast-history analysis.

Open Waters provides tide predictions through an open API powered by the open-source Neaps harmonic prediction engine.

Copernicus Marine Service provides open marine datasets covering ocean physical, biogeochemical and wave conditions. The project uses its global in-situ observations as an additional oceanographic data source.

World Surf League data is ingested as complementary event information, providing context around professional surf competitions rather than forecast conditions.

Python Ingestion Layer

Each source is handled through dedicated Python ingestion modules responsible for retrieving, validating, normalizing and loading data into PostgreSQL.

The ingestion pattern is:

External Source → Python Connector → Validation & Normalization → PostgreSQL RAW

The RAW layer preserves source-level data before transformation, maintaining a clear separation between data acquisition and analytics logic.

This also makes individual connectors easier to maintain or replace without affecting downstream dbt models.

Historical Data

Historical forecast data is handled separately from the operational forecast pipeline to support analysis of forecast evolution and potential future forecast-error studies.

The ingestion layer is orchestrated by Apache Airflow, which schedules the source-specific tasks and triggers the dbt transformation once the ingestion phase is complete.

Apache Airflow Orchestration

Apache Airflow is the orchestration layer of the platform. It coordinates the ingestion jobs and ensures that the analytical transformation pipeline runs after the required source data has been collected.

The pipeline is implemented as a single DAG named surf_pipeline, scheduled to run daily.

Pipeline Workflow

The DAG follows this execution pattern:

Scheduled Run → Parallel Ingestion Tasks → dbt Build → Analytics Dataset

The ingestion tasks cover:

Weather data

Marine forecast data

Historical forecast data

Sunrise / sunset data

Tide data

WSL event data

Copernicus Marine data

Once ingestion completes successfully, Airflow triggers dbt build, which transforms the newly ingested data into the analytical models consumed by the dashboard.

Reliability & Scheduling

The DAG is configured with:

Daily scheduling with @daily

Automatic retries for failed tasks

5-minute retry delay

Maximum of 2 retries per task

catchup=False to avoid automatically processing historical scheduled runs

max_active_runs=1 to prevent overlapping pipeline executions

Date windows derived from the Airflow data interval to make ingestion runs reproducible

These mechanisms allow the pipeline to recover from temporary API or network failures without requiring manual intervention.

Airflow Execution Environment

Airflow runs inside the custom Docker image deployed on AWS EC2.

The image contains:

Apache Airflow

Python ingestion code

The dbt environment

Project configuration and dependencies

With LocalExecutor, ingestion and dbt tasks execute within the Airflow execution environment rather than through a separate worker cluster.

Separation of Responsibilities

The architecture deliberately separates orchestration from processing:

Airflow → Orchestration
Python → Data ingestion
PostgreSQL → Data storage
dbt → Data transformation
Streamlit → Analytics & visualization

dbt & Data Modeling

dbt (data build tool) is used as the transformation and data modeling layer.

Once ingestion has loaded source data into PostgreSQL, dbt transforms the raw datasets into structured analytical models.

The project follows a layered modeling approach:

RAW → STAGING → INTERMEDIATE → MARTS

Staging

The staging layer provides a clean interface between raw source tables and downstream models.

Staging models are responsible for:

Renaming and standardizing source columns

Casting data types

Normalizing timestamps and units

Creating consistent source-level interfaces

Applying lightweight source-specific transformations

Most staging models are materialized as views.

Intermediate

The intermediate layer combines and prepares datasets for the final analytical models.

It handles transformations such as:

Combining weather, marine and tide conditions

Applying local timezone conversions

Preparing daylight and surfable-hour information

Calculating intermediate surf-condition indicators

Joining spot-specific characteristics and scoring parameters

Intermediate models are also materialized as views to keep the transformation logic modular.

Marts

The mart layer contains the final analytical datasets consumed by Streamlit.

The main fact tables are:

fct_surf_hourly — hourly surf conditions, forecasts and calculated surf scores

fct_surf_daily — daily aggregated surf conditions and quality indicators

These models are materialized as tables to provide stable analytical datasets for dashboard queries.

The analytical layer also incorporates spot-specific characteristics and scoring parameters, allowing the same scoring framework to evaluate different surf spots according to their local conditions.

Data Quality & Testing

dbt is also used as a data quality layer.

The project includes automated tests covering:

Primary-key uniqueness

Non-null critical fields

Referential integrity

Accepted values

Model-level consistency

The complete dbt project currently executes successfully with 213 models and tests passing, with no errors or warnings.

Why dbt?

dbt creates a clear separation between data ingestion and data transformation.

Python collects and loads source data, while dbt manages SQL transformation logic, dependencies, testing and analytical models.

This makes the transformation layer:

Modular — transformations are split into focused models

Testable — data quality checks are automated

Traceable — model dependencies form a clear transformation graph

Maintainable — source-specific ingestion logic remains separated from analytical logic

From Raw Data to Surf Index

The Surf Index was not defined upfront as a fixed formula. It was developed progressively through data exploration, validation and iterative modeling of the available surf conditions.

The objective was to transform heterogeneous forecast data into a transparent and interpretable indicator of surf quality while keeping the underlying environmental conditions available for further analysis.

1. Exploring the Raw Data

The analysis focused on variables such as:

Wave and swell height

Wave and swell period

Wave and swell direction

Wind speed and direction

Wind gusts

Tide level and tidal phase

Sunrise and sunset

Local timezone

Forecast timestamps and data availability

This exploration helped identify which variables were consistently available and relevant across the selected surf spots.

2. Building a Unified Conditions Layer

The different datasets were combined into a common hourly representation of surf conditions.

The int_surf_conditions model provides this standardized layer by handling:

Timestamp alignment

Unit and data-type normalization

Wind and swell direction calculations

Local timezone conversion

Data completeness

Relationships between environmental variables

This separation was important: environmental conditions are modeled first, and scoring is applied afterwards.

3. Testing Different Scoring Approaches

Different environmental dimensions were initially considered independently, including:

Swell quality

Wind quality

Wave size

Tide suitability

The analysis showed that several variables could be grouped into broader components. Wave height, period and direction, for example, are all characteristics of the incoming swell and are more meaningful when evaluated together.

The model was therefore progressively simplified into three main components:

Swell → Wind → Tide

This provided a better balance between model interpretability and complexity.

4. Making the Model Spot-Specific

A single set of global thresholds would not accurately represent different surf spots.

Preferred swell direction, wind direction, wave size and tide can vary significantly depending on the characteristics and exposure of each location.

Spot-specific characteristics and scoring parameters were therefore introduced into the data model.

Rather than hard-coding these rules into the SQL transformations, the model uses parameter tables containing information such as:

Preferred swell directions

Preferred wind directions

Wave-height ranges

Preferred wave periods

Wind-speed thresholds

Tide preferences

This made the scoring engine parameter-driven and easier to calibrate.

5. Defining the Final Composite Index

The final V1 model was defined as:

Surf Index = 60% Swell + 25% Wind + 15% Tide

Each component is first normalized to a 0–100 score before being combined.

The swell component combines:

50% Wave Height + 25% Wave Period + 25% Wave Direction

The wind component combines:

60% Wind Direction + 40% Wind Speed

Tide remains a simplified spot-specific factor.

6. Validating the Results

The resulting scores were inspected across different spots and forecast periods to identify unexpected behavior, missing values and overly favorable or restrictive results.

This validation also revealed limitations in some of the first scoring rules. In particular, the initial tide logic could produce insufficient variation for certain spots.

The decision was therefore made to keep tide scoring spot-specific and parameter-driven, while leaving further calibration for a future version.

Additional validation included duplicate detection, null audits, score-range checks and dbt tests.

7. Keeping Forecast Quality Separate from Surf Quality

The project also explored the possibility of analyzing forecast evolution and forecast error using historical Open-Meteo forecasts.

This analysis is kept separate from the Surf Index itself.

The Surf Index answers:

How favorable are the predicted surf conditions?

Forecast-error analysis would answer:

How reliable is the forecast for this type of condition and location?

Keeping these concepts separate prevents environmental conditions from being mixed with forecast uncertainty.

Result

The final approach evolved through:

Raw external data
→ Data exploration
→ Standardized surf conditions
→ Candidate environmental indicators
→ Spot-specific parameters
→ Normalized component scores
→ Composite Surf Index
→ Quality bands

The result is a transparent, explainable scoring model rather than a black-box prediction system.

Surf Quality Scoring

The final Surf Index combines three normalized components into a single 0–100 score:

Surf Index = 60% Swell + 25% Wind + 15% Tide

Component

Breakdown

Swell — 60%

50% height, 25% period, 25% direction

Wind — 25%

60% direction, 40% speed

Tide — 15%

Spot-specific tidal suitability

The scoring parameters are spot-specific, allowing the model to account for differences in preferred swell direction, wind direction, wave size, period, wind speed and tide conditions.

The resulting score is converted into qualitative surf-quality bands used by the Streamlit dashboard.

All calculations are performed using local time and surfable daylight hours, ensuring that the recommendations correspond to the actual surfing window at each location.

The model is deliberately transparent and explainable: every Surf Index can be traced back to measurable swell, wind and tide conditions.

Streamlit Dashboard

The Streamlit application provides the user-facing analytics layer of the platform.

It connects to the PostgreSQL ANALYTICS layer and consumes fct_surf_hourly through a read-only database user.

The dashboard allows users to:

Select a surf spot and local date

View the daily Surf Index and overall quality

Identify the best surf window

Explore wave, swell and wind conditions

Visualize the hourly Surf Index

Understand how swell, wind and tide contribute to the score

Only surfable daylight hours are displayed as primary forecast results, using each spot's local timezone.

The application also uses data caching to reduce unnecessary database queries and improve responsiveness.

The dashboard is deployed on Streamlit Community Cloud, providing the user-facing interface for the AWS-hosted data platform.

Secrets and database credentials are securely managed through Streamlit Community Cloud secrets and are not stored in the repository.

PostgreSQL ANALYTICS → Streamlit → Interactive Surf Dashboard

AWS Deployment

The data platform is deployed on AWS EC2 in the eu-west-3 (Paris) region.

The backend runs on a single EC2 instance using Docker Compose, providing a reproducible environment for Airflow and PostgreSQL.

The deployment includes:

EC2 — compute environment

Docker Compose — container orchestration

PostgreSQL 18 — surf data storage

PostgreSQL 16 — Airflow metadata

Apache Airflow — pipeline orchestration

dbt — data transformation environment

Persistent Docker volumes preserve PostgreSQL data across container restarts and deployments.

The Streamlit application is deployed separately on Streamlit Community Cloud and connects to the AWS PostgreSQL analytics layer through a restricted read-only connection.

The infrastructure was deliberately kept lightweight to demonstrate a complete cloud deployment while avoiding unnecessary managed services and infrastructure costs.

Security

Security was considered at both the infrastructure and application levels.

AWS Security Groups restrict access to the required ports.

PostgreSQL is accessed by Streamlit through a dedicated read-only user.

The Streamlit user has access only to the analytics schema and cannot modify data.

Secrets and database credentials are kept outside the Git repository.

Streamlit credentials are managed through Streamlit Community Cloud secrets.

AWS credentials and private keys are excluded from version control.

This provides a simple security model based on least-privilege database access, restricted network exposure and external secret management.

Engineering & Reliability

The platform was designed with reliability and maintainability in mind.

Key engineering practices include:

Airflow retries to recover from temporary ingestion or API failures

Idempotent date-windowed ingestion to make scheduled runs reproducible

max_active_runs=1 to prevent overlapping pipeline executions

Persistent PostgreSQL volumes to preserve data across container restarts

Layered data architecture separating ingestion, storage, transformation and analytics

Read-only database access for the Streamlit application

Containerized execution to ensure a reproducible deployment environment

Automated dbt testing before analytical data is exposed to the dashboard

These design choices aim to make the platform reproducible, recoverable and maintainable, while keeping the infrastructure deliberately lightweight.

Engineering Decisions & Future Improvements

The project was deliberately designed as a lightweight but complete data platform, prioritizing simplicity, transparency and cost efficiency over unnecessary infrastructure complexity.

Key decisions included:

Using PostgreSQL as both the raw and analytical storage layer

Using Airflow for orchestration and dbt for transformations

Running the backend on a single Dockerized EC2 instance

Keeping the Streamlit application separate from the data platform

Using parameter-driven scoring instead of a black-box machine learning model

Selecting mostly free or open-source technologies to avoid recurring infrastructure costs

Future Improvements

Several improvements could extend the platform further:

Calibrate the Surf Index using historical observed surf conditions

Integrate forecast-error analysis to estimate forecast reliability

Expand the number of surf spots and data sources

Improve tide modeling using more detailed spot-specific rules

Introduce automated monitoring and alerting for pipeline failures

Explore machine learning models once sufficient historical data is available

The project provides a foundation that can progressively evolve from a portfolio data platform into a more advanced forecast analysis and decision-support system.