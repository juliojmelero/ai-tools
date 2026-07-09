FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
COPY pyproject.toml .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY mcp_server.py .
COPY tools ./tools
COPY research_config ./research_config
COPY research_models ./research_models
COPY research_engine ./research_engine
COPY research_cache ./research_cache

RUN pip install -e .

CMD ["python", "mcp_server.py"]
