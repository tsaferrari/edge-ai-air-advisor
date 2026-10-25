#!/usr/bin/env python3
"""
Air advisor on the Pimoroni Display HAT Mini (320x240).

Pages (buttons):
    A  Advice   - what to do now, written by the LLM on the AI HAT+ 2
    B  Now      - indoor and outdoor readings
    X  Tonight  - condensation / mould risk on the windows tonight
    Y  Refresh  - re-read the data and ask the LLM again

Power-saving behaviour:
    - The LLM only runs when the decision changes, or every LLM_REFRESH_S
      (default 30 min), never more often than LLM_MIN_GAP_S. Between runs the
      AI HAT sits idle.
    - The screen backlight turns off after SCREEN_TIMEOUT_S without a button
      press. Any button wakes it, and so does a new recommendation.
    - The RGB LED shows the current decision at low brightness, so the status
      is visible with the screen off.
    - The screen is only redrawn when a displayed value has changed.

Testing: LLM_MODE=manual makes the model run only when you press Y, and
FACTS_INTERVAL_S sets how often the display re-reads the database.

Work split: everything except text generation runs on the Pi's CPU (reading
the database, maths, decisions, checking the LLM's answer, drawing). Only the
language model runs on the AI HAT.

Usage:
    python3 display.py                    # run on the Display HAT Mini
    python3 display.py --snapshot shots/  # save each page as a PNG, no hardware
"""

import argparse
import logging
import os
import signal
import threading
import time
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import advisor
import airlib

# --- Settings (override with environment variables) --------------------------
FACTS_INTERVAL_S = int(os.getenv("FACTS_INTERVAL_S", "60"))
FORECAST_INTERVAL_S = int(os.getenv("FORECAST_INTERVAL_S", "1800"))
LLM_REFRESH_S = int(os.getenv("LLM_REFRESH_S", "1800"))
LLM_MIN_GAP_S = int(os.getenv("LLM_MIN_GAP_S", "300"))
SCREEN_TIMEOUT_S = int(os.getenv("SCREEN_TIMEOUT_S", "300"))   # 0 = always on
BRIGHTNESS = float(os.getenv("BRIGHTNESS", "0.8"))
LED_BRIGHTNESS = float(os.getenv("LED_BRIGHTNESS", "0.05"))     # 0 = LED off
ROTATE = int(os.getenv("ROTATE", "0"))                           # 0 or 180
USE_LLM = os.getenv("USE_LLM", "1") != "0"
# "auto": model runs when the decision changes / every LLM_REFRESH_S
# "manual": model only runs when you press Y (handy for testing)
LLM_MODE = os.getenv("LLM_MODE", "auto").lower()

W, H = 320, 240
HEADER_H = 46
FOOTER_Y = H - 24
PAD = 12

# --- Colours ----------------------------------------------------------------
BG = (14, 16, 20)
FG = (236, 236, 236)
MUTED = (150, 156, 166)
DIM = (70, 74, 82)
GREEN = (40, 150, 70)
BLUE = (36, 110, 210)
AMBER = (214, 138, 26)
RED = (196, 58, 52)
GREY = (58, 62, 70)

ACTION_STYLE = {
    "no_action": ("ALL GOOD", GREEN),
    "open_window": ("OPEN THE WINDOW", BLUE),
    "open_window_short": ("OPEN WINDOW 5-10 MIN", BLUE),
    "keep_closed": ("KEEP WINDOW CLOSED", AMBER),
}

log = logging.getLogger("display")


# --- Drawing helpers ----------------------------------------------------------
def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for path in (f"/usr/share/fonts/truetype/dejavu/{name}", name):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


FONTS = {
    "title": load_font(22, bold=True),
    "big": load_font(30, bold=True),
    "body": load_font(18),
    "body_bold": load_font(18, bold=True),
    "small": load_font(14),
    "tiny": load_font(12),
}


def wrap_px(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    lines = []
    for para in text.split("\n"):
        line = ""
        for word in para.split():
            trial = f"{line} {word}".strip()
            if draw.textlength(trial, font=font) <= max_w or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)
    return lines


