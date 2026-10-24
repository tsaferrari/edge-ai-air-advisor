This is a blind test. Below are independent prompts, each with an ID.
Answer each one as if it were the only message you received, following its instructions exactly.
Format your whole reply as the ID on its own line, then your answer, for every prompt, like:

### P1
<answer>

### P2
<answer>

Nothing else before, between or after.

### P1
```
Tell the user what to do about their room's air and why, in one or two plain sentences.
Rules: no greeting, no sign-off, no headings, no quotation marks. Use only the facts and reasons below; do not add any other facts or numbers. Do not change the decision.

Facts: Indoor: 21.5C, 50% humidity. Outdoor: 12.0C, 85% humidity, air quality index 25, dropping to 9C tonight.
Reasons: indoor conditions are fine.
Decision: No action needed.
```

### P2
```
Tell the user what to do about their room's air and why, in one or two plain sentences.
Rules: no greeting, no sign-off, no headings, no quotation marks. Use only the facts and reasons below; do not add any other facts or numbers. Do not change the decision.

Facts: Indoor: 22.0C, 52% humidity. Outdoor: 8.0C, 90% humidity, air quality index 20, dropping to 5C tonight.
Reasons: indoor air is stale (gas sensor at 55% of its normal level); it's cold outside (8.0C), so a short burst keeps the heat in.
Decision: Open the window wide for 5-10 minutes, then close it.
```

### P3
```
Tell the user what to do about their room's air and why, in one or two plain sentences.
Rules: no greeting, no sign-off, no headings, no quotation marks. Use only the facts and reasons below; do not add any other facts or numbers. Do not change the decision.

Facts: Indoor: 21.0C, 68% humidity. Outdoor: 10.0C, 88% humidity, air quality index 30, dropping to 7C tonight.
Reasons: indoor humidity is high (68%); window glass will cool to about 16C tonight and stay damp, which encourages mould over time; outdoor air holds less water, so airing the room will dry it; it's cold outside (10.0C), so a short burst keeps the heat in.
Decision: Open the window wide for 5-10 minutes, then close it.
```

### P4
```
Tell the user what to do about their room's air and why, in one or two plain sentences.
Rules: no greeting, no sign-off, no headings, no quotation marks. Use only the facts and reasons below; do not add any other facts or numbers. Do not change the decision.

Facts: Indoor: 20.0C, 63% humidity. Outdoor: 19.0C, 95% humidity, air quality index 20, dropping to 17C tonight.
Reasons: indoor humidity is high (63%); outdoor air holds more water, so opening a window won't dry the room; a dehumidifier or keeping the room warm will help more.
Decision: Keep the window closed for now.
```

### P5
```
Tell the user what to do about their room's air and why, in one or two plain sentences.
Rules: no greeting, no sign-off, no headings, no quotation marks. Use only the facts and reasons below; do not add any other facts or numbers. Do not change the decision.

Facts: Indoor: 22.0C, 50% humidity. Outdoor: 15.0C, 70% humidity, air quality index 75, dropping to 12C tonight.
Reasons: indoor air is stale (gas sensor at 60% of its normal level); but outdoor air quality is poor (European AQI 75).
Decision: Keep the window closed for now.
```

### P6
```
Tell the user what to do about their room's air and why, in one or two plain sentences.
Rules: no greeting, no sign-off, no headings, no quotation marks. Use only the facts and reasons below; do not add any other facts or numbers. Do not change the decision.

Facts: Indoor: 26.5C, 45% humidity. Outdoor: 18.0C, 60% humidity, air quality index 20, dropping to 14C tonight.
Reasons: the room is warm (26.5C) and it's cooler outside.
Decision: Open the window.
```

### P7
```
Tell the user what to do about their room's air and why, in one or two plain sentences.
Rules: no greeting, no sign-off, no headings, no quotation marks. Use only the facts and reasons below; do not add any other facts or numbers. Do not change the decision.

Facts: Indoor: 20.0C, 60% humidity. Outdoor: 4.0C, 85% humidity, air quality index 20, dropping to 0C tonight.
Reasons: window glass will cool to about 13C tonight and stay damp, which encourages mould over time; outdoor air holds less water, so airing the room will dry it; it's cold outside (4.0C), so a short burst keeps the heat in.
Decision: Open the window wide for 5-10 minutes, then close it.
```

