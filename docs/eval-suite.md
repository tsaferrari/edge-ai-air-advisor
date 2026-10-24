# Evaluation suite: edge LLMs vs a frontier model

`eval.py` measures what small on-device language models running on the AI HAT+ 2
(Hailo-10H) can and can't do for this project, and compares them with a frontier
model. Every test case has a known correct answer and is scored automatically by
code, not by impression.

## Results (24 Oct 2026)

| Category                                | Qwen2.5-Instruct 1.5B (edge) | DeepSeek-R1-Distill 1.5B (edge) | Claude Opus 5.5 Medium (cloud) |
| --------------------------------------- | ---------------------------- | ------------------------------- | ------------------------------ |
| Phrasing: raw output fully correct      | 5/21 (24 %)                  | 4/7 (57 %)                      | 7/7 (100 %)                    |
| Phrasing: usable after the output guard | 13/21 (62 %)                 | 5/7 (71 %)                      | 7/7 (100 %)                    |
| Make the decision from raw numbers      | 6/21 (29 %)                  | 0/7 (0 %)                       | 7/7 (100 %)                    |
| Arithmetic                              | 6/18 (33 %)                  | 4/6 (67 %)                      | 6/6 (100 %)                    |
| Tool selection (JSON)                   | 7/24 (29 %)                  | 1/8 (13 %)                      | 7/8 (88 %)                     |
| Admit "I don't know" (+ 1 control)      | 11/12 (92 %)                 | 2/4 (50 %)                      | 4/4 (100 %)                    |
| **Overall**                             | **35/96 (36 %)**             | **11/32 (34 %)**                | **31/32 (97 %)**               |
| Median time per answer (warm)           | 13.3 s                       | 82.5 s                          | not measured                   |
| Repetitions                             | 3                            | 1                               | 1                              |

Phrasing detail (raw model output, before the guard):

| Model                    | Facts correct | Decision kept | Format followed | Usable after guard |
| ------------------------ | ------------- | ------------- | --------------- | ------------------ |
| Qwen2.5-Instruct 1.5B    | 17/21         | 19/21         | 6/21            | 13/21              |
| DeepSeek-R1-Distill 1.5B | 5/7           | 7/7           | 5/7             | 5/7                |
| Claude Opus 5.5 Medium   | 7/7           | 7/7           | 7/7             | 7/7                |

### What the results mean

1. **Keeping decisions in Python is essential, not a style choice.** Asked to
   apply five written rules to raw numbers, Qwen was right 29 % of the time,
   close to the 25 % you'd get by guessing one of four answers. The frontier
   model got all 7 right. On this hardware, the LLM can't be trusted with the
   decision.
