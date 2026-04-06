import ast
import json
import re
import time
from datetime import datetime, date as date_type
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.agent.prompts import TOOL_CALLING_AGENT_PROMPT, RESPONSE_SYNTHESIS_AGENT_PROMPT


class ToolCallingAgent:
    def __init__(
        self,
        llm: LLMProvider,
        tools: List[Dict[str, Any]],
        max_steps: int = 15,
        debug: bool = False,
        debug_printer: Optional[Callable[[str], None]] = None,
    ):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.debug = debug
        self.debug_printer = debug_printer or print

    def _debug(self, message: str) -> None:
        if self.debug:
            self.debug_printer(message)

    def get_system_prompt(self, current_dt: Optional[datetime] = None) -> str:
        now = current_dt or datetime.now()
        date_str = now.strftime("%A, %d %B %Y")
        time_str = now.strftime("%H:%M")

        return f"{TOOL_CALLING_AGENT_PROMPT}\nCurrent datetime: {date_str}, {time_str} (local time)\n"

    def collect(self, user_input: str, current_dt: Optional[datetime] = None) -> Dict[str, Any]:
        system_prompt = self.get_system_prompt(current_dt=current_dt or datetime.now())

        current_prompt = f"User Request: {user_input}\n"
        steps = 0
        invalid_turns = 0
        done_without_tool_turns = 0
        tool_results: List[Dict[str, Any]] = []
        llm_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        llm_latency_ms = 0
        first_llm_latency_ms: Optional[int] = None

        while steps < self.max_steps:
            logger.log_event("AGENT_STEP", {"step": steps + 1, "prompt_length": len(current_prompt)})
            result_dict = self.llm.generate(current_prompt, system_prompt=system_prompt)
            result = result_dict.get("content", "").strip()
            usage = result_dict.get("usage", {}) or {}
            llm_usage["prompt_tokens"] += int(usage.get("prompt_tokens", 0) or 0)
            llm_usage["completion_tokens"] += int(usage.get("completion_tokens", 0) or 0)
            llm_usage["total_tokens"] += int(usage.get("total_tokens", 0) or 0)
            current_latency = int(result_dict.get("latency_ms", 0) or 0)
            llm_latency_ms += current_latency
            if first_llm_latency_ms is None and current_latency > 0:
                first_llm_latency_ms = current_latency

            tool_name, args_str = self._extract_action(result)
            if tool_name is not None:
                invalid_turns = 0
                self._debug(f"[DEBUG][TOOL_CALL] {tool_name} args={args_str if args_str else '{}'}")
                observation = self._execute_tool(tool_name, args_str)
                self._debug(f"[DEBUG][TOOL_RESULT] {tool_name}: {observation}")
                tool_results.append({"tool": tool_name, "args": args_str, "observation": observation})
                current_prompt += f"{result}\nObservation: {observation}\n"
                steps += 1
                continue

            if re.search(r"\bDONE\b", result, re.IGNORECASE):
                if len(tool_results) == 0:
                    done_without_tool_turns += 1
                    if done_without_tool_turns <= 2:
                        current_prompt += (
                            "Observation: You returned DONE without any tool call. "
                            "If destination exists, call at least one relevant tool first.\n"
                        )
                        steps += 1
                        continue
                self._debug(f"[DEBUG][COLLECT_STATUS] done after {steps + 1} step(s)")
                return {
                    "tool_results": tool_results,
                    "steps": steps + 1,
                    "status": "done",
                    "llm_usage": llm_usage,
                    "llm_latency_ms": llm_latency_ms,
                    "ttft_ms": first_llm_latency_ms or llm_latency_ms,
                }

            invalid_turns += 1
            if invalid_turns >= 3:
                self._debug(f"[DEBUG][COLLECT_STATUS] fallback after {steps + 1} step(s)")
                return {
                    "tool_results": tool_results,
                    "steps": steps + 1,
                    "status": "fallback",
                    "llm_usage": llm_usage,
                    "llm_latency_ms": llm_latency_ms,
                    "ttft_ms": first_llm_latency_ms or llm_latency_ms,
                }
            current_prompt += (
                f"{result}\nObservation: Invalid format. Return Action: tool_name({{\"key\":\"value\"}}) or DONE.\n"
            )
            steps += 1

        self._debug(f"[DEBUG][COLLECT_STATUS] timeout after {steps} step(s)")
        return {
            "tool_results": tool_results,
            "steps": steps,
            "status": "timeout",
            "llm_usage": llm_usage,
            "llm_latency_ms": llm_latency_ms,
            "ttft_ms": first_llm_latency_ms or llm_latency_ms,
        }

    def _extract_action(self, llm_output: str) -> Tuple[Optional[str], str]:
        action_match = re.search(r"Action:\s*([a-zA-Z0-9_]+)\s*\(", llm_output)
        if not action_match:
            return None, ""

        tool_name = action_match.group(1).strip()
        paren_start = action_match.end() - 1

        rest = llm_output[paren_start:]
        if re.match(r"\(\s*\)", rest):
            return tool_name, ""

        brace_start = llm_output.find("{", paren_start)
        if brace_start == -1:
            return tool_name, ""

        args_str = self._extract_balanced_braces(llm_output, brace_start)
        return tool_name, args_str

    def _extract_balanced_braces(self, text: str, start: int) -> str:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        return ""

    def _parse_args(self, args_str: str) -> Dict[str, Any]:
        if not args_str:
            return {}
        try:
            parsed = json.loads(args_str)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        try:
            normalized = (
                args_str
                .replace(": true",  ": True")
                .replace(": false", ": False")
                .replace(": null",  ": None")
            )
            parsed = ast.literal_eval(normalized)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        raise ValueError(f"Cannot parse action args: {args_str}")

    def _execute_tool(self, tool_name: str, args_str: str) -> str:
        logger.log_event("TOOL_CALL", {"tool": tool_name, "args": args_str})
        for tool in self.tools:
            if tool["name"] == tool_name:
                try:
                    kwargs = self._parse_args(args_str)
                    result = tool["func"](**kwargs)
                    logger.log_event("TOOL_RESULT", {"tool": tool_name, "result_length": len(str(result))})
                    return str(result)
                except Exception as e:
                    error_msg = f"Error executing tool '{tool_name}': {str(e)}"
                    logger.log_event("TOOL_ERROR", {"tool": tool_name, "error": error_msg})
                    return error_msg

        error_msg = f"Tool '{tool_name}' not found. Available: {[t['name'] for t in self.tools]}"
        logger.log_event("TOOL_ERROR", {"error": error_msg})
        return error_msg


