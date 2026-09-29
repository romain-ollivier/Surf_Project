"""Acces a la base PostgreSQL."""

import os

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


def get_db_connection():
    """Create and return a connection to PostgreSQL."""
    return psycopg2.connect(**DB_CONFIG)


def get_surf_spots(connection):
    """Retrieve all surf spots from the RAW database."""
    query = """
        SELECT
            spot_id,
            spot_name,
            latitude,
            longitude
        FROM raw.surf_spots;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchall()