#!/usr/bin/env python3
"""
Benchmark suite: how well do small on-device LLMs handle this project's tasks,
compared with a frontier model?

Every test case has a known correct answer and is scored automatically by code.

Categories
  phrasing      P*  turn a decision into a message (the advisor's real job)
  raw_decision  D*  make the decision itself from raw numbers + written rules
  arithmetic    A*  compare absolute humidity / compute a dew point
  tools         T*  pick the right query tool as JSON (for "ask your room" questions)
  unknown       U*  admit when the facts don't contain the answer

Usage
  # Local models on the AI HAT+ 2 (hailo-ollama must be running)
  python3 eval.py --model qwen2.5-instruct:1.5b --reps 3
  python3 eval.py --model deepseek_r1_distill_qwen:1.5b --reps 1
  python3 eval.py --model qwen2.5-instruct:1.5b --only tools        # one category

  # Frontier model, blind test in a fresh chat
  python3 eval.py --export-prompts frontier_prompts.md   # paste into a NEW chat
  python3 eval.py --score-answers frontier_answers.md --label frontier

  # Combine everything into a table
  python3 eval.py --report

  # After changing the scoring code: re-score saved outputs without re-running models
  python3 eval.py --rescore
"""

import argparse
import json
import re
import statistics
import sys
import urllib.error
import uuid
from datetime import datetime
from pathlib import Path

import airlib

RESULTS_DIR = Path(__file__).resolve().parent / "eval_results"
RESULTS_FILE = RESULTS_DIR / "results.jsonl"
CATEGORIES = ("phrasing", "raw_decision", "arithmetic", "tools", "unknown")

# --- Scenarios (shared by phrasing and raw_decision) -----------------------------
SCENARIOS = {
    "fine":          dict(indoor_temp=21.5, indoor_rh=50, outdoor_temp=12, outdoor_rh=85, outdoor_aqi=25, gas_ratio=1.05, tonight_min_temp=9),
    "stale_cold":    dict(indoor_temp=22, indoor_rh=52, outdoor_temp=8, outdoor_rh=90, outdoor_aqi=20, gas_ratio=0.55, tonight_min_temp=5),
    "humid_dry_out": dict(indoor_temp=21, indoor_rh=68, outdoor_temp=10, outdoor_rh=88, outdoor_aqi=30, gas_ratio=1.0, tonight_min_temp=7),
    "humid_wet_out": dict(indoor_temp=20, indoor_rh=63, outdoor_temp=19, outdoor_rh=95, outdoor_aqi=20, gas_ratio=1.0, tonight_min_temp=17),
    "stale_bad_aqi": dict(indoor_temp=22, indoor_rh=50, outdoor_temp=15, outdoor_rh=70, outdoor_aqi=75, gas_ratio=0.6, tonight_min_temp=12),
    "warm":          dict(indoor_temp=26.5, indoor_rh=45, outdoor_temp=18, outdoor_rh=60, outdoor_aqi=20, gas_ratio=1.0, tonight_min_temp=14),
    "condensation":  dict(indoor_temp=20, indoor_rh=60, outdoor_temp=4, outdoor_rh=85, outdoor_aqi=20, gas_ratio=1.0, tonight_min_temp=0),
}

LABELS = {"open_window": "OPEN_WINDOW", "open_window_short": "OPEN_WINDOW_SHORT",
          "keep_closed": "KEEP_CLOSED", "no_action": "NO_ACTION"}
LABEL_RE = re.compile(r"\b(OPEN_WINDOW_SHORT|OPEN_WINDOW|KEEP_CLOSED|NO_ACTION)\b")

RAW_DECISION_RULES = """You decide whether the user should open a window. Rules:
1. Ventilating is useful if: the indoor air is stale (gas sensor below 70% of normal), OR the room is above 25C and it is at least 2C cooler outside, OR there is a moisture problem AND the outdoor air contains less water per cubic metre than the indoor air (compare absolute humidity, not relative humidity).
2. A moisture problem means indoor humidity above 60%, or window glass surface humidity tonight of 80% or more.
3. If ventilating is useful but the outdoor air quality index is above 60, keep the window closed.
4. If ventilating is useful and it is below 12C outside, open it for a short burst only.
5. If ventilating is not useful but there is a moisture problem, keep the window closed. Otherwise no action is needed.

Answer with exactly one of: OPEN_WINDOW, OPEN_WINDOW_SHORT, KEEP_CLOSED, NO_ACTION. Nothing else."""