### D1
```
You decide whether the user should open a window. Rules:
1. Ventilating is useful if: the indoor air is stale (gas sensor below 70% of normal), OR the room is above 25C and it is at least 2C cooler outside, OR there is a moisture problem AND the outdoor air contains less water per cubic metre than the indoor air (compare absolute humidity, not relative humidity).
2. A moisture problem means indoor humidity above 60%, or window glass surface humidity tonight of 80% or more.
3. If ventilating is useful but the outdoor air quality index is above 60, keep the window closed.
4. If ventilating is useful and it is below 12C outside, open it for a short burst only.
5. If ventilating is not useful but there is a moisture problem, keep the window closed. Otherwise no action is needed.

Answer with exactly one of: OPEN_WINDOW, OPEN_WINDOW_SHORT, KEEP_CLOSED, NO_ACTION. Nothing else.

Facts: Indoor: 21.5C, 50% humidity. Outdoor: 12.0C, 85% humidity, air quality index 25, dropping to 9C tonight. Gas sensor at 105% of normal. Window glass surface humidity tonight: 66%.
```

### D2
```
You decide whether the user should open a window. Rules:
1. Ventilating is useful if: the indoor air is stale (gas sensor below 70% of normal), OR the room is above 25C and it is at least 2C cooler outside, OR there is a moisture problem AND the outdoor air contains less water per cubic metre than the indoor air (compare absolute humidity, not relative humidity).
2. A moisture problem means indoor humidity above 60%, or window glass surface humidity tonight of 80% or more.
3. If ventilating is useful but the outdoor air quality index is above 60, keep the window closed.
4. If ventilating is useful and it is below 12C outside, open it for a short burst only.
5. If ventilating is not useful but there is a moisture problem, keep the window closed. Otherwise no action is needed.

Answer with exactly one of: OPEN_WINDOW, OPEN_WINDOW_SHORT, KEEP_CLOSED, NO_ACTION. Nothing else.

Facts: Indoor: 22.0C, 52% humidity. Outdoor: 8.0C, 90% humidity, air quality index 20, dropping to 5C tonight. Gas sensor at 55% of normal. Window glass surface humidity tonight: 77%.
```

### D3
```
You decide whether the user should open a window. Rules:
1. Ventilating is useful if: the indoor air is stale (gas sensor below 70% of normal), OR the room is above 25C and it is at least 2C cooler outside, OR there is a moisture problem AND the outdoor air contains less water per cubic metre than the indoor air (compare absolute humidity, not relative humidity).
2. A moisture problem means indoor humidity above 60%, or window glass surface humidity tonight of 80% or more.
3. If ventilating is useful but the outdoor air quality index is above 60, keep the window closed.
4. If ventilating is useful and it is below 12C outside, open it for a short burst only.
5. If ventilating is not useful but there is a moisture problem, keep the window closed. Otherwise no action is needed.

Answer with exactly one of: OPEN_WINDOW, OPEN_WINDOW_SHORT, KEEP_CLOSED, NO_ACTION. Nothing else.

Facts: Indoor: 21.0C, 68% humidity. Outdoor: 10.0C, 88% humidity, air quality index 30, dropping to 7C tonight. Gas sensor at 100% of normal. Window glass surface humidity tonight: 94%.
```

### D4
```
You decide whether the user should open a window. Rules:
1. Ventilating is useful if: the indoor air is stale (gas sensor below 70% of normal), OR the room is above 25C and it is at least 2C cooler outside, OR there is a moisture problem AND the outdoor air contains less water per cubic metre than the indoor air (compare absolute humidity, not relative humidity).
2. A moisture problem means indoor humidity above 60%, or window glass surface humidity tonight of 80% or more.
3. If ventilating is useful but the outdoor air quality index is above 60, keep the window closed.
4. If ventilating is useful and it is below 12C outside, open it for a short burst only.
5. If ventilating is not useful but there is a moisture problem, keep the window closed. Otherwise no action is needed.

Answer with exactly one of: OPEN_WINDOW, OPEN_WINDOW_SHORT, KEEP_CLOSED, NO_ACTION. Nothing else.

Facts: Indoor: 20.0C, 63% humidity. Outdoor: 19.0C, 95% humidity, air quality index 20, dropping to 17C tonight. Gas sensor at 100% of normal. Window glass surface humidity tonight: 67%.
```

### D5
```
You decide whether the user should open a window. Rules:
1. Ventilating is useful if: the indoor air is stale (gas sensor below 70% of normal), OR the room is above 25C and it is at least 2C cooler outside, OR there is a moisture problem AND the outdoor air contains less water per cubic metre than the indoor air (compare absolute humidity, not relative humidity).
2. A moisture problem means indoor humidity above 60%, or window glass surface humidity tonight of 80% or more.
3. If ventilating is useful but the outdoor air quality index is above 60, keep the window closed.
4. If ventilating is useful and it is below 12C outside, open it for a short burst only.
5. If ventilating is not useful but there is a moisture problem, keep the window closed. Otherwise no action is needed.

Answer with exactly one of: OPEN_WINDOW, OPEN_WINDOW_SHORT, KEEP_CLOSED, NO_ACTION. Nothing else.

Facts: Indoor: 22.0C, 50% humidity. Outdoor: 15.0C, 70% humidity, air quality index 75, dropping to 12C tonight. Gas sensor at 60% of normal. Window glass surface humidity tonight: 63%.
```

