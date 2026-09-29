"""Ingestion de l'historique des prévisions Open-Meteo."""

import requests

from psycopg2.extras import execute_values
from .database import get_db_connection


BASE_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"

FORECAST_VARIABLES = [
    "temperature_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "precipitation",
    "cloud_cover",
]


def get_forecast_data(
    latitude,
    longitude,
    start_date,
    end_date,
    max_horizon_days=7,
):
    """Récupère l'historique des prévisions Open-Meteo."""

    hourly_variables = []

    for variable in FORECAST_VARIABLES:
        for horizon in range(1, max_horizon_days + 1):
            hourly_variables.append(
                f"{variable}_previous_day{horizon}"
            )

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(hourly_variables),
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "UTC",
    }

    response = requests.get(
        BASE_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()
    return data

def transform_forecast_data(
    data,
    spot_id,
):
    """Transforme la réponse Open-Meteo en lignes PostgreSQL."""

    rows = []

    times = data["hourly"]["time"]

    for horizon in range(1, 8):

        temperature = data["hourly"][
            f"temperature_2m_previous_day{horizon}"
        ]

        wind_speed = data["hourly"][
            f"wind_speed_10m_previous_day{horizon}"
        ]

        wind_direction = data["hourly"][
            f"wind_direction_10m_previous_day{horizon}"
        ]

        wind_gusts = data["hourly"][
            f"wind_gusts_10m_previous_day{horizon}"
        ]

        precipitation = data["hourly"][
            f"precipitation_previous_day{horizon}"
        ]

        cloud_cover = data["hourly"][
            f"cloud_cover_previous_day{horizon}"
        ]

        for i, observation_time in enumerate(times):

            rows.append(
                (
                    spot_id,
                    observation_time,
                    horizon,
                    data["latitude"],
                    data["longitude"],
                    temperature[i],
                    wind_speed[i],
                    wind_direction[i],
                    wind_gusts[i],
                    precipitation[i],
                    cloud_cover[i],
                )
            )

    return rows

def insert_forecast_data(connection, rows):
    """Insère l'historique des prévisions dans PostgreSQL."""

    if not rows:
        return

    query = """
        INSERT INTO raw.open_meteo_forecast_history (
            spot_id,
            observation_time,
            forecast_horizon_days,
            latitude,
            longitude,
            temperature_2m,
            wind_speed_10m,
            wind_direction_10m,
            wind_gusts_10m,
            precipitation,
            cloud_cover
        )
        VALUES %s

        ON CONFLICT (
            spot_id,
            observation_time,
            forecast_horizon_days
        )

        DO UPDATE SET
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            temperature_2m = EXCLUDED.temperature_2m,
            wind_speed_10m = EXCLUDED.wind_speed_10m,
            wind_direction_10m = EXCLUDED.wind_direction_10m,
            wind_gusts_10m = EXCLUDED.wind_gusts_10m,
            precipitation = EXCLUDED.precipitation,
            cloud_cover = EXCLUDED.cloud_cover,
            ingested_at = NOW()
    """

    with connection.cursor() as cursor:
        execute_values(cursor, query, rows)

    connection.commit()

if __name__ == "__main__":

    data = get_forecast_data(
        latitude=43.66,
        longitude=-1.43,
        start_date="2026-09-23",
        end_date="2026-09-25",
    )

    rows = transform_forecast_data(
        data,
        spot_id=1,
    )

    print("Forecast data retrieved.")
    print("Number of rows:", len(rows))

    connection = get_db_connection()

    try:
        insert_forecast_data(connection, rows)
        print("Forecast data inserted successfully.")

    finally:
        connection.close()