TOOLS_PROMPT = """You route questions about a home air-quality sensor to a tool. Available tools:
- current_conditions: latest indoor temperature, humidity and air quality (no period)
- worst_air_quality: when the indoor air was stalest (needs period)
- humidity_summary: lowest, average and highest indoor humidity (needs period)
- temperature_summary: lowest, average and highest indoor temperature (needs period)
- window_open_events: when a window was opened (needs period)
period must be "today" or "week".
If none of these tools can answer the question, reply {"tool": "none"}.
Reply with only a JSON object, for example {"tool": "humidity_summary", "period": "today"}.

Question: """

TOOL_CASES = [
    ("What's the temperature in the room right now?", "current_conditions", None),
    ("When was the air quality worst this week?", "worst_air_quality", "week"),
    ("How humid was it today?", "humidity_summary", "today"),
    ("Did anyone open the window today?", "window_open_events", "today"),
    ("How warm has the room been over the past week?", "temperature_summary", "week"),
    ("What's the CO2 level?", "none", None),
    ("Is it going to rain tomorrow?", "none", None),
    ("Was the air stuffy at any point today?", "worst_air_quality", "today"),
]

UNKNOWN_FACTS = dict(indoor_temp=21.5, indoor_rh=56, outdoor_temp=14.4, outdoor_rh=91, outdoor_aqi=24)
UNKNOWN_CASES = [  # (question, answerable, expected number if answerable)
    ("What is the CO2 level in the room?", False, None),
    ("How many people are in the room?", False, None),
    ("What is the PM2.5 level inside the room?", False, None),
    ("What is the humidity inside the room?", True, "56"),  # control: must answer, not refuse
]
REFUSAL_RE = re.compile(
    r"not (\w+ )?(measured|available|provided|included|given|known|listed|mentioned|specified)|"
    r"no (\w+ )?(data|information|measurements?|readings?|details)|"
    r"(don't|do not|doesn't|does not) (\w+ )?(have|include|contain|mention|provide|say|specify)|"
    r"cannot|can't|can not|unable|unknown|isn't (measured|available|provided|included)|aren't|not possible|no way", re.I)

COMPARE_CASES = [  # (A temp, A rh, B temp, B rh) - "B" is often cold and very humid on purpose
    (22.0, 50, 11.0, 92),
    (20.0, 60, 15.0, 90),
    (24.0, 40, 5.0, 95),
    (18.0, 70, 18.0, 75),
]
DEW_CASES = [(21.5, 56), (25.0, 70)]


