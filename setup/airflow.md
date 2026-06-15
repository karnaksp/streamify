## Настройка Airflow VM

![airflow](../images/airflow.jpg)

Airflow запускается в Docker на выделенной compute instance. dbt находится внутри Airflow runtime и запускается DAG-ом.

- Подключиться по SSH:

  ```bash
  ssh streamify-airflow
  ```

- Склонировать repository:

  ```bash
  git clone https://github.com/ankurchavda/streamify.git && \
  cd streamify
  ```

- Установить anaconda, docker и docker-compose:

  ```bash
  bash ~/streamify/scripts/vm_setup.sh && \
  exec newgrp docker
  ```

- Перенести service account json file с локальной машины на VM в directory `~/.google/credentials/`.

  Файл должен называться `google_credentials.json`, иначе DAGs не смогут использовать credentials.

  - Для передачи файла можно использовать [sftp](https://youtu.be/ae-CV2KfoN0?t=2442).

- Установить environment variables, совпадающие со значениями Terraform:

  - GCP Project ID;
  - Cloud Storage Bucket Name.

    ```bash
    export GCP_PROJECT_ID=project-id
    export GCP_GCS_BUCKET=bucket-name
    ```

  **Note:** эти env vars нужно задавать в каждой новой shell session.

- Запустить Airflow. Это может занять несколько минут:

  ```bash
  bash ~/streamify/scripts/airflow_startup.sh && cd ~/streamify/airflow
  ```

- Через пару минут Airflow должен быть доступен на port `8080`. Default username и password: **airflow**.

- Airflow работает в detached mode. Чтобы смотреть Docker logs:

  ```bash
  docker-compose logs --follow
  ```

- Остановить Airflow:

  ```bash
  docker-compose down
  ```

### DAGs

В setup есть два DAGs:

- `load_songs_dag`
  - Запустить первым и только один раз, чтобы загрузить one-time song file в BigQuery.

![songs_dag](../images/songs_dag.png)

- `streamify_dag`
  - Запускать после `load_songs_dag`, чтобы songs table была доступна для transformations.
  - DAG запускается каждый час на пятой минуте и создает dimensions и fact.

![streamify_dag](../images/streamify_dag.png)

DAG flow:

- создать external table для данных, полученных за последний час;
- создать empty table, куда будет append-иться hourly data; обычно это требуется только на первом run;
- insert/append hourly data в table;
- удалить external table;
- запустить dbt transformation для создания dimensions и facts.

### dbt

Transformations выполняются через dbt, который запускается Airflow. dbt lineage должен выглядеть примерно так:

![img](../images/dbt.png)

Dimensions:

- `dim_artists`
- `dim_songs`
- `dim_datetime`
- `dim_location`
- `dim_users`

Facts:

- `fact_streams`
  - Partitioning:
    - Data partitioned by timestamp column by hour, чтобы dashboard быстрее обновлял данные за последние часы.

Итоговая view для dashboarding:

- `wide_stream`
