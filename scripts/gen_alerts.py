#!/usr/bin/env python3
"""Генерирует правила Grafana Alerting для provisioning.

Файл получается в формате JSON. JSON является подмножеством YAML,
поэтому Grafana читает его как обычный .yml.
Запуск из корня репозитория: python3 scripts/gen_alerts.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "ansible/roles/monitoring/files/grafana-alerting/alert-rules.yml"
PROM = {"type": "prometheus", "uid": "prometheus"}
EXPR = {"type": "__expr__", "uid": "__expr__"}
RANGE = {"from": 600, "to": 0}


def rule(uid, title, expr, op, threshold, for_, severity, service, summary, description, no_data="OK"):
    """Одно правило: A - запрос в Prometheus, B - последнее значение, C - сравнение с порогом."""
    return {
        "uid": uid,
        "title": title,
        "condition": "C",
        "data": [
            {"refId": "A", "relativeTimeRange": RANGE, "datasourceUid": "prometheus",
             "model": {"datasource": PROM, "expr": expr, "instant": True, "range": False, "refId": "A"}},
            {"refId": "B", "relativeTimeRange": RANGE, "datasourceUid": "__expr__",
             "model": {"type": "reduce", "expression": "A", "reducer": "last", "datasource": EXPR, "refId": "B"}},
            {"refId": "C", "relativeTimeRange": RANGE, "datasourceUid": "__expr__",
             "model": {"type": "threshold", "expression": "B", "datasource": EXPR, "refId": "C",
                       "conditions": [{"evaluator": {"type": op, "params": [threshold]}}]}},
        ],
        "noDataState": no_data,
        "execErrState": "Error",
        "for": for_,
        "annotations": {"summary": summary, "description": description},
        "labels": {"severity": severity, "service": service},
        "isPaused": False,
    }


FS = 'mountpoint="/", fstype!~"tmpfs|overlay"'

availability = [
    rule("app-down", "Приложение недоступно",
         'up{job="app-actuator"}', "lt", 1, "2m", "critical", "app",
         "Приложение недоступно ({{ $labels.instance }})",
         "Prometheus не может опросить Actuator уже 2 минуты: контейнер упал или Nginx не отвечает."),
    rule("node-exporter-down", "Node Exporter недоступен",
         'up{job="node"}', "lt", 1, "2m", "critical", "host",
         "Node Exporter недоступен ({{ $labels.instance }})",
         "Метрики хоста не собираются 2 минуты: сервис упал или сервер недоступен по сети."),
    rule("services-down", "Системный сервис остановлен",
         'node_systemd_unit_state{state="active", name=~"nginx.service|docker.service"}', "lt", 1, "2m",
         "critical", "host",
         "Сервис {{ $labels.name }} остановлен",
         "Сервис {{ $labels.name }} не в состоянии active на {{ $labels.instance }} дольше 2 минут."),
    rule("metrics-missing", "Метрики перестали поступать",
         'absent(node_load1) or absent(process_uptime_seconds)', "gt", 0, "5m", "warning", "monitoring",
         "Нет метрик хоста или приложения",
         "Prometheus не видит метрик node_load1 или process_uptime_seconds уже 5 минут."),
]

application = [
    rule("high-5xx", "Много ответов 5xx",
         '(sum(rate(http_server_requests_seconds_count{status=~"5.."}[5m])) or vector(0)) '
         '/ sum(rate(http_server_requests_seconds_count[5m]))',
         "gt", 0.05, "5m", "critical", "app",
         "Доля ответов 5xx выше 5%",
         "Больше 5% запросов к приложению заканчиваются ошибкой 5xx уже 5 минут."),
    rule("high-latency-p95", "Высокая задержка ответов",
         'histogram_quantile(0.95, sum by (le) (rate(http_server_requests_seconds_bucket[5m])))',
         "gt", 1, "5m", "warning", "app",
         "p95 задержки выше 1 секунды",
         "95% запросов обрабатываются дольше 1 секунды уже 5 минут."),
]

resources = [
    rule("high-cpu", "Высокая загрузка CPU",
         '100 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100', "gt", 85, "10m", "warning", "host",
         "CPU загружен больше чем на 85%",
         "Загрузка процессора выше 85% уже 10 минут."),
    rule("high-memory", "Мало свободной памяти",
         '(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100', "gt", 90, "10m",
         "warning", "host",
         "Занято больше 90% памяти",
         "Память на {{ $labels.instance }} занята больше чем на 90% уже 10 минут."),
    rule("low-disk", "Заканчивается место на диске",
         f'(1 - node_filesystem_avail_bytes{{{FS}}} / node_filesystem_size_bytes{{{FS}}}) * 100',
         "gt", 85, "5m", "warning", "host",
         "Диск заполнен больше чем на 85%",
         "Корневой раздел на {{ $labels.instance }} заполнен больше чем на 85%."),
]

groups = [
    {"orgId": 1, "name": name, "folder": "Observability", "interval": "1m", "rules": rules}
    for name, rules in (("availability", availability), ("application", application), ("resources", resources))
]

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({"apiVersion": 1, "groups": groups}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("written", OUT, "-", sum(len(g["rules"]) for g in groups), "rules")
