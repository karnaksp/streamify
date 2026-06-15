## Debug guide

### General guidelines

- Всегда проверяйте, что ENV variables установлены.
- Запускайте процессы в порядке: Kafka -> Eventsim -> Spark Streaming -> Airflow.
- Следите за CPU utilization на VM, если pipeline ведет себя нестабильно.

### Kafka

- Иногда containers `broker` и `schema-registry` падают при startup, поэтому Control Center может быть недоступен на `9021`. Остановите containers через `docker-compose down` или `ctrl+C`, затем повторите `docker-compose up`.
- Если `KAFKA_ADDRESS` не установлен, Kafka будет писать в localhost, и Spark не сможет читать messages.

### Eventsim

- Если запускать Eventsim с большим числом users, например 2-3 million+, он может зависнуть на generating events. Уменьшите number of users или запустите два parallel processes с разделенными users.

### Spark

Ошибка:

> Connection to node -1 (localhost/127.0.0.1:9092) could not be established. Broker may not be available.

Проверьте, что `KAFKA_ADDRESS` установлен в External IP Address Kafka VM. Если переменная установлена, но чтение все равно не работает, перезапустите cluster.

### Airflow

- Permission denied для dbt logs.
  - `airflow_startup.sh` меняет permissions для dbt folder. Если folder был удален/создан заново или `airflow_startup.sh` не запускался, измените permissions вручную:

    ```bash
    sudo chmod -R 777 dbt/
    ```
