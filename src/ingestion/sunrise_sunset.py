
import requests
from psycopg2.extras import execute_values


BASE_URL = "https://api.sunrise-sunset.org/v2"


def get_sunrise_sunset_data(
    latitude,
    longitude,
    start_date,
    end_date,
):
    """Récupère les données de lever/coucher du soleil."""

    params = {
        "lat": latitude,
        "lng": longitude,
        "date_start": start_date,
        "date_end": end_date,
        "time_format": "iso8601",
    }

    response = requests.get(
        BASE_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if "days" not in data:
        raise ValueError(
            "Sunrise-Sunset API response does not contain 'days'."
        )

    return data


def transform_sunrise_sunset_data(
    data,
    spot_id,
):
    """Transforme la réponse API en lignes PostgreSQL."""

    rows = []

    timezone = data["tzid"]
    latitude = data["lat"]
    longitude = data["lng"]

    for day in data["days"]:
        rows.append(
            (
                spot_id,
                day["date"],
                timezone,
                day["utc_offset"],
                latitude,
                longitude,
                day["sunrise"],
                day["sunset"],
                day["dawn"],
                day["dusk"],
                day["first_light"],
                day["last_light"],
                day["civil_twilight_begin"],
                day["civil_twilight_end"],
                day["day_length"],
            )
        )

    return rows


def insert_sunrise_sunset_data(
    connection,
    rows,
):
    """Insère les données solaires dans PostgreSQL."""

    if not rows:
        return

    query = """
        INSERT INTO raw.sunrise_sunset (
            spot_id,
            observation_date,
            timezone,
            utc_offset,
            latitude,
            longitude,
            sunrise,
            sunset,
            dawn,
            dusk,
            first_light,
            last_light,
            civil_twilight_begin,
            civil_twilight_end,
            day_length_seconds
        )
        VALUES %s
        ON CONFLICT (
            spot_id,
            observation_date
        )
        DO UPDATE SET
            timezone = EXCLUDED.timezone,
            utc_offset = EXCLUDED.utc_offset,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            sunrise = EXCLUDED.sunrise,
            sunset = EXCLUDED.sunset,
            dawn = EXCLUDED.dawn,
            dusk = EXCLUDED.dusk,
            first_light = EXCLUDED.first_light,
            last_light = EXCLUDED.last_light,
            civil_twilight_begin = EXCLUDED.civil_twilight_begin,
            civil_twilight_end = EXCLUDED.civil_twilight_end,
            day_length_seconds = EXCLUDED.day_length_seconds,
            ingested_at = NOW()
    """

    with connection.cursor() as cursor:
        execute_values(
            cursor,
            query,
            rows,
        )

    connection.commit()