FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Copy mcp_server package
COPY mcp_server/ ./mcp_server/

# Copy environment file template
COPY .env.example ./

# Create non-root user
RUN useradd -m -u 1000 mcpuser && chown -R mcpuser:mcpuser /app
USER mcpuser

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# The server runs on STDIO, no port exposure needed
# For MCP Inspector testing, run: mcp-inspector python -m mcp_server.server

# Run the MCP server
CMD ["python", "-m", "mcp_server.server"]
