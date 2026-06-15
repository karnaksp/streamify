## Terraform infra setup

Склонируйте repository на локальную машину:

```bash
git clone https://github.com/ankurchavda/streamify.git && \
cd streamify/terraform
```

Поднять infrastructure:

- Инициализировать Terraform и скачать dependencies:

  ```bash
  terraform init
  ```

- Посмотреть Terraform plan.

  Terraform попросит ввести два значения: имя GCS bucket и GCP Project ID. Используйте одни и те же значения на протяжении всего проекта.

  ```bash
  terraform plan
  ```

- Terraform plan должен показать создание следующих resources:

  - `e2-standard-4` Compute Instance для Kafka;
  - `e2-standard-4` Compute Instance для Airflow;
  - Dataproc Spark Cluster:
    - один `e2-standard-2` Master node;
    - два `e2-medium` Worker nodes;
  - Google Cloud Storage bucket;
  - два BigQuery datasets:
    - `streamify_stg`;
    - `streamify_prod`;
  - Firewall rule для открытия port `9092` на Kafka Instance.

- Применить infrastructure.

  **Note:** billing начнется сразу после `terraform apply`.

  ```bash
  terraform apply
  ```

- После завершения работы удалить infrastructure:

  ```bash
  terraform destroy
  ```

**Note:** infrastructure настроена достаточно щедро. Если compute power используется не полностью, можно уменьшить instance sizes и протестировать повторно.
