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
# ВМ (cloud-init.yaml с вашим публичным SSH-ключом, см. ниже)
yc compute instance create --name app-vm --zone ru-central1-b \
  --platform standard-v3 --cores 2 --core-fraction 50 --memory 2 \
  --create-boot-disk size=15,image-folder-id=standard-images,image-family=ubuntu-2404-lts \
  --network-interface subnet-name=default-ru-central1-b,nat-ip-version=ipv4 \
  --metadata-from-file user-data=cloud-init.yaml

# Кластер PostgreSQL (пароль сгенерировать и положить в Ansible Vault)
yc managed-postgresql cluster create --name bulletins-db --environment production \
  --network-name default \
  --host zone-id=ru-central1-b,subnet-id=<ID подсети default-ru-central1-b> \
  --resource-preset b2.medium --disk-type network-hdd --disk-size 10 \
  --user name=bulletins,password=<пароль> --database name=bulletins,owner=bulletins
```

`cloud-init.yaml`: пользователь `wh0am1` с `sudo` и вашим ключом в `ssh_authorized_keys`. Бакет создаёт Ansible-роль `storage`.

## Ansible

Всё лежит в каталоге `ansible/`:

- `playbook.yml` — подготовка сервера и деплой, `update.yml` — обновление версии образа;
- `roles/common` (Docker, пользователь, UFW), `roles/deploy` (compose, `.env`, проверка health), `roles/nginx` (reverse proxy), `roles/storage` (бакет), `roles/update`;
- `group_vars/all/main.yml` — несекретные переменные, `group_vars/*/vault.yml` — секреты в Ansible Vault.

Приложение запускается с профилем `prod` и подключается к PostgreSQL по TLS (`sslmode=require`). Actuator слушает только `127.0.0.1:9090`.

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