# --- Case construction -----------------------------------------------------------
def build_cases() -> list[dict]:
    cases = []
    for i, (name, f) in enumerate(SCENARIOS.items(), 1):
        d = airlib.decide(f)
        cases.append(dict(id=f"P{i}", category="phrasing", scenario=name,
                          prompt=airlib.build_prompt(f, d), action=d.action))
    for i, (name, f) in enumerate(SCENARIOS.items(), 1):
        d = airlib.decide(f)
        facts = (airlib.facts_text(f) + f" Gas sensor at {f['gas_ratio']:.0%} of normal. "
                 f"Window glass surface humidity tonight: {d.derived['glass_rh_tonight']:.0f}%.")
        cases.append(dict(id=f"D{i}", category="raw_decision", scenario=name,
                          prompt=f"{RAW_DECISION_RULES}\n\nFacts: {facts}", expected=LABELS[d.action]))
    for i, (ta, ra, tb, rb) in enumerate(COMPARE_CASES, 1):
        more = "A" if airlib.absolute_humidity(ta, ra) > airlib.absolute_humidity(tb, rb) else "B"
        cases.append(dict(id=f"A{i}", category="arithmetic", kind="compare", expected=more, prompt=(
            f"Air A: {ta:.1f}C at {ra}% relative humidity. Air B: {tb:.1f}C at {rb}% relative humidity.\n"
            "Which contains more water vapour per cubic metre? Answer with exactly AIR_A or AIR_B.")))
    for j, (t, rh) in enumerate(DEW_CASES, len(COMPARE_CASES) + 1):
        cases.append(dict(id=f"A{j}", category="arithmetic", kind="dew_point",
                          expected=round(airlib.dew_point(t, rh), 1), prompt=(
            f"What is the dew point of air at {t:.1f}C and {rh}% relative humidity? "
            "Reply with just the number in degrees C, rounded to one decimal place.")))
    for i, (q, tool, period) in enumerate(TOOL_CASES, 1):
        cases.append(dict(id=f"T{i}", category="tools", prompt=TOOLS_PROMPT + q, tool=tool, period=period))
    facts = airlib.facts_text(UNKNOWN_FACTS)
    for i, (q, answerable, number) in enumerate(UNKNOWN_CASES, 1):
        cases.append(dict(id=f"U{i}", category="unknown", answerable=answerable, number=number, prompt=(
            "You are a home air-quality assistant. Answer the question in one or two sentences using only "
            "the facts below. If the facts don't contain the answer, say so.\n\n"
            f"Facts: {facts}\nQuestion: {q}")))
    return cases


# --- Scoring -------------------------------------------------------------------------
def score(case: dict, raw: str) -> tuple[bool, dict]:
    text = airlib.strip_think(raw).strip()
    cat = case["category"]

    if cat == "phrasing":
        g = airlib.guard(text, case["prompt"], case["action"])
        facts_ok = not any(p.startswith("numbers not in the facts") for p in g.problems)
        decision_ok = not any("decision" in p or "ventilate" in p for p in g.problems)
        format_ok = not g.format_issues
        m = dict(facts_ok=facts_ok, decision_ok=decision_ok, format_ok=format_ok,
                 usable_after_guard=g.ok, problems=g.problems, format_issues=g.format_issues)
        return facts_ok and decision_ok and format_ok, m

    if cat == "raw_decision":
        found = LABEL_RE.findall(text)
        pred = found[0] if found else None  # the answer comes first; later mentions are explanation
        vent = lambda lab: lab is not None and lab.startswith("OPEN")
        return pred == case["expected"], dict(predicted=pred, expected=case["expected"],
                                              ventilate_ok=pred is not None and vent(pred) == vent(case["expected"]))

    if cat == "arithmetic":
        if case["kind"] == "compare":
            # First mention is the answer. Tolerate typos like "AIRC_B" and "Air B"; record exact format separately.
            found = re.findall(r"\bair\w?[ _]?([ab])\b", text, re.I)
            pred = found[0].upper() if found else None
            exact = bool(re.fullmatch(r"\s*AIR_[AB]\.?\s*", text))
            return pred == case["expected"], dict(predicted=pred, expected=case["expected"], exact_format=exact)
        # Prefer a bold number; otherwise the first number that isn't just the question repeated back
        bold = re.findall(r"\*\*\s*(-?\d+(?:\.\d+)?)", text)
        given = set(re.findall(r"\d+(?:\.\d+)?", case["prompt"]))
        nums = bold or [n for n in re.findall(r"-?\d+(?:\.\d+)?", text) if n.lstrip("-") not in given]
        pred = float(nums[0]) if nums else None
        ok = pred is not None and abs(pred - case["expected"]) <= 1.0
        return ok, dict(predicted=pred, expected=case["expected"], tolerance=1.0)

    if cat == "tools":
        mjson = re.search(r"\{.*?\}", text, re.S)
        try:
            obj = json.loads(mjson.group(0)) if mjson else None
        except ValueError:
            obj = None
        valid = isinstance(obj, dict)
        tool = obj.get("tool") if valid else None
        period = obj.get("period") if valid else None
        tool_ok = tool == case["tool"]
        period_ok = case["period"] is None or period == case["period"]
        return valid and tool_ok and period_ok, dict(valid_json=valid, tool=tool, period=period,
                                                     tool_ok=tool_ok, period_ok=period_ok)

    if cat == "unknown":
        refused = bool(REFUSAL_RE.search(text))
        if case["answerable"]:
            ok = case["number"] in re.findall(r"\d+(?:\.\d+)?", text) and not refused
            return ok, dict(refused=refused, answered_correctly=ok)
        allowed = set(re.findall(r"\d+(?:\.\d+)?", case["prompt"]))
        invented = sorted(set(re.findall(r"\d+(?:\.\d+)?", text)) - allowed)
        return refused and not invented, dict(refused=refused, invented_numbers=invented)

    raise ValueError(cat)


