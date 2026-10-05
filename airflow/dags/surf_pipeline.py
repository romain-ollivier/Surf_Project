"""Daily surf-data ingestion followed by the dbt project build.

The ingestion callables own their provider logic and database connections.
All date-windowed tasks use the same UTC Airflow data-interval boundary, so a
retry of a DAG run receives the same window. WSL ingestion is event-configured
and therefore does not receive dates.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import shlex
import sys

from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DBT_PROJECT_DIR = REPOSITORY_ROOT / "surf_dbt"

if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.ingestion.airflow_jobs import (
    ingest_copernicus,
    ingest_forecast,
    ingest_marine,
    ingest_sunrise_sunset,
    ingest_tides,
    ingest_weather,
    ingest_wsl,
)


def _date_window_kwargs():
    """Return identical, retry-stable date templates for ingestion tasks."""
    start_date = "{{ (dag_run.data_interval_start if dag_run.data_interval_start else dag_run.run_after) | ds }}"
    end_date = "{{ macros.ds_add((dag_run.data_interval_start if dag_run.data_interval_start else dag_run.run_after) | ds, 7) }}"
    return {
        "start_date": start_date,
        "end_date": end_date,
    }


default_args = {
    "owner": "surf-data",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


with DAG(
    dag_id="surf_pipeline",
    description="Ingest surf forecast sources and build the dbt analytics project.",
    doc_md=__doc__,
    default_args=default_args,
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    tags=["surf", "ingestion", "dbt"],
) as dag:
    ingest_weather_task = PythonOperator(
        task_id="ingest_weather",
        python_callable=ingest_weather,
        op_kwargs=_date_window_kwargs(),
        doc_md="Fetch, transform, and load Open-Meteo weather data for all spots.",
    )

    ingest_marine_task = PythonOperator(
        task_id="ingest_marine",
        python_callable=ingest_marine,
        op_kwargs=_date_window_kwargs(),
        doc_md="Fetch, transform, and load Open-Meteo marine data for all spots.",
    )

    ingest_forecast_task = PythonOperator(
        task_id="ingest_forecast",
        python_callable=ingest_forecast,
        op_kwargs=_date_window_kwargs(),
        doc_md="Fetch, transform, and load previous-run forecast data for all spots.",
    )

    ingest_sunrise_sunset_task = PythonOperator(
        task_id="ingest_sunrise_sunset",
        python_callable=ingest_sunrise_sunset,
        op_kwargs=_date_window_kwargs(),
        doc_md="Fetch and load sunrise/sunset data for all spots.",
    )

    ingest_tides_task = PythonOperator(
        task_id="ingest_tides",
        python_callable=ingest_tides,
        op_kwargs=_date_window_kwargs(),
        doc_md="Resolve tide stations and load their observations for all spots.",
    )

    ingest_wsl_task = PythonOperator(
        task_id="ingest_wsl",
        python_callable=ingest_wsl,
        doc_md="Fetch and load every event configured in the WSL ingestion module.",
    )

    ingest_copernicus_task = PythonOperator(
        task_id="ingest_copernicus",
        python_callable=ingest_copernicus,
        op_kwargs=_date_window_kwargs(),
        doc_md="Fetch and load Copernicus observations for the shared run window.",
    )

    dbt_build_task = BashOperator(
        task_id="dbt_build",
        bash_command=(
            "dbt build --project-dir "
            f"{shlex.quote(str(DBT_PROJECT_DIR))}"
        ),
        doc_md=(
            "Build the dbt project after every ingestion task succeeds. "
            "The project path is resolved relative to this DAG file."
        ),
    )

    ingestion_tasks = [
        ingest_weather_task,
        ingest_marine_task,
        ingest_forecast_task,
        ingest_sunrise_sunset_task,
        ingest_tides_task,
        ingest_wsl_task,
        ingest_copernicus_task,
    ]
    ingestion_tasks >> dbt_build_task