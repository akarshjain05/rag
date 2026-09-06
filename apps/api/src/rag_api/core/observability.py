from opentelemetry import trace
from prometheus_client import Counter, Histogram

tracer = trace.get_tracer("rag_api")

llm_calls_total = Counter("rag_llm_calls_total", "LLM calls by pipeline stage", ["stage", "provider"])
llm_call_seconds = Histogram("rag_llm_call_seconds", "LLM call latency by stage", ["stage"])
retrieval_confidence = Histogram("rag_retrieval_confidence", "Distribution of retrieval confidence scores")
import sentry_sdk
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

def init_observability(app, settings):
    # Sentry
    if getattr(settings, "sentry_dsn", None):
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=1.0,
        )

    # OpenTelemetry Tracing
    provider = TracerProvider()
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=getattr(settings, "otlp_endpoint", "http://localhost:4318/v1/traces")))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(app)

    # Prometheus
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app)
