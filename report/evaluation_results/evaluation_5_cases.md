# Evaluation Report: Chatbot vs Agent

- Generated at: 2026-04-06T21:20:40.979965
- Provider: openai
- Model: gpt-4o

## Aggregate Metrics

| Metric | Chatbot Baseline | Agent |
|---|---:|---:|
| P50 Latency (ms) | 21378 | 36957 |
| P99 Latency (ms) | 32635 | 44134 |
| Avg TTFT (ms) | 23602 | 1683 |
| Avg Tokens / Task | 2618 | 16439 |
| Total Tokens (5 cases) | 13091 | 82197 |
| Avg Loop Count | 1 | 4.6 |
| JSON Parser Errors | 0 | 0 |
| Hallucination Errors | 0 | 0 |
| Timeout Errors | 0 | 0 |

## Test Cases

1. Lên kế hoạch đi Đà Nẵng 3 ngày 2 đêm từ Hà Nội, đi ngày 10/04/2026.
2. Tôi muốn du lịch Nha Trang 4 ngày 3 đêm cho 2 người, ngân sách 12 triệu VND, đi ngày 12/04/2026.
3. Tư vấn chuyến đi Huế 2 ngày 1 đêm từ Đà Nẵng, ưu tiên tàu hỏa, đi ngày 15/04/2026.
4. Lên lịch trình đi Phú Quốc 3 ngày, ưu tiên resort gần biển, khởi hành ngày 18/04/2026.
5. Tôi muốn đi Sapa 3 ngày 2 đêm từ Hà Nội, ăn món địa phương, đi ngày 20/04/2026.
