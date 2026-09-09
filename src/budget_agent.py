import os
import asyncio
from typing import Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Define the path to the MCP Grafana executable
MCP_GRAFANA_EXE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mcp-grafana-bin', 'mcp-grafana.exe')

async def get_budget_report(grafana_url: str, grafana_token: str) -> str:
    """
    Connects to the Grafana MCP server and queries Prometheus for recent token usage.
    """
    if not grafana_url or not grafana_token:
        return "⚠️ **Budget Report Unavailable:** Missing `GRAFANA_URL` or `GRAFANA_API_TOKEN` in `.env`."
        
    # Configure the server parameters
    server_params = StdioServerParameters(
        command=MCP_GRAFANA_EXE,
        args=[],  # stdio is default transport
        env={
            **os.environ,
            "GRAFANA_URL": grafana_url,
            "GRAFANA_SERVICE_ACCOUNT_TOKEN": grafana_token, 
        }
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the connection
                await session.initialize()
                
                # PromQL query to get token usage over the last 15 minutes
                promql_query = 'sum(increase(gen_ai_client_token_usage_sum[15m])) by (gen_ai_token_type)'
                
                # Call the query_prometheus tool provided by the Grafana MCP
                try:
                    result = await session.call_tool("query_prometheus", arguments={
                        "expr": promql_query,
                        "datasourceUid": "grafanacloud-prom",
                        "startTime": "now-15m",
                        "endTime": "now",
                        "stepSeconds": 60
                    })
                    
                    if getattr(result, 'isError', False):
                        return f"Failed to fetch budget data: {result.content}"
                    import json
                    
                    # Extract the JSON string from the TextContent object
                    text_content = result.content[0].text
                    parsed_data = json.loads(text_content)
                    
                    input_tokens = 0.0
                    output_tokens = 0.0
                    
                    # Parse the timeseries data (taking the last value of the increase function)
                    if "data" in parsed_data:
                        for series in parsed_data["data"]:
                            metric_type = series.get("metric", {}).get("gen_ai_token_type", "unknown")
                            values = series.get("values", [])
                            if values:
                                # Get the most recent value from the timeseries
                                last_value = float(values[-1][1])
                                if metric_type == "input":
                                    input_tokens = last_value
                                elif metric_type == "output":
                                    output_tokens = last_value
                    
                    # Cost estimates (Example rates: $0.15 / 1M input, $0.60 / 1M output)
                    # Adjust these rates based on the actual model being used
                    input_cost = (input_tokens / 1_000_000) * 0.15
                    output_cost = (output_tokens / 1_000_000) * 0.60
                    total_cost = input_cost + output_cost
                    
                    # Format as a Markdown Table
                    report = f"--- Studio Executive Budget Report ---\n\n"
                    report += "I've reviewed the Grafana Cloud metrics for our latest shoot over the last 15 minutes.\n\n"
                    report += "| Token Type | Tokens Used | Est. Cost ($) |\n"
                    report += "|------------|-------------|---------------|\n"
                    report += f"| **Input**  | {int(input_tokens):,} | ${input_cost:.5f} |\n"
                    report += f"| **Output** | {int(output_tokens):,} | ${output_cost:.5f} |\n"
                    report += f"| **Total**  | {int(input_tokens + output_tokens):,} | **${total_cost:.5f}** |\n\n"
                    report += "Keep an eye on those tokens, director! We're not made of money."
                    
                    return report
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    return f"Error executing PromQL query via MCP: {str(e)}"
    except Exception as e:
        return f"Failed to connect to Grafana MCP server: {str(e)}"

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    token = os.environ.get("GRAFANA_API_TOKEN")
    url = os.environ.get("GRAFANA_URL")
    
    if token and url:
        print("Testing Grafana MCP Connection...")
        report = asyncio.run(get_budget_report(url, token))
        print(report)
    else:
        print("Missing GRAFANA_API_TOKEN or GRAFANA_URL in .env")
