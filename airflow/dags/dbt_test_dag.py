from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'airflow'
}

with DAG(
    dag_id='dbt_quality_gate',
    default_args=default_args,
    description='Run dbt dependencies and core data quality checks',
    schedule_interval="@once",
    start_date=datetime(2022,3,20),
    catchup=False,
    tags=['streamify', 'dbt']
) as dag:

    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command="cd /dbt && dbt deps",
        execution_timeout=timedelta(minutes=10),
    )

    dbt_build_core = BashOperator(
        task_id="dbt_build_core",
        bash_command=(
            "cd /dbt && "
            "dbt build --select core --profiles-dir . --target prod"
        ),
        execution_timeout=timedelta(minutes=30),
    )

    dbt_deps >> dbt_build_core
