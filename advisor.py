#!/usr/bin/env python3
"""
Ventilation + condensation advisor.

Reads the latest indoor (BME690) and outdoor (Open-Meteo) data logged by logger.py,
fetches tonight's forecast low, decides what to do with deterministic rules (airlib.decide),
then asks the LLM on the AI HAT+ 2 to phrase the advice. The LLM output is checked by
airlib.guard; if it fails, a rule-based message is shown instead.

Usage:
    python3 advisor.py                                   # default model (Qwen2.5-Instruct)
    MODEL=deepseek_r1_distill_qwen:1.5b python3 advisor.py
    GLAZING_U=1.4 python3 advisor.py                     # modern double glazing
"""

import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import airlib

DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).resolve().parent / "data" / "env.db"))
LAT = float(os.getenv("LAT", "52.205"))   # Cambridge, UK
LON = float(os.getenv("LON", "0.119"))
MIN_BASELINE_SAMPLES = 30
STALE_DATA_MIN = 10
FORECAST_URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}&hourly=temperature_2m&forecast_hours=12&timezone=UTC"
)


def iso_ago(minutes: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat(timespec="seconds")


def tonight_min_temp() -> float | None:
    """Lowest forecast outdoor temperature over the next 12 hours."""
    try:
        with urllib.request.urlopen(FORECAST_URL, timeout=10) as resp:
            temps = [t for t in json.load(resp)["hourly"]["temperature_2m"] if t is not None]
        return min(temps) if temps else None
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError):
        return None


def gather_facts(conn: sqlite3.Connection) -> dict:
    q = lambda sql, *a: conn.execute(sql, a).fetchone()

    indoor = q("SELECT ts, temperature_c, humidity_pct FROM indoor ORDER BY ts DESC LIMIT 1")
    outdoor = q("SELECT temperature_c, humidity_pct, precipitation_mm, european_aqi "
                "FROM outdoor ORDER BY ts DESC LIMIT 1")
    if not indoor or not outdoor:
        sys.exit("Not enough data yet: need at least one indoor and one outdoor reading.")

    f = {"indoor_temp": indoor[1], "indoor_rh": indoor[2],
         "outdoor_temp": outdoor[0], "outdoor_rh": outdoor[1],
         "outdoor_rain_mm": outdoor[2], "outdoor_aqi": outdoor[3]}
    f["data_age_min"] = (datetime.now(timezone.utc) - datetime.fromisoformat(indoor[0])).total_seconds() / 60

    hour_ago = q("SELECT humidity_pct FROM indoor WHERE ts <= ? ORDER BY ts DESC LIMIT 1", iso_ago(60))
    f["rh_change_1h"] = f["indoor_rh"] - hour_ago[0] if hour_ago else None

    latest_gas = q("SELECT gas_ohms FROM indoor WHERE gas_ohms IS NOT NULL ORDER BY ts DESC LIMIT 1")
    gas_rows = sorted(r[0] for r in conn.execute(
        "SELECT gas_ohms FROM indoor WHERE gas_ohms IS NOT NULL AND ts >= ?", (iso_ago(7 * 24 * 60),)))
    f["gas_ratio"] = (latest_gas[0] / gas_rows[len(gas_rows) // 2]
                      if latest_gas and len(gas_rows) >= MIN_BASELINE_SAMPLES else None)
    return f


def main() -> None:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)  # read-only: never blocks the logger
    f = gather_facts(conn)
    conn.close()
    f["tonight_min_temp"] = tonight_min_temp()

    d = airlib.decide(f)
    x = d.derived
    print(f"Indoor   {f['indoor_temp']:.1f}C  {f['indoor_rh']:.0f}%  ({x['indoor_ah']:.1f} g/m3 water, "
          f"dew point {x['dew_point']:.1f}C)")
    print(f"Outdoor  {f['outdoor_temp']:.1f}C  {f['outdoor_rh']:.0f}%  ({x['outdoor_ah']:.1f} g/m3 water)"
          f"  AQI {f['outdoor_aqi']}")
    night = f["tonight_min_temp"]
    print(f"Tonight  low {'unknown (forecast failed)' if night is None else f'{night:.1f}C'} -> window glass "
          f"about {x['glass_tonight']:.1f}C, surface humidity {x['glass_rh_tonight']:.0f}% "
          f"(glazing U={airlib.GLAZING_U})")
    print(f"Gas vs baseline: {'not enough data yet' if f['gas_ratio'] is None else format(f['gas_ratio'], '.0%')}")
    if f["rh_change_1h"] is not None:
        print(f"Humidity change last hour: {f['rh_change_1h']:+.1f}%")
    if f["data_age_min"] > STALE_DATA_MIN:
        print(f"WARNING: latest indoor reading is {f['data_age_min']:.0f} min old - is the logger running?")
    print(f"\nDecision: {d.action}")
    for r in d.reasons:
        print(f"  - {r}")

    fallback = f"{airlib.ACTION_TEXT[d.action]} Reason: {'; '.join(d.reasons)}."
    prompt = airlib.build_prompt(f, d)
    try:
        raw, secs = airlib.ask_llm(prompt)
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
        print(f"\n(LLM unavailable: {exc}) Fallback advice:\n{fallback}")
        return

    g = airlib.guard(raw, prompt, d.action)
    tag = f"{airlib.DEFAULT_MODEL}, {secs:.1f}s on AI HAT, prompt {airlib.PROMPT_VERSION}"
    if g.ok:
        cleaned = f", cleaned: {', '.join(g.format_issues)}" if g.format_issues else ""
        print(f"\nAdvisor ({tag}{cleaned}):\n{g.text}")
    else:
        print(f"\nAdvisor ({tag}) REJECTED by guard: {'; '.join(g.problems)}")
        print(f"  model said: {raw!r}")
        print(f"Fallback advice:\n{fallback}")


if __name__ == "__main__":
    main()
