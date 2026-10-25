"""
Shared logic for advisor.py and eval.py, so the live advisor and the benchmarks
use exactly the same physics, decision rules, prompt and output checks.

Contents:
- physics: absolute humidity, dew point, window-glass temperature, surface humidity
- decide(): deterministic ventilation / condensation rules (Python decides, not the LLM)
- build_prompt(): prompt v2 for the LLM
- ask_llm(): call hailo-ollama on the AI HAT+ 2
- guard(): clean up and validate the LLM's message before showing it
"""

import json
import math
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

# --- LLM settings -------------------------------------------------------------
LLM_URL = os.getenv("LLM_URL", "http://localhost:8000/api/chat")
DEFAULT_MODEL = os.getenv("MODEL", "qwen2.5-instruct:1.5b")
LLM_TIMEOUT_S = int(os.getenv("LLM_TIMEOUT_S", "180"))

# --- Decision thresholds (tune for your room) ---------------------------------
HUMID_RH = 60.0            # % indoor RH considered too humid
WARM_C = 25.0              # indoor temp considered too warm
COLD_OUTSIDE_C = 12.0      # below this, suggest a short burst instead of leaving it open
STALE_GAS_RATIO = 0.70     # gas resistance < 70% of baseline -> more VOCs / stale air
BAD_OUTDOOR_AQI = 60       # European AQI above 60 is "poor"
MOULD_SURFACE_RH = 80.0    # surface humidity above ~80% for long periods lets mould grow

# --- Window model ---------------------------------------------------------------
# U-value of the glazing (W/m2K): single 5.8, older double 2.8, modern double 1.4, triple 0.8
GLAZING_U = float(os.getenv("GLAZING_U", "2.8"))
H_INSIDE = 7.7             # W/m2K, standard inside-surface heat transfer coefficient (Rsi = 0.13)


# --- Physics ------------------------------------------------------------------
def saturation_vp(temp_c: float) -> float:
    """Saturation vapour pressure in hPa (Magnus formula)."""
    return 6.112 * math.exp(17.67 * temp_c / (temp_c + 243.5))


def absolute_humidity(temp_c: float, rh_pct: float) -> float:
    """Water vapour content in g/m^3."""
    return saturation_vp(temp_c) * rh_pct * 2.1674 / (273.15 + temp_c)


def dew_point(temp_c: float, rh_pct: float) -> float:
    """Temperature at which this air starts to condense, in degC."""
    g = math.log(rh_pct / 100) + 17.67 * temp_c / (temp_c + 243.5)
    return 243.5 * g / (17.67 - g)


def window_surface_temp(indoor_c: float, outdoor_c: float) -> float:
    """Steady-state inner glass temperature: the glass sits between room and outside
    temperature, closer to outside the worse the glazing (higher U)."""
    return indoor_c - (indoor_c - outdoor_c) * GLAZING_U / H_INSIDE


def surface_rh(indoor_c: float, indoor_rh: float, surface_c: float) -> float:
    """Relative humidity of room air right at a surface. >= 100% means condensation."""
    return saturation_vp(indoor_c) * indoor_rh / saturation_vp(surface_c)


# --- Decision -----------------------------------------------------------------
ACTIONS = ("open_window", "open_window_short", "keep_closed", "no_action")
ACTION_TEXT = {
    "open_window": "Open the window.",
    "open_window_short": "Open the window wide for 5-10 minutes, then close it.",
    "keep_closed": "Keep the window closed for now.",
    "no_action": "No action needed.",
}


@dataclass
class Decision:
    action: str
    reasons: list[str]
    derived: dict = field(default_factory=dict)


def _fine_reasons(f: dict, gas: float | None) -> list[str]:
    """Concrete reasons when no action is needed, so the LLM has something real to say."""
    reasons = []
    if 40 <= f["indoor_rh"] <= HUMID_RH:
        reasons.append(f"indoor humidity is comfortable ({f['indoor_rh']:.0f}%)")
    elif f["indoor_rh"] < 40:
        reasons.append(f"indoor air is on the dry side ({f['indoor_rh']:.0f}%) but not a problem")
    if gas is not None:
        reasons.append("the indoor air isn't stale")
    if 18 <= f["indoor_temp"] <= WARM_C:
        reasons.append(f"the room is at a comfortable {f['indoor_temp']:.1f}C")
    return reasons or ["indoor conditions are fine"]


