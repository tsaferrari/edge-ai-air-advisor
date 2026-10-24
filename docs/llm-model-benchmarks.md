# LLM model benchmarks: ventilation advisor on AI HAT+ 2

Comparison of on-device language models used to turn the ventilation decision
into a plain-English message.

## Setup

| Item         | Detail                                                                |
| ------------ | --------------------------------------------------------------------- |
| Host         | Raspberry Pi 5, 4 GB RAM                                              |
| Accelerator  | Raspberry Pi AI HAT+ 2 (Hailo-10H, 8 GB on-board RAM, firmware 5.1.1) |
| Model server | `hailo-ollama` on `localhost:8000`, `/api/chat`, `stream: false`      |
| Client       | `advisor.py` (reads SQLite logged by `logger.py`)                     |
| Power tool   | `power_log.py` (samples `vcgencmd pmic_read_adc` every 0.25 s)        |
| Sensor       | Pimoroni BME690 over I2C                                              |
| Outdoor data | Open-Meteo weather + air quality API (Cambridge, UK)                  |

### Architecture

Python computes the facts (temperature, relative and absolute humidity, gas vs.
baseline, outdoor AQI) and makes the decision with deterministic rules. The LLM
only phrases that decision for the user. Small 1-1.5B models are unreliable at
comparing numbers, so they never make the decision. If the LLM is unavailable, a
rule-based fallback message is printed.

### Method

- Same prompt template (v1) and same expected decision (`no_action`) for every
  run. Sensor conditions were similar but not identical between the two models'
  sessions; see each section.
- **Time** is the end-to-end `/api/chat` request time measured in `advisor.py`.
- **Cold** = first request with the model not yet loaded, so it includes loading
  the model onto the HAT.
- **Warm** = later requests with the model already loaded.
- **Quality** is judged against the prompt rules: at most 2 sentences, use only
  the given facts, don't change the decision, don't add numbers.

## Comparison

| Metric                               | DeepSeek-R1-Distill 1.5B | Qwen2.5-Instruct 1.5B          |
| ------------------------------------ | ------------------------ | ------------------------------ |
| Cold start                           | 81.7 s                   | 34.1 s                         |
| Warm response                        | 30.6–51.1 s              | 5.1–8.6 s                      |
| Stuck to the facts                   | 1 of 4 runs              | 3 of 4 runs                    |
| Followed the format                  | 1 of 4 runs              | 1 of 4 runs                    |
| Decision preserved                   | 4 of 4                   | 4 of 4                         |
| Extra Pi CPU-side energy per message | ≈ 0 J (within noise)     | ≈ 3 J (mostly script start-up) |
| HAT busy time per message (warm)     | 30–51 s                  | 5–9 s                          |

**Choice: Qwen2.5-Instruct 1.5B.** It's about 5–8× faster warm, keeps the HAT
busy for a fraction of the time, and invents facts less often. Its main weakness
was formatting (letter-style greetings and sign-offs), addressed by prompt v2
and the output guard (see `eval-suite.md`).

## Results: DeepSeek-R1-Distill-Qwen 1.5B

Model: `deepseek_r1_distill_qwen:1.5b`, HEF format, Q4_0 quantisation, 2.37 GB
on disk. It is a reasoning model, so it emits a hidden `<think>...</think>`
section before its answer; `advisor.py` strips it.

Date: 24 Oct 2026. Runs 1–3 at ~17:00 (indoor about 22.5 °C / 50 % RH, outdoor
11.4 °C / 92 % RH, AQI 29). Run 4 at ~20:15 during the power measurement (indoor
21.5 °C / 56 %, outdoor 14.4 °C / 91 %, AQI 24).

| Run | State | Time   | Followed facts?                                                                               | Followed format?                                                       | Output (summary)                                         |
| --- | ----- | ------ | --------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | -------------------------------------------------------- |
| 1   | Cold  | 81.7 s | No: said 51 % humidity, actual 50 %                                                           | No: 3 sentences, written as "My home…"                                 | Described conditions, "No action needed."                |
| 2   | Warm  | 45.9 s | No: invented advice to "monitor humidity, slightly over 80 %", which contradicts the decision | No: added a "Message:" heading, quotes and a repeated "Decision:" line | Long, padded message                                     |
| 3   | Warm  | 30.6 s | Yes                                                                                           | Yes                                                                    | "Indoor comfort is excellent, no need for intervention." |
| 4   | Warm  | 51.1 s | No: said 55 % humidity, actual 56 %                                                           | No: "Hi [Name], thanks for reaching out!", 4 sentences                 | Restated conditions, "No need to adjust anything!"       |

### Observations

- **Unpredictable latency.** Warm time ranged from 30.6 s to 51.1 s on similar
  input, because the length of the hidden reasoning changes every run.
- **Unpredictable quality.** Two wrong numbers, one invented recommendation and
  one good answer in four runs.
