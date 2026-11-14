# Historic context run hist-ft

- date: 2026-11-14T15:45
- model: run1-step1050 style: ft split: all endpoint: vLLM OpenAI-compatible
- questions: 158; buckets {'lookup': 123, 'visual': 12, 'derived': 23}

| mode | n | acc | lookup | derived | visual | dev | test | record | record+reasoning | image | in tok/q | €/1k q |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| noctx | 158 | 0.589 | 0.585 | 0.435 | 0.917 | 0.547 | 0.627 | 0.539 | 0.575 | 0.938 | 1720 | 0.058 |
| ctx | 158 | 0.880 | 0.935 | 0.565 | 0.917 | 0.893 | 0.867 | 0.922 | 0.750 | 0.938 | 2123 | 0.053 |

| mode | author | count | drawing_type | floor | function | language | name | other | place | scale | year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| noctx | 0.083 | 1.000 | 0.900 | 0.333 | 0.800 | 0.500 | 0.474 | 0.786 | 0.574 | 1.000 | 0.519 |
| ctx | 0.917 | 1.000 | 1.000 | 0.667 | 0.950 | 0.500 | 0.947 | 0.857 | 0.936 | 0.000 | 0.704 |

Paired: context fixed 49 questions and broke 3 (of 158).
