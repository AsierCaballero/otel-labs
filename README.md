# 🔭 OpenTelemetry DevOps Labs

Stack de observabilidad **vendor-free** con OpenTelemetry, Jaeger, Prometheus, Loki y Grafana. Arranca con un comando y tienes trazas, métricas y logs correlacionados.

[![OTel](https://img.shields.io/badge/OpenTelemetry-0.96-000?style=for-the-badge&logo=opentelemetry)](https://opentelemetry.io/)
[![Grafana](https://img.shields.io/badge/Grafana-10.4-F46800?style=for-the-badge&logo=grafana&logoColor=white)](#)
[![Jaeger](https://img.shields.io/badge/Jaeger-1.55-66CFE3?style=for-the-badge)](#)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](#)

---

## ¿Por qué OpenTelemetry en vez de Datadog?

| | Datadog / New Relic | OpenTelemetry |
|--|--|--|
| Coste | $18–$23/host/mes | Gratis (estándar abierto) |
| Vendor lock-in | Total | Cero — cambia el backend sin tocar el código |
| Estándar | Propio | CNCF — respaldado por Google, Microsoft, Amazon |
| Correlación Traces+Logs | De pago | Automática via `trace_id` |
| Kubernetes nativo | Plugin de pago | DaemonSet incluido |

---

## Estructura del repositorio

```
opentelemetry-devops-labs/
│
├── app/                        ← Flask app con OTel completo
│   ├── app.py                  ← Traces + Metrics + Logs correlacionados
│   ├── requirements.txt
│   ├── Dockerfile              ← Multi-stage, non-root
│   └── tests/
│       └── test_app.py         ← Tests unitarios (pytest)
│
├── otel-collector/
│   └── config.yaml             ← Collector: OTLP → Jaeger + Prometheus + Loki
│
├── prometheus/
│   └── prometheus.yml          ← Scrape del Collector
│
├── loki/
│   └── loki-config.yaml        ← Storage de logs
│
├── grafana/
│   └── provisioning/
│       ├── datasources/        ← Prometheus + Jaeger + Loki con trace linking
│       └── dashboards/
│           └── flask-app.json  ← Dashboard: req/s, error rate, p95, items DB
│
├── kubernetes/
│   └── otel-k8s.yaml           ← DaemonSet + RBAC + Service
│
├── docker-compose.yml          ← Stack completo local
├── demo.sh                     ← Genera telemetría de prueba
└── .env.example
```

---

## Quick Start — stack completo en 2 minutos

### Prerrequisitos
- Docker Desktop o Docker Engine + Compose
- 4 GB RAM disponibles para los contenedores

```bash
# 1. Clonar
git clone https://github.com/asier-caballero/opentelemetry-devops-labs
cd opentelemetry-devops-labs

# 2. Copiar variables de entorno (los defaults funcionan sin cambios)
cp .env.example .env

# 3. Arrancar todo el stack
docker compose up -d

# 4. Esperar ~30 segundos y verificar
docker compose ps
# Todos los servicios deben mostrar "healthy" o "running"

# 5. Generar telemetría de prueba
chmod +x demo.sh && ./demo.sh
```

### Abrir las UIs
| Servicio | URL | Credenciales |
|---------|-----|-------------|
| **Grafana** | http://localhost:3000 | admin / admin |
| **Jaeger** | http://localhost:16686 | — |
| **Prometheus** | http://localhost:9090 | — |
| **Flask App** | http://localhost:5000 | — |
| **OTel zPages** | http://localhost:55679/debug/tracez | — |

---

## Ejecutar tests

```bash
cd app
pip install -r requirements-dev.txt
pytest tests/ -v --cov=app --cov-report=term-missing
```

---

## Ejecutar la app en local (sin Docker)

```bash
cd app
pip install -r requirements.txt

# La app funciona sin Collector — cae a ConsoleSpanExporter
python app.py

# Con Collector local corriendo:
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 python app.py
```

---

## Qué hace la Flask app

- **`GET /api/items`** — lista items de SQLite (span `db.list_items`)
- **`POST /api/items`** — crea item (span `db.create_item`)
- **`GET /api/items/:id`** — obtiene item (span `db.get_item`)
- **`DELETE /api/items/:id`** — soft delete (span `db.delete_item`)
- **`POST /api/process`** — procesa un batch con spans anidados y error rate configurable
- **`GET /metrics`** — métricas Prometheus (scrapeadas por el Collector)
- **`GET /health/live`** y **`/health/ready`** — health checks (filtrados del trace view)

### Traces en Jaeger

```
POST /api/process
└── process.item (item_id=1, latency_ms=87)
└── process.item (item_id=2, latency_ms=143) ← ERROR: ValueError
└── process.item (item_id=3, latency_ms=62)
```

---

## Desplegar en Kubernetes

```bash
# Aplicar DaemonSet + RBAC + Service
kubectl apply -f kubernetes/otel-k8s.yaml

# Verificar
kubectl get daemonset -n observability
kubectl get pods -n observability

# Ver logs del agente
kubectl logs -n observability daemonset/otel-collector-agent
```

Configura `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector.observability:4317` en tu Deployment para enviar telemetría al agente.

---

## Cambiar el backend (vendor-neutral)

Solo hay que cambiar el exportador en `otel-collector/config.yaml`:

```yaml
# Azure Monitor (Application Insights)
exporters:
  azuremonitor:
    connection_string: "${APPLICATIONINSIGHTS_CONNECTION_STRING}"

# Grafana Cloud (todo en uno)
exporters:
  otlp/grafana:
    endpoint: "${GRAFANA_CLOUD_OTLP_ENDPOINT}"
    headers:
      authorization: "Basic ${GRAFANA_CLOUD_KEY}"
```

El código de la app Flask **no cambia**. Eso es la ventaja de OTel.

---

## Autor

**Asier Caballero** — Senior DevOps Engineer & Cloud Architect  
📧 asier.caballero1@gmail.com | 💼 [linkedin.com/in/asier-caballero](https://linkedin.com/in/asier-caballero)
