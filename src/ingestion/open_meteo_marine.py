"""Extraction, transformation et chargement des donnees marines."""

from datetime import datetime, timezone

import requests
from psycopg2.extras import execute_values

MARINE_API_URL = "https://marine-api.open-meteo.com/v1/marine"


def get_marine_data(latitude, longitude, start_date, end_date):
    """Retrieve marine forecast data from Open-Meteo."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": [
            "wave_height",
            "wave_direction",
            "wave_period",
            "wave_peak_period",
            "wind_wave_height",
            "wind_wave_direction",
            "wind_wave_period",
            "wind_wave_peak_period",
            "swell_wave_height",
            "swell_wave_direction",
            "swell_wave_period",
            "swell_wave_peak_period",
            "sea_surface_temperature",
            "sea_level_height_msl",
            "ocean_current_velocity",
            "ocean_current_direction",
        ],
        "timezone": "UTC",
        "start_date": start_date,
        "end_date": end_date,
    }

    response = requests.get(
        MARINE_API_URL,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    return response.json()

def _parse_timestamp(timestamp):
    return datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc)


def transform_marine_data(data, spot_id):
    """Transform marine JSON into rows ready for PostgreSQL."""
    hourly = data["hourly"]
    times = hourly["time"]

    def values(name):
        return hourly.get(name, [None] * len(times))

    fields = [
        "wave_height", "wave_direction", "wave_period", "wave_peak_period",
        "wind_wave_height", "wind_wave_direction", "wind_wave_period",
        "wind_wave_peak_period", "swell_wave_height", "swell_wave_direction",
        "swell_wave_period", "swell_wave_peak_period",
        "sea_surface_temperature", "sea_level_height_msl",
        "ocean_current_velocity", "ocean_current_direction",
    ]

    return [
        (
            spot_id,
            data.get("latitude"),
            data.get("longitude"),
            data.get("elevation"),
            _parse_timestamp(timestamp),
            *(values(field)[index] for field in fields),
        )
        for index, timestamp in enumerate(times)
    ]


def insert_marine_data(connection, rows):
    """Insert or update marine data in raw.open_meteo_marine."""
    query = """
        INSERT INTO raw.open_meteo_marine (
            spot_id, latitude, longitude, elevation, observation_time,
            wave_height, wave_direction, wave_period, wave_peak_period,
            wind_wave_height, wind_wave_direction, wind_wave_period,
            wind_wave_peak_period, swell_wave_height, swell_wave_direction,
            swell_wave_period, swell_wave_peak_period, sea_surface_temperature,
            sea_level_height_msl, ocean_current_velocity, ocean_current_direction
        )
        VALUES %s
        ON CONFLICT (spot_id, observation_time)
        DO UPDATE SET
            latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude,
            elevation = EXCLUDED.elevation,
            wave_height = EXCLUDED.wave_height,
            wave_direction = EXCLUDED.wave_direction,
            wave_period = EXCLUDED.wave_period,
            wave_peak_period = EXCLUDED.wave_peak_period,
            wind_wave_height = EXCLUDED.wind_wave_height,
            wind_wave_direction = EXCLUDED.wind_wave_direction,
            wind_wave_period = EXCLUDED.wind_wave_period,
            wind_wave_peak_period = EXCLUDED.wind_wave_peak_period,
            swell_wave_height = EXCLUDED.swell_wave_height,
            swell_wave_direction = EXCLUDED.swell_wave_direction,
            swell_wave_period = EXCLUDED.swell_wave_period,
            swell_wave_peak_period = EXCLUDED.swell_wave_peak_period,
            sea_surface_temperature = EXCLUDED.sea_surface_temperature,
            sea_level_height_msl = EXCLUDED.sea_level_height_msl,
            ocean_current_velocity = EXCLUDED.ocean_current_velocity,
            ocean_current_direction = EXCLUDED.ocean_current_direction,
            ingested_at = NOW();
    """

    with connection.cursor() as cursor:
        execute_values(cursor, query, rows)
    connection.commit()