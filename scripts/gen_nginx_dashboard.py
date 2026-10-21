#!/usr/bin/env python3
"""Дашборд Nginx на метриках nginx-prometheus-exporter (stub_status).

Использует функции из gen_dashboards.py. Запуск: python3 scripts/gen_nginx_dashboard.py
"""
from gen_dashboards import dashboard, stat, ts, q, S, UP_MAP

panels = [
    stat("Nginx доступен (nginx_up)", [q(f"nginx_up{S}", "{{instance}}")], mappings=UP_MAP),
    stat("Запросов в секунду", [q(f"sum(rate(nginx_http_requests_total{S}[1m]))")], "reqps"),
    stat("Активные соединения", [q(f"sum(nginx_connections_active{S})")]),
    stat("Всего запросов", [q(f"sum(nginx_http_requests_total{S})")]),
    ts("RPS (rate(nginx_http_requests_total[1m]))", [q(f"rate(nginx_http_requests_total{S}[1m])", "{{instance}}")], "reqps"),
    ts("Активные соединения", [q(f"nginx_connections_active{S}", "{{instance}}")]),
    ts("Соединения: reading / writing / waiting", [q(f"nginx_connections_reading{S}", "reading"),
                                                   q(f"nginx_connections_writing{S}", "writing"),
                                                   q(f"nginx_connections_waiting{S}", "waiting")]),
    ts("Соединения: принято и обработано (в секунду)", [q(f"rate(nginx_connections_accepted{S}[1m])", "accepted"),
                                                         q(f"rate(nginx_connections_handled{S}[1m])", "handled")]),
]

dashboard("nginx", "Nginx", "nginx_up", panels)
