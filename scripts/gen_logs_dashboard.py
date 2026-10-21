#!/usr/bin/env python3
"""Дашборд «Логи (Loki)»: ошибки, 5xx, latency по access-логу Nginx, поиск по тексту.

Запуск из корня репозитория: python3 scripts/gen_logs_dashboard.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "ansible/roles/monitoring/files/dashboards/logs.json"
DS = {"type": "loki", "uid": "loki"}
APP = "bulletin-board"

NGINX = '{job="nginx", log_type="access"} != "/actuator/"'
NGINX_5XX = '{job="nginx", log_type="access", status=~"5.."}'
APPLOG = '{job="containerlogs", app="' + APP + '"}'
APP_ERR = '{job="containerlogs", app="' + APP + '", level="ERROR"}'


def target(expr, legend="", ref="A"):
    return {"datasource": DS, "refId": ref, "expr": expr, "queryType": "range", "legendFormat": legend}


def pos(x, y, w, h):
    return {"x": x, "y": y, "w": w, "h": h}


def stat(pid, title, expr, g, unit="short"):
    return {"id": pid, "type": "stat", "title": title, "datasource": DS, "gridPos": g,
            "targets": [target(expr)],
            "fieldConfig": {"defaults": {"unit": unit, "noValue": "0"}, "overrides": []}}


def graph(pid, title, targets, g, unit="short"):
    return {"id": pid, "type": "timeseries", "title": title, "datasource": DS, "gridPos": g,
            "targets": targets, "fieldConfig": {"defaults": {"unit": unit}, "overrides": []}}


def logs(pid, title, expr, g):
    return {"id": pid, "type": "logs", "title": title, "datasource": DS, "gridPos": g,
            "targets": [{"datasource": DS, "refId": "A", "expr": expr, "queryType": "range"}],
            "options": {"showTime": True, "wrapLogMessage": True, "sortOrder": "Descending",
                        "enableLogDetails": True, "dedupStrategy": "none"}}


def quantile(p):
    return ("quantile_over_time(" + str(p) + ", " + NGINX + " | json | unwrap request_time [5m]) by (host)")


panels = [
    stat(1, "Строк логов за 5 минут", 'sum(count_over_time({job=~"containerlogs|nginx"}[5m]))', pos(0, 0, 6, 4)),
    stat(2, "Запросов Nginx за 5 минут", "sum(count_over_time(" + NGINX + "[5m]))", pos(6, 0, 6, 4)),
    stat(3, "Ответов 5xx за 5 минут", "sum(count_over_time(" + NGINX_5XX + "[5m]))", pos(12, 0, 6, 4)),
    stat(4, "ERROR в приложении за 5 минут", "sum(count_over_time(" + APP_ERR + "[5m]))", pos(18, 0, 6, 4)),
    graph(5, "Запросы Nginx по кодам ответа (в минуту)",
          [target("sum by (status) (count_over_time(" + NGINX + "[1m]))", "{{status}}")], pos(0, 4, 12, 8)),
    graph(6, "Latency Nginx по access-логу (p50 / p95 / p99)",
          [target(quantile(0.5), "p50", "A"), target(quantile(0.95), "p95", "B"),
           target(quantile(0.99), "p99", "C")], pos(12, 4, 12, 8), "s"),
    graph(7, "Записи лога приложения по уровням (в минуту)",
          [target("sum by (level) (count_over_time(" + APPLOG + "[1m]))", "{{level}}")], pos(0, 12, 12, 8)),
    graph(8, "5xx по URI (Nginx)",
          [target("sum by (request_uri) (count_over_time(" + NGINX_5XX + " | json [5m]))", "{{request_uri}}")],
          pos(12, 12, 12, 8)),
    logs(9, "Ответы 5xx (Nginx)", NGINX_5XX, pos(0, 20, 12, 8)),
    logs(10, "Ошибки приложения (level=ERROR)", APP_ERR, pos(12, 20, 12, 8)),
    logs(11, "Access-лог Nginx (поиск по тексту, IP, URI)", NGINX + ' |~ "$search"', pos(0, 28, 12, 9)),
    logs(12, "Логи приложения (поиск по тексту, пользователю)", APPLOG + ' |~ "$search"', pos(12, 28, 12, 9)),
    logs(13, "Error-лог Nginx", '{job="nginx", log_type="error"} |~ "$search"', pos(0, 37, 24, 6)),
]

dash = {
    "uid": "logs", "title": "Логи (Loki)", "tags": ["observability", "logs"],
    "schemaVersion": 39, "version": 1, "editable": False,
    "refresh": "30s", "time": {"from": "now-1h", "to": "now"},
    "templating": {"list": [{
        "name": "search", "label": "Поиск (пользователь, IP, текст)", "type": "textbox", "query": "",
        "current": {"selected": False, "text": "", "value": ""},
        "options": [{"selected": True, "text": "", "value": ""}],
    }]},
    "panels": panels,
}
OUT.write_text(json.dumps(dash, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("written", OUT)