### D6
```
You decide whether the user should open a window. Rules:
1. Ventilating is useful if: the indoor air is stale (gas sensor below 70% of normal), OR the room is above 25C and it is at least 2C cooler outside, OR there is a moisture problem AND the outdoor air contains less water per cubic metre than the indoor air (compare absolute humidity, not relative humidity).
2. A moisture problem means indoor humidity above 60%, or window glass surface humidity tonight of 80% or more.
3. If ventilating is useful but the outdoor air quality index is above 60, keep the window closed.
4. If ventilating is useful and it is below 12C outside, open it for a short burst only.
5. If ventilating is not useful but there is a moisture problem, keep the window closed. Otherwise no action is needed.

Answer with exactly one of: OPEN_WINDOW, OPEN_WINDOW_SHORT, KEEP_CLOSED, NO_ACTION. Nothing else.

Facts: Indoor: 26.5C, 45% humidity. Outdoor: 18.0C, 60% humidity, air quality index 20, dropping to 14C tonight. Gas sensor at 100% of normal. Window glass surface humidity tonight: 59%.
```

### D7
```
You decide whether the user should open a window. Rules:
1. Ventilating is useful if: the indoor air is stale (gas sensor below 70% of normal), OR the room is above 25C and it is at least 2C cooler outside, OR there is a moisture problem AND the outdoor air contains less water per cubic metre than the indoor air (compare absolute humidity, not relative humidity).
2. A moisture problem means indoor humidity above 60%, or window glass surface humidity tonight of 80% or more.
3. If ventilating is useful but the outdoor air quality index is above 60, keep the window closed.
4. If ventilating is useful and it is below 12C outside, open it for a short burst only.
5. If ventilating is not useful but there is a moisture problem, keep the window closed. Otherwise no action is needed.

Answer with exactly one of: OPEN_WINDOW, OPEN_WINDOW_SHORT, KEEP_CLOSED, NO_ACTION. Nothing else.

Facts: Indoor: 20.0C, 60% humidity. Outdoor: 4.0C, 85% humidity, air quality index 20, dropping to 0C tonight. Gas sensor at 100% of normal. Window glass surface humidity tonight: 95%.
```

### A1
```
Air A: 22.0C at 50% relative humidity. Air B: 11.0C at 92% relative humidity.
Which contains more water vapour per cubic metre? Answer with exactly AIR_A or AIR_B.
```

### A2
```
Air A: 20.0C at 60% relative humidity. Air B: 15.0C at 90% relative humidity.
Which contains more water vapour per cubic metre? Answer with exactly AIR_A or AIR_B.
```

### A3
```
Air A: 24.0C at 40% relative humidity. Air B: 5.0C at 95% relative humidity.
Which contains more water vapour per cubic metre? Answer with exactly AIR_A or AIR_B.
```

### A4
```
Air A: 18.0C at 70% relative humidity. Air B: 18.0C at 75% relative humidity.
Which contains more water vapour per cubic metre? Answer with exactly AIR_A or AIR_B.
```

### A5
```
What is the dew point of air at 21.5C and 56% relative humidity? Reply with just the number in degrees C, rounded to one decimal place.
```

### A6
```
What is the dew point of air at 25.0C and 70% relative humidity? Reply with just the number in degrees C, rounded to one decimal place.
```

### T1
```
You route questions about a home air-quality sensor to a tool. Available tools:
- current_conditions: latest indoor temperature, humidity and air quality (no period)
- worst_air_quality: when the indoor air was stalest (needs period)
- humidity_summary: lowest, average and highest indoor humidity (needs period)
- temperature_summary: lowest, average and highest indoor temperature (needs period)
- window_open_events: when a window was opened (needs period)
period must be "today" or "week".
If none of these tools can answer the question, reply {"tool": "none"}.
Reply with only a JSON object, for example {"tool": "humidity_summary", "period": "today"}.

Question: What's the temperature in the room right now?
```

### T2
```
You route questions about a home air-quality sensor to a tool. Available tools:
- current_conditions: latest indoor temperature, humidity and air quality (no period)
- worst_air_quality: when the indoor air was stalest (needs period)
- humidity_summary: lowest, average and highest indoor humidity (needs period)
- temperature_summary: lowest, average and highest indoor temperature (needs period)
- window_open_events: when a window was opened (needs period)
period must be "today" or "week".
If none of these tools can answer the question, reply {"tool": "none"}.
Reply with only a JSON object, for example {"tool": "humidity_summary", "period": "today"}.

Question: When was the air quality worst this week?
```

