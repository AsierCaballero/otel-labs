#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# demo.sh — Genera telemetría de prueba contra la Flask app
# Uso: ./demo.sh [URL]
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

BASE="${1:-http://localhost:5000}"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

log()  { echo -e "${GREEN}[demo]${NC} $*"; }
info() { echo -e "${YELLOW}[info]${NC} $*"; }

# Esperar a que la app esté lista
log "Esperando a que la app esté lista en $BASE ..."
for i in $(seq 1 30); do
  if curl -sf "$BASE/health/live" > /dev/null 2>&1; then
    log "App lista ✅"
    break
  fi
  echo -n "."
  sleep 2
done

echo ""
info "Generando telemetría — ábrelo en Jaeger: http://localhost:16686"
info "Dashboards Grafana: http://localhost:3000 (admin/admin)"
echo ""

# 1. Crear items
log "Creando items..."
for name in "Laptop Dell" "Monitor LG" "Teclado Logitech" "Ratón gaming" "Webcam HD"; do
  curl -sf -X POST "$BASE/api/items" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"$name\", \"description\": \"Producto de demo\"}" \
    > /dev/null
  echo -n "."
done
echo " ✅"

# 2. Listar items (genera spans de lectura DB)
log "Leyendo items (x10)..."
for _ in $(seq 1 10); do
  curl -sf "$BASE/api/items" > /dev/null
  sleep 0.3
done
echo " ✅"

# 3. Batch process (genera spans anidados)
log "Procesando batches (x5)..."
for _ in $(seq 1 5); do
  curl -sf -X POST "$BASE/api/process" \
    -H "Content-Type: application/json" \
    -d '{"items": [{"id":1},{"id":2},{"id":3},{"id":4},{"id":5}], "error_rate": 0.15}' \
    > /dev/null
  sleep 0.5
done
echo " ✅"

# 4. Mix de requests para simular tráfico real
log "Simulando tráfico real (60s)..."
END=$((SECONDS + 60))
while [ $SECONDS -lt $END ]; do
  # Requests normales
  curl -sf "$BASE/api/items" > /dev/null &
  curl -sf "$BASE/api/items/1" > /dev/null &
  curl -sf -X POST "$BASE/api/process" \
    -H "Content-Type: application/json" \
    -d '{"items":[{"id":1},{"id":2}],"error_rate":0.1}' > /dev/null &
  
  # Request 404 intencionada
  curl -sf "$BASE/api/items/9999" > /dev/null 2>&1 || true &
  
  wait
  sleep 1
done
echo " ✅"

echo ""
log "Demo completado 🎉"
log "→ Jaeger (traces):   http://localhost:16686"
log "→ Grafana (metrics): http://localhost:3000"
log "→ Prometheus:        http://localhost:9090"
log "→ OTel zPages:       http://localhost:55679/debug/tracez"
