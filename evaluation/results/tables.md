| System | Exact | Medicine | Dose | Time | Frequency | Schedulable | Dose halluc. | JSON valid | Qwen latency (s) |
|---|---|---|---|---|---|---|---|---|---|
| B1 Rule-based (IndicTrans2 + regex, no LLM) | 42.0 [32.0, 52.0] | 52.0 | 80.0 | 83.0 | 100.0 | 88.0 | 0.0 | - | - |
| B2 Original pipeline (Qwen-1.5B, plain prompt, v1 validation) | 13.0 [7.0, 20.0] | 74.0 | 46.0 | 24.0 | 68.0 | 34.0 | 85.7 | 100.0 | 16.25 |
| Ours (Qwen-0.5B, chat + few-shot, v2 validation) | 52.0 [42.0, 62.0] | 74.0 | 76.0 | 83.0 | 100.0 | 100.0 | 39.3 | 100.0 | 1.11 |
| Ours with Qwen-1.5B | 61.0 [51.0, 71.0] | 74.0 | 88.0 | 83.0 | 100.0 | 96.0 | 0.0 | 100.0 | 10.06 |
| - few-shot examples (system prompt only) | 53.0 [43.0, 63.0] | 77.0 | 70.0 | 86.0 | 100.0 | 100.0 | 42.9 | 100.0 | 1.02 |
| - system prompt and examples (plain prompt) | 13.0 [7.0, 20.0] | 35.0 | 60.0 | 23.0 | 100.0 | 77.0 | 14.3 | 71.0 | 1.50 |
| - rule-based frequency | 40.0 [31.0, 50.0] | 74.0 | 76.0 | 83.0 | 74.0 | 74.0 | 39.3 | 100.0 | 1.11 |
| - validation layer (v1 defaults only) | 40.0 [31.0, 50.0] | 74.0 | 76.0 | 83.0 | 74.0 | 74.0 | 39.3 | 100.0 | 1.11 |
| - IndicTrans2 (Indic text straight to Qwen) | 0.0 [0.0, 0.0] | 14.0 | 42.0 | 42.0 | 47.0 | 97.0 | 67.9 | 99.0 | 1.27 |
| Wrong source language (all translated as Tamil) | 17.0 [10.0, 25.0] | 29.0 | 51.0 | 51.0 | 73.0 | 91.0 | 53.6 | 99.0 | 1.30 |
| Ours on noisy input (5% characters deleted) | 35.0 [26.0, 44.0] | 61.0 | 68.0 | 64.0 | 93.0 | 96.0 | 32.1 | 100.0 | 1.12 |
| B1 on noisy input | 31.0 [22.0, 40.0] | 43.0 | 75.0 | 70.0 | 93.0 | 85.0 | 0.0 | - | - |
| Ours run 2 (greedy) | 52.0 [42.0, 62.0] | 74.0 | 76.0 | 83.0 | 100.0 | 100.0 | 39.3 | 100.0 | 1.11 |
| Ours run 3 (greedy) | 52.0 [42.0, 62.0] | 74.0 | 76.0 | 83.0 | 100.0 | 100.0 | 39.3 | 100.0 | 1.11 |
| Ours sampled T=0.7 seed 0 | 49.0 [39.0, 59.0] | 73.0 | 72.0 | 78.0 | 100.0 | 96.0 | 42.9 | 100.0 | 1.12 |
| Ours sampled T=0.7 seed 1 | 53.0 [43.0, 63.0] | 73.0 | 81.0 | 83.0 | 96.0 | 99.0 | 35.7 | 100.0 | 1.11 |
| Ours sampled T=0.7 seed 2 | 54.0 [44.0, 64.0] | 74.0 | 81.0 | 79.0 | 100.0 | 100.0 | 25.0 | 100.0 | 1.11 |

| Comparison | Ours-only correct | Other-only correct | p (exact McNemar) | p (Holm) |
|---|---|---|---|---|
| Ours vs B1 Rule-based (IndicTrans2 + regex, no LLM) | 21 | 11 | 0.11 | 0.22 |
| Ours vs B2 Original pipeline (Qwen-1.5B, plain prompt, v1 validation) | 39 | 0 | 3.6e-12 | 2.9e-11 |
| Ours vs Ours with Qwen-1.5B | 1 | 10 | 0.012 | 0.035 |
| Ours vs - few-shot examples (system prompt only) | 6 | 7 | 1 | 1 |
| Ours vs - system prompt and examples (plain prompt) | 44 | 5 | 7.6e-09 | 4.6e-08 |
| Ours vs - rule-based frequency | 12 | 0 | 0.00049 | 0.0024 |
| Ours vs - validation layer (v1 defaults only) | 12 | 0 | 0.00049 | 0.0024 |
| Ours vs - IndicTrans2 (Indic text straight to Qwen) | 52 | 0 | 4.4e-16 | 4e-15 |
| Ours vs Wrong source language (all translated as Tamil) | 36 | 1 | 5.5e-10 | 3.9e-09 |