class ResponseSynthesisAgent:
    def __init__(self, llm: LLMProvider):
        self.llm = llm
        self._system_prompt = RESPONSE_SYNTHESIS_AGENT_PROMPT

    def synthesize(self, user_input: str, collected: Dict[str, Any]) -> str:
        return self.synthesize_with_metrics(user_input, collected)["answer"]

    def synthesize_with_metrics(self, user_input: str, collected: Dict[str, Any]) -> Dict[str, Any]:
        tool_results_json = json.dumps(collected.get("tool_results", []), ensure_ascii=False)
        prompt = (
            f"Yêu cầu người dùng:\n{user_input}\n\n"
            f"Kết quả thu thập từ ToolCallingAgent (JSON):\n{tool_results_json}\n\n"
            "Hãy tổng hợp thành lịch trình/đề xuất hoàn chỉnh cho người dùng."
        )
        result_dict = self.llm.generate(prompt, system_prompt=self._system_prompt)
        usage = result_dict.get("usage", {}) or {}
        return {
            "answer": result_dict.get("content", "").strip(),
            "usage": {
                "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
                "total_tokens": int(usage.get("total_tokens", 0) or 0),
            },
            "latency_ms": int(result_dict.get("latency_ms", 0) or 0),
        }


class ReActAgent:
    def __init__(
        self,
        llm: LLMProvider,
        tools: List[Dict[str, Any]],
        max_steps: int = 15,
        debug: bool = False,
        debug_printer: Optional[Callable[[str], None]] = None,
    ):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.debug = debug
        self.debug_printer = debug_printer or print
        self.collector = ToolCallingAgent(
            llm=llm,
            tools=tools,
            max_steps=max_steps,
            debug=debug,
            debug_printer=self.debug_printer,
        )
        self.synthesizer = ResponseSynthesisAgent(llm=llm)

    def _debug(self, message: str) -> None:
        if self.debug:
            self.debug_printer(message)

    @staticmethod
    def _parse_date(date_str: str) -> Optional[date_type]:
        for pattern in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(date_str, pattern).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _extract_dates_from_text(text: str) -> List[str]:
        return re.findall(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}-\d{2}-\d{2})\b", text)

    def _validate_dates(self, user_input: str) -> Tuple[bool, str]:
        today = date_type.today()
        date_strs = self._extract_dates_from_text(user_input)
        if not date_strs:
            return True, ""
        warnings = []
        for ds in date_strs:
            parsed = self._parse_date(ds)
            if parsed is None:
                warnings.append(f"'{ds}' không parse được ngày hợp lệ.")
                continue
            delta = (parsed - today).days
            if delta > 365:
                warnings.append(f"'{ds}' quá xa hiện tại (> 365 ngày), dữ liệu có thể chưa sẵn sàng.")
        if warnings:
            return False, "Date issue(s):\n" + "\n".join(f"- {w}" for w in warnings)
        return True, ""

    def run(self, user_input: str) -> str:
        return self.run_with_metrics(user_input)["answer"]

    def run_with_metrics(self, user_input: str) -> Dict[str, Any]:
        wall_start = time.perf_counter()
        logger.log_event("AGENT_START", {"input": user_input, "model": self.llm.model_name})
        is_valid, warning = self._validate_dates(user_input)
        if not is_valid:
            logger.log_event("AGENT_DATE_ERROR", {"warning": warning})
            return {
                "answer": warning,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "latency_ms": int((time.perf_counter() - wall_start) * 1000),
                "ttft_ms": 0,
                "loop_count": 0,
                "errors": {"json_parser_error": 0, "hallucination_error": 0, "timeout_error": 0},
                "collector_status": "date_error",
            }

        collected = self.collector.collect(user_input)
        self._debug(
            f"[DEBUG][COLLECTED] status={collected.get('status')} steps={collected.get('steps')} tools={len(collected.get('tool_results', []))}"
        )
        if len(collected.get("tool_results", [])) == 0:
            answer = "Tool agent chưa lấy được dữ liệu từ web. Vui lòng cung cấp thêm thông tin cụ thể (ngày đi, ngân sách, ưu tiên phương tiện) hoặc thử lại câu hỏi chi tiết hơn."
            return {
                "answer": answer,
                "usage": collected.get("llm_usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
                "latency_ms": int((time.perf_counter() - wall_start) * 1000),
                "ttft_ms": int(collected.get("ttft_ms", 0) or 0),
                "loop_count": int(collected.get("steps", 0) or 0),
                "errors": {"json_parser_error": 0, "hallucination_error": 0, "timeout_error": 0},
                "collector_status": collected.get("status", "unknown"),
            }
        synthesis = self.synthesizer.synthesize_with_metrics(user_input, collected)
        answer = synthesis["answer"]
        self._debug(f"[DEBUG][FINAL_ANSWER] {answer}")
        logger.log_event("AGENT_END", {"status": "success", "collected_steps": collected.get("steps", 0)})
        tool_results = collected.get("tool_results", [])
        json_errors = sum(1 for item in tool_results if "Cannot parse action args" in str(item.get("observation", "")))
        hallucination_errors = sum(1 for item in tool_results if "not found" in str(item.get("observation", "")).lower())
        timeout_error = 1 if collected.get("status") == "timeout" else 0
        collected_usage = collected.get("llm_usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
        usage = {
            "prompt_tokens": int(collected_usage.get("prompt_tokens", 0) or 0) + int(synthesis["usage"].get("prompt_tokens", 0) or 0),
            "completion_tokens": int(collected_usage.get("completion_tokens", 0) or 0) + int(synthesis["usage"].get("completion_tokens", 0) or 0),
            "total_tokens": int(collected_usage.get("total_tokens", 0) or 0) + int(synthesis["usage"].get("total_tokens", 0) or 0),
        }
        return {
            "answer": answer,
            "usage": usage,
            "latency_ms": int((time.perf_counter() - wall_start) * 1000),
            "ttft_ms": int(collected.get("ttft_ms", 0) or 0),
            "loop_count": int(collected.get("steps", 0) or 0),
            "errors": {
                "json_parser_error": json_errors,
                "hallucination_error": hallucination_errors,
                "timeout_error": timeout_error,
            },
            "collector_status": collected.get("status", "unknown"),
        }
