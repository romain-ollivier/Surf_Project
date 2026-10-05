"""Acces a la base PostgreSQL."""

import csv
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}

SURF_SPOTS_SEED = (
    Path(__file__).resolve().parents[2]
    / "surf_dbt"
    / "seeds"
    / "surf_spots.csv"
)


def get_db_connection():
    """Create and return a connection to PostgreSQL."""
    return psycopg2.connect(**DB_CONFIG)


def get_surf_spots():
    """Load all surf spots from the dbt seed CSV."""
    with SURF_SPOTS_SEED.open(
        mode="r",
        newline="",
        encoding="utf-8",
    ) as seed_file:
        return [
            (
                int(row["spot_id"]),
                row["spot_name"],
                float(row["latitude"]),
                float(row["longitude"]),
            )
            for row in csv.DictReader(seed_file)
        ]