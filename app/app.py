"""
Flask app con OpenTelemetry — Traces + Metrics + Logs correlacionados

OTel es OPCIONAL: la app funciona perfectamente sin los paquetes instalados.
Cuando está disponible, envía telemetría completa al Collector.

Ejecutar local (sin OTel): python app.py
Ejecutar en Docker (con OTel): docker compose up
Tests: python -m unittest tests.test_app -v
"""
import os
import time
import random
import logging
import sqlite3

from flask import Flask, jsonify, request, g

# ── OpenTelemetry — importación opcional ─────────────────────────
# Si los paquetes no están instalados la app sigue funcionando.
# En producción (Docker) todos los paquetes están en el requirements.txt.
OTEL_AVAILABLE = False
try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.instrumentation.flask import FlaskInstrumentor
    from opentelemetry.instrumentation.sqlite3 import SQLite3Instrumentor
    OTEL_AVAILABLE = True
except ImportError:
    pass  # Sin OTel: la app funciona, simplemente no envía telemetría

# ── Configuración via env vars ────────────────────────────────────
OTEL_ENDPOINT   = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
SERVICE_NAME    = os.getenv("OTEL_SERVICE_NAME", "flask-otel-demo")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")
ENVIRONMENT     = os.getenv("ENVIRONMENT", "development")
PORT            = int(os.getenv("PORT", "5000"))
DB_PATH         = os.getenv("DB_PATH", "/tmp/app.db")

# ── No-op tracer/meter para cuando OTel no está instalado ────────
class _NoopSpan:
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def set_attribute(self, *a): pass
    def set_status(self, *a): pass
    def record_exception(self, *a): pass

class _NoopTracer:
    def start_as_current_span(self, *a, **kw): return _NoopSpan()

class _NoopCounter:
    def add(self, *a, **kw): pass

class _NoopHistogram:
    def record(self, *a, **kw): pass

_noop_tracer   = _NoopTracer()
_noop_counter  = _NoopCounter()
_noop_histogram = _NoopHistogram()

# ── Setup OTel (solo si está disponible) ─────────────────────────
if OTEL_AVAILABLE:
    resource = Resource.create({
        "service.name":           SERVICE_NAME,
        "service.version":        SERVICE_VERSION,
        "deployment.environment": ENVIRONMENT,
    })

    # Traces
    _tp = TracerProvider(resource=resource)
    try:
        _tp.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True))
        )
    except Exception:
        _tp.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(_tp)
    tracer = trace.get_tracer(SERVICE_NAME, SERVICE_VERSION)

    # Metrics
    try:
        _exporter = OTLPMetricExporter(endpoint=OTEL_ENDPOINT, insecure=True)
    except Exception:
        _exporter = ConsoleMetricExporter()
    _reader = PeriodicExportingMetricReader(_exporter, export_interval_millis=15000)
    _mp = MeterProvider(resource=resource, metric_readers=[_reader])
    metrics.set_meter_provider(_mp)
    meter = metrics.get_meter(SERVICE_NAME, SERVICE_VERSION)

    http_requests_total  = meter.create_counter(
        "http_requests_total", description="Total HTTP requests", unit="1")
    http_request_duration = meter.create_histogram(
        "http_request_duration_seconds", description="HTTP request duration", unit="s")
else:
    tracer              = _noop_tracer
    http_requests_total  = _noop_counter
    http_request_duration = _noop_histogram

# ── Logging con trace context ─────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
log = logging.getLogger(__name__)

# ── Flask app ─────────────────────────────────────────────────────
app = Flask(__name__)

if OTEL_AVAILABLE:
    FlaskInstrumentor().instrument_app(app)
    SQLite3Instrumentor().instrument()

