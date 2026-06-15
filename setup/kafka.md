## Настройка Kafka VM

![kafka](../images/kafka.jpg)

Kafka и Eventsim запускаются как два отдельных Docker process на выделенной compute instance. Eventsim отправляет события в `broker` container Kafka на port `9092`.

- Подключиться по SSH:

  ```bash
  ssh streamify-kafka
  ```

- Склонировать repository и перейти в Kafka folder:

  ```bash
  git clone https://github.com/ankurchavda/streamify.git && \
  cd streamify/kafka
  ```

- Установить anaconda, docker и docker-compose:

  ```bash
  bash ~/streamify/scripts/vm_setup.sh && \
  exec newgrp docker
  ```

- Установить environment variable:

  - External IP Kafka VM:

    ```bash
    export KAFKA_ADDRESS=IP.ADD.RE.SS
    ```

  **Note:** эти env vars нужно задавать в каждой новой shell session или после stop/start VM.

- Запустить Kafka:

  ```bash
  cd ~/streamify/kafka && \
  docker-compose build && \
  docker-compose up
  ```

  **Note:** иногда containers `broker` и `schema-registry` падают при startup. Остановите все containers через `docker-compose down`, затем повторите `docker-compose up`.

- Kafka Control Center должен быть доступен на port `9021`. Откройте UI и проверьте, что сервисы работают.

- Откройте еще одну terminal session для Kafka VM и запустите Eventsim:

  ```bash
  bash ~/streamify/scripts/eventsim_startup.sh
  ```

  Скрипт начнет создавать events для 1 million users на интервале от текущего времени до следующих 24 часов. Container работает в detached mode.

- Смотреть logs:

  ```bash
  docker logs --follow million_events
  ```

- Через несколько минут messages должны начать поступать в Kafka.

- Ожидаемые topics:

  - `listen_events`
  - `page_view_events`
  - `auth_events`
  - `status_change_events`

  ![topics](../images/topics.png)

- **Note:** если при повторном запуске Eventsim появляется ошибка:

  > docker: Error response from daemon: Conflict. The container name "/million_events" is already in use by container

  выполните:

  ```bash
  docker system prune
  ```
