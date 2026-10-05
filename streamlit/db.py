import os

from dotenv import load_dotenv
from sqlalchemy import create_engine


load_dotenv()


def get_engine():
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    database = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD", "")

    connection_url = (
        f"postgresql+psycopg2://"
        f"{user}:{password}@{host}:{port}/{database}"
    )

    return create_engine(connection_url)