### T3
```
You route questions about a home air-quality sensor to a tool. Available tools:
- current_conditions: latest indoor temperature, humidity and air quality (no period)
- worst_air_quality: when the indoor air was stalest (needs period)
- humidity_summary: lowest, average and highest indoor humidity (needs period)
- temperature_summary: lowest, average and highest indoor temperature (needs period)
- window_open_events: when a window was opened (needs period)
period must be "today" or "week".
If none of these tools can answer the question, reply {"tool": "none"}.
Reply with only a JSON object, for example {"tool": "humidity_summary", "period": "today"}.

Question: How humid was it today?
```

### T4
```
You route questions about a home air-quality sensor to a tool. Available tools:
- current_conditions: latest indoor temperature, humidity and air quality (no period)
- worst_air_quality: when the indoor air was stalest (needs period)
- humidity_summary: lowest, average and highest indoor humidity (needs period)
- temperature_summary: lowest, average and highest indoor temperature (needs period)
- window_open_events: when a window was opened (needs period)
period must be "today" or "week".
If none of these tools can answer the question, reply {"tool": "none"}.
Reply with only a JSON object, for example {"tool": "humidity_summary", "period": "today"}.

Question: Did anyone open the window today?
```

### T5
```
You route questions about a home air-quality sensor to a tool. Available tools:
- current_conditions: latest indoor temperature, humidity and air quality (no period)
- worst_air_quality: when the indoor air was stalest (needs period)
- humidity_summary: lowest, average and highest indoor humidity (needs period)
- temperature_summary: lowest, average and highest indoor temperature (needs period)
- window_open_events: when a window was opened (needs period)
period must be "today" or "week".
If none of these tools can answer the question, reply {"tool": "none"}.
Reply with only a JSON object, for example {"tool": "humidity_summary", "period": "today"}.

Question: How warm has the room been over the past week?
```

### T6
```
You route questions about a home air-quality sensor to a tool. Available tools:
- current_conditions: latest indoor temperature, humidity and air quality (no period)
- worst_air_quality: when the indoor air was stalest (needs period)
- humidity_summary: lowest, average and highest indoor humidity (needs period)
- temperature_summary: lowest, average and highest indoor temperature (needs period)
- window_open_events: when a window was opened (needs period)
period must be "today" or "week".
If none of these tools can answer the question, reply {"tool": "none"}.
Reply with only a JSON object, for example {"tool": "humidity_summary", "period": "today"}.

Question: What's the CO2 level?
```

### T7
```
You route questions about a home air-quality sensor to a tool. Available tools:
- current_conditions: latest indoor temperature, humidity and air quality (no period)
- worst_air_quality: when the indoor air was stalest (needs period)
- humidity_summary: lowest, average and highest indoor humidity (needs period)
- temperature_summary: lowest, average and highest indoor temperature (needs period)
- window_open_events: when a window was opened (needs period)
period must be "today" or "week".
If none of these tools can answer the question, reply {"tool": "none"}.
Reply with only a JSON object, for example {"tool": "humidity_summary", "period": "today"}.

Question: Is it going to rain tomorrow?
```

### T8
```
You route questions about a home air-quality sensor to a tool. Available tools:
- current_conditions: latest indoor temperature, humidity and air quality (no period)
- worst_air_quality: when the indoor air was stalest (needs period)
- humidity_summary: lowest, average and highest indoor humidity (needs period)
- temperature_summary: lowest, average and highest indoor temperature (needs period)
- window_open_events: when a window was opened (needs period)
period must be "today" or "week".
If none of these tools can answer the question, reply {"tool": "none"}.
Reply with only a JSON object, for example {"tool": "humidity_summary", "period": "today"}.

Question: Was the air stuffy at any point today?
```

### U1
```
You are a home air-quality assistant. Answer the question in one or two sentences using only the facts below. If the facts don't contain the answer, say so.

Facts: Indoor: 21.5C, 56% humidity. Outdoor: 14.4C, 91% humidity, air quality index 24.
Question: What is the CO2 level in the room?
```

### U2
```
You are a home air-quality assistant. Answer the question in one or two sentences using only the facts below. If the facts don't contain the answer, say so.

Facts: Indoor: 21.5C, 56% humidity. Outdoor: 14.4C, 91% humidity, air quality index 24.
Question: How many people are in the room?
```

### U3
```
You are a home air-quality assistant. Answer the question in one or two sentences using only the facts below. If the facts don't contain the answer, say so.

Facts: Indoor: 21.5C, 56% humidity. Outdoor: 14.4C, 91% humidity, air quality index 24.
Question: What is the PM2.5 level inside the room?
```

### U4
```
You are a home air-quality assistant. Answer the question in one or two sentences using only the facts below. If the facts don't contain the answer, say so.

Facts: Indoor: 21.5C, 56% humidity. Outdoor: 14.4C, 91% humidity, air quality index 24.
Question: What is the humidity inside the room?
```
