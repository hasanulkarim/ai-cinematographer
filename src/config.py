import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

class Config:
    
     # Vertex AI vs Gemini Developer API
    USE_VERTEXAI = os.getenv("USE_VERTEXAI", "false").lower() in ("true", "1")
    GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
    GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    # Grafana OTLP Telemetry
    GRAFANA_OTLP_ENDPOINT = os.getenv("GRAFANA_OTLP_ENDPOINT")
    GRAFANA_AUTH_HEADER = os.getenv("GRAFANA_AUTH_HEADER")
    
    # Grafana Agent Observability
    AGENTO11Y_ENDPOINT = os.getenv("AGENTO11Y_ENDPOINT", "https://agento11y-prod-us-west-0.grafana.net")
    AGENTO11Y_AUTH_TENANT_ID = os.getenv("AGENTO11Y_AUTH_TENANT_ID", "1812797")
    AGENTO11Y_AUTH_TOKEN = os.getenv("AGENTO11Y_AUTH_TOKEN")
    
    OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://otlp-gateway-prod-us-west-0.grafana.net/otlp")
    OTEL_EXPORTER_OTLP_HEADERS = os.getenv("OTEL_EXPORTER_OTLP_HEADERS")

    @classmethod
    def validate(cls) -> None:
        if cls.USE_VERTEXAI:
            if not cls.GOOGLE_CLOUD_PROJECT:
                raise ValueError("Missing GOOGLE_CLOUD_PROJECT when USE_VERTEXAI is true.")
        else:
            if not cls.GEMINI_API_KEY:
                raise ValueError("Missing GEMINI_API_KEY environment variable.")


