#!/usr/bin/env python3
"""Дашборд Status Page: состояние сервисов и активные алерты.

Использует функции из gen_dashboards.py. Запуск: python3 scripts/gen_status_page.py
"""
from gen_dashboards import dashboard, stat, q, UP_MAP, rc, pct, S


def svc(title, expr):
    return stat(title, [q(expr)], "short", w=4, h=4, mappings=UP_MAP)


panels = [
    svc("Приложение", 'up{job="app-actuator"}'),
    svc("Node Exporter", 'up{job="node"}'),
    svc("Nginx", 'node_systemd_unit_state{name="nginx.service", state="active"}'),
    svc("Docker", 'node_systemd_unit_state{name="docker.service", state="active"}'),
    svc("SSH", 'node_systemd_unit_state{name="ssh.service", state="active"}'),
    stat("Запросов в секунду", [q("sum(" + rc() + ")")], "reqps", w=4, h=4),
    stat("Доля ответов 5xx", [q('(sum(' + rc('status=~"5.."') + ') or vector(0)) / sum(' + rc() + ')')], "percentunit", w=6, h=4),
    stat("Latency p95", [q(pct(0.95))], "s", w=6, h=4),
    stat("Загрузка CPU", [q('100 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100')], "percent", w=6, h=4),
    stat("Диск /, занято", [q('(1 - node_filesystem_avail_bytes{mountpoint="/", fstype!~"tmpfs|overlay"} '
                              '/ node_filesystem_size_bytes{mountpoint="/", fstype!~"tmpfs|overlay"}) * 100')],
         "percent", w=6, h=4),
    {"type": "alertlist", "title": "Активные алерты", "queries": [], "unit": "short", "w": 24, "h": 9,
     "options": {"viewMode": "list", "groupMode": "default", "maxItems": 20, "sortOrder": 1,
                 "dashboardAlerts": False, "showInstances": True, "alertName": "",
                 "stateFilter": {"firing": True, "pending": True, "noData": True, "normal": False, "error": True}}},
]

dashboard("status-page", "Status Page", "up", panels)
