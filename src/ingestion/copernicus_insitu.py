import os
import logging
from datetime import datetime

import copernicusmarine
from dotenv import load_dotenv

from src.ingestion.database import get_db_connection, get_surf_spots


DATASET_ID = "cmems_obs-ins_glo_phybgcwav_mynrt_na_irr"
logger = logging.getLogger(__name__)


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


def get_spot_ids():
    return {spot[1]: spot[0] for spot in get_surf_spots()}


def get_copernicus_data(
    platform_id,
    variables,
    start_datetime,
    end_datetime,
):
    load_dotenv()
    username = os.getenv("COPERNICUS_USERNAME")
    password = os.getenv("COPERNICUS_PASSWORD")

    if not username or not password:
        raise ValueError(
            "COPERNICUS_USERNAME and COPERNICUS_PASSWORD "
            "must be configured before Copernicus ingestion."
        )

    return copernicusmarine.read_dataframe(
        dataset_id=DATASET_ID,
        platform_ids=[platform_id],
        variables=variables,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        username=username,
        password=password,
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


def run_copernicus_ingestion(
    start_datetime,
    end_datetime,
    connection=None,
):
    owns_connection = connection is None
    if owns_connection:
        connection = get_db_connection()

    try:
        spot_ids = get_spot_ids()
        total_rows = 0
        failures = []

        for platform_id, config in STATIONS.items():
            spot_name = config["spot_name"]
            variables = config["variables"]

            try:
                data = get_copernicus_data(
                    platform_id,
                    variables,
                    start_datetime,
                    end_datetime,
                )

                if data.empty:
                    logger.info(
                        "copernicus ingestion found no data for spot=%s "
                        "platform=%s",
                        spot_name,
                        platform_id,
                    )
                    continue

                spot_id = spot_ids[spot_name]
                rows_inserted = insert_data(connection, spot_id, data)
                total_rows += rows_inserted
                logger.info(
                    "copernicus ingestion completed for spot=%s "
                    "platform=%s rows_inserted=%d",
                    spot_name,
                    platform_id,
                    rows_inserted,
                )
            except Exception as error:
                try:
                    connection.rollback()
                except Exception:
                    logger.exception(
                        "copernicus rollback failed for spot=%s",
                        spot_name,
                    )
                failures.append(
                    f"{spot_name} ({platform_id}): "
                    f"{type(error).__name__}: {error}"
                )
                logger.exception(
                    "copernicus ingestion failed for spot=%s platform=%s",
                    spot_name,
                    platform_id,
                )

        if failures:
            raise RuntimeError(
                "Copernicus ingestion failed for "
                f"{len(failures)} platform(s): {'; '.join(failures)}"
            )

        return total_rows

    finally:
        if owns_connection:
            connection.close()