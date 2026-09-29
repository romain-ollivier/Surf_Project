"""Extraction, transformation et chargement des donnees meteo."""

from datetime import datetime, timezone

import requests
from psycopg2.extras import execute_values

WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"


def get_weather_data(latitude, longitude, start_date, end_date):
    """Retrieve weather forecast data from Open-Meteo."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": [
            "temperature_2m",
            "apparent_temperature",
            "dew_point_2m",
            "relative_humidity_2m",
            "precipitation",
            "rain",
            "showers",
            "snowfall",
            "weather_code",
            "cloud_cover",
            "cloud_cover_low",
            "cloud_cover_mid",
            "cloud_cover_high",
            "wind_speed_10m",
            "wind_direction_10m",
            "wind_gusts_10m",
            "pressure_msl",
            "surface_pressure",
            "visibility",
        ],
        "timezone": "UTC",
        "start_date": start_date,
        "end_date": end_date,
    }

    response = requests.get(
        WEATHER_API_URL,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    return response.json()


def _parse_timestamp(timestamp):
    return datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc)


def transform_weather_data(data, spot_id):
    """Transform weather JSON into rows ready for PostgreSQL."""
    hourly = data["hourly"]
    times = hourly["time"]

    def values(name):
        return hourly.get(name, [None] * len(times))

    return [
        (
            spot_id,
            data.get("latitude"),
            data.get("longitude"),
            data.get("elevation"),
            _parse_timestamp(timestamp),
            values("temperature_2m")[index],
            values("apparent_temperature")[index],
            values("dew_point_2m")[index],
            values("relative_humidity_2m")[index],
            values("precipitation")[index],
            values("rain")[index],
            values("showers")[index],
            values("snowfall")[index],
            values("weather_code")[index],
            values("cloud_cover")[index],
            values("cloud_cover_low")[index],
            values("cloud_cover_mid")[index],
            values("cloud_cover_high")[index],
            values("wind_speed_10m")[index],
            values("wind_direction_10m")[index],
            values("wind_gusts_10m")[index],
            values("pressure_msl")[index],
            values("surface_pressure")[index],
            values("visibility")[index],
        )
        for index, timestamp in enumerate(times)
    ]


def insert_weather_data(connection, rows):
    """Insert or update weather data in raw.open_meteo_weather."""
    query = """
        INSERT INTO raw.open_meteo_weather (
            spot_id, latitude, longitude, elevation, observation_time,
            temperature_2m, apparent_temperature, dew_point_2m,
            relative_humidity_2m, precipitation, rain, showers, snowfall,
            weather_code, cloud_cover, cloud_cover_low, cloud_cover_mid,
            cloud_cover_high, wind_speed_10m, wind_direction_10m,
            wind_gusts_10m, pressure_msl, surface_pressure, visibility
        )
        VALUES %s
        ON CONFLICT (spot_id, observation_time)
        DO UPDATE SET
            latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude,
            elevation = EXCLUDED.elevation,
            temperature_2m = EXCLUDED.temperature_2m,
            apparent_temperature = EXCLUDED.apparent_temperature,
            dew_point_2m = EXCLUDED.dew_point_2m,
            relative_humidity_2m = EXCLUDED.relative_humidity_2m,
            precipitation = EXCLUDED.precipitation, rain = EXCLUDED.rain,
            showers = EXCLUDED.showers, snowfall = EXCLUDED.snowfall,
            weather_code = EXCLUDED.weather_code,
            cloud_cover = EXCLUDED.cloud_cover,
            cloud_cover_low = EXCLUDED.cloud_cover_low,
            cloud_cover_mid = EXCLUDED.cloud_cover_mid,
            cloud_cover_high = EXCLUDED.cloud_cover_high,
            wind_speed_10m = EXCLUDED.wind_speed_10m,
            wind_direction_10m = EXCLUDED.wind_direction_10m,
            wind_gusts_10m = EXCLUDED.wind_gusts_10m,
            pressure_msl = EXCLUDED.pressure_msl,
            surface_pressure = EXCLUDED.surface_pressure,
            visibility = EXCLUDED.visibility,
            ingested_at = NOW();
    """

    with connection.cursor() as cursor:
        execute_values(cursor, query, rows)
    connection.commit()