2. **The output guard turns a 24 % model into a 62 % usable one.** Most raw Qwen
   messages broke a format rule (greetings, extra sentences, "The decision to…
   is based on…" restatements), but the facts and decision were usually right
   (17/21 and 19/21). The guard cleans the format and rejects the rest, which
   then fall back to a rule-based message, so the user never sees a wrong
   number.
3. **Each small model has a different weakness.** DeepSeek's reasoning helps
   with arithmetic (67 % vs 33 %), but in most raw-decision and tool cases it
   **ran out of output before finishing its reasoning** and never gave an answer
   at all. Qwen always answers, quickly, but reasons poorly. In its own words:
   "Air B has a higher relative humidity, which means it contains more water
   vapour", the same misconception as finding #1 in `findings.md`.
4. **Qwen is honest about missing data (92 %), DeepSeek invents (50 %).**
   DeepSeek answered "One person would be expected" for the number of people in
   the room, and treated the outdoor AQI as an indoor reading. For an assistant,
   admitting ignorance matters more than sounding helpful.
5. **"Ask your room" questions (see the T tests below) aren't viable with these
   models as-is.** Tool selection was 29 % and 13 %. Qwen invented tools that
   don't exist (`best_air_quality`, `weather_forecast`, `current_humidities`)
   and often returned several JSON objects instead of one. This feature would
   need keyword or intent matching with the LLM as a fallback, constrained
   output, or a fine-tuned model.
6. **Qwen is slower in the benchmark (13.3 s) than in the advisor (5–9 s)**
   because it often ignored "answer only" instructions and added explanations.
   Longer outputs mean longer generation time.

### Notes on specific results

- **Frontier tool miss (T6, "What's the CO₂ level?"):** it chose
  `current_conditions`, whose description mentions "air quality". The test is
  arguably ambiguous, since the gas sensor measures VOCs, not CO₂, but the
  description doesn't say so. A future version should make that explicit.
- **Frontier model:** Claude Opus 5.5 (Medium). 1 rep so far, answered in a
  fresh chat with no project context (blind). 2 more reps are planned.

### Validating the scoring

The first scoring pass gave Qwen 32/96 and DeepSeek 10/32. Reviewing every
failure by hand found three scoring bugs:

- the parser read the last label in a reply, which was often inside the
  explanation, not the answer
- it rejected typos like `AIRC_B`
- the "I don't know" pattern missed phrasings like "no direct data"

After fixing them and re-scoring the saved outputs with `eval.py --rescore`, the
totals became 35/96 and 11/32; the frontier score didn't change. Exact-format
compliance is still recorded separately, so the format errors aren't hidden.

## Code layout

| File         | Role                                                                                                                                |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| `airlib.py`  | Shared logic: physics (absolute humidity, dew point, window-glass temperature), decision rules, prompt v2, LLM client, output guard |
| `advisor.py` | Live advisor: reads the SQLite log, fetches tonight's forecast low, decides, asks the LLM, guards the output                        |
| `eval.py`    | Benchmark suite (this document)                                                                                                     |

The advisor and the benchmark import the same `airlib.py`, so the benchmark
tests exactly what runs in production.

## Test categories (32 cases)

| ID    | Category     | Task                                                                                                             | What it reveals                                  | Scored by                                                                                                                                   |
| ----- | ------------ | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| P1–P7 | phrasing     | Turn a decision and its reasons into one or two sentences                                                        | Instruction following, sticking to the facts     | Output guard: numbers must appear in the facts, decision not contradicted, no greeting, sign-off, label or placeholder, at most 2 sentences |
| D1–D7 | raw_decision | Make the decision from raw numbers plus written rules                                                            | Whether the model could replace the Python rules | First label in the reply must match (also records whether it at least got "ventilate or not" right)                                         |
| A1–A4 | arithmetic   | Which air holds more water per m³ (cold, humid air vs warm, drier air)                                           | Number handling                                  | First "Air A/B" in the reply must match; exact format recorded separately                                                                   |
| A5–A6 | arithmetic   | Calculate a dew point                                                                                            | Multi-step calculation                           | Within ±1 °C                                                                                                                                |
| T1–T8 | tools        | Pick a query tool and period as JSON; 2 questions have no suitable tool                                          | Readiness for "ask your room" questions          | Valid JSON + correct tool + correct period (first JSON object in the reply)                                                                 |
| U1–U4 | unknown      | Answer from the facts or say the answer isn't there (CO₂, people count, indoor PM2.5; plus 1 answerable control) | Making things up                                 | Must admit not knowing with no invented numbers; the control must give the right value                                                      |

**What the tools tests (T1–T8) are for.** "Ask your room" is a planned feature:
the user types a question about the logged data, such as "How humid was it
today?". Because the small models can't read the database and are unreliable
with numbers, they don't answer directly. Instead, the model picks one of a few
Python query functions ("tools") and the time period, as JSON, for example
`{"tool": "humidity_summary", "period": "today"}`. Python runs that function on
the real data, and the model phrases the result. The T tests check only the
model's part: choosing the right tool and period. Two of the eight questions
(CO₂ level, tomorrow's rain) have no suitable tool, so the correct answer is
`{"tool": "none"}`.

The seven scenarios used for P and D cover: conditions fine, stale air on a cold
day, humid with drier outdoor air, humid with wetter outdoor air, stale air with
poor outdoor AQI, warm room, and condensation risk only.

## Protocol

**Local models** (hailo-ollama running; warm the model first with one
`advisor.py` call):

```bash
python3 eval.py --model qwen2.5-instruct:1.5b --reps 3
python3 eval.py --model deepseek_r1_distill_qwen:1.5b --reps 1  # ~80 s/case
```

**Frontier model (blind test):**

1. `python3 eval.py --export-prompts frontier_prompts.md`
2. Paste the whole file into a **new chat with no prior context**. A session
   that knows the expected answers and the models' past mistakes would bias the
   result.
3. Copy the reply, save it as `frontier_answers.md`, then run `python3 eval.py
   --score-answers frontier_answers.md --label frontier`.
4. Repeat in 2 more fresh chats for 3 reps.

**Report:** `python3 eval.py --report` combines all runs into
`eval_results/report.md`. All raw model outputs are kept in
`eval_results/results.jsonl`, so `python3 eval.py --rescore` can re-score them
after any change to the scoring code without re-running the models.

## Fairness notes

- Same prompts, same scoring code for every model.
- The frontier model answers all 32 prompts in one message, while local models
  get one request per prompt. Each prompt is self-contained, so the extra
  context shouldn't help much, but it is a difference.
- Frontier latency is not measured: chat-app response time includes the
  interface and network, so it isn't comparable. Accuracy is directly
  comparable.
- Local model latency is the end-to-end `/api/chat` time on a warm model.
- Rep counts differ (Qwen 3, DeepSeek 1, frontier 1), so DeepSeek and frontier
  percentages are less certain.