# --- Storage ---------------------------------------------------------------------------
def save(rows: list[dict]) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    with RESULTS_FILE.open("a") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def summarize(rows: list[dict]) -> str:
    """Markdown table: one row per label, one column per category."""
    by_label: dict[str, list[dict]] = {}
    for r in rows:
        by_label.setdefault(r["label"], []).append(r)

    head = "| Model | " + " | ".join(CATEGORIES) + " | Overall | Median time |"
    lines = [head, "|" + "---|" * (len(CATEGORIES) + 3)]
    for label, rs in by_label.items():
        cells = []
        for c in CATEGORIES:
            cr = [r for r in rs if r["category"] == c]
            cells.append(f"{sum(r['pass'] for r in cr)}/{len(cr)}" if cr else "-")
        secs = [r["secs"] for r in rs if r.get("secs") is not None]
        med = f"{statistics.median(secs):.1f} s" if secs else "n/a"
        lines.append(f"| {label} | " + " | ".join(cells) + f" | {sum(r['pass'] for r in rs)}/{len(rs)} | {med} |")

    # Phrasing detail: which rule failed
    lines += ["", "Phrasing detail (raw model output, before the guard):", "",
              "| Model | Facts correct | Decision kept | Format followed | Usable after guard |", "|---|---|---|---|---|"]
    for label, rs in by_label.items():
        pr = [r for r in rs if r["category"] == "phrasing" and "metrics" in r and "facts_ok" in r["metrics"]]
        if pr:
            n = len(pr)
            f = lambda k: f"{sum(r['metrics'][k] for r in pr)}/{n}"
            lines.append(f"| {label} | {f('facts_ok')} | {f('decision_ok')} | {f('format_ok')} | {f('usable_after_guard')} |")
    return "\n".join(lines)


# --- Modes ---------------------------------------------------------------------------
def run_local(model: str, reps: int, label: str, only: str | None, timeout: int) -> None:
    cases = [c for c in build_cases() if not only or c["category"] == only]
    run_id = uuid.uuid4().hex[:8]
    rows = []
    print(f"Run {run_id}: {len(cases)} cases x {reps} reps on {model} (label '{label}')")
    print("Tip: run advisor.py once first so the model is already loaded (warm).\n")
    for rep in range(1, reps + 1):
        for c in cases:
            try:
                opts = airlib.PHRASE_OPTIONS if c["category"] == "phrasing" else None
                raw, secs = airlib.ask_llm(c["prompt"], model=model, timeout=timeout, options=opts)
                ok, metrics = score(c, raw)
            except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
                raw, secs, ok, metrics = "", None, False, {"error": str(exc)}
            row = dict(run_id=run_id, time=datetime.now().isoformat(timespec="seconds"), label=label,
                       model=model, prompt_version=airlib.PROMPT_VERSION, rep=rep,
                       case=c["id"], category=c["category"],
                       secs=secs, raw=raw, metrics=metrics, **{"pass": ok})
            rows.append(row)
            save([row])  # save as we go, so a long run isn't lost if interrupted
            t = f"{secs:5.1f}s" if secs is not None else "  err "
            print(f"rep {rep}  {c['id']:4} {c['category']:13} {'PASS' if ok else 'fail'}  {t}  "
                  f"{json.dumps(metrics)[:90]}")
    print("\n" + summarize(rows))
    print(f"\nRaw outputs saved to {RESULTS_FILE}")


