# Project DevOps Deploy — Observability

![Hexlet Check](https://github.com/n0d33p/devops-engineer-from-scratch-project-318/actions/workflows/hexlet-check.yml/badge.svg)

Сервис «Доска объявлений» (Spring Boot + PostgreSQL) и инфраструктура вокруг него в Yandex Cloud, описанная кодом (Ansible + Makefile).

## Ссылки

- Приложение: http://84.201.178.195/
- Swagger UI: http://84.201.178.195/swagger-ui/index.html
- Форк приложения: https://github.com/n0d33p/project-devops-deploy
- Docker-образ: `nxdeep/project-devops-deploy` (Docker Hub)

## Инфраструктура (Yandex Cloud)

| Ресурс | Параметры |
|---|---|
| App VM `app-vm` | Ubuntu 24.04, 2 vCPU (50%), 2 ГБ RAM, 15 ГБ, зона `ru-central1-b`, статический внешний IP |
| Managed PostgreSQL `bulletins-db` | 1 хост `b2.medium` (Intel Cascade Lake, 50% vCPU), network-hdd 10 ГБ, без публичного доступа |
| Object Storage | бакет `bulletins-obs-p4-zayats` |
| Сеть | `default`, подсеть `default-ru-central1-b` |

### Создание ресурсов

```bash
# ВМ (cloud-init.yaml с публичным SSH-ключом, см. ниже)
yc compute instance create --name app-vm --zone ru-central1-b \
  --platform standard-v3 --cores 2 --core-fraction 50 --memory 2 \
  --create-boot-disk size=15,image-folder-id=standard-images,image-family=ubuntu-2404-lts \
  --network-interface subnet-name=default-ru-central1-b,nat-ip-version=ipv4 \
  --metadata-from-file user-data=cloud-init.yaml

# Кластер PostgreSQL (пароль сгенерировать и положить в Ansible Vault)
yc managed-postgresql cluster create --name bulletins-db --environment production \
  --network-name default \
  --host zone-id=ru-central1-b,subnet-id=e2l0b2ksj0hev2no4qfl \
  --resource-preset b2.medium --disk-type network-hdd --disk-size 10 \
  --user name=bulletins,password=<пароль> --database name=bulletins,owner=bulletins
```

Пример `cloud-init.yaml` (подставьте свой публичный ключ):

```yaml
#cloud-config
users:
  - name: wh0am1
    groups: sudo
    shell: /bin/bash
    sudo: 'ALL=(ALL) NOPASSWD:ALL'
    ssh_authorized_keys:
      - ssh-ed25519 AAAA... комментарий
```

Бакет создаёт Ansible-роль `storage`.

## Ansible

Всё лежит в каталоге `ansible/`:

- `playbook.yml` — подготовка сервера и деплой, `update.yml` — обновление версии образа;
- `roles/common` (Docker, пользователь, UFW), `roles/deploy` (compose, `.env`, проверка health), `roles/nginx` (reverse proxy), `roles/storage` (бакет), `roles/update`;
- `group_vars/all/main.yml` — несекретные переменные, `group_vars/*/vault.yml` — секреты в Ansible Vault.

Приложение запускается с профилем `prod` и подключается к PostgreSQL по TLS (`sslmode=require`). Actuator в контейнере слушает только 127.0.0.1:9090, наружу метрики отдаёт Nginx (см. раздел «Метрики»)

## Команды

```bash
make bootstrap                    # роли и коллекции Ansible
make deploy                       # подготовка сервера + деплой (спросит пароль Vault)
make update IMAGE_TAG=<тег>       # обновить версию
make rollback IMAGE_TAG=<тег>     # откат на предыдущий тег
```

Требования: Ansible 2.15+, `python3-boto3` (для создания бакета), доступ по SSH к `app-vm`, пароль от Vault.

## Проверка

```bash
curl -i http://84.201.178.195/api/bulletins
ssh wh0am1@84.201.178.195 'curl -s localhost:9090/actuator/health'
ssh wh0am1@84.201.178.195 'docker logs bulletin-board-app-1'
```
## Метрики (Node Exporter и Actuator)

Роль `ansible/roles/node_exporter` ставит Node Exporter как systemd-сервис (пользователь `node_exporter`, бинарник в `/usr/local/bin`, автозапуск и перезапуск при изменении бинарника или юнита). Метрики приложения отдаёт Spring Actuator, наружу их проксирует Nginx.

### Endpoints

| Назначение | Адрес | Защита |
|---|---|---|
| Метрики хоста | `http://<app-private-ip>:9100/metrics` | UFW: только сеть мониторинга |
| Health приложения | `http://<app-private-ip>:9090/actuator/health` | Nginx: `allow/deny` + basic-auth, UFW |
| Метрики приложения | `http://<app-private-ip>:9090/actuator/prometheus` | то же |
| Сайт и API | `http://84.201.178.195/` | публично |

Здесь `<app-private-ip>` — приватный адрес App VM (`10.129.0.21`). Снаружи порты 9100 и 9090 недоступны.

### Параметры доступа

| Параметр | Значение | Где задан |
|---|---|---|
| `node_exporter_version` | версия Node Exporter | `group_vars/all/main.yml` |
| `node_exporter_port` | `9100` | `group_vars/all/main.yml` |
| `app_management_port` | `9090` | `group_vars/all/main.yml` |
| `monitoring_allowed_cidr` | `10.129.0.0/24` (на шаге с Monitoring VM сузить до её адреса) | `group_vars/all/main.yml` |
| `metrics_user` | `prometheus` | `group_vars/all/main.yml` |
| `vault_metrics_password` | пароль basic-auth | Ansible Vault |

Порт контейнера `9090` привязан к `127.0.0.1` намеренно: опубликованные Docker-порты обходят UFW. Наружу метрики выходят только через Nginx, который слушает приватный IP и пускает запросы лишь из `monitoring_allowed_cidr` с паролем.

### Обязательные метрики

Хост (Node Exporter):

| Область | Метрика | Что показывает |
|---|---|---|
| CPU | `node_load1`, `node_load5`, `node_load15` | средняя нагрузка за 1/5/15 минут |
| CPU | `node_cpu_seconds_total` | время CPU по режимам |
| Память | `node_memory_MemTotal_bytes`, `node_memory_MemAvailable_bytes` | всего и доступно памяти |
| Память | `node_memory_SwapFree_bytes` | свободный swap |
| Диски | `node_filesystem_size_bytes`, `node_filesystem_avail_bytes` | размер и свободное место |
| Диски | `node_disk_io_time_seconds_total` | загрузка дискового ввода-вывода |
| Сеть | `node_network_receive_bytes_total`, `node_network_transmit_bytes_total` | входящий и исходящий трафик |
| Процессы | `node_procs_running`, `node_processes_pids` | запущенные процессы и их число |
| Сервисы | `node_systemd_unit_state{name=...}` | состояние `docker`, `nginx`, `ssh`, `node_exporter` |

Приложение (Actuator/Micrometer):

| Метрика | Что показывает |
|---|---|
| `process_uptime_seconds` | время работы приложения |
| `application_ready_time_seconds` | время старта до готовности |
| `process_cpu_usage`, `system_cpu_usage` | загрузка CPU процессом и системой |
| `jvm_memory_used_bytes`, `jvm_memory_max_bytes` | память JVM |
| `jvm_threads_live_threads` | число живых потоков |
| `jvm_gc_pause_seconds_count` | паузы сборщика мусора |
| `http_server_requests_seconds_count`, `http_server_requests_seconds_sum` | запросы по меткам `uri`, `status`, `method`, `outcome` |
| `hikaricp_connections_active`, `hikaricp_connections_max` | пул соединений с PostgreSQL |

Коллекторы `systemd` и `processes` в Node Exporter выключены по умолчанию и включены флагами в systemd-юните.

### Проверка

На App VM:

```bash
systemctl status node_exporter --no-pager
curl -s http://10.129.0.21:9100/metrics | grep -E '^node_load1 '
curl -i http://10.129.0.21:9090/actuator/health            # 401 без пароля
curl -s -u prometheus http://10.129.0.21:9090/actuator/health
curl -s -u prometheus http://10.129.0.21:9090/actuator/prometheus | head
```

С ноутбука (должен быть таймаут, порты закрыты):

```bash
curl --max-time 5 http://84.201.178.195:9100/metrics
curl --max-time 5 http://84.201.178.195:9090/actuator/health
```

### Логи Nginx

Access-лог `/var/log/nginx/access.log` пишется в JSON (поля: `time`, `remote_addr`, `x_forwarded_for`, `host`, `request_method`, `request_uri`, `status`, `body_bytes_sent`, `request_time`, `upstream_response_time`, `http_referer`, `http_user_agent`). Формат задан переменной `nginx_log_format` в роли `ansible/roles/nginx`. Error-лог остаётся текстовым: Nginx не поддерживает JSON-формат для `error_log`.
