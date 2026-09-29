"""Ingestion des données de marée depuis l'API Open Waters."""

import requests
from psycopg2.extras import execute_values


BASE_URL = "https://api.openwaters.io"


def get_nearby_tide_stations(latitude, longitude, max_results=10):
    """Recherche les stations de marée proches d'un spot."""
    url = f"{BASE_URL}/tides/stations"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "maxResults": max_results,
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    return response.json()

def get_or_create_tide_station(
    connection,
    spot_id,
    latitude,
    longitude,
):
    """
    Retrieve the existing tide station for a spot.
    If none exists, discover and save the most appropriate station.
    """

    station = get_tide_station(connection, spot_id)

    if station is not None:
        return station

    print("  No tide station configured. Searching nearby stations...")

    stations = get_nearby_tide_stations(
        latitude,
        longitude,
    )

    selected_station = select_tide_station(stations)

    save_tide_station(
        connection,
        spot_id,
        selected_station,
    )

    print(
        f"  Tide station selected: "
        f"{selected_station['name']} "
        f"({selected_station['distance']:.1f} km)"
    )

    return (
        selected_station["id"],
        selected_station["name"],
        selected_station.get("latitude"),
        selected_station.get("longitude"),
        selected_station.get("distance"),
        selected_station.get("source", {}).get("name"),
        selected_station.get("license", {}).get("type"),
        selected_station.get("license", {}).get("commercial_use"),
        selected_station.get("type"),
        selected_station.get("timezone"),
        selected_station.get("chart_datum"),
        selected_station.get("datums_source"),
    )

def select_tide_station(stations):
    """
    Sélectionne automatiquement la station de marée la plus appropriée.

    Priorité :
    1. Stations autorisant l'utilisation commerciale
    2. Plus petite distance par rapport au spot
    """
    commercial_stations = [
        station
        for station in stations
        if station.get("license", {}).get("commercial_use") is True
    ]

    if not commercial_stations:
        raise ValueError(
            "No tide station with commercial_use=True was found."
        )

    return min(
        commercial_stations,
        key=lambda station: station["distance"],
    )


def get_tide_station(connection, spot_id):
    """
    Récupère la station de marée déjà associée au spot.

    Retourne None si aucune station n'est encore configurée.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                tide_station_id,
                station_name,
                latitude,
                longitude,
                distance_to_spot_km,
                source,
                license,
                commercial_use,
                station_type,
                timezone,
                chart_datum,
                datums_source
            FROM raw.tide_stations
            WHERE spot_id = %s
            """,
            (spot_id,),
        )

        return cursor.fetchone()


def save_tide_station(connection, spot_id, station):
    """Enregistre ou met à jour la station de marée associée au spot."""

    source = station.get("source", {})

    license_data = station.get("license", {})

    values = (
        station["id"],
        spot_id,
        station["name"],
        station.get("latitude"),
        station.get("longitude"),
        station.get("distance"),
        source.get("name"),
        license_data.get("type"),
        license_data.get("commercial_use"),
        station.get("type"),
        station.get("timezone"),
        station.get("chart_datum"),
        station.get("datums_source"),
    )

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO raw.tide_stations (
                tide_station_id,
                spot_id,
                station_name,
                latitude,
                longitude,
                distance_to_spot_km,
                source,
                license,
                commercial_use,
                station_type,
                timezone,
                chart_datum,
                datums_source
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (spot_id)
            DO UPDATE SET
                tide_station_id = EXCLUDED.tide_station_id,
                station_name = EXCLUDED.station_name,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                distance_to_spot_km = EXCLUDED.distance_to_spot_km,
                source = EXCLUDED.source,
                license = EXCLUDED.license,
                commercial_use = EXCLUDED.commercial_use,
                station_type = EXCLUDED.station_type,
                timezone = EXCLUDED.timezone,
                chart_datum = EXCLUDED.chart_datum,
                datums_source = EXCLUDED.datums_source
            """,
            values,
        )

    connection.commit()


def get_tide_data(tide_station_id, start_date, end_date):
    """Récupère le timeline de marée d'une station."""

    source, station_code = tide_station_id.split("/", 1)

    url = (
        f"{BASE_URL}/tides/stations/"
        f"{source}/{station_code}/timeline"
    )

    params = {
        "start": start_date,
        "end": end_date,
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    return response.json()


def transform_tide_data(tide_data, tide_station_id):
    """Transforme la réponse Open Waters en lignes PostgreSQL."""

    rows = []

    datum = tide_data["datum"]
    units = tide_data["units"]

    for observation in tide_data["timeline"]:
        rows.append(
            (
                tide_station_id,
                observation["time"],
                observation["level"],
                datum,
                units,
            )
        )

    return rows


def insert_tide_data(connection, rows):
    """Insère les données de marée dans PostgreSQL."""

    if not rows:
        return

    query = """
        INSERT INTO raw.open_waters_tides (
            tide_station_id,
            observation_time,
            water_level_m,
            datum,
            units
        )
        VALUES %s
        ON CONFLICT (
            tide_station_id,
            observation_time
        )
        DO UPDATE SET
            water_level_m = EXCLUDED.water_level_m,
            datum = EXCLUDED.datum,
            units = EXCLUDED.units,
            ingested_at = NOW()
    """

    with connection.cursor() as cursor:
        execute_values(cursor, query, rows)

    connection.commit()