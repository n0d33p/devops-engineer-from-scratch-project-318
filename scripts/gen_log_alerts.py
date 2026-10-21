#!/usr/bin/env python3
"""Правила Grafana Alerting по логам (Loki). Формат JSON (подмножество YAML).

Запуск из корня репозитория: python3 scripts/gen_log_alerts.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "ansible/roles/monitoring/files/grafana-alerting/alert-rules-logs.yml"
LOKI = {"type": "loki", "uid": "loki"}
EXPR = {"type": "__expr__", "uid": "__expr__"}
RANGE = {"from": 600, "to": 0}


def rule(uid, title, expr, threshold, for_, severity, service, summary, description):
    return {
        "uid": uid, "title": title, "condition": "C",
        "data": [
            {"refId": "A", "relativeTimeRange": RANGE, "datasourceUid": "loki",
             "model": {"datasource": LOKI, "expr": expr, "queryType": "instant", "refId": "A"}},
            {"refId": "B", "relativeTimeRange": RANGE, "datasourceUid": "__expr__",
             "model": {"type": "reduce", "expression": "A", "reducer": "last", "datasource": EXPR, "refId": "B"}},
            {"refId": "C", "relativeTimeRange": RANGE, "datasourceUid": "__expr__",
             "model": {"type": "threshold", "expression": "B", "datasource": EXPR, "refId": "C",
                       "conditions": [{"evaluator": {"type": "gt", "params": [threshold]}}]}},
        ],
        "noDataState": "OK", "execErrState": "Error", "for": for_,
        "annotations": {"summary": summary, "description": description},
        "labels": {"severity": severity, "service": service},
        "isPaused": False,
    }


rules = [
    rule("logs-5xx-spike", "Всплеск 5xx в логах Nginx",
         'sum(count_over_time({job="nginx", log_type="access", status=~"5.."}[5m]))', 5, "1m",
         "critical", "app",
         "Больше 5 ответов 5xx за 5 минут (по логам Nginx)",
         "В access-логе Nginx за последние 5 минут больше 5 ответов с кодом 5xx. Смотрите дашборд «Логи (Loki)»."),
    rule("logs-app-errors", "Ошибки ERROR в логах приложения",
         'sum(count_over_time({job="containerlogs", app="bulletin-board", level="ERROR"}[5m]))', 3, "2m",
         "warning", "app",
         "Больше 3 записей ERROR за 5 минут в логах приложения",
         "В JSON-логах приложения за последние 5 минут больше 3 записей уровня ERROR."),
]

groups = [{"orgId": 1, "name": "logs", "folder": "Observability", "interval": "1m", "rules": rules}]
OUT.write_text(json.dumps({"apiVersion": 1, "groups": groups}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("written", OUT, "-", len(rules), "rules")
