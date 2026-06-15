## GCP

### Initial setup

Для общего контекста можно посмотреть [видео](https://www.youtube.com/watch?v=Hajwnmj0xfQ&list=PL3MmuxUbc_hJed7dXYoJw8DoCuVHhGEQb&index=11&t=3s).

1. Создайте Google Cloud account через Google email ID.
2. Создайте первый [project](https://console.cloud.google.com/), если он еще не создан.
   - Например: `Streamify`.
   - Сохраните `Project ID`: он понадобится при деплое infrastructure через Terraform.
3. Настройте [service account & authentication](https://cloud.google.com/docs/authentication/getting-started) для проекта.
   - Для начала выдайте role `Viewer`.
   - Скачайте service-account keys (`.json`) для auth.
   - Не публикуйте key file и не коммитьте его в git.
   - Переименуйте `.json` key file в `google_credentials.json`.
4. Установите [Google Cloud SDK](https://cloud.google.com/sdk/docs/quickstart) локально.
5. Укажите environment variable с path до downloaded GCP keys:

   ```shell
   export GOOGLE_APPLICATION_CREDENTIALS="<path/to/your/google_credentials.json>"

   # Refresh token/session, and verify authentication
   gcloud auth application-default login
   ```

### Setup for access

1. IAM roles для service account:
   - Откройте раздел *IAM* в *IAM & Admin*: https://console.cloud.google.com/iam-admin/iam.
   - Нажмите *Edit principal* для service account.
   - Добавьте к `Viewer` roles: **Storage Admin**, **Storage Object Admin**, **BigQuery Admin**.

2. Включите APIs для проекта:
   - https://console.cloud.google.com/apis/library/iam.googleapis.com
   - https://console.cloud.google.com/apis/library/iamcredentials.googleapis.com
   - Note: по ходу запуска могут потребоваться дополнительные APIs, например Dataproc.

3. Проверьте, что `GOOGLE_APPLICATION_CREDENTIALS` установлен:

   ```shell
   export GOOGLE_APPLICATION_CREDENTIALS="<path/to/your/service-account-authkeys>.json"
   ```

#### Installation reference

- [DataTalks Club GCP overview](https://github.com/DataTalksClub/data-engineering-zoomcamp/blob/main/week_1_basics_n_setup/1_terraform_gcp/2_gcp_overview.md#initial-setup)
