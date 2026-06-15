## Настройка SSH для VM

Перед настройкой полезно посмотреть первые минуты [видео Alexey](https://www.youtube.com/watch?v=ae-CV2KfoN0&list=PL3MmuxUbc_hJed7dXYoJw8DoCuVHhGEQb): там показан общий принцип SSH-доступа к VM. Дальше можно выполнить шаги ниже.

- Создайте SSH key на локальной машине в папке `.ssh`: [Guide](https://cloud.google.com/compute/docs/connect/create-ssh-keys#linux-and-macos).

- Добавьте public key (`.pub`) в VM instance: [Guide](https://cloud.google.com/compute/docs/connect/add-ssh-keys#expandable-2).

- Создайте config file в локальной папке `.ssh`:

  ```bash
  touch ~/.ssh/config
  ```

- Скопируйте snippet ниже и замените External IP для Kafka, Spark Master Node и Airflow VM, username и path to ssh private key:

  ```bash
  Host streamify-kafka
      HostName <External IP Address>
      User <username>
      IdentityFile <path/to/home/.ssh/keyfile>

  Host streamify-spark
      HostName <External IP Address Of Master Node>
      User <username>
      IdentityFile <path/to/home/.ssh/keyfile>

  Host streamify-airflow
      HostName <External IP Address>
      User <username>
      IdentityFile <path/to/home/.ssh/gcp>
  ```

- После настройки можно подключаться к серверам из отдельных terminal sessions:

  ```bash
  ssh streamify-kafka
  ```

  ```bash
  ssh streamify-spark
  ```

  ```bash
  ssh streamify-airflow
  ```

- Если VM была остановлена и запущена заново, проверьте External IP и обновите `~/.ssh/config`.

- Для доступа к Kafka Control Center и Airflow UI нужно пробросить ports с VM на локальную машину. Пример показан [здесь](https://youtu.be/ae-CV2KfoN0?t=1074).
