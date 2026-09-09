FROM python:3.11-slim

WORKDIR /app

# Install apt dependencies
RUN apt-get update && apt-get install -y curl tar && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download and install Grafana MCP server for Linux
RUN curl -sL https://github.com/grafana/mcp-grafana/releases/download/v1.3.0/mcp-grafana_Linux_x86_64.tar.gz | tar -xz -C /usr/local/bin mcp-grafana

# Copy application source
COPY src/ ./src/

# Expose the Streamlit port
EXPOSE 8501

# Health check for Cloud Run
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run Streamlit — Cloud Run provides PORT env var but we bind to 8501
ENTRYPOINT ["streamlit", "run", "src/app.py", \
    "--server.port=8501", \
    "--server.address=0.0.0.0", \
    "--server.headless=true", \
    "--browser.gatherUsageStats=false"]
