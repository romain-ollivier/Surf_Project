FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir streamlit pandas plotly sqlalchemy psycopg2-binary python-dotenv
COPY app.py db.py ./
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--browser.gatherUsageStats=false"]