def export_prompts(path: Path) -> None:
    cases = build_cases()
    out = ["This is a blind test. Below are independent prompts, each with an ID.",
           "Answer each one as if it were the only message you received, following its instructions exactly.",
           "Format your whole reply as the ID on its own line, then your answer, for every prompt, like:",
           "", "### P1", "<answer>", "", "### P2", "<answer>", "", "Nothing else before, between or after.", ""]
    for c in cases:
        out += [f"### {c['id']}", "```", c["prompt"], "```", ""]
    path.write_text("\n".join(out))
    print(f"Wrote {len(cases)} prompts to {path}")
    print("Paste the whole file into a NEW chat (outside this project), save the reply as a file,")
    print("then run: python3 eval.py --score-answers <file> --label frontier")


def score_answers(path: Path, label: str) -> None:
    cases = {c["id"]: c for c in build_cases()}
    text = path.read_text()
    parts = re.split(r"^#{2,3}\s*([PDATU]\d+)\s*$", text, flags=re.M)
    answers = {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}
    run_id = uuid.uuid4().hex[:8]
    rows = []
    for cid, c in cases.items():
        raw = re.sub(r"^```\w*\s*$", "", answers.get(cid, ""), flags=re.M).strip()
        ok, metrics = score(c, raw) if raw else (False, {"error": "no answer"})
        rows.append(dict(run_id=run_id, time=datetime.now().isoformat(timespec="seconds"), label=label,
                         model=label, rep=1, case=cid, category=c["category"], secs=None,
                         raw=raw, metrics=metrics, **{"pass": ok}))
        print(f"{cid:4} {c['category']:13} {'PASS' if ok else 'fail'}  {json.dumps(metrics)[:90]}")
    missing = [cid for cid in cases if cid not in answers]
    if missing:
        print(f"\nWARNING: no answer found for {', '.join(missing)}")
    save(rows)
    print("\n" + summarize(rows))


def rescore() -> None:
    """Re-apply the current scoring to saved raw outputs (no model calls). Keeps a backup."""
    if not RESULTS_FILE.exists():
        sys.exit("No results yet.")
    cases = {c["id"]: c for c in build_cases()}
    rows = [json.loads(l) for l in RESULTS_FILE.read_text().splitlines() if l.strip()]
    backup = RESULTS_FILE.with_name("results.before_rescore.jsonl")
    backup.write_text(RESULTS_FILE.read_text())
    changed = 0
    for r in rows:
        c = cases.get(r["case"])
        if c is None or (r.get("metrics") or {}).get("error"):
            continue
        ok, metrics = score(c, r["raw"])
        if ok != r["pass"]:
            changed += 1
            print(f"{r['label']:32} {r['case']:4} {'fail -> PASS' if ok else 'PASS -> fail'}  {r['raw'][:70]!r}")
        r["pass"], r["metrics"] = ok, metrics
    RESULTS_FILE.write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"\n{changed} results changed (backup: {backup.name})\n")
    report()


def report() -> None:
    if not RESULTS_FILE.exists():
        sys.exit("No results yet.")
    rows = [json.loads(l) for l in RESULTS_FILE.read_text().splitlines() if l.strip()]
    md = summarize(rows)
    (RESULTS_DIR / "report.md").write_text(md + "\n")
    print(md)
    print(f"\nSaved to {RESULTS_DIR / 'report.md'}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", help="hailo-ollama model to test")
    ap.add_argument("--label", help="name in the results (default: model name)")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--only", choices=CATEGORIES)
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--export-prompts", type=Path, metavar="FILE")
    ap.add_argument("--score-answers", type=Path, metavar="FILE")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--rescore", action="store_true", help="re-score saved outputs with the current scoring")
    a = ap.parse_args()

    if a.rescore:
        rescore()
    elif a.export_prompts:
        export_prompts(a.export_prompts)
    elif a.score_answers:
        score_answers(a.score_answers, a.label or "frontier")
    elif a.report:
        report()
    elif a.model:
        run_local(a.model, a.reps, a.label or a.model, a.only, a.timeout)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
