import json
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chatbot_baseline import ChatbotBaseline
from src.agent.agent import ReActAgent
from src.tools.tools import TRAVEL_TOOLS


TEST_CASES = [
    "Lên kế hoạch đi Đà Nẵng 3 ngày 2 đêm từ Hà Nội, đi ngày 10/04/2026.",
    "Tôi muốn du lịch Nha Trang 4 ngày 3 đêm cho 2 người, ngân sách 12 triệu VND, đi ngày 12/04/2026.",
    "Tư vấn chuyến đi Huế 2 ngày 1 đêm từ Đà Nẵng, ưu tiên tàu hỏa, đi ngày 15/04/2026.",
    "Lên lịch trình đi Phú Quốc 3 ngày, ưu tiên resort gần biển, khởi hành ngày 18/04/2026.",
    "Tôi muốn đi Sapa 3 ngày 2 đêm từ Hà Nội, ăn món địa phương, đi ngày 20/04/2026.",
]


def _provider_from_env():
    provider_name = os.getenv("DEFAULT_PROVIDER", "openai").lower()
    if provider_name == "openai":
        from src.core.openai_provider import OpenAIProvider
        return OpenAIProvider(model_name=os.getenv("DEFAULT_MODEL", "gpt-4o"))
    if provider_name == "google":
        from src.core.gemini_provider import GeminiProvider
        return GeminiProvider(model_name=os.getenv("DEFAULT_MODEL", "gemini-1.5-flash"))
    if provider_name == "local":
        from src.core.local_provider import LocalProvider
        model_path = os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf")
        return LocalProvider(model_path=model_path)
    raise ValueError(f"Provider không hợp lệ: {provider_name}")


def _percentile(values: List[int], p: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * p
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return int(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def _empty_errors() -> Dict[str, int]:
    return {"json_parser_error": 0, "hallucination_error": 0, "timeout_error": 0}


def _run_chatbot(chatbot: ChatbotBaseline, prompt: str) -> Dict[str, Any]:
    start = time.perf_counter()
    result = chatbot.chat_with_metrics(prompt)
    result["latency_ms"] = int((time.perf_counter() - start) * 1000)
    if "errors" not in result:
        result["errors"] = _empty_errors()
    return result


def _run_agent(agent: ReActAgent, prompt: str) -> Dict[str, Any]:
    start = time.perf_counter()
    result = agent.run_with_metrics(prompt)
    result["latency_ms"] = int((time.perf_counter() - start) * 1000)
    return result


def _aggregate(name: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    latencies = [int(r.get("latency_ms", 0) or 0) for r in rows]
    tokens = [int((r.get("usage", {}) or {}).get("total_tokens", 0) or 0) for r in rows]
    loops = [int(r.get("loop_count", 0) or 0) for r in rows]
    ttfts = [int(r.get("ttft_ms", 0) or 0) for r in rows]
    error_sum = _empty_errors()
    for r in rows:
        errors = r.get("errors", {}) or {}
        for k in error_sum:
            error_sum[k] += int(errors.get(k, 0) or 0)
    return {
        "system": name,
        "num_cases": len(rows),
        "latency_ms": {
            "p50": _percentile(latencies, 0.5),
            "p99": _percentile(latencies, 0.99),
            "avg": int(statistics.mean(latencies)) if latencies else 0,
        },
        "ttft_ms_avg": int(statistics.mean(ttfts)) if ttfts else 0,
        "tokens": {
            "avg_total_tokens": int(statistics.mean(tokens)) if tokens else 0,
            "sum_total_tokens": int(sum(tokens)),
        },
        "loop_count": {
            "avg": round(statistics.mean(loops), 2) if loops else 0,
            "max": max(loops) if loops else 0,
        },
        "errors": error_sum,
    }


def _to_markdown(report: Dict[str, Any]) -> str:
    c = report["chatbot"]
    a = report["agent"]
    return (
        "# Evaluation Report: Chatbot vs Agent\n\n"
        f"- Generated at: {report['generated_at']}\n"
        f"- Provider: {report['provider']}\n"
        f"- Model: {report['model']}\n\n"
        "## Aggregate Metrics\n\n"
        "| Metric | Chatbot Baseline | Agent |\n"
        "|---|---:|---:|\n"
        f"| P50 Latency (ms) | {c['latency_ms']['p50']} | {a['latency_ms']['p50']} |\n"
        f"| P99 Latency (ms) | {c['latency_ms']['p99']} | {a['latency_ms']['p99']} |\n"
        f"| Avg TTFT (ms) | {c['ttft_ms_avg']} | {a['ttft_ms_avg']} |\n"
        f"| Avg Tokens / Task | {c['tokens']['avg_total_tokens']} | {a['tokens']['avg_total_tokens']} |\n"
        f"| Total Tokens (5 cases) | {c['tokens']['sum_total_tokens']} | {a['tokens']['sum_total_tokens']} |\n"
        f"| Avg Loop Count | {c['loop_count']['avg']} | {a['loop_count']['avg']} |\n"
        f"| JSON Parser Errors | {c['errors']['json_parser_error']} | {a['errors']['json_parser_error']} |\n"
        f"| Hallucination Errors | {c['errors']['hallucination_error']} | {a['errors']['hallucination_error']} |\n"
        f"| Timeout Errors | {c['errors']['timeout_error']} | {a['errors']['timeout_error']} |\n\n"
        "## Test Cases\n\n"
        + "\n".join([f"{i + 1}. {q}" for i, q in enumerate(report["test_cases"])])
        + "\n"
    )


def main():
    load_dotenv()
    provider = _provider_from_env()
    provider_name = os.getenv("DEFAULT_PROVIDER", "openai")
    model_name = os.getenv("DEFAULT_MODEL", "")
    chatbot = ChatbotBaseline(provider)
    agent = ReActAgent(provider, TRAVEL_TOOLS, max_steps=15, debug=False)

    chatbot_rows: List[Dict[str, Any]] = []
    agent_rows: List[Dict[str, Any]] = []

    for case in TEST_CASES:
        chatbot_rows.append(_run_chatbot(chatbot, case))
        agent_rows.append(_run_agent(agent, case))

    report = {
        "generated_at": datetime.now().isoformat(),
        "provider": provider_name,
        "model": model_name,
        "test_cases": TEST_CASES,
        "chatbot": _aggregate("chatbot", chatbot_rows),
        "agent": _aggregate("agent", agent_rows),
        "chatbot_details": chatbot_rows,
        "agent_details": agent_rows,
    }

    out_dir = Path("report/evaluation_results")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "evaluation_5_cases.json"
    md_path = out_dir / "evaluation_5_cases.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_to_markdown(report), encoding="utf-8")
    print(f"Saved JSON: {json_path}")
    print(f"Saved Markdown: {md_path}")


if __name__ == "__main__":
    main()