# ── Database (SQLite para demo — sin dependencias externas) ───────
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            description TEXT,
            active      INTEGER DEFAULT 1,
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    """)
    db.commit()
    db.close()

def get_item_count() -> int:
    try:
        db = sqlite3.connect(DB_PATH)
        row = db.execute("SELECT COUNT(*) FROM items WHERE active=1").fetchone()
        db.close()
        return row[0] if row else 0
    except Exception:
        return 0

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()

# ── Middleware: métricas por request ──────────────────────────────
@app.before_request
def start_timer():
    g.start = time.time()

@app.after_request
def record_metrics(response):
    duration = time.time() - g.get("start", time.time())
    labels = {
        "method":      request.method,
        "endpoint":    request.endpoint or "unknown",
        "status_code": str(response.status_code),
        "environment": ENVIRONMENT,
    }
    http_requests_total.add(1, labels)
    http_request_duration.record(duration, labels)
    return response

# ── Routes ────────────────────────────────────────────────────────
@app.route("/")
def index():
    return jsonify({
        "service":     SERVICE_NAME,
        "version":     SERVICE_VERSION,
        "environment": ENVIRONMENT,
        "tracing":     "opentelemetry",
        "endpoints": ["/api/items", "/api/process", "/health/live", "/health/ready", "/metrics"],
    })


@app.route("/health/live")
def liveness():
    return jsonify({"status": "alive", "service": SERVICE_NAME}), 200


@app.route("/health/ready")
def readiness():
    checks = {"database": "ok"}
    status = 200
    try:
        get_db().execute("SELECT 1").fetchone()
    except Exception as e:
        checks["database"] = f"error: {e}"
        status = 503
    return jsonify({"status": "ready" if status == 200 else "not_ready", "checks": checks}), status


@app.route("/api/items", methods=["GET"])
def list_items():
    with tracer.start_as_current_span("db.list_items") as span:
        db = get_db()
        rows = db.execute(
            "SELECT id, name, description, active, created_at FROM items WHERE active=1 ORDER BY id DESC"
        ).fetchall()
        items = [dict(r) for r in rows]
        span.set_attribute("db.result_count", len(items))
        log.info("Listed %d items", len(items))
        return jsonify({"items": items, "total": len(items)})


@app.route("/api/items", methods=["POST"])
def create_item():
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "Campo 'name' requerido"}), 400

    with tracer.start_as_current_span("db.create_item") as span:
        span.set_attribute("item.name", data["name"])
        db = get_db()
        cursor = db.execute(
            "INSERT INTO items (name, description) VALUES (?, ?)",
            (data["name"], data.get("description", ""))
        )
        db.commit()
        item_id = cursor.lastrowid
        row = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        log.info("Created item id=%d name=%s", item_id, data["name"])
        return jsonify(dict(row)), 201


@app.route("/api/items/<int:item_id>", methods=["GET"])
def get_item(item_id):
    with tracer.start_as_current_span("db.get_item") as span:
        span.set_attribute("item.id", item_id)
        row = get_db().execute("SELECT * FROM items WHERE id=? AND active=1", (item_id,)).fetchone()
        if not row:
            span.set_attribute("item.found", False)
            return jsonify({"error": "Item no encontrado"}), 404
        span.set_attribute("item.found", True)
        return jsonify(dict(row))


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    with tracer.start_as_current_span("db.delete_item") as span:
        span.set_attribute("item.id", item_id)
        db = get_db()
        row = db.execute("SELECT id FROM items WHERE id=? AND active=1", (item_id,)).fetchone()
        if not row:
            return jsonify({"error": "Item no encontrado"}), 404
        db.execute("UPDATE items SET active=0 WHERE id=?", (item_id,))
        db.commit()
        log.info("Deleted item id=%d", item_id)
        return jsonify({"message": f"Item {item_id} eliminado"}), 200


@app.route("/api/process", methods=["POST"])
def process_items():
    """
    Endpoint que demuestra spans anidados y propagación de contexto.
    Simula procesamiento con latencia variable y tasa de error configurable.
    """
    data = request.get_json(silent=True) or {}
    items = data.get("items", [{"id": i} for i in range(1, 4)])
    error_rate = float(data.get("error_rate", 0.1))  # 10% por defecto

    current_span = _NoopSpan()
    if OTEL_AVAILABLE:
        import opentelemetry.trace as _trace
        current_span = _trace.get_current_span()
    current_span.set_attribute("batch.size", len(items))
    current_span.set_attribute("batch.error_rate", error_rate)

    results = []
    errors  = 0

    for item in items:
        item_id = item.get("id", "?")
        with tracer.start_as_current_span(f"process.item") as span:
            span.set_attribute("item.id", str(item_id))

            # Latencia realista variable (50-300ms)
            latency = random.uniform(0.05, 0.3)
            time.sleep(latency)

            if random.random() < error_rate:
                errors += 1
                ex = ValueError(f"Fallo procesando item {item_id}")
                span.record_exception(ex)
                results.append({"id": item_id, "status": "error", "latency_ms": round(latency * 1000)})
            else:
                results.append({"id": item_id, "status": "ok", "latency_ms": round(latency * 1000)})

    log.info("Batch processed: total=%d errors=%d", len(items), errors)
    return jsonify({
        "total":     len(items),
        "ok":        len(items) - errors,
        "errors":    errors,
        "results":   results,
    })


@app.route("/metrics")
def prometheus_metrics():
    """Métricas en formato texto Prometheus — scrapeado por el Collector."""
    item_count = get_item_count()
    output = (
        "# HELP items_total Total active items in database\n"
        "# TYPE items_total gauge\n"
        f'items_total{{service="{SERVICE_NAME}",env="{ENVIRONMENT}"}} {item_count}\n'
        "# HELP app_info Build info\n"
        "# TYPE app_info gauge\n"
        f'app_info{{version="{SERVICE_VERSION}",service="{SERVICE_NAME}"}} 1\n'
    )
    return output, 200, {"Content-Type": "text/plain; version=0.0.4"}


# ── Entrypoint ────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    log.info("Starting %s v%s on port %d [%s]", SERVICE_NAME, SERVICE_VERSION, PORT, ENVIRONMENT)
    app.run(host="0.0.0.0", port=PORT, debug=(ENVIRONMENT == "development"))
