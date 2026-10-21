#!/usr/bin/env bash
# Сквозная проверка логов: запрос -> Nginx -> Promtail -> Loki (-> Grafana).
set -euo pipefail

APP_IP="${APP_IP:-178.154.234.125}"
MON_SSH="${MON_SSH:-wh0am1@93.77.167.172}"
LOKI_URL="${LOKI_URL:-http://10.131.0.18:3100}"
MARK="e2e-$(date +%s)"

curl -s -o /dev/null --noproxy '*' "http://${APP_IP}/api/${MARK}"
echo "Тестовая строка отправлена: ${MARK}. Жду доставку в Loki (до 60 секунд)..."

for _ in $(seq 1 12); do
  sleep 5
  out="$(ssh "${MON_SSH}" "curl -sG '${LOKI_URL}/loki/api/v1/query_range' --data-urlencode 'query={job=\"nginx\"} |= \"${MARK}\"' --data-urlencode 'limit=5'")"
  if grep -q "${MARK}" <<<"${out}"; then
    echo "OK: строка ${MARK} найдена в Loki"
    echo "В Grafana (Explore, источник Loki): {job=\"nginx\"} |= \"${MARK}\""
    exit 0
  fi
done
echo "FAIL: строка ${MARK} не найдена в Loki" >&2
exit 1
