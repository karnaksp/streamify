## Настройка Spark Cluster

![spark](../images/spark.jpg)

Spark Streaming process запускается в Dataproc cluster и читает Kafka VM по port `9092`. Firewall rule для `9092` создается на этапе Terraform setup.

- Подключиться по SSH к **master node**:

  ```bash
  ssh streamify-spark
  ```

- Склонировать repository:

  ```bash
  git clone https://github.com/ankurchavda/streamify.git && \
  cd streamify/spark_streaming
  ```

- Установить environment variables:

  - External IP Kafka VM, чтобы Spark мог подключиться к Kafka;
  - GCS bucket name, заданный при Terraform setup.

    ```bash
    export KAFKA_ADDRESS=IP.ADD.RE.SS
    export GCP_GCS_BUCKET=bucket-name
    ```

  **Note:** эти env vars нужно задавать в каждой новой shell session или после stop/start cluster.

- Начать чтение messages:

  ```bash
  spark-submit \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.1.2 \
  stream_all_events.py
  ```

- Если все прошло успешно, в bucket появятся новые `parquet` files. Spark пишет file каждые две минуты для каждого topic.

- Topics, которые читает Spark:

  - `listen_events`
  - `page_view_events`
  - `auth_events`
