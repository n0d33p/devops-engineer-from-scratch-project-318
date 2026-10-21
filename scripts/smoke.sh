#!/usr/bin/env bash
# Smoke-тест инфраструктуры: доступность сервисов, метрики, логи, закрытые порты.
# Для проверки таргетов Prometheus задайте пароль: read -rs PROM_PASSWORD; export PROM_PASSWORD
set -uo pipefail
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_env

fail=0
ok()   { echo "OK      $1"; }
bad()  { echo "FAIL    $1"; fail=1; }
skip() { echo "SKIP    $1"; }

http_code() { curl -s -o /dev/null -m 10 --noproxy '*' -w '%{http_code}' "$@" || true; }

expect_code() { # имя url ожидаемый_код
  local got
  got="$(http_code "$2")"
  if [[ "$got" == "$3" ]]; then ok "$1 ($got)"; else bad "$1: ожидали $3, получили $got"; fi
}

closed() { # имя хост порт
  if nc -z -w 3 "$2" "$3" 2>/dev/null; then bad "$1: порт $3 открыт снаружи"; else ok "$1: порт $3 закрыт снаружи"; fi
}

prom_q() {
  curl -s -m 10 -u "${PROM_USER}:${PROM_PASSWORD}" --data-urlencode "query=$1" "http://${MON}:9090/api/v1/query" \
    | python3 -c "import sys,json; r=json.load(sys.stdin)['data']['result']; print(r[0]['value'][1] if r else 0)" 2>/dev/null || echo 0
}

echo "== Приложение (App VM ${APP})"
expect_code "REST /api/bulletins" "http://${APP}/api/bulletins" 200
expect_code "Статика (frontend)" "http://${APP}/" 200
expect_code "Swagger UI" "http://${APP}/swagger-ui/index.html" 200

echo "== Мониторинг (Monitoring VM ${MON})"
expect_code "Grafana health" "http://${MON}:3000/api/health" 200
n="$(curl -s -m 10 --noproxy '*' "http://${MON}:3000/api/search?type=dash-db" | python3 -c 'import sys,json; print(len(json.load(sys.stdin)))' 2>/dev/null || echo 0)"
if [[ "$n" -ge 6 ]]; then ok "Grafana: дашбордов $n (нужно не меньше 6)"; else bad "Grafana: дашбордов $n, нужно не меньше 6"; fi
expect_code "Prometheus без пароля отдаёт 401" "http://${MON}:9090/-/healthy" 401
if [[ -n "${PROM_PASSWORD:-}" ]]; then
  total="$(prom_q 'count(up)')"
  healthy="$(prom_q 'count(up == 1)')"
  if [[ "$total" == "$healthy" && "$total" -ge 3 ]]; then ok "Prometheus: таргетов up $healthy из $total"; else bad "Prometheus: таргетов up $healthy из $total"; fi
  nu="$(prom_q 'nginx_up')"
  if [[ "$nu" == "1" ]]; then ok "nginx_up = 1"; else bad "nginx_up = $nu"; fi
else
  skip "Таргеты Prometheus (задайте PROM_PASSWORD)"
fi
loki=""
for _ in 1 2 3 4 5 6; do
  loki="$(ssh -o ConnectTimeout=10 "${SSH_USER}@${MON}" "curl -s -m 5 http://${MON_PRIV}:$(var loki_port)/ready" 2>/dev/null)"
  [[ "$loki" == "ready" ]] && break
  sleep 5
done
if [[ "$loki" == "ready" ]]; then ok "Loki ready"; else bad "Loki: '${loki}'"; fi

echo "== Сервисы и контейнеры"
missing="$(ssh -o ConnectTimeout=10 "${SSH_USER}@${APP}" 'for s in nginx node_exporter nginx_exporter docker; do systemctl is-active --quiet "$s" || echo "$s"; done; for c in bulletin-board-app-1 promtail; do docker ps --format "{{.Names}}" | grep -qx "$c" || echo "$c"; done' 2>/dev/null)"
if [[ -z "$missing" ]]; then ok "App VM: сервисы и контейнеры работают"; else bad "App VM, не работают: ${missing//$'\n'/ }"; fi
missing="$(ssh -o ConnectTimeout=10 "${SSH_USER}@${MON}" 'for c in prometheus grafana loki; do docker ps --format "{{.Names}}" | grep -qx "$c" || echo "$c"; done' 2>/dev/null)"
if [[ -z "$missing" ]]; then ok "Monitoring VM: контейнеры работают"; else bad "Monitoring VM, не работают: ${missing//$'\n'/ }"; fi

echo "== Закрытые порты (проверка снаружи)"
if command -v nc >/dev/null; then
  for p in 9100 9113 8081 9090; do closed "App VM" "$APP" "$p"; done
  closed "Monitoring VM (Loki)" "$MON" 3100
else
  skip "Проверка портов (нет утилиты nc)"
fi

echo
if [[ "$fail" -eq 0 ]]; then echo "SMOKE: всё в порядке"; else echo "SMOKE: есть ошибки" >&2; exit 1; fi
