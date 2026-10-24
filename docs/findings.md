# Findings

Interesting results from the project, with the evidence for each.

## 1. 92 % humidity outside can be drier than 50 % inside

Relative humidity only says how full the air is relative to what it *could* hold
at that temperature. Cold air holds much less water. On 24 Oct 2026 the logger
recorded:

|         | Temperature | Relative humidity | Water content |
| ------- | ----------- | ----------------- | ------------- |
| Indoor  | 22.5 °C     | 50 %              | 10.0 g/m³     |
| Outdoor | 11.4 °C     | 92 %              | 9.4 g/m³      |

So airing the room with "very humid" outdoor air actually dries it slightly. The
advisor compares **absolute humidity** (g/m³), not relative humidity, for this
reason. It's also test A1 in the evaluation suite, because it catches people out
and is a good probe of whether a model can reason with numbers. Qwen2.5-Instruct
fell for it, explaining that "higher relative humidity means it contains more
water vapour".

## 2. LLM inference is fully offloaded to the Hailo-10H

During a 51 s DeepSeek generation, the Pi's own power rails stayed at idle (2.13
W against a 2.25 W baseline). The CPU just waits for the HAT. See
`llm-model-benchmarks.md`, Power section.

## 3. A reasoning model is the wrong tool for a phrasing job

DeepSeek-R1-Distill 1.5B took 30–51 s per message, with response time varying by
run because its hidden reasoning length changes. Qwen2.5-Instruct 1.5B took 5–9
s and stuck to the facts more often. When the decision is already made in code,
reasoning only adds latency. See `llm-model-benchmarks.md`.

## 4. Small models need an output guard

Across 8 runs, the two local models produced invented numbers (51 % for 50 %, 55
% for 56 %), an invented "city annual average limit of 50", advice contradicting
the decision, and letter-style greetings with "[Your Name]" placeholders.
`airlib.guard()` now strips formatting noise and rejects messages with numbers
not in the facts or that contradict the decision, falling back to a rule-based
message. In the evaluation suite it raised Qwen's usable messages from 24 %
(raw) to 62 %.

## 5. HailoRT power measurement isn't available on the AI HAT+ 2

`hailortcli measure-power` fails with `HAILO_OPEN_FILE_FAILURE(13)` on the
Hailo-10H (firmware 5.1.1), even with sudo. HAT power must be measured
externally.

## 6. The edge models can't make the decision; a frontier model can

Given five written rules and raw numbers, Qwen2.5-Instruct chose correctly 29 %
of the time, close to random guessing among four options. DeepSeek scored 0 %
(mostly by never finishing its reasoning). A frontier model got 7/7. That's the
evidence behind the architecture: Python decides, the LLM only phrases. See
`eval-suite.md`.

## 7. The gap is uneven: honesty is close, reasoning is far apart

Overall, the edge models scored 36 % and 34 % against the frontier model's 97 %.
But on admitting missing data, Qwen reached 92 %, close to the frontier's 100 %.
The biggest gaps are in decisions, arithmetic and tool selection. The useful
question isn't "is the small model good?" but "which parts of the job can it do
safely?"

## 8. Reasoning models can run out of output before answering

On the decision tests, DeepSeek-R1-Distill returned no recognisable answer in 6
of 7 cases: only part of its reasoning ("Okay, let's break this down…") or
nothing at all.

The timings show why. In the evaluation run, four of those cases took **exactly
151.3 s** and four arithmetic cases took **exactly 149.8 s**. Identical times
across different prompts mean generation stopped at a fixed ceiling, almost
certainly hailo-ollama's maximum output length, not because the model had
finished. On a device with fixed output limits, a reasoning model can spend its
whole budget thinking and never answer. Instruction-tuned models don't have this
failure mode.

## 9. Evaluation code needs testing too

The first scoring pass under-counted the small models: it read labels from their
explanations rather than their answers, rejected typos like `AIRC_B`, and missed
"no direct data" as an admission of not knowing. Reviewing every failure by hand
found these bugs. Because all raw outputs were saved, re-scoring took seconds
and needed no model re-runs.
