# Operating the surf platform

## Database compatibility

The application expects an existing surf database with the RAW source tables.
The repository currently does **not** contain a full empty-database bootstrap.
Docker Compose provisions PostgreSQL, but does not create all application tables.
Use an authorized database backup or an existing installation before ingestion.

Schema upgrades live in `database/migrations/`. Before upgrading, stop scheduling,
wait for active tasks to finish, and create a PostgreSQL backup outside the repository.
Review local changes before pulling new code; do not discard them with a hard reset.

Apply the station-validity upgrade before starting ingestion or dbt with this version:

```bash
docker compose exec -T surf-db sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < database/migrations/001_tide_station_validity.sql
```

This migration is re-runnable, retains existing observations, and does not change
provider station identifiers. An already migrated installation needs no data rewrite.
If it fails, keep scheduling stopped and inspect the error before proceeding.

## Tide station lifecycle

`tide_station_id` is the provider's identifier, preserved on every observation.
Several historical stations may belong to one surf spot, but only one may be active.
Ingestion selects the active station; historical analytics retain retired stations.

- `valid_from` is inclusive; `valid_to` is exclusive. Null bounds are unbounded.
- Validity applies to the **observation timestamp**, not the ingestion timestamp.
- dbt joins observations to their station within that station's validity window.
- Hourly rate calculations require the same station and consecutive hourly samples.
- Tests check overlapping validity windows and exactly one active station per
  represented spot. The database also enforces at most one active station.

When a provider retires a station, validate the proposed replacement's coordinates,
license, datum, units, and actual API response. The same name or datum label does not
prove physical equivalence. Preserve both station records and their source metadata.
In one reviewed transaction, close the old validity window, deactivate it, and insert
the new active station with its true identifier and matching start boundary. Do not
alias the new API identifier to the old database identifier. Do not rewrite old heights.

Station replacement is currently an operator-managed process, not automatic failover.
A retired reference still produces a visible ingestion failure until it is replaced.
This model supports one spot per station record; sharing a station across multiple
spots would require a separate association table.

## Scheduling and provider failures

`surf_pipeline` runs daily with two retries, five minutes apart, and at most one active
run. Weather, marine, tides, and daylight ingestion must succeed before `dbt_build`.
Forecast-history ingestion runs independently and cannot prevent the dashboard build.
Its errors are **not** marked successful: a failed history task can leave the overall
DAG run failed even when `dbt_build` succeeded. Inspect task states, not just DAG color.

History-derived analytics use the latest successfully ingested rows available when
dbt runs. They are not guaranteed to include that run's history ingestion. External
API availability and source freshness remain separate from dbt model correctness.

## Validation and deployment

Offline DAG regression tests (using ingestion dependencies and Jinja2):

```bash
python -m unittest discover -s airflow/tests -p 'test_*.py'
```

After a compatible schema migration, build and test the database models:

```bash
docker compose exec -w /opt/airflow/project airflow-dag-processor dbt build --project-dir /opt/airflow/project/surf_dbt
```

Check per-spot forecast dates and the dashboard before starting the scheduler.
Restart Streamlit if its cached queries still show old results. Verify the next daily
run and its task-level status. An empty import-error list does not verify ingestion.

Compose bind-mounts the DAGs, `src/`, and `surf_dbt/`; code updates in those paths are
visible to the running containers. Dependency or Dockerfile updates require a rebuild.
Database dumps, temporary repair scripts, logs, and credentials stay outside Git.

A successful dbt build validates the selected models and tests. It is not an atomic
publish of all marts: if a later test fails, some tables may already have been rebuilt.
