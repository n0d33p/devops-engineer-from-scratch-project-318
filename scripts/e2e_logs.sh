#!/usr/bin/env bash
# Сквозная проверка логов: запрос -> Nginx -> Promtail -> Loki.
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_env

LOKI_URL="http://${MON_PRIV}:$(var loki_port)"
MARK="e2e-$(date +%s)"

curl -s -o /dev/null --noproxy '*' "http://${APP}/api/${MARK}"
echo "Тестовая строка отправлена: ${MARK}. Жду доставку в Loki (до 60 секунд)..."

for _ in $(seq 1 12); do
  sleep 5
  out="$(ssh "${SSH_USER}@${MON}" "curl -sG '${LOKI_URL}/loki/api/v1/query_range' --data-urlencode 'query={job=\"nginx\"} |= \"${MARK}\"' --data-urlencode 'limit=5'")"
  if grep -q "${MARK}" <<<"${out}"; then
    echo "OK: строка ${MARK} найдена в Loki"
    echo "В Grafana (Explore, источник Loki): {job=\"nginx\"} |= \"${MARK}\""
    exit 0
  fi
done
echo "FAIL: строка ${MARK} не найдена в Loki" >&2
exit 1
