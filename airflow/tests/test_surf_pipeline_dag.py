"""Offline regression tests for the surf Airflow DAG definition."""

import importlib.util
import subprocess
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import copernicusmarine
import psycopg2
import requests
from jinja2 import Environment


EXPECTED_INGESTION_TASKS = {
    "ingest_weather",
    "ingest_marine",
    "ingest_forecast",
    "ingest_sunrise_sunset",
    "ingest_tides",
    "ingest_wsl",
    "ingest_copernicus",
}
EXPECTED_TASKS = EXPECTED_INGESTION_TASKS | {"dbt_build"}
DAG_FILE = Path(__file__).resolve().parents[1] / "dags" / "surf_pipeline.py"
REPOSITORY_ROOT = DAG_FILE.parents[2]
MISSING = object()


class FakeDAG:
    current = None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.tasks = {}

    def __enter__(self):
        FakeDAG.current = self
        return self

    def __exit__(self, exception_type, exception, traceback):
        FakeDAG.current = None


class FakeOperator:
    def __init__(self, *, task_id, **kwargs):
        self.task_id = task_id
        self.__dict__.update(kwargs)
        self.op_kwargs = kwargs.get("op_kwargs", {})
        self.upstream_task_ids = set()
        self.downstream_task_ids = set()
        self.dag = FakeDAG.current
        self.trigger_rule = kwargs.get("trigger_rule", "all_success")
        self.retries = kwargs.get(
            "retries",
            self.dag.default_args.get("retries", 0),
        )
        self.retry_delay = kwargs.get(
            "retry_delay",
            self.dag.default_args.get("retry_delay"),
        )
        self.dag.tasks[task_id] = self
        self.execute_calls = 0

    def __rshift__(self, other):
        self.downstream_task_ids.add(other.task_id)
        other.upstream_task_ids.add(self.task_id)
        return other

    def __rrshift__(self, upstream_tasks):
        for upstream_task in upstream_tasks:
            upstream_task >> self
        return self


class FakePythonOperator(FakeOperator):
    pass


class FakeBashOperator(FakeOperator):
    pass


