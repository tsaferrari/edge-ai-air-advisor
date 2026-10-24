| Model | phrasing | raw_decision | arithmetic | tools | unknown | Overall | Median time |
|---|---|---|---|---|---|---|---|
| qwen2.5-instruct:1.5b | 5/21 | 6/21 | 6/18 | 7/24 | 11/12 | 35/96 | 13.3 s |
| deepseek_r1_distill_qwen:1.5b | 4/7 | 0/7 | 4/6 | 1/8 | 2/4 | 11/32 | 82.5 s |
| frontier | 7/7 | 7/7 | 6/6 | 7/8 | 4/4 | 31/32 | n/a |

Phrasing detail (raw model output, before the guard):

| Model | Facts correct | Decision kept | Format followed | Usable after guard |
|---|---|---|---|---|
| qwen2.5-instruct:1.5b | 17/21 | 19/21 | 6/21 | 13/21 |
| deepseek_r1_distill_qwen:1.5b | 5/7 | 7/7 | 5/7 | 5/7 |
| frontier | 7/7 | 7/7 | 7/7 | 7/7 |
