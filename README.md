# OpenTelemetry DevOps Labs

A vendor-free observability stack using OpenTelemetry, Jaeger, Prometheus, Loki, and Grafana. One command boots the whole thing -- traces, metrics, and logs correlated out of the box.

[![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-0.96-000?style=for-the-badge&logo=opentelemetry)](https://opentelemetry.io/)
[![Grafana](https://img.shields.io/badge/Grafana-10.4-F46800?style=for-the-badge&logo=grafana&logoColor=white)](https://grafana.com/)
[![Jaeger](https://img.shields.io/badge/Jaeger-1.55-66CFE3?style=for-the-badge)](https://www.jaegertracing.io/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker%20Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Kubernetes](https://img.shields.io/badge/Kubernetes%20DaemonSet-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white)](https://kubernetes.io/)
[![CI](https://img.shields.io/github/actions/workflow/status/AsierCaballero/otel-labs/ci.yml?branch=main&style=for-the-badge&logo=githubactions&logoColor=white)](https://github.com/AsierCaballero/otel-labs/actions)

---

## Why OpenTelemetry over Datadog?

Vendor lock-in and per-host pricing add up fast. Here is how the open standard compares:

| | Datadog / New Relic | OpenTelemetry |
|---|---|---|
| Cost | $18-$23/host/month | Free (open standard) |
| Vendor lock-in | Full | Zero -- swap backends without touching code |
| Standard | Proprietary | CNCF -- backed by Google, Microsoft, Amazon |
| Trace+Log correlation | Paid tier | Automatic via `trace_id` |
| Kubernetes support | Paid plugin | DaemonSet included |

---

## Architecture

```
                    +-----------+
                    |   Flask   |
                    |   App     |------- Metric (Prometheus endpoint)
                    +-----+-----+
                          | OTLP (gRPC :4317)
                          v
               +------------------+
               |  OTel Collector  |
               | (otel-collector/ |
               |  config.yaml)    |
               +----+----+---+---+
                    |    |   |
         +----------+    |   +----------+
         v               v              v
   +----------+   +----------+   +------+
   |  Jaeger   |   |Prometheus|   | Loki |
   | (traces)  |   |(metrics) |   |(logs)|
   +----------+   +----------+   +------+
         |               |              |
         +-------+-------+----+--------+
                     v
              +------------+
              |  Grafana   |
              | (dashboards)|
              +------------+
```

All telemetry flows from the Flask app into the OTel Collector, which fans out to Jaeger (traces), Prometheus (metrics), and Loki (logs). Grafana ties them together with pre-configured datasources that support trace-to-log and log-to-trace linking.

---

## Quick Start

### Prerequisites
- Docker Desktop or Docker Engine + Compose v2
- 4 GB RAM free for the containers

```bash
# Clone and enter
git clone https://github.com/AsierCaballero/otel-labs.git
cd otel-labs

# Copy environment defaults (they work as-is)
cp .env.example .env

# Start everything
docker compose up -d

# Wait ~30 seconds, then check
docker compose ps
# All services should show "healthy" or "running"

# Generate test telemetry
chmod +x demo.sh && ./demo.sh
```

Alternatively, use the Makefile:

```bash
make up     # docker compose up -d
make logs   # tail logs
make down   # tear down
```

### Access the UIs

| Service | URL | Credentials |
|---|---|---|
| Grafana | http://localhost:3000 | admin / admin |
| Jaeger | http://localhost:16686 | -- |
| Prometheus | http://localhost:9090 | -- |
| Flask App | http://localhost:5000 | -- |
| OTel zPages | http://localhost:55679/debug/tracez | -- |

---

## Components

### Flask App (`app/`)

A CRUD API instrumented with OpenTelemetry SDK. Every endpoint produces a trace, red metrics, and structured logs with `trace_id` injection.

**Endpoints:**

| Method | Path | What it does |
|---|---|---|
| GET | `/api/items` | List items from SQLite (span `db.list_items`) |
| POST | `/api/items` | Create an item (span `db.create_item`) |
| GET | `/api/items/:id` | Get a single item (span `db.get_item`) |
| DELETE | `/api/items/:id` | Soft delete (span `db.delete_item`) |
| POST | `/api/process` | Batch processing with nested spans and configurable error rate |
| GET | `/metrics` | Prometheus metrics (scraped by the Collector) |
| GET | `/health/live`, `/health/ready` | Health checks (filtered out of traces) |

**Trace example in Jaeger:**

```
POST /api/process
  process.item (item_id=1, latency_ms=87)
  process.item (item_id=2, latency_ms=143) <- ERROR: ValueError
  process.item (item_id=3, latency_ms=62)
```

Run locally without Docker:

```bash
cd app
pip install -r requirements.txt
python app.py                        # falls back to ConsoleSpanExporter
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 python app.py  # with Collector
```

Run tests:

```bash
cd app
pip install -r requirements-dev.txt
pytest tests/ -v --cov=app --cov-report=term-missing
```

### OTel Collector (`otel-collector/`)

Central hub that receives OTLP from the app and exports to Jaeger, Prometheus, and Loki. Configuration lives in `config.yaml`.

### Jaeger

Stores and visualizes traces. Uses Badger storage (local disk) with persistent volume for development.

### Prometheus

Scrapes metrics from the Collector's Prometheus exporter endpoint (`:8889`). 7-day retention by default.

### Loki

Log aggregation system. The Collector ships logs with `trace_id` metadata, enabling Grafana's log-to-trace linking.

### Grafana (`grafana/provisioning/`)

Pre-provisioned datasources (Prometheus, Jaeger, Loki) with trace-to-log and log-to-trace links. Ships one dashboard (`flask-app.json`) showing requests per second, error rate, p95 latency, and database item counts.

---

## Configuration

### OTel Collector

The collector pipeline is defined in `otel-collector/config.yaml`. The default setup:

1. **Receivers**: OTLP gRPC (`:4317`) and OTLP HTTP (`:4318`)
2. **Processors**: Batch, memory limiter, attributes
3. **Exporters**: Jaeger gRPC, Prometheus (`:8889`), Loki gRPC, logging (debug)

### Environment variables (`.env`)

| Variable | Default | Description |
|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4317` | Collector endpoint for the app |
| `OTEL_SERVICE_NAME` | `flask-otel-demo` | Service name in traces/metrics |
| `DB_PATH` | `/tmp/app.db` | SQLite database path |
| `ENVIRONMENT` | `development` | Deployment environment tag |

---

## Deployment Options

### Local (Docker Compose)

The standard way to run the stack. See [Quick Start](#quick-start).

### Kubernetes

A DaemonSet manifest is provided in `kubernetes/otel-k8s.yaml` for running the OTel Collector as a cluster agent.

```bash
kubectl apply -f kubernetes/otel-k8s.yaml
kubectl get daemonset -n observability
kubectl logs -n observability daemonset/otel-collector-agent
```

Set `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector.observability:4317` in your Deployment to send telemetry to the agent.

---

## Swapping Backends (Vendor-Neutral)

Because the app speaks only OTLP to the Collector, switching backends means changing only the Collector config -- the application code stays the same.

```yaml
# Azure Monitor (Application Insights)
exporters:
  azuremonitor:
    connection_string: "${APPLICATIONINSIGHTS_CONNECTION_STRING}"

# Grafana Cloud (all-in-one)
exporters:
  otlp/grafana:
    endpoint: "${GRAFANA_CLOUD_OTLP_ENDPOINT}"
    headers:
      authorization: "Basic ${GRAFANA_CLOUD_KEY}"
```

---

## Author

**Asier Caballero** -- Senior DevOps Engineer & Cloud Architect
asier.caballero1@gmail.com | [linkedin.com/in/asier-caballero](https://linkedin.com/in/asier-caballero)