def decide(f: dict) -> Decision:
    """f needs: indoor_temp, indoor_rh, outdoor_temp, outdoor_rh.
    Optional: outdoor_aqi, gas_ratio, tonight_min_temp."""
    ah_in = absolute_humidity(f["indoor_temp"], f["indoor_rh"])
    ah_out = absolute_humidity(f["outdoor_temp"], f["outdoor_rh"])
    night_c = f.get("tonight_min_temp")
    night_c = f["outdoor_temp"] if night_c is None else night_c
    glass = window_surface_temp(f["indoor_temp"], night_c)
    glass_rh = surface_rh(f["indoor_temp"], f["indoor_rh"], glass)
    dp = dew_point(f["indoor_temp"], f["indoor_rh"])
    derived = {"indoor_ah": ah_in, "outdoor_ah": ah_out, "dew_point": dp,
               "glass_tonight": glass, "glass_rh_tonight": glass_rh}

    gas = f.get("gas_ratio")
    aqi = f.get("outdoor_aqi")
    stale = gas is not None and gas < STALE_GAS_RATIO
    humid = f["indoor_rh"] > HUMID_RH
    warm = f["indoor_temp"] > WARM_C and f["outdoor_temp"] < f["indoor_temp"] - 2
    condensation = glass_rh >= 100
    mould = MOULD_SURFACE_RH <= glass_rh < 100
    outdoor_drier = ah_out < ah_in
    aqi_bad = aqi is not None and aqi > BAD_OUTDOOR_AQI

    reasons = []
    if stale:
        reasons.append(f"indoor air is stale (gas sensor at {gas:.0%} of its normal level)")
    if humid:
        reasons.append(f"indoor humidity is high ({f['indoor_rh']:.0f}%)")
    if condensation:
        reasons.append(f"window glass will cool to about {glass:.0f}C tonight, below the room's "
                       f"dew point of {dp:.0f}C, so condensation is likely")
    elif mould:
        reasons.append(f"window glass will cool to about {glass:.0f}C tonight and stay damp, "
                       "which encourages mould over time")
    moisture = humid or condensation or mould
    if moisture:
        reasons.append("outdoor air holds less water, so airing the room will dry it" if outdoor_drier else
                       "outdoor air holds more water, so opening a window won't dry the room; "
                       "a dehumidifier or keeping the room warm will help more")
    if warm:
        reasons.append(f"the room is warm ({f['indoor_temp']:.1f}C) and it's cooler outside")

    useful = stale or warm or (moisture and outdoor_drier)
    if not useful:
        if moisture:
            return Decision("keep_closed", reasons, derived)
        return Decision("no_action", reasons or _fine_reasons(f, gas), derived)
    if aqi_bad:
        reasons.append(f"but outdoor air quality is poor (European AQI {aqi:.0f})")
        return Decision("keep_closed", reasons, derived)
    if f["outdoor_temp"] < COLD_OUTSIDE_C:
        reasons.append(f"it's cold outside ({f['outdoor_temp']:.1f}C), so a short burst keeps the heat in")
        return Decision("open_window_short", reasons, derived)
    return Decision("open_window", reasons, derived)


# --- Prompt -------------------------------------------------------------------
def facts_text(f: dict) -> str:
    s = (f"Indoor: {f['indoor_temp']:.1f}C, {f['indoor_rh']:.0f}% humidity. "
         f"Outdoor: {f['outdoor_temp']:.1f}C, {f['outdoor_rh']:.0f}% humidity")
    if f.get("outdoor_aqi") is not None:
        s += f", air quality index {f['outdoor_aqi']:.0f}"
    if (f.get("outdoor_rain_mm") or 0) > 0.2:
        s += ", raining"
    if f.get("tonight_min_temp") is not None:
        s += f", dropping to {f['tonight_min_temp']:.0f}C tonight"
    return s + "."


PROMPT_VERSION = "v3"
MAX_SENTENCES = 1            # longer replies are trimmed to this many sentences

# Generation settings sent to the model server for the advice message.
# num_predict caps the reply length (fewer tokens = less time and energy on the HAT).
# If the server rejects "options", ask_llm retries without them.
PHRASE_OPTIONS = {"num_predict": int(os.getenv("LLM_MAX_TOKENS", "60")),
                  "temperature": float(os.getenv("LLM_TEMPERATURE", "0.3"))}


def build_prompt(f: dict, d: Decision) -> str:
    return (
        "Write ONE short sentence (at most 25 words) telling the user what to do about the air "
        "in their room, and the main reason why. Begin with what to do.\n"
        "Rules: no greeting, no sign-off, no lists, no extra tips. "
        "Use only the facts and reasons below; do not add any other facts or numbers. "
        "Do not change the decision.\n\n"
        f"Facts: {facts_text(f)}\n"
        f"Reasons: {'; '.join(d.reasons)}.\n"
        f"Decision: {ACTION_TEXT[d.action]}"
    )


# --- LLM client ---------------------------------------------------------------
def strip_think(text: str) -> str:
    """Reasoning models emit <think>...</think> first; keep only the final answer."""
    return text.rsplit("</think>", 1)[1] if "</think>" in text else text


_options_supported = True


