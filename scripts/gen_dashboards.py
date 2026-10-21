#!/usr/bin/env python3
"""Генерирует JSON-дашборды Grafana в ansible/roles/monitoring/files/dashboards.

Запуск из корня репозитория: python3 scripts/gen_dashboards.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "ansible/roles/monitoring/files/dashboards"
DS = {"type": "prometheus", "uid": "prometheus"}


def sel(extra=""):
    """Селектор меток: фильтр по переменным $job и $instance плюс доп. условия."""
    base = 'job=~"$job", instance=~"$instance"'
    return "{" + base + (", " + extra if extra else "") + "}"


S = sel()


def q(expr, legend=""):
    return {"expr": expr, "legendFormat": legend}


def ts(title, queries, unit="short", w=12, h=8):
    return {"type": "timeseries", "title": title, "queries": queries, "unit": unit, "w": w, "h": h}


UP_MAP = [{"type": "value", "options": {
    "0": {"text": "DOWN", "color": "red"},
    "1": {"text": "UP", "color": "green"}}}]


def stat(title, queries, unit="short", w=6, h=4, mappings=None):
    p = {"type": "stat", "title": title, "queries": queries, "unit": unit, "w": w, "h": h}
    if mappings:
        p["mappings"] = mappings
    return p


def variable(name, query):
    return {
        "name": name, "label": name, "type": "query", "datasource": DS,
        "query": query, "definition": query, "refresh": 2, "sort": 1,
        "multi": True, "includeAll": True, "allValue": ".*",
        "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
    }


def dashboard(uid, title, metric, panels):
    """metric - любая метрика источника: по ней строятся списки job и instance."""
    items, x, y, row_h = [], 0, 0, 0
    for i, p in enumerate(panels, 1):
        if x + p["w"] > 24:  # ширина сетки Grafana - 24 колонки
            x, y, row_h = 0, y + row_h, 0
        defaults = {"unit": p["unit"]}
        if p["type"] == "stat" and p["unit"] in ("s", "short"):
            defaults["color"] = {"mode": "fixed", "fixedColor": "blue"}
        if "mappings" in p:
            defaults["mappings"] = p["mappings"]
        items.append({
            "id": i, "type": p["type"], "title": p["title"], "datasource": DS,
            "gridPos": {"h": p["h"], "w": p["w"], "x": x, "y": y},
            "targets": [dict(t, datasource=DS, refId=chr(65 + n)) for n, t in enumerate(p["queries"])],
            "fieldConfig": {"defaults": defaults, "overrides": []},
        })
        if "options" in p:
            items[-1]["options"] = p["options"]
        x += p["w"]
        row_h = max(row_h, p["h"])
    data = {
        "uid": uid, "title": title, "tags": ["observability"],
        "schemaVersion": 39, "version": 1, "editable": False,
        "refresh": "30s", "time": {"from": "now-1h", "to": "now"},
        "templating": {"list": [
            variable("job", f"label_values({metric}, job)"),
            variable("instance", f'label_values({metric}{{job=~"$job"}}, instance)'),
        ]},
        "panels": items,
    }
    path = OUT / f"{uid}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("written", path)


# --- вспомогательные выражения для HTTP-метрик приложения ---
def rc(extra=""):
    return f"rate(http_server_requests_seconds_count{sel(extra)}[5m])"


def pct(p, by="le"):
    return f"histogram_quantile({p}, sum by ({by}) (rate(http_server_requests_seconds_bucket{S}[5m])))"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    idle = sel('mode="idle"')
    root = sel('mountpoint="/", fstype!~"tmpfs|overlay"')
    nic = sel('device!~"lo|docker.*|br-.*|veth.*"')
    active = sel('state="active"')
    heap = sel('area="heap"')
    nonheap = sel('area="nonheap"')

    system = [
        stat("Аптайм хоста", [q(f"time() - node_boot_time_seconds{S}")], "s"),
        stat("Процессов в системе", [q(f"node_processes_pids{S}")]),
        stat("Загрузка CPU", [q(f"100 - avg(rate(node_cpu_seconds_total{idle}[5m])) * 100")], "percent"),
        stat("Память занята", [q(f"(1 - node_memory_MemAvailable_bytes{S} / node_memory_MemTotal_bytes{S}) * 100")], "percent"),
        ts("CPU, %", [q(f"100 - avg by (instance) (rate(node_cpu_seconds_total{idle}[5m])) * 100", "{{instance}}")], "percent"),
        ts("Load average", [q(f"node_load1{S}", "load1"), q(f"node_load5{S}", "load5"), q(f"node_load15{S}", "load15")]),
        ts("Память занята, %", [q(f"(1 - node_memory_MemAvailable_bytes{S} / node_memory_MemTotal_bytes{S}) * 100", "{{instance}}")], "percent"),
        ts("Диск /, занято %", [q(f"(1 - node_filesystem_avail_bytes{root} / node_filesystem_size_bytes{root}) * 100", "{{instance}}")], "percent"),
        ts("Сеть: приём и передача", [q(f"rate(node_network_receive_bytes_total{nic}[5m])", "{{device}} rx"),
                                      q(f"rate(node_network_transmit_bytes_total{nic}[5m])", "{{device}} tx")], "Bps"),
        ts("Процессы", [q(f"node_procs_running{S}", "running"), q(f"node_processes_pids{S}", "всего")]),
        ts("Диск: время ввода-вывода", [q(f"rate(node_disk_io_time_seconds_total{S}[5m])", "{{device}}")], "percentunit"),
        stat("Системные сервисы (systemd)", [q(f"node_systemd_unit_state{active}", "{{name}}")], w=24, h=4, mappings=UP_MAP),
    ]

    app = [
        stat("Таргет Prometheus", [q(f"up{S}", "{{instance}}")], mappings=UP_MAP),
        stat("Аптайм приложения", [q(f"process_uptime_seconds{S}")], "s"),
        stat("Время старта", [q(f"application_ready_time_seconds{S}")], "s"),
        stat("Потоки JVM", [q(f"jvm_threads_live_threads{S}")]),
        ts("CPU: процесс и система", [q(f"process_cpu_usage{S}", "процесс"), q(f"system_cpu_usage{S}", "система")], "percentunit"),
        ts("Память JVM", [q(f"sum(jvm_memory_used_bytes{heap})", "heap"), q(f"sum(jvm_memory_used_bytes{nonheap})", "non-heap")], "bytes"),
        ts("Паузы сборщика мусора (в сек.)", [q(f"sum by (action) (rate(jvm_gc_pause_seconds_count{S}[5m]))", "{{action}}")]),
        ts("Пул соединений HikariCP", [q(f"hikaricp_connections_active{S}", "active"), q(f"hikaricp_connections_idle{S}", "idle"),
                                       q(f"hikaricp_connections_pending{S}", "pending"), q(f"hikaricp_connections_max{S}", "max")]),
    ]

    five = 'status=~"5.."'
    four = 'status=~"4.."'
    http = [
        stat("Запросов в секунду", [q("sum(" + rc() + ")")], "reqps"),
        stat("Доля ответов 4xx", [q("(sum(" + rc(four) + ") or vector(0)) / sum(" + rc() + ")")], "percentunit"),
        stat("Доля ответов 5xx", [q("(sum(" + rc(five) + ") or vector(0)) / sum(" + rc() + ")")], "percentunit"),
        stat("Latency p95", [q(pct(0.95))], "s"),
        ts("Запросы по кодам ответа (rps)", [q("sum by (status) (" + rc() + ")", "{{status}}")], "reqps"),
        ts("Latency: p50 / p95 / p99", [q(pct(0.5), "p50"), q(pct(0.95), "p95"), q(pct(0.99), "p99")], "s"),
        ts("Средняя latency", [q(f"sum(rate(http_server_requests_seconds_sum{S}[5m])) / sum(rate(http_server_requests_seconds_count{S}[5m]))", "avg")], "s"),
        ts("Топ URI по числу запросов", [q("topk(10, sum by (uri) (" + rc() + "))", "{{uri}}")], "reqps"),
        ts("Latency p95 по URI", [q(pct(0.95, "le, uri"), "{{uri}}")], "s", w=24),
    ]

    dashboard("system-resources", "Системные ресурсы", "node_load1", system)
    dashboard("application-state", "Состояние приложения", "process_uptime_seconds", app)
    dashboard("http-latency", "HTTP: коды ответов и latency", "http_server_requests_seconds_count", http)


if __name__ == "__main__":
    main()
