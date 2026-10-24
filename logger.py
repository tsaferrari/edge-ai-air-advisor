#!/usr/bin/env python3
"""
Indoor/outdoor environment logger.

- Reads the BME690 (I2C) every SENSOR_INTERVAL_S seconds.
- Fetches outdoor weather + air quality from Open-Meteo every WEATHER_INTERVAL_S seconds.
- Stores everything in SQLite (data/env.db) for later analysis / model training.
- Designed to run as a systemd service: logs to stdout (journald), shuts down cleanly on SIGTERM.
"""

import json
import logging
import os
import signal
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from bme690 import BME690

# --- Configuration (override via environment variables) ---------------------
SENSOR_INTERVAL_S = int(os.getenv("SENSOR_INTERVAL_S", "60"))
WEATHER_INTERVAL_S = int(os.getenv("WEATHER_INTERVAL_S", "900"))
LAT = float(os.getenv("LAT", "52.205"))   # Cambridge, UK
LON = float(os.getenv("LON", "0.119"))
DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).resolve().parent / "data" / "env.db"))
HTTP_TIMEOUT_S = 10

WEATHER_URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}"
    "&current=temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,precipitation"
)
AIR_QUALITY_URL = (
    "https://air-quality-api.open-meteo.com/v1/air-quality"
    f"?latitude={LAT}&longitude={LON}"
    "&current=pm2_5,pm10,european_aqi"
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS indoor (
    ts            TEXT PRIMARY KEY,   -- ISO 8601 UTC
    temperature_c REAL,
    humidity_pct  REAL,
    pressure_hpa  REAL,
    gas_ohms      REAL,               -- NULL when heater not stable
    heat_stable   INTEGER
);
CREATE TABLE IF NOT EXISTS outdoor (
    ts               TEXT PRIMARY KEY,
    temperature_c    REAL,
    humidity_pct     REAL,
    pressure_hpa     REAL,
    wind_kmh         REAL,
    precipitation_mm REAL,
    pm2_5            REAL,
    pm10             REAL,
    european_aqi     REAL
);
"""

log = logging.getLogger("env_logger")
stop_event = threading.Event()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- Database ---------------------------------------------------------------
def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")    # safe concurrent reads while logging
    conn.execute("PRAGMA synchronous=NORMAL")  # fewer fsyncs -> less SD card wear
    conn.executescript(SCHEMA)
    return conn


def insert(conn: sqlite3.Connection, table: str, row: dict) -> None:
    cols = ", ".join(row)
    params = ", ".join(f":{k}" for k in row)
    conn.execute(f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({params})", row)
    conn.commit()


# --- Sensor -----------------------------------------------------------------
def configure_sensor(sensor: BME690) -> None:
    """Apply a sensible gas heater profile. Wrapped in try in case the
    library API differs slightly from the BME680 library it is based on."""
    try:
        sensor.set_gas_heater_temperature(320)  # degC
        sensor.set_gas_heater_duration(150)     # ms
        sensor.select_gas_heater_profile(0)
    except AttributeError as exc:
        log.warning("Could not set heater profile, using library defaults: %s", exc)


def read_indoor(sensor: BME690, retries: int = 3) -> dict | None:
    for _ in range(retries):
        if sensor.get_sensor_data():
            d = sensor.data
            stable = bool(getattr(d, "heat_stable", True))
            return {
                "ts": utc_now(),
                "temperature_c": round(d.temperature, 2),
                "humidity_pct": round(d.humidity, 2),
                "pressure_hpa": round(d.pressure, 2),
                "gas_ohms": round(d.gas_resistance) if stable else None,
                "heat_stable": int(stable),
            }
        time.sleep(0.5)
    return None


# --- Outdoor data -----------------------------------------------------------
def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_S) as resp:
        return json.load(resp)


def read_outdoor() -> dict | None:
    try:
        cur = fetch_json(WEATHER_URL)["current"]
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
        log.warning("Weather fetch failed: %s", exc)
        return None

    row = {
        "ts": utc_now(),
        "temperature_c": cur.get("temperature_2m"),
        "humidity_pct": cur.get("relative_humidity_2m"),
        "pressure_hpa": cur.get("surface_pressure"),
        "wind_kmh": cur.get("wind_speed_10m"),
        "precipitation_mm": cur.get("precipitation"),
        "pm2_5": None,
        "pm10": None,
        "european_aqi": None,
    }

    # Air quality is a separate API; don't lose the weather row if it fails.
    try:
        aq = fetch_json(AIR_QUALITY_URL)["current"]
        row.update(pm2_5=aq.get("pm2_5"), pm10=aq.get("pm10"), european_aqi=aq.get("european_aqi"))
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
        log.warning("Air quality fetch failed: %s", exc)

    return row


# --- Main loop --------------------------------------------------------------
def handle_signal(signum, _frame):
    log.info("Received signal %s, shutting down", signum)
    stop_event.set()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    sensor = BME690()
    configure_sensor(sensor)
    conn = open_db(DB_PATH)
    log.info("Logging to %s (sensor every %ss, weather every %ss)", DB_PATH, SENSOR_INTERVAL_S, WEATHER_INTERVAL_S)

    next_sensor = next_weather = time.monotonic()
    try:
        while not stop_event.is_set():
            now = time.monotonic()

            if now >= next_sensor:
                row = read_indoor(sensor)
                if row:
                    insert(conn, "indoor", row)
                    log.info("indoor  %.2fC %.1f%% %.1fhPa gas=%s",
                             row["temperature_c"], row["humidity_pct"], row["pressure_hpa"], row["gas_ohms"])
                else:
                    log.warning("No sensor data this cycle")
                next_sensor += SENSOR_INTERVAL_S

            if now >= next_weather:
                row = read_outdoor()
                if row:
                    insert(conn, "outdoor", row)
                    log.info("outdoor %sC %s%% aqi=%s", row["temperature_c"], row["humidity_pct"], row["european_aqi"])
                next_weather += WEATHER_INTERVAL_S

            stop_event.wait(max(0.0, min(next_sensor, next_weather) - time.monotonic()))
    finally:
        conn.close()
        log.info("Stopped")


if __name__ == "__main__":
    main()
