"""Reusable ingestion task entrypoints for an external orchestrator."""

import logging

from .copernicus_insitu import run_copernicus_ingestion
from .database import get_db_connection, get_surf_spots
from .open_meteo_forecast import (
    get_forecast_data,
    insert_forecast_data,
    transform_forecast_data,
)
from .open_meteo_marine import (
    get_marine_data,
    insert_marine_data,
    transform_marine_data,
)
from .open_meteo_weather import (
    get_weather_data,
    insert_weather_data,
    transform_weather_data,
)
from .sunrise_sunset import (
    get_sunrise_sunset_data,
    insert_sunrise_sunset_data,
    transform_sunrise_sunset_data,
)
from .tides_open_water import (
    get_or_create_tide_station,
    get_tide_data,
    insert_tide_data,
    transform_tide_data,
)
from .wsl_performance import (
    EVENTS,
    get_wsl_data,
    insert_wsl_data,
    transform_wsl_data,
)


logger = logging.getLogger(__name__)


class IngestionTaskError(RuntimeError):
    """Raised after a task has attempted every configured item."""

    def __init__(self, provider, failures):
        self.provider = provider
        self.failures = failures
        failure_summary = "; ".join(failures)
        super().__init__(
            f"{provider} ingestion failed for {len(failures)} item(s): "
            f"{failure_summary}"
        )


def _rollback_after_failure(connection, provider, item_name):
    try:
        connection.rollback()
    except Exception:
        logger.exception(
            "%s rollback failed after an error for %s",
            provider,
            item_name,
        )


def _raise_for_failures(provider, failures):
    if failures:
        raise IngestionTaskError(provider, failures)


def _run_spot_ingestion(provider, process_spot):
    spots = get_surf_spots()
    connection = get_db_connection()
    failures = []
    total_rows = 0

    try:
        for spot_id, spot_name, latitude, longitude in spots:
            try:
                rows_inserted = process_spot(
                    connection,
                    spot_id,
                    spot_name,
                    latitude,
                    longitude,
                )
            except Exception as error:
                _rollback_after_failure(connection, provider, spot_name)
                failures.append(
                    f"{spot_name}: {type(error).__name__}: {error}"
                )
                logger.exception(
                    "%s ingestion failed for spot=%s",
                    provider,
                    spot_name,
                )
                continue

            total_rows += rows_inserted
            logger.info(
                "%s ingestion completed for spot=%s rows_inserted=%d",
                provider,
                spot_name,
                rows_inserted,
            )
    finally:
        connection.close()

    _raise_for_failures(provider, failures)
    return total_rows


def _run_event_ingestion(provider, events, process_event):
    connection = get_db_connection()
    failures = []
    total_rows = 0

    try:
        for event in events:
            event_name = event.get("event_name", "unknown event")
            try:
                rows_inserted = process_event(connection, event)
            except Exception as error:
                _rollback_after_failure(connection, provider, event_name)
                failures.append(
                    f"{event_name}: {type(error).__name__}: {error}"
                )
                logger.exception(
                    "%s ingestion failed for event=%s",
                    provider,
                    event_name,
                )
                continue

            total_rows += rows_inserted
            logger.info(
                "%s ingestion completed for event=%s rows_inserted=%d",
                provider,
                event_name,
                rows_inserted,
            )
    finally:
        connection.close()

    _raise_for_failures(provider, failures)
    return total_rows


def ingest_weather(start_date, end_date):
    """Fetch and load weather forecasts for all configured surf spots."""

    def process_spot(connection, spot_id, spot_name, latitude, longitude):
        data = get_weather_data(latitude, longitude, start_date, end_date)
        rows = transform_weather_data(data, spot_id)
        insert_weather_data(connection, rows)
        return len(rows)

    return _run_spot_ingestion("weather", process_spot)


def ingest_marine(start_date, end_date):
    """Fetch and load marine forecasts for all configured surf spots."""

    def process_spot(connection, spot_id, spot_name, latitude, longitude):
        data = get_marine_data(latitude, longitude, start_date, end_date)
        rows = transform_marine_data(data, spot_id)
        insert_marine_data(connection, rows)
        return len(rows)

    return _run_spot_ingestion("marine", process_spot)


def ingest_forecast(start_date, end_date):
    """Fetch and load previous-run forecast data for all surf spots."""

    def process_spot(connection, spot_id, spot_name, latitude, longitude):
        data = get_forecast_data(latitude, longitude, start_date, end_date)
        rows = transform_forecast_data(data, spot_id)
        insert_forecast_data(connection, rows)
        return len(rows)

    return _run_spot_ingestion("forecast", process_spot)


def ingest_sunrise_sunset(start_date, end_date):
    """Fetch and load daily daylight times for all surf spots."""

    def process_spot(connection, spot_id, spot_name, latitude, longitude):
        data = get_sunrise_sunset_data(
            latitude,
            longitude,
            start_date,
            end_date,
        )
        rows = transform_sunrise_sunset_data(data, spot_id)
        insert_sunrise_sunset_data(connection, rows)
        return len(rows)

    return _run_spot_ingestion("sunrise_sunset", process_spot)


def ingest_tides(start_date, end_date):
    """Load tide observations, creating a station mapping when necessary."""

    def process_spot(connection, spot_id, spot_name, latitude, longitude):
        tide_station = get_or_create_tide_station(
            connection,
            spot_id,
            latitude,
            longitude,
        )
        tide_station_id = tide_station[0]
        data = get_tide_data(tide_station_id, start_date, end_date)
        rows = transform_tide_data(data, tide_station_id)
        insert_tide_data(connection, rows)
        return len(rows)

    return _run_spot_ingestion("tides", process_spot)


def ingest_wsl():
    """Fetch and load all events configured in the WSL module."""

    def process_event(connection, event):
        data = get_wsl_data(event)
        rows = transform_wsl_data(data)
        insert_wsl_data(connection, rows)
        return len(rows)

    return _run_event_ingestion("wsl", EVENTS, process_event)


def ingest_copernicus(start_date, end_date):
    """Fetch and load Copernicus observations within the supplied window."""
    connection = get_db_connection()

    try:
        return run_copernicus_ingestion(
            start_datetime=_to_isoformat(start_date),
            end_datetime=_to_isoformat(end_date),
            connection=connection,
        )
    finally:
        connection.close()


def _to_isoformat(value):
    if isinstance(value, str):
        return value
    return value.isoformat()