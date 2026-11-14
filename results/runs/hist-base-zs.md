# Historic context run hist-base-zs

- date: 2026-11-14T15:44
- model: Qwen/Qwen3.5-4B style: zs split: all endpoint: vLLM OpenAI-compatible
- questions: 158; buckets {'lookup': 123, 'visual': 12, 'derived': 23}

| mode | n | acc | lookup | derived | visual | dev | test | record | record+reasoning | image | in tok/q | €/1k q |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| noctx | 158 | 0.576 | 0.545 | 0.522 | 1.000 | 0.547 | 0.602 | 0.520 | 0.575 | 0.938 | 1786 | 0.061 |
| ctx | 158 | 0.937 | 0.959 | 0.826 | 0.917 | 0.973 | 0.904 | 0.951 | 0.900 | 0.938 | 2189 | 0.060 |
| ctx-noweb | 158 | 0.930 | 0.943 | 0.826 | 1.000 | 0.920 | 0.940 | 0.971 | 0.800 | 1.000 | 2046 | 0.056 |

| mode | author | count | drawing_type | floor | function | language | name | other | place | scale | year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| noctx | 0.083 | 1.000 | 1.000 | 0.333 | 0.500 | 1.000 | 0.421 | 0.786 | 0.553 | 1.000 | 0.667 |
| ctx | 1.000 | 1.000 | 1.000 | 1.000 | 0.700 | 1.000 | 0.947 | 0.929 | 0.957 | 1.000 | 1.000 |
| ctx-noweb | 1.000 | 1.000 | 1.000 | 1.000 | 0.650 | 1.000 | 1.000 | 0.857 | 0.979 | 1.000 | 0.963 |

Paired: context fixed 59 questions and broke 2 (of 158).
