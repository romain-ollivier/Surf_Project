FROM apache/airflow:3.3.2-python3.14

USER airflow

COPY --chown=airflow:root airflow/requirements-airflow.txt /tmp/requirements-airflow.txt
COPY --chown=airflow:root airflow/dbt-requirements.txt /tmp/dbt-requirements.txt

RUN pip install --no-cache-dir \
        --constraint "${HOME}/constraints.txt" \
        "apache-airflow==3.3.2" \
        -r /tmp/requirements-airflow.txt \
    && pip check \
    && python -m venv /home/airflow/dbt-venv \
    && /home/airflow/dbt-venv/bin/pip install --no-cache-dir \
        -r /tmp/dbt-requirements.txt \
    && /home/airflow/dbt-venv/bin/pip check \
    && mkdir -p /opt/airflow/auth /opt/airflow/dbt-profile

COPY --chown=airflow:root airflow/dags/ /opt/airflow/project/airflow/dags/
COPY --chown=airflow:root airflow/dbt-profiles.yml.example /opt/airflow/project/airflow/dbt-profiles.yml.example
COPY --chown=airflow:root src/ /opt/airflow/project/src/
COPY --chown=airflow:root surf_dbt/ /opt/airflow/project/surf_dbt/
RUN chown -R airflow:root /opt/airflow/project/surf_dbt/

ENV PYTHONPATH=/opt/airflow/project \
    DBT_PROFILES_DIR=/opt/airflow/dbt-profile \
    PATH="/home/airflow/dbt-venv/bin:${PATH}"

WORKDIR /opt/airflow/project