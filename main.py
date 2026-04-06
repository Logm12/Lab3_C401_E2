import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agent.agent import ReActAgent
from src.tools.travel_tools import TRAVEL_TOOLS

def _is_truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

def main():
    load_dotenv()

    provider_name = os.getenv("DEFAULT_PROVIDER", "openai").lower()
    if provider_name == "openai":
        from src.core.openai_provider import OpenAIProvider
        llm = OpenAIProvider(model_name=os.getenv("DEFAULT_MODEL", "gpt-5.4-mini"))
    elif provider_name == "google":
        from src.core.gemini_provider import GeminiProvider
        llm = GeminiProvider(model_name=os.getenv("DEFAULT_MODEL", "gemini-1.5-flash"))
    elif provider_name == "local":
        from src.core.local_provider import LocalProvider
        model_path = os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf")
        if not os.path.exists(model_path):
            print(f"Không tìm thấy local model tại: {model_path}")
            return
        llm = LocalProvider(model_path=model_path)
    else:
        print(f"Provider không hợp lệ: {provider_name}")
        return

    debug_mode = _is_truthy(os.getenv("AGENT_DEBUG", "false"))
    print(f"Khởi động Agent với provider: {provider_name}")
    print(f"Debug mode: {'ON' if debug_mode else 'OFF'}")
    agent = ReActAgent(llm=llm, tools=TRAVEL_TOOLS, debug=debug_mode)

    print("Nhập câu hỏi (gõ 'exit' để thoát, '/debug on' hoặc '/debug off' để bật/tắt debug)")
    while True:
        try:
            user_request = input("\nBạn: ").strip()
            if not user_request:
                continue
            if user_request.lower() in {"exit", "quit"}:
                print("Tạm biệt!")
                break
            if user_request.lower() == "/debug on":
                debug_mode = True
                agent = ReActAgent(llm=llm, tools=TRAVEL_TOOLS, debug=debug_mode)
                print("Đã bật debug.")
                continue
            if user_request.lower() == "/debug off":
                debug_mode = False
                agent = ReActAgent(llm=llm, tools=TRAVEL_TOOLS, debug=debug_mode)
                print("Đã tắt debug.")
                continue
            result = agent.run(user_request)
            print(f"\nAgent v1: {result}")
        except KeyboardInterrupt:
            print("\nTạm biệt!")
            break
        except Exception as error:
            print(f"\nLỗi: {error}")

if __name__ == "__main__":
    main()