def _load_dag_with_airflow_stubs():
    airflow_module = types.ModuleType("airflow")
    airflow_module.__path__ = []

    sdk_module = types.ModuleType("airflow.sdk")
    sdk_module.DAG = FakeDAG

    providers_module = types.ModuleType("airflow.providers")
    providers_module.__path__ = []
    standard_module = types.ModuleType("airflow.providers.standard")
    standard_module.__path__ = []
    operators_module = types.ModuleType(
        "airflow.providers.standard.operators"
    )
    operators_module.__path__ = []

    python_module = types.ModuleType(
        "airflow.providers.standard.operators.python"
    )
    python_module.PythonOperator = FakePythonOperator

    bash_module = types.ModuleType(
        "airflow.providers.standard.operators.bash"
    )
    bash_module.BashOperator = FakeBashOperator

    airflow_modules = {
        "airflow": airflow_module,
        "airflow.sdk": sdk_module,
        "airflow.providers": providers_module,
        "airflow.providers.standard": standard_module,
        "airflow.providers.standard.operators": operators_module,
        "airflow.providers.standard.operators.python": python_module,
        "airflow.providers.standard.operators.bash": bash_module,
    }
    previous_modules = {
        name: sys.modules.get(name, MISSING)
        for name in airflow_modules
    }
    sys.modules.update(airflow_modules)

    if str(REPOSITORY_ROOT) not in sys.path:
        sys.path.insert(0, str(REPOSITORY_ROOT))

    spec = importlib.util.spec_from_file_location(
        "surf_pipeline_dag_under_test",
        DAG_FILE,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, previous_modules


def _render_window(op_kwargs, logical_date, wall_clock_time):
    environment = Environment()
    environment.filters["ds"] = lambda value: value.strftime("%Y-%m-%d")

    def ds_add(date_string, days):
        parsed_date = datetime.strptime(date_string, "%Y-%m-%d")
        return (parsed_date + timedelta(days=days)).strftime("%Y-%m-%d")

    run_start = logical_date.replace(tzinfo=timezone.utc)
    context = {
        "data_interval_start": run_start,
        "data_interval_end": run_start + timedelta(days=1),
        "macros": SimpleNamespace(ds_add=ds_add),
        "wall_clock_time": wall_clock_time,
    }
    return tuple(
        environment.from_string(op_kwargs[key]).render(**context)
        for key in ("start_date", "end_date")
    )


def _can_run_all_success(task, states):
    return task.trigger_rule == "all_success" and all(
        states.get(upstream_task_id) == "success"
        for upstream_task_id in task.upstream_task_ids
    )


class SurfPipelineDAGTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.side_effect_mocks = [
            patch.object(requests, "get", Mock(name="requests.get")),
            patch.object(psycopg2, "connect", Mock(name="psycopg2.connect")),
            patch.object(
                copernicusmarine,
                "read_dataframe",
                Mock(name="copernicusmarine.read_dataframe"),
            ),
            patch.object(subprocess, "run", Mock(name="subprocess.run")),
        ]
        for side_effect_mock in cls.side_effect_mocks:
            side_effect_mock.start()

        cls.dag_module, cls.previous_airflow_modules = (
            _load_dag_with_airflow_stubs()
        )
        cls.dag = cls.dag_module.dag

    @classmethod
    def tearDownClass(cls):
        for side_effect_mock in reversed(cls.side_effect_mocks):
            side_effect_mock.stop()

        for name, previous_module in cls.previous_airflow_modules.items():
            if previous_module is MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous_module

    def test_exact_task_set(self):
        self.assertEqual(set(self.dag.tasks), EXPECTED_TASKS)

    def test_dependencies_are_independent_and_acyclic(self):
        dbt_task = self.dag.tasks["dbt_build"]
        self.assertEqual(dbt_task.upstream_task_ids, EXPECTED_INGESTION_TASKS)
        self.assertEqual(dbt_task.downstream_task_ids, set())

        for task_id in EXPECTED_INGESTION_TASKS:
            task = self.dag.tasks[task_id]
            self.assertEqual(task.upstream_task_ids, set())
            self.assertEqual(task.downstream_task_ids, {"dbt_build"})

        visited = set()
        active = set()

        def visit(task_id):
            if task_id in active:
                return False
            if task_id in visited:
                return True

            active.add(task_id)
            for downstream_task_id in self.dag.tasks[
                task_id
            ].downstream_task_ids:
                if not visit(downstream_task_id):
                    return False
            active.remove(task_id)
            visited.add(task_id)
            return True

        self.assertTrue(all(visit(task_id) for task_id in EXPECTED_TASKS))

    def test_daily_configuration_and_retries(self):
        self.assertEqual(self.dag.dag_id, "surf_pipeline")
        self.assertEqual(self.dag.schedule, "@daily")
        self.assertFalse(self.dag.catchup)
        self.assertEqual(self.dag.max_active_runs, 1)
        self.assertEqual(self.dag.default_args["retries"], 2)
        self.assertEqual(
            self.dag.default_args["retry_delay"],
            timedelta(minutes=5),
        )

    def test_date_window_matches_logical_date_and_is_retry_stable(self):
        logical_date = datetime(2026, 9, 30)
        first_wall_clock = datetime(2026, 9, 30, 1, tzinfo=timezone.utc)
        retry_wall_clock = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)

        windows = []
        for task_id in EXPECTED_INGESTION_TASKS - {"ingest_wsl"}:
            op_kwargs = self.dag.tasks[task_id].op_kwargs
            first_window = _render_window(
                op_kwargs,
                logical_date,
                first_wall_clock,
            )
            retry_window = _render_window(
                op_kwargs,
                logical_date,
                retry_wall_clock,
            )
            self.assertEqual(first_window, ("2026-09-30", "2026-10-07"))
            self.assertEqual(retry_window, first_window)
            windows.append(first_window)

        self.assertEqual(len(set(windows)), 1)
        self.assertNotIn("start_date", self.dag.tasks["ingest_wsl"].op_kwargs)

    def test_dbt_waits_for_all_ingestions_after_failure(self):
        dbt_task = self.dag.tasks["dbt_build"]
        failed_states = {
            task_id: "success"
            for task_id in EXPECTED_INGESTION_TASKS
        }
        failed_states["ingest_tides"] = "failed"
        self.assertFalse(_can_run_all_success(dbt_task, failed_states))

        successful_states = {
            task_id: "success"
            for task_id in EXPECTED_INGESTION_TASKS
        }
        self.assertTrue(_can_run_all_success(dbt_task, successful_states))
        self.assertEqual(dbt_task.execute_calls, 0)

    def test_ingestion_functions_are_direct_task_callables(self):
        from src.ingestion import airflow_jobs

        for task_id in EXPECTED_INGESTION_TASKS:
            task = self.dag.tasks[task_id]
            self.assertIs(
                task.python_callable,
                getattr(airflow_jobs, task_id),
            )

    def test_import_has_no_external_side_effects(self):
        requests.get.assert_not_called()
        psycopg2.connect.assert_not_called()
        copernicusmarine.read_dataframe.assert_not_called()
        subprocess.run.assert_not_called()
        self.assertEqual(self.dag.tasks["dbt_build"].execute_calls, 0)


if __name__ == "__main__":
    unittest.main()