"""Point d'entrée du pipeline d'ingestion."""

from datetime import datetime, timedelta, timezone

import requests

from .database import get_db_connection, get_surf_spots

from .copernicus_insitu import run_copernicus_ingestion

# ---------------------------------------------------------
# 0. External functions import
# ---------------------------------------------------------

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

from .open_meteo_forecast import (
    get_forecast_data,
    insert_forecast_data,
    transform_forecast_data,
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
    transform_wsl_data,
    insert_wsl_data,
)


def main():
    print("Starting surf data ingestion...")

    # ---------------------------------------------------------
    # 1. Define the common ingestion window in UTC
    # ---------------------------------------------------------

    now_utc = datetime.now(timezone.utc)

    start_date = now_utc.date()
    end_date = start_date + timedelta(days=7)

    print(
        f"Ingestion period (UTC): "
        f"{start_date} → {end_date}"
    )

    # ---------------------------------------------------------
    # 2. Connect to PostgreSQL
    # ---------------------------------------------------------

    connection = get_db_connection()

    try:
        # -----------------------------------------------------
        # 3. Retrieve surf spots
        # -----------------------------------------------------

        spots = get_surf_spots()

        print(f"{len(spots)} surf spots found.")

        # -----------------------------------------------------
        # 4. Process every surf spot
        # -----------------------------------------------------

        for spot_id, spot_name, latitude, longitude in spots:

            print(f"\nProcessing {spot_name}...")

            try:
                # -------------------------------------------------
                # Weather
                # -------------------------------------------------

                weather_data = get_weather_data(
                    latitude,
                    longitude,
                    start_date,
                    end_date,
                )

                weather_rows = transform_weather_data(
                    weather_data,
                    spot_id,
                )

                insert_weather_data(
                    connection,
                    weather_rows,
                )

                # -------------------------------------------------
                # Marine
                # -------------------------------------------------

                marine_data = get_marine_data(
                    latitude,
                    longitude,
                    start_date,
                    end_date,
                )

                marine_rows = transform_marine_data(
                    marine_data,
                    spot_id,
                )

                insert_marine_data(
                    connection,
                    marine_rows,
                )

                # -------------------------------------------------
                # Forecast
                # -------------------------------------------------

                forecast_data = get_forecast_data(
                    latitude,
                    longitude,
                    start_date,
                    end_date,
                )

                forecast_rows = transform_forecast_data(
                    forecast_data,
                    spot_id,
                )

                insert_forecast_data(
                    connection,
                    forecast_rows,
                )

                # -------------------------------------------------
                # Sunrise / Sunset
                # -------------------------------------------------

                sunrise_sunset_data = get_sunrise_sunset_data(
                    latitude,
                    longitude,
                    start_date,
                    end_date,
                )

                sunrise_sunset_rows = transform_sunrise_sunset_data(
                    sunrise_sunset_data,
                    spot_id,
                )

                insert_sunrise_sunset_data(
                    connection,
                    sunrise_sunset_rows,
                )

                # -------------------------------------------------
                # Tide station
                # -------------------------------------------------

                tide_station = get_or_create_tide_station(
                    connection,
                    spot_id,
                    latitude,
                    longitude,
                )

                tide_station_id = tide_station[0]

                # -------------------------------------------------
                # Tides
                # -------------------------------------------------

                tide_data = get_tide_data(
                    tide_station_id,
                    start_date,
                    end_date,
                )

                tide_rows = transform_tide_data(
                    tide_data,
                    tide_station_id,
                )

                insert_tide_data(
                    connection,
                    tide_rows,
                )

                # -------------------------------------------------
                # Summary
                # -------------------------------------------------

                print(
                    f"{spot_name}: "
                    f"{len(weather_rows)} weather rows + "
                    f"{len(marine_rows)} marine rows + "
                    f"{len(forecast_rows)} forecast rows + "
                    f"{len(sunrise_sunset_rows)} sunrise/sunset rows + "
                    f"{len(tide_rows)} tide rows loaded."
                )

            except requests.exceptions.RequestException as error:
                connection.rollback()
                print(
                    f"{spot_name}: API error - {error}"
                )

            except Exception as error:
                connection.rollback()
                print(
                    f"{spot_name}: ingestion error - {error}"
                )

        # ---------------------------------------------------------
        # 5. WSL
        # ---------------------------------------------------------

        print("\nStarting WSL ingestion...")

        for event in EVENTS:

            try:
                wsl_data = get_wsl_data(event)

                wsl_rows = transform_wsl_data(
                    wsl_data,
                )

                insert_wsl_data(
                    connection,
                    wsl_rows,
                )

                print(
                    f"{event['event_name']}: "
                    f"{len(wsl_rows)} WSL records loaded."
                )

            except requests.exceptions.RequestException as error:
                connection.rollback()
                print(
                    f"{event['event_name']}: "
                    f"WSL API error - {error}"
                )

            except Exception as error:
                connection.rollback()
                print(
                    f"{event['event_name']}: "
                    f"WSL ingestion error - {error}"
                )

        # ---------------------------------------------------------
        # 6. Copernicus Marine
        # ---------------------------------------------------------
        # Copernicus provides observations, not forecasts.
        # Therefore we only ingest the last 24 hours.
        # ---------------------------------------------------------

        copernicus_end = now_utc
        copernicus_start = now_utc - timedelta(days=1)

        run_copernicus_ingestion(
            start_datetime=copernicus_start.isoformat(),
            end_datetime=copernicus_end.isoformat(),
        )

    finally:
        connection.close()
        print("\nDatabase connection closed.")

    print("Surf data ingestion completed.")


if __name__ == "__main__":
    main()