- **Wasted strength.** The model's reasoning ability isn't needed, because the
  decision is already made in Python. It only adds latency.
- **Validated the architecture.** The decision layer was correct on every run.
  Letting the LLM decide would have produced a wrong or contradictory
  recommendation in some runs.

### Conclusion

Not suitable for this task. An embedded advisor needs predictable latency and
output that sticks to the facts.

## Results: Qwen2.5-Instruct 1.5B

Model: `qwen2.5-instruct:1.5b`, an instruction-tuned model with no reasoning
phase.

Date: 24 Oct 2026. Runs 1–3 at ~19:58 (indoor 20.9 °C / 55–58 % RH, outdoor
13.9–14.2 °C / 91 % RH, AQI 26, gas at about 128 % of baseline). Run 4 at ~20:18
during the power measurement (indoor 21.5 °C / 56 %, outdoor 14.4 °C / 91 %, AQI
24).

| Run | State | Time   | Followed facts?                                              | Followed format?                                                          | Output (summary)                                                                                                      |
| --- | ----- | ------ | ------------------------------------------------------------ | ------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| 1   | Cold  | 34.1 s | No: invented "the city's annual average limit of 50" for AQI | No: letter format ("Dear user", "Warm regards, [Your Name]"), 3 sentences | Correct numbers and decision, plus the invented limit                                                                 |
| 2   | Warm  | 5.1 s  | Yes                                                          | Yes: 2 sentences                                                          | "...the indoor conditions are considered fine, so no action is needed. Keep up the good work..." Correct but generic. |
| 3   | Warm  | 8.6 s  | Yes: quoted 20.9 °C and 56 % correctly                       | No: letter format again, 3 sentences                                      | Correct content in a letter wrapper                                                                                   |
| 4   | Warm  | 6.2 s  | Yes                                                          | No: letter format, signed "Your Home Air-Quality Assistant"               | Correct, generic, in a letter wrapper                                                                                 |

### Observations

- **Fast and steady.** Warm responses in 5–9 s, compared with 30–51 s for
  DeepSeek, because there's no hidden reasoning phase.
- **Faster cold start.** 34 s, compared with 82 s.
- **Better at sticking to the facts.** One invented claim in four runs; the
  numbers it quoted were always correct.
- **Formatting is the weak point.** Three of four runs used a letter format. The
  prompt asked for a "message", which the model seems to read as "letter".

## Power

### HAT power: on-chip measurement not available

HailoRT includes `hailortcli measure-power`, but on the AI HAT+ 2 (Hailo-10H,
firmware 5.1.1) it fails with `HAILO_OPEN_FILE_FAILURE(13)`, both as a normal
user and with `sudo`, and with no other process using the device. The board
doesn't appear to have the power-monitoring circuit that Hailo's evaluation
boards and some M.2 modules have. HAT power therefore has to be measured
externally, with a USB-C power meter between the PSU and the Pi.

### Pi-side power (CPU, RAM, I/O; excludes the HAT)

Measured with `power_log.py`: a 10 s idle baseline, then sampling every 0.25 s
during one warm `advisor.py` run. hailo-ollama and the logger service were
running throughout.

| Model                    | Baseline | Average during run | Peak   | Run time | Extra energy above baseline |
| ------------------------ | -------- | ------------------ | ------ | -------- | --------------------------- |
| DeepSeek-R1-Distill 1.5B | 2.25 W   | 2.13 W             | 3.19 W | 51.2 s   | −5.9 J (≈ 0, within noise)  |
| Qwen2.5-Instruct 1.5B    | 2.24 W   | 2.69 W             | 2.98 W | 6.3 s    | 2.8 J                       |

### Findings

- **Inference is fully offloaded to the Hailo-10H.** During DeepSeek's 51 s of
  generation, the Pi's own rails stayed at idle power; the slight negative value
  is background fluctuation. The CPU just waits for the HAT's answer.
- **The small Qwen figure is fixed overhead, not inference.** About 3 J comes
  from starting Python, querying SQLite and the HTTP call. Over Qwen's short 6 s
  run it shows up in the average; over DeepSeek's 51 s run it's lost in the
  noise.
- **The real difference between the models is on the HAT.** It's busy for 30–51
  s per DeepSeek message against 5–9 s per Qwen message. If the HAT draws
  similar power for both models, DeepSeek uses roughly 6–8× more energy per
  message. *This is an estimate until HAT power is measured externally.*

## Follow-ups

- **Done:** prompt v2 (one or two plain sentences, no greeting or sign-off, no
  outside facts) and an output guard that checks every number against the facts
  and falls back to a rule-based message. Results in `eval-suite.md`.
- **HAT power:** measure total system power with a logging USB-C meter (e.g.
  FNIRSI FNB58) in three states (idle, model loaded, generating) for both
  models, and confirm the energy-per-message estimate.
- **Longer baselines:** use a 30 s baseline and repeat each power measurement 3
  times to reduce noise.