def ask_llm(prompt: str, model: str = DEFAULT_MODEL, timeout: int = LLM_TIMEOUT_S,
            options: dict | None = None) -> tuple[str, float]:
    global _options_supported
    payload = {"model": model, "stream": False, "messages": [{"role": "user", "content": prompt}]}
    if options and _options_supported:
        payload["options"] = options
    req = urllib.request.Request(LLM_URL, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = json.load(resp)["message"]["content"]
    except urllib.error.HTTPError as exc:
        if "options" in payload and 400 <= exc.code < 500:
            _options_supported = False   # server doesn't accept options; don't send them again
            return ask_llm(prompt, model, timeout)
        raise
    return strip_think(text).strip(), time.monotonic() - t0


# --- Output guard -------------------------------------------------------------
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
GREETING_RE = re.compile(r"^\s*(dear|hi|hello|hey|greetings)\b[^,!.\n]*[,!.]?\s*", re.I)
THANKS_RE = re.compile(r"^\s*(thanks|thank you)\b[^.!\n]*[.!]\s*", re.I)
SIGNOFF_RE = re.compile(r"^\s*((best|kind|warm|warmest)\s+(regards|wishes)|regards|sincerely|cheers|"
                        r"best|yours( truly| sincerely)?)\b", re.I)
LABEL_RE = re.compile(r"^\s*(message|answer|response|advice)\s*:\s*", re.I)
ECHO_RE = re.compile(r"^\s*(decision|reasons?|facts)\s*:", re.I)  # model repeating the prompt
PLACEHOLDER_RE = re.compile(r"\[[^\]]*\]")
OPEN_RE = re.compile(r"\bopen(ing)?\b[^.!?]*\bwindows?\b|\bwindows?\b[^.!?]*\bopen\b", re.I)
NEGATION_RE = re.compile(r"\b(no need|don't|do not|not|keep|avoid|no)\b", re.I)
VENTILATE_RE = re.compile(r"\b(open|air|ventilat\w*|crack)\b", re.I)


@dataclass
class GuardResult:
    ok: bool
    text: str
    problems: list[str]
    format_issues: list[str]  # what had to be cleaned up (for benchmarking)


_FILLER = {"is", "are", "the", "a", "right", "now", "at", "this", "time", "currently", "required", "needed"}


def _words(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def _repeats_decision(sentence: str, action: str) -> bool:
    """True if the sentence only restates the decision line from the prompt."""
    w = _words(sentence)
    return bool(w) and w <= _words(ACTION_TEXT[action]) | _FILLER


def split_sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def _allowed_numbers(prompt: str) -> set[str]:
    allowed = set()
    for tok in NUM_RE.findall(prompt):
        x = float(tok)
        allowed.update({tok, f"{x:g}", str(int(x)), str(round(x)), f"{x:.1f}"})
    return allowed


def guard(raw: str, prompt: str, action: str) -> GuardResult:
    format_issues, problems = [], []
    text = raw.replace("**", "").strip()

    # Line-level clean-up: labels, greeting lines, and everything from a sign-off onwards
    kept = []
    for line in text.splitlines():
        if SIGNOFF_RE.match(line) and len(line.split()) <= 6:
            format_issues.append("sign-off")
            break
        if ECHO_RE.match(line):
            format_issues.append("echoed prompt")
            continue
        if LABEL_RE.match(line):
            format_issues.append("label")
            line = LABEL_RE.sub("", line)
            if not line.strip():
                continue
        kept.append(line.strip())
    text = " ".join(l for l in kept if l)

    if GREETING_RE.match(text):
        format_issues.append("greeting")
        text = GREETING_RE.sub("", text, count=1)
        text = THANKS_RE.sub("", text, count=1)
    if PLACEHOLDER_RE.search(text):
        format_issues.append("placeholder")
        text = PLACEHOLDER_RE.sub("", text)
    if re.search(r"[\"“”]", text):
        format_issues.append("quotes")
        text = re.sub(r"[\"“”]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if text[:1].islower():
        text = text[0].upper() + text[1:]

    # Small models often start by repeating the decision line from the prompt, then give
    # the reason, then pad (extra tips, restating facts). Keep the repeated decision plus
    # the first real sentence, and trim the padding instead of rejecting the whole reply.
    sentences = split_sentences(text)
    copies = 0
    while copies < len(sentences) and _repeats_decision(sentences[copies], action):
        copies += 1
    keep = min(len(sentences), copies + MAX_SENTENCES)
    if copies:
        format_issues.append("repeated the decision")
    if len(sentences) > keep:
        format_issues.append(f"trimmed {len(sentences)} to {keep} sentences")
        sentences = sentences[:keep]
        text = " ".join(sentences)
    only_copy = bool(sentences) and copies >= len(sentences)
    if text and text[-1] not in ".!?":
        format_issues.append("cut off")      # reply hit the length cap mid-sentence
        if len(sentences) > 1:
            sentences = sentences[:-1]
            text = " ".join(sentences)
        else:
            problems.append("unfinished sentence")

    # Hard checks: these make the message unusable
    if not text:
        problems.append("empty message")
    elif only_copy:
        problems.append("only repeated the decision, no reason given")
    extra = sorted(set(NUM_RE.findall(text)) - _allowed_numbers(prompt))
    if extra:
        problems.append(f"numbers not in the facts: {', '.join(extra)}")
    if action in ("no_action", "keep_closed"):
        for s in sentences:
            if OPEN_RE.search(s) and not NEGATION_RE.search(s):
                problems.append("tells the user to open a window, contradicting the decision")
                break
    elif not VENTILATE_RE.search(text):
        problems.append("doesn't tell the user to ventilate")

    return GuardResult(not problems, text, problems, format_issues)
