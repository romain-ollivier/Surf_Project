import os
from datetime import datetime

import copernicusmarine
from dotenv import load_dotenv

from src.ingestion.database import get_db_connection


# Load environment variables
load_dotenv()

COPERNICUS_USERNAME = os.getenv("COPERNICUS_USERNAME")
COPERNICUS_PASSWORD = os.getenv("COPERNICUS_PASSWORD")

if not COPERNICUS_USERNAME or not COPERNICUS_PASSWORD:
    raise ValueError(
        "COPERNICUS_USERNAME and COPERNICUS_PASSWORD "
        "must be defined in the .env file."
    )


DATASET_ID = "cmems_obs-ins_glo_phybgcwav_mynrt_na_irr"


STATIONS = {
    "6200066": {
        "spot_name": "Hossegor",
        "variables": [
            "VAVH",
            "VAVT",
            "VDIR",
            "VZMX",
            "VEMH",
            "VGHS",
            "VGTA",
        ],
    },
    "IndentedHead": {
        "spot_name": "Bells Beach",
        "variables": [
            "VHM0",
            "VMDR",
            "VPED",
            "VPSP",
            "VTM10",
            "VTPK",
        ],
    },
    "51201": {
        "spot_name": "Pipeline",
        "variables": [
            "TEMP",
            "VHM0",
            "VMDR",
            "VTM02",
            "VTPK",
        ],
    },
}


def get_spot_ids(connection):
    query = """
        SELECT spot_id, spot_name
        FROM raw.surf_spots
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    return {row[1]: row[0] for row in rows}


def get_copernicus_data(
    platform_id,
    variables,
    start_datetime,
    end_datetime,
):
    return copernicusmarine.read_dataframe(
        dataset_id=DATASET_ID,
        platform_ids=[platform_id],
        variables=variables,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        username=COPERNICUS_USERNAME,
        password=COPERNICUS_PASSWORD,
        disable_progress_bar=False,
    )


def insert_data(connection, spot_id, df):

    if df.empty:
        return 0

    query = """
        INSERT INTO raw.copernicus_insitu (
            spot_id,
            platform_id,
            observation_time,
            latitude,
            longitude,
            variable,
            value,
            value_qc,
            institution,
            doi,
            product_doi
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (
            platform_id,
            observation_time,
            variable
        )
        DO UPDATE SET
            value = EXCLUDED.value,
            value_qc = EXCLUDED.value_qc,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            institution = EXCLUDED.institution,
            doi = EXCLUDED.doi,
            product_doi = EXCLUDED.product_doi;
    """

    rows = []

    for _, row in df.iterrows():

        observation_time = datetime.fromisoformat(
            row["time"].replace("Z", "+00:00")
        )

        rows.append(
            (
                spot_id,
                str(row["platform_id"]),
                observation_time,
                row["latitude"],
                row["longitude"],
                row["variable"],
                row["value"],
                row["value_qc"],
                row["institution"],
                row["doi"],
                row["product_doi"],
            )
        )

    with connection.cursor() as cursor:
        cursor.executemany(query, rows)

    connection.commit()

    return len(rows)


def run_copernicus_ingestion(start_datetime, end_datetime):

    print("\nStarting Copernicus Marine ingestion...")

    connection = get_db_connection()

    try:

        spot_ids = get_spot_ids(connection)

        total_rows = 0

        for platform_id, config in STATIONS.items():

            spot_name = config["spot_name"]
            variables = config["variables"]

            print(f"\nProcessing {spot_name}...")
            print(f"Platform: {platform_id}")
            print(f"Variables: {', '.join(variables)}")

            df = get_copernicus_data(
                platform_id,
                variables,
                start_datetime,
                end_datetime,
            )

            if df.empty:
                print(f"{spot_name}: no data found.")
                continue

            spot_id = spot_ids[spot_name]

            rows_inserted = insert_data(
                connection,
                spot_id,
                df,
            )

            total_rows += rows_inserted

            print(
                f"{spot_name}: "
                f"{rows_inserted} Copernicus observations loaded."
            )

        print(
            f"\nCopernicus ingestion completed. "
            f"{total_rows} observations processed."
        )

    finally:

        connection.close()
        print("Database connection closed.")