def text_block(draw, x: int, y: int, text: str, font, max_w: int, max_y: int,
               fill=FG, spacing: int = 4) -> int:
    """Draw wrapped text from (x, y), stopping before max_y. Returns the next y."""
    line_h = font.getbbox("Ag")[3] + spacing
    lines = wrap_px(draw, text, font, max_w)
    max_lines = max(1, (max_y - y) // line_h)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and draw.textlength(lines[-1] + "…", font=font) > max_w:
            lines[-1] = lines[-1].rsplit(" ", 1)[0] if " " in lines[-1] else lines[-1][:-1]
        lines[-1] += "…"
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_h
    return y


def fit_font(draw, text: str, max_w: int, start: int = 22, bold: bool = True):
    size = start
    while size > 12:
        font = load_font(size, bold)
        if draw.textlength(text, font=font) <= max_w:
            return font
        size -= 1
    return load_font(12, bold)


def header(draw, title: str, colour, right: str = "") -> None:
    draw.rectangle((0, 0, W, HEADER_H), fill=colour)
    right_w = draw.textlength(right, font=FONTS["small"]) + PAD if right else 0
    font = fit_font(draw, title, W - 2 * PAD - right_w)
    th = font.getbbox(title)[3]
    draw.text((PAD, (HEADER_H - th) // 2), title, font=font, fill=FG)
    if right:
        rh = FONTS["small"].getbbox(right)[3]
        draw.text((W - PAD - right_w + PAD, (HEADER_H - rh) // 2), right, font=FONTS["small"], fill=FG)


def footer(draw, status: str, page: int) -> None:
    draw.line((0, FOOTER_Y - 4, W, FOOTER_Y - 4), fill=DIM)
    dots_w = 3 * 12
    status_font = FONTS["tiny"]
    while status and draw.textlength(status, font=status_font) > W - 2 * PAD - dots_w - 6:
        status = status[:-2] + "…"
    draw.text((PAD, FOOTER_Y + 2), status, font=status_font, fill=MUTED)
    for i in range(3):
        cx = W - PAD - dots_w + i * 12 + 4
        cy = FOOTER_Y + 9
        draw.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=FG if i == page else DIM)


def risk_of(glass_rh: float) -> tuple[str, tuple, str]:
    if glass_rh >= 100:
        return "CONDENSATION LIKELY", RED, "Condensation likely on the windows tonight."
    if glass_rh >= airlib.MOULD_SURFACE_RH:
        return "DAMP WINDOWS", AMBER, "Glass stays damp overnight: mould risk."
    return "LOW RISK", GREEN, "Windows should stay dry tonight."


# --- Application ------------------------------------------------------------
class App:
    def __init__(self, hardware: bool = True):
        self.canvas = Image.new("RGB", (W, H), BG)
        self.draw = ImageDraw.Draw(self.canvas)
        self.hat = None
        if hardware:
            from displayhatmini import DisplayHATMini
            self.buffer = Image.new("RGB", (W, H), BG)
            self.hat = DisplayHATMini(self.buffer, backlight_pwm=True)
            self.hat.set_backlight(BRIGHTNESS)
            self.buttons = {"A": self.hat.BUTTON_A, "B": self.hat.BUTTON_B,
                            "X": self.hat.BUTTON_X, "Y": self.hat.BUTTON_Y}

        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stop = threading.Event()

        # Shared state (protected by self.lock)
        self.facts = None
        self.decision = None
        self.error = None
        self.advice = None          # last result of advisor.phrase() plus "action" and "at"
        self.llm_busy = False
        self.force = False
        self.night = None
        self.night_at = None        # monotonic time of last forecast fetch
        self.updated_at = None      # wall-clock time of last facts refresh
        self.last_llm_action = None
        self.last_llm_at = None     # monotonic
        self.shown_key = None

        # UI state (main thread only)
        self.page = 0
        self.dirty = True
        self.screen_on = True
        self.last_input = time.monotonic()
        self.prev_pressed = {}
        self.led_action = None
        self.shown_action = None

    # --- Background worker: data, decision, LLM ---------------------------------
    def refresh_once(self) -> None:
        now = time.monotonic()
        with self.lock:
            forced, self.force = self.force, False
        try:
            if self.night_at is None or forced or now - self.night_at > FORECAST_INTERVAL_S:
                night = advisor.tonight_min_temp()
                with self.lock:
                    if night is not None or self.night is None:
                        self.night = night
                    self.night_at = now
            f = advisor.load_facts()
            f["tonight_min_temp"] = self.night
            d = airlib.decide(f)
        except advisor.NotEnoughData as exc:
            log.warning("Waiting for data: %s", exc)
            with self.lock:
                self.error, self.dirty = str(exc), True
            return

        with self.lock:
            # Only redraw when something on screen would change
            if self.view_key(f, d) != self.shown_key or self.error is not None:
                self.shown_key = self.view_key(f, d)
                self.updated_at = datetime.now()
                self.dirty = True
            self.facts, self.decision, self.error = f, d, None
            since = None if self.last_llm_at is None else now - self.last_llm_at
            changed = d.action != self.last_llm_action
            auto = LLM_MODE != "manual" and (
                since is None
                or (changed and since >= LLM_MIN_GAP_S)
                or since >= LLM_REFRESH_S)
            need_llm = USE_LLM and (forced or auto)
            if need_llm:
                self.llm_busy = True

        if not need_llm:
            return
        p = advisor.phrase(f, d)
        raw = (p["raw"] or "").replace("\n", " ")[:300]
        if p["source"] == "llm":
            log.info("LLM %.1fs on AI HAT (%s): %s", p["secs"], d.action, p["text"])
            if p["format_issues"]:
                log.info("  model wrote: %r  [cleaned: %s]", raw, ", ".join(p["format_issues"]))
        else:
            log.info("LLM fallback (%s): %s", d.action, p["reason"])
            if p["raw"] is not None:
                log.info("  model wrote: %r", raw)
        with self.lock:
            self.advice = {**p, "action": d.action, "at": datetime.now()}
            self.llm_busy = False
            self.last_llm_action = d.action
            self.last_llm_at = time.monotonic()
            self.dirty = True

    @staticmethod
    def view_key(f: dict, d: airlib.Decision) -> tuple:
        """The values the pages show, rounded as displayed."""
        r = lambda v, n=1: None if v is None else round(v, n)
        return (r(f["indoor_temp"]), r(f["indoor_rh"], 0), r(f["outdoor_temp"]), r(f["outdoor_rh"], 0),
                r(f.get("outdoor_aqi"), 0), r(f["gas_ratio"], 2), r(f["rh_change_1h"]),
                r(f.get("tonight_min_temp"), 0), d.action, tuple(d.reasons),
                f["data_age_min"] > advisor.STALE_DATA_MIN)

    def worker(self) -> None:
        while not self.stop.is_set():
            try:
                self.refresh_once()
            except Exception:  # keep the display alive whatever happens
                log.exception("Refresh failed")
                with self.lock:
                    self.llm_busy = False
            self.wake.wait(FACTS_INTERVAL_S)
            self.wake.clear()

    # --- Pages ------------------------------------------------------------------
    def snapshot_state(self) -> dict:
        with self.lock:
            return dict(facts=self.facts, decision=self.decision, error=self.error,
                        advice=self.advice, busy=self.llm_busy, updated=self.updated_at)

    def render(self) -> None:
        s = self.snapshot_state()
        d = self.draw
        d.rectangle((0, 0, W, H), fill=BG)
        if s["error"] and s["facts"] is None:
            self.page_waiting(s)
        elif s["facts"] is None:
            header(d, "STARTING…", GREY)
            text_block(d, PAD, HEADER_H + 14, "Reading the sensor data…", FONTS["body"],
                       W - 2 * PAD, FOOTER_Y - 8)
            footer(d, "", self.page)
        else:
            (self.page_advice, self.page_now, self.page_tonight)[self.page](s)
        self.push()

    def page_waiting(self, s: dict) -> None:
        d = self.draw
        header(d, "WAITING FOR DATA", GREY)
        text_block(d, PAD, HEADER_H + 14, "No sensor data yet. The advice appears once the logger "
                   "has saved an indoor and an outdoor reading.", FONTS["body"], W - 2 * PAD,
                   FOOTER_Y - 8, fill=MUTED)
        footer(d, "Check: systemctl status env-logger", self.page)

    def page_advice(self, s: dict) -> None:
        d = self.draw
        dec, adv = s["decision"], s["advice"]
        title, colour = ACTION_STYLE[dec.action]
        header(d, title, colour)
        y = HEADER_H + 12
        max_y = FOOTER_Y - 8

        current = adv is not None and adv["action"] == dec.action
        if current and adv["source"] == "llm":
            text_block(d, PAD, y, adv["text"], FONTS["body"], W - 2 * PAD, max_y)
        else:
            # Rule-based view: the reasons, as short bullets
            for reason in dec.reasons:
                if y >= max_y - 18:
                    break
                d.text((PAD, y), "•", font=FONTS["small"], fill=MUTED)
                y = text_block(d, PAD + 14, y, reason[0].upper() + reason[1:], FONTS["small"],
                               W - 2 * PAD - 14, max_y) + 4

        if s["busy"]:
            status = "Writing advice on the AI HAT…"
        elif current and adv["source"] == "llm":
            model = airlib.DEFAULT_MODEL.split(":")[0]
            status = f"{model} on AI HAT · {adv['secs']:.1f} s · {adv['at']:%H:%M}"
        elif current and adv["raw"] is not None:
            status = "Rule-based · model reply rejected by check"
        elif current:
            status = "Rule-based · model unavailable"
        elif not USE_LLM:
            status = "Rule-based"
        elif LLM_MODE == "manual":
            status = "Rule-based · press Y for AI advice"
        else:
            status = "Rule-based · model update pending"
        footer(d, status, 0)

    def page_now(self, s: dict) -> None:
        d = self.draw
        f, x = s["facts"], s["decision"].derived
        header(d, "RIGHT NOW", GREY, right=f"{s['updated']:%H:%M}" if s["updated"] else "")
        lx, vx, y = PAD, 96, HEADER_H + 10
        big, small = FONTS["body_bold"], FONTS["small"]

        def row(label, value, sub=None, sub_fill=MUTED):
            nonlocal y
            d.text((lx, y + 2), label, font=small, fill=MUTED)
            d.text((vx, y), value, font=big, fill=FG)
            y += 23
            if sub:
                d.text((vx, y), sub, font=small, fill=sub_fill)
                y += 19
            y += 4

        row("Indoor", f"{f['indoor_temp']:.1f}°C   {f['indoor_rh']:.0f}%",
            f"{x['indoor_ah']:.1f} g/m³ · dew pt {x['dew_point']:.1f}°C")
        aqi = f" · AQI {f['outdoor_aqi']:.0f}" if f.get("outdoor_aqi") is not None else ""
        row("Outdoor", f"{f['outdoor_temp']:.1f}°C   {f['outdoor_rh']:.0f}%",
            f"{x['outdoor_ah']:.1f} g/m³{aqi}")
        gas = "learning…" if f["gas_ratio"] is None else f"{f['gas_ratio']:.0%} of normal"
        trend = None if f["rh_change_1h"] is None else f"Humidity {f['rh_change_1h']:+.1f}% last hour"
        row("Air (gas)", gas, trend)

        if f["data_age_min"] > advisor.STALE_DATA_MIN:
            footer(d, f"Last reading {f['data_age_min']:.0f} min ago!", 1)
        else:
            footer(d, "A advice · X tonight · Y refresh", 1)

    def page_tonight(self, s: dict) -> None:
        d = self.draw
        f, dec = s["facts"], s["decision"]
        x = dec.derived
        title, colour, sentence = risk_of(x["glass_rh_tonight"])
        header(d, title, colour, right="Tonight")
        lx, vx, y = PAD, 168, HEADER_H + 12
        night = f.get("tonight_min_temp")
        rows = [
            ("Outdoor low", "unknown" if night is None else f"{night:.0f}°C"),
            ("Window glass", f"about {x['glass_tonight']:.0f}°C"),
            ("Room dew point", f"{x['dew_point']:.1f}°C"),
            ("Glass humidity", f"{min(x['glass_rh_tonight'], 100):.0f}%"),
        ]
        for label, value in rows:
            d.text((lx, y + 2), label, font=FONTS["small"], fill=MUTED)
            d.text((vx, y), value, font=FONTS["body_bold"], fill=FG)
            y += 25
        y += 6
        if x["glass_rh_tonight"] >= airlib.MOULD_SURFACE_RH:
            sentence += (" Air the room briefly before bed." if x["outdoor_ah"] < x["indoor_ah"]
                         else " A dehumidifier will help more than airing.")
        text_block(d, PAD, y, sentence, FONTS["small"], W - 2 * PAD, FOOTER_Y - 6)
        note = "no forecast, using current temp" if night is None else "12 h forecast"
        footer(d, f"Glazing U={airlib.GLAZING_U} · {note}", 2)

    # --- Hardware output ----------------------------------------------------------
    def push(self) -> None:
        if self.hat is None:
            return
        self.buffer.paste(self.canvas.rotate(180) if ROTATE == 180 else self.canvas)
        self.hat.display()

    def set_led(self, action: str | None) -> None:
        if self.hat is None or action == self.led_action:
            return
        self.led_action = action
        if action is None or LED_BRIGHTNESS <= 0:
            self.hat.set_led(0, 0, 0)
            return
        r, g, b = ACTION_STYLE[action][1]
        self.hat.set_led(r / 255 * LED_BRIGHTNESS, g / 255 * LED_BRIGHTNESS, b / 255 * LED_BRIGHTNESS)

    def set_screen(self, on: bool) -> None:
        if on == self.screen_on:
            return
        self.screen_on = on
        if self.hat:
            self.hat.set_backlight(BRIGHTNESS if on else 0)
        if on:
            self.dirty = True
        log.info("Screen %s", "on" if on else "off")

    # --- Input ----------------------------------------------------------------------
    def on_press(self, name: str) -> None:
        self.last_input = time.monotonic()
        if not self.screen_on:  # the first press only wakes the screen
            self.set_screen(True)
            return
        if name == "Y":
            with self.lock:
                self.force = True
                self.llm_busy = USE_LLM  # shows "Writing advice…" straight away
            self.wake.set()
        else:
            self.page = {"A": 0, "B": 1, "X": 2}[name]
        self.dirty = True

    def poll_buttons(self) -> None:
        for name, pin in self.buttons.items():
            pressed = bool(self.hat.read_button(pin))
            if pressed and not self.prev_pressed.get(name):
                self.on_press(name)
            self.prev_pressed[name] = pressed

    # --- Main loop ----------------------------------------------------------------------
    def tick(self) -> None:
        """One pass of the UI loop: LED, wake-on-new-advice, timeout, redraw."""
        with self.lock:
            action = self.decision.action if self.decision else None
            if self.dirty:
                self.dirty, redraw = False, True
            else:
                redraw = False
        self.set_led(action)

        # A new recommendation wakes the screen and shows the advice page
        if action != self.shown_action:
            if self.shown_action is not None and action not in (None, "no_action"):
                self.page = 0
                self.last_input = time.monotonic()
                self.set_screen(True)
                redraw = True
            self.shown_action = action

        if SCREEN_TIMEOUT_S and self.screen_on and time.monotonic() - self.last_input > SCREEN_TIMEOUT_S:
            self.set_screen(False)
        if (redraw or self.dirty) and self.screen_on:
            self.dirty = False
            self.render()

    def run(self) -> None:
        signal.signal(signal.SIGTERM, lambda *_: self.stop.set())
        signal.signal(signal.SIGINT, lambda *_: self.stop.set())
        log.info("Display started (LLM %s, model %s)", "on" if USE_LLM else "off", airlib.DEFAULT_MODEL)
        threading.Thread(target=self.worker, daemon=True).start()
        try:
            while not self.stop.is_set():
                self.poll_buttons()
                self.tick()
                time.sleep(0.05)
        finally:
            self.draw.rectangle((0, 0, W, H), fill=(0, 0, 0))
            self.push()
            self.hat.set_backlight(0)
            self.hat.set_led(0, 0, 0)
            log.info("Display stopped")


def snapshot(out_dir: Path) -> None:
    """Render every page to PNG without the Display HAT (for testing and docs)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    app = App(hardware=False)
    app.refresh_once()
    gap = 12
    strip = Image.new("RGB", (3 * W + 2 * gap, H), (255, 255, 255))
    for i, name in enumerate(("advice", "now", "tonight")):
        app.page = i
        app.render()
        path = out_dir / f"page_{i + 1}_{name}.png"
        app.canvas.save(path)
        strip.paste(app.canvas, (i * (W + gap), 0))
        print(f"saved {path}")
    strip.save(out_dir / "display-pages.png")
    print(f"saved {out_dir / 'display-pages.png'} (all three pages, for the README)")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot", type=Path, metavar="DIR", help="save each page as a PNG and exit")
    a = ap.parse_args()
    if a.snapshot:
        snapshot(a.snapshot)
    else:
        App().run()


if __name__ == "__main__":
    main()
