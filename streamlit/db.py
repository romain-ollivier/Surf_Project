import os

import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

def get_engine():
    try:
        config = st.secrets["db"]
        st.write("DEBUG DB HOST:", config.get("host", "NO_HOST"))
    except (FileNotFoundError, KeyError):
        config = None
    if config is not None:
        host = config["host"]
        port = config.get("port", "5432")
        database = config["database"]
        user = config["user"]
        password = config["password"]
    else:
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        database = os.getenv("DB_NAME")
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD", "")
    connection_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
    return create_engine(connection_url)
