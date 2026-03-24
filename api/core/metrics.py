"""
Métricas Prometheus customizadas do Freky.

Importar em main.py para registrar; usar em routes/scans.py para incrementar.
"""

from prometheus_client import Counter, Histogram, Gauge

# Total de scans processados, particionado por decisão
scans_total = Counter(
    "freky_scans_total",
    "Total de scans processados",
    ["decision"],
)

# Tempo de inferência do modelo ONNX (em segundos)
inference_duration = Histogram(
    "freky_inference_duration_seconds",
    "Tempo de inferência do modelo ONNX",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# Itens detectados por classe
detections_total = Counter(
    "freky_detections_total",
    "Total de itens detectados por classe",
    ["class_name"],
)

# Conexões WebSocket ativas
websocket_connections = Gauge(
    "freky_websocket_connections_active",
    "Número de conexões WebSocket abertas",
)
