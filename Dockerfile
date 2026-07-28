FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Keep in sync with Config.dashboard_port default in app/config.py.
EXPOSE 8080

# TODO: add a HEALTHCHECK once main.py/NiceGUI exposes something to poll
# (NiceGUI serves on "/" by default, which is fine as a health endpoint).

CMD ["python", "-m", "app.main"]
