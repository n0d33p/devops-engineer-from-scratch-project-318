#!/usr/bin/env bash
# Общие функции для скриптов. Адреса берутся из inventory и переменных Ansible, без хардкода.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INV="$ROOT/ansible/inventories/hosts.ini"
VARS="$ROOT/ansible/group_vars/all/main.yml"

# inv_host <группа>: ansible_host первого хоста группы из inventory.ini
inv_host() {
  awk -v g="[$1]" '$0 == g {f=1; next} /^\[/ {f=0} f {for (i=1; i<=NF; i++) if ($i ~ /^ansible_host=/) {sub("ansible_host=", "", $i); print $i; exit}}' "$INV"
}

# var <имя>: значение простой переменной из group_vars/all/main.yml
var() {
  sed -nE "s/^$1:[[:space:]]*[\"']?([^\"' #]+).*/\1/p" "$VARS" | head -1
}

load_env() {
  APP="$(inv_host app)"
  MON="$(inv_host monitoring)"
  MON_PRIV="$(var monitoring_private_ip)"
  SSH_USER="$(var username)"
  PROM_USER="$(var prometheus_web_user)"
  if [[ -z "$APP" || -z "$MON" || -z "$MON_PRIV" || -z "$SSH_USER" ]]; then
    echo "Не удалось прочитать адреса из inventory.ini и group_vars/all/main.yml" >&2
    exit 2
  fi
}
