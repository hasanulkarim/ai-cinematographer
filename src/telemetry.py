import os
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from config import Config

try:
    from agento11y import Client as Agento11yClient
except ImportError:
    # Graceful fallback mock if agento11y package is not installed yet
    class _MockRecorder:
        def __init__(self, generation_id="gen_mock"):
            self.generation_id = generation_id
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def set_result(self, *args, **kwargs):
            pass
        def set_call_error(self, *args, **kwargs):
            pass
        def err(self):
            return None

    class Agento11yClient:
        def start_generation(self, *args, **kwargs):
            import uuid
            return _MockRecorder(generation_id=f"gen_{uuid.uuid4().hex[:8]}")
        def shutdown(self):
            pass

def setup_telemetry():
    resource = Resource(attributes={
        "service.name": "ai-cinematographer-agent"
    })
    
    # 1. Setup TracerProvider
    tp = TracerProvider(resource=resource)
    
    # Resolve OTLP endpoint and Auth headers
    otlp_endpoint = Config.OTEL_EXPORTER_OTLP_ENDPOINT or Config.GRAFANA_OTLP_ENDPOINT
    headers = {}
    if Config.OTEL_EXPORTER_OTLP_HEADERS and "Authorization=" in Config.OTEL_EXPORTER_OTLP_HEADERS:
        headers["Authorization"] = Config.OTEL_EXPORTER_OTLP_HEADERS.split("Authorization=", 1)[1].strip()
    elif Config.GRAFANA_AUTH_HEADER:
        headers["Authorization"] = f"Basic {Config.GRAFANA_AUTH_HEADER.strip()}"
        
    metric_readers = []
    if otlp_endpoint and headers:
        # Trace exporter
        trace_endpoint = otlp_endpoint if otlp_endpoint.endswith("/v1/traces") else f"{otlp_endpoint.rstrip('/')}/v1/traces"
        tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(
            endpoint=trace_endpoint,
            headers=headers
        )))
        
        # Metric exporter
        metric_endpoint = otlp_endpoint if otlp_endpoint.endswith("/v1/metrics") else f"{otlp_endpoint.rstrip('/')}/v1/metrics"
        metric_readers.append(PeriodicExportingMetricReader(OTLPMetricExporter(
            endpoint=metric_endpoint,
            headers=headers
        )))
        
    trace.set_tracer_provider(tp)
    
    # 2. Setup MeterProvider (required by Agent Observability for gen_ai metrics)
    mp = MeterProvider(resource=resource, metric_readers=metric_readers)
    metrics.set_meter_provider(mp)
    
    # 3. Initialize Agent Observability Client
    # The client automatically picks up AGENTO11Y_* environment variables
    client = Agento11yClient()
    
    return trace.get_tracer(__name__), client

# Create singleton instances to import across the app
tracer, agento11y_client = setup_telemetry()
