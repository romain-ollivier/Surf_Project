from datetime import datetime, timezone

import requests

from src.ingestion.database import get_db_connection, get_surf_spots


START_DATE = "2025-09-25"
END_DATE = "2026-09-24"

WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"


def parse_utc_timestamp(timestamp):
    return datetime.fromisoformat(timestamp).replace(
        tzinfo=timezone.utc
    )


def get_weather_history(latitude, longitude):
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "hourly": (
            "temperature_2m,"
            "precipitation,"
            "cloud_cover,"
            "visibility,"
            "wind_speed_10m,"
            "wind_direction_10m,"
            "wind_gusts_10m"
        ),
        "timezone": "GMT",
    }

    response = requests.get(
        WEATHER_URL,
        params=params,
    )

    response.raise_for_status()

    data = response.json()

    print(
        f"Weather API: "
        f"{len(data['hourly']['time'])} rows | "
        f"{data['hourly']['time'][0]} → "
        f"{data['hourly']['time'][-1]}"
    )

    return data


def get_marine_history(latitude, longitude):
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "hourly": (
            "wave_height,"
            "wave_direction,"
            "wave_period,"
            "swell_wave_height,"
            "swell_wave_direction,"
            "swell_wave_period,"
            "sea_surface_temperature"
        ),
        "timezone": "GMT",
    }

    response = requests.get(
        MARINE_URL,
        params=params,
    )

    response.raise_for_status()

    data = response.json()

    print(
        f"Marine API: "
        f"{len(data['hourly']['time'])} rows | "
        f"{data['hourly']['time'][0]} → "
        f"{data['hourly']['time'][-1]}"
    )

    return data


def insert_weather_history(
    connection,
    spot_id,
    latitude,
    longitude,
    data,
):
    hourly = data["hourly"]

    rows = [
        (
            spot_id,
            parse_utc_timestamp(timestamp),
            latitude,
            longitude,
            temperature,
            precipitation,
            cloud_cover,
            visibility,
            wind_speed,
            wind_direction,
            wind_gusts,
        )
        for (
            timestamp,
            temperature,
            precipitation,
            cloud_cover,
            visibility,
            wind_speed,
            wind_direction,
            wind_gusts,
        ) in zip(
            hourly["time"],
            hourly["temperature_2m"],
            hourly["precipitation"],
            hourly["cloud_cover"],
            hourly["visibility"],
            hourly["wind_speed_10m"],
            hourly["wind_direction_10m"],
            hourly["wind_gusts_10m"],
        )
    ]

    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO raw.open_meteo_weather_history (
                spot_id,
                observation_time,
                latitude,
                longitude,
                temperature_2m,
                precipitation,
                cloud_cover,
                visibility,
                wind_speed_10m,
                wind_direction_10m,
                wind_gusts_10m
            )
            VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            ON CONFLICT (spot_id, observation_time)
            DO NOTHING;
            """,
            rows,
        )

    connection.commit()

    return len(rows)


def insert_marine_history(
    connection,
    spot_id,
    latitude,
    longitude,
    data,
):
    hourly = data["hourly"]

    rows = [
        (
            spot_id,
            parse_utc_timestamp(timestamp),
            latitude,
            longitude,
            wave_height,
            wave_direction,
            wave_period,
            swell_height,
            swell_direction,
            swell_period,
            sea_surface_temperature,
        )
        for (
            timestamp,
            wave_height,
            wave_direction,
            wave_period,
            swell_height,
            swell_direction,
            swell_period,
            sea_surface_temperature,
        ) in zip(
            hourly["time"],
            hourly["wave_height"],
            hourly["wave_direction"],
            hourly["wave_period"],
            hourly["swell_wave_height"],
            hourly["swell_wave_direction"],
            hourly["swell_wave_period"],
            hourly["sea_surface_temperature"],
        )
    ]

    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO raw.open_meteo_marine_history (
                spot_id,
                observation_time,
                latitude,
                longitude,
                wave_height,
                wave_direction,
                wave_period,
                swell_wave_height,
                swell_wave_direction,
                swell_wave_period,
                sea_surface_temperature
            )
            VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            ON CONFLICT (spot_id, observation_time)
            DO NOTHING;
            """,
            rows,
        )

    connection.commit()

    return len(rows)


def main():
    print("Starting Open-Meteo historical data ingestion...")
    print(f"Period: {START_DATE} → {END_DATE}")

    connection = get_db_connection()

    try:
        spots = get_surf_spots()

        print(f"{len(spots)} surf spots found.")

        for (
            spot_id,
            spot_name,
            latitude,
            longitude,
        ) in spots:

            print(f"\nProcessing {spot_name}...")

            weather_data = get_weather_history(
                latitude,
                longitude,
            )

            marine_data = get_marine_history(
                latitude,
                longitude,
            )

            weather_rows = insert_weather_history(
                connection,
                spot_id,
                latitude,
                longitude,
                weather_data,
            )

            marine_rows = insert_marine_history(
                connection,
                spot_id,
                latitude,
                longitude,
                marine_data,
            )

            print(
                f"{spot_name}: "
                f"{weather_rows} weather rows + "
                f"{marine_rows} marine rows loaded."
            )

    finally:
        connection.close()

    print("\nHistorical data ingestion completed.")


if __name__ == "__main__":
    main()