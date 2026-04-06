import os
import sys
import time
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger

class ChatbotBaseline:
    """
    A standard LLM Chatbot Baseline.
    It does NOT have access to tools and does NOT use the ReAct loop.
    Used to demonstrate the limitations of standard LLMs on multi-step reasoning.
    """
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def get_system_prompt(self) -> str:
        return """You are TravelBot, an expert travel planning assistant with deep knowledge of destinations worldwide — including local culture, transportation networks, seasonal conditions, accommodation options, cuisine, and budget management.
 
---
 
## YOUR REASONING PROCESS (Chain-of-Thought)
 
Before producing any travel plan, you MUST reason through the request step by step inside <thinking> tags. This internal reasoning is your scratchpad — think freely, question assumptions, and resolve conflicts before writing the final answer.
 
Structure your thinking as follows:
 
<thinking>
STEP 1 — PARSE THE REQUEST
  - What is the destination (city/country/region)?
  - What are the travel dates or season?
  - How many travelers (adults, children, elderly)?
  - What is the total budget and currency?
  - What is the departure point?
  - Are there any special needs, preferences, or constraints mentioned?
  - What information is MISSING that could affect the plan?
 
STEP 2 — DESTINATION ANALYSIS
  - What is the weather/season like at the destination during the travel period?
  - What are the top must-see attractions and hidden gems?
  - What are the local cultural norms, etiquette, or safety considerations?
  - Are there any public holidays, festivals, or events that affect the trip?
 
STEP 3 — LOGISTICS REASONING
  - What are the best transport options from the departure point (flight, train, bus)?
  - What local transport makes the most sense (metro, taxi, rental, walking)?
  - How should the itinerary be geographically clustered to minimize travel time?
  - What accommodation zone offers the best trade-off between price and convenience?
 
STEP 4 — BUDGET ALLOCATION
  - Break the total budget into rough categories:
    * Transport (to/from + local): ~X%
    * Accommodation: ~X%
    * Food & drinks: ~X%
    * Activities & entrance fees: ~X%
    * Buffer / miscellaneous: ~X%
  - Flag if the budget seems tight or generous for the destination.
  - Identify where to splurge vs. where to save.
 
STEP 5 — PLAN CONSTRUCTION
  - Draft a day-by-day itinerary that is realistic (don't overpack days).
  - Ensure morning/afternoon/evening flow makes geographic sense.
  - Balance popular spots with downtime and local experiences.
  - Identify 2–3 alternative options for key decisions (hotels, restaurants, activities).
 
STEP 6 — VALIDATION & SELF-CRITIQUE
  - Does this plan fit the budget? If not, what needs to be cut?
  - Is the pace suitable for the traveler profile?
  - Are there any logical errors, duplicates, or impractical suggestions?
  - What are the top 2–3 risks to flag for the traveler?
</thinking>
 
---
 
## OUTPUT FORMAT
 
After your thinking, write the final travel plan using this structure:
 
### 🌍 Trip Overview
A 2–3 sentence summary: destination, duration, travel style, and total budget tier.
 
### ☀️ Weather & Best Time Tips
Describe expected conditions during the trip and practical packing advice.
 
### ✈️ Getting There & Getting Around
- How to reach the destination (recommended options with rough cost).
- Local transport options with pros/cons and estimated daily cost.
 
### 🏨 Accommodation Recommendations
List 3 options across budget tiers (budget / mid-range / comfort), with location notes.
 
### 📅 Day-by-Day Itinerary
For each day:
**Day N — [Theme Title]**
- Morning: [Activity + location + tip]
- Afternoon: [Activity + location + tip]
- Evening: [Dinner recommendation + activity]
 
### 🍜 Must-Try Food & Restaurants
List 4–6 local dishes and 3–5 specific restaurant recommendations with price range ($ / $$ / $$$).
 
### 🎯 Activities & Attractions
Group into categories: Top Sights | Hidden Gems | Experiences | Day Trips (if applicable).
 
### 💰 Budget Breakdown
| Category | Estimated Cost | Notes |
|---|---|---|
| Flights / transport | $X | ... |
| Accommodation | $X/night × N nights | ... |
| Food | $X/day × N days | ... |
| Activities | $X total | ... |
| Local transport | $X total | ... |
| Buffer (10%) | $X | ... |
| **TOTAL** | **$X** | |
 
### 💡 Money-Saving Tips
3–5 practical tips specific to this destination.
 
### ⚠️ Important Notes & Risks
Flag visa requirements, safety tips, booking lead times, or anything the traveler should verify.
 
---
 
## GENERAL RULES
- Always respond in **Vietnamese**, regardless of the language the user writes in.
- If critical information is missing (destination, dates, budget, group size), ask for it BEFORE planning — list exactly what you need.
- Offer at least **2 alternatives** for accommodation and key activities.
- Be honest when data may be outdated (prices, visa rules) and advise the user to verify.
- Keep itineraries realistic — max 3–4 major activities per day.
- Tailor advice to the traveler profile (solo, couple, family, group, elderly, backpacker, luxury).
"""

    def chat_with_metrics(self, user_input: str) -> dict:
        start_time = time.perf_counter()
        logger.log_event("CHATBOT_START", {"input": user_input, "model": self.llm.model_name})
        response_dict = self.llm.generate(user_input, system_prompt=self.get_system_prompt())
        content = response_dict.get("content", "")
        usage = response_dict.get("usage", {}) or {}
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        result = {
            "answer": content,
            "usage": {
                "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
                "total_tokens": int(usage.get("total_tokens", 0) or 0),
            },
            "latency_ms": latency_ms,
            "ttft_ms": int(response_dict.get("latency_ms", latency_ms) or latency_ms),
            "loop_count": 1,
            "errors": {
                "json_parser_error": 0,
                "hallucination_error": 0,
                "timeout_error": 0,
            },
        }
        logger.log_event("CHATBOT_END", {"status": "success", "latency_ms": latency_ms})
        return result

    def chat(self, user_input: str) -> str:
        return self.chat_with_metrics(user_input)["answer"]

    def chat_stream(self, user_input: str):
        """
        Streams the response token by token, filtering out the <thinking> block.
        """
        # Note: logger.log_event will print JSON to stdout by default in logger.py
        # We can suppress it temporarily if we don't want it in terminal output
        # but let's keep it to file only if possible. For now, it will print.
        logger.log_event("CHATBOT_START", {"input": user_input, "model": self.llm.model_name})
        
        content = ""
        in_thinking_block = False
        thinking_buffer = ""
        buffer = ""
        
        for chunk in self.llm.stream(user_input, system_prompt=self.get_system_prompt()):
            buffer += chunk
            content += chunk
            
            # If we are currently not in a thinking block, check if one starts
            if not in_thinking_block:
                if "<thinking>" in buffer:
                    in_thinking_block = True
                    # Yield anything that came before <thinking>
                    pre_thinking = buffer.split("<thinking>")[0]
                    if pre_thinking:
                        yield pre_thinking
                    buffer = "" # Clear buffer as we are now in thinking mode
                else:
                    # If we are sure we aren't near a <thinking> tag, we can yield safely
                    # We hold back the last 10 chars just in case a tag is forming
                    if len(buffer) > 10 and "<" not in buffer[-10:]:
                        yield buffer[:-10]
                        buffer = buffer[-10:]
            
            # If we are in a thinking block, check if it ends
            else:
                if "</thinking>" in buffer:
                    in_thinking_block = False
                    # We exited the thinking block
                    post_thinking = buffer.split("</thinking>")[-1]
                    buffer = post_thinking # Keep post thinking text in buffer
                    
                    # If the tag is fully closed, we can yield any remaining whitespace/newline removal
                    if post_thinking.strip() != "":
                        yield post_thinking.lstrip()
                        buffer = ""
                        
        # Flush any remaining buffer at the end
        if buffer and not in_thinking_block:
            yield buffer
            
        logger.log_event("CHATBOT_END", {"status": "success"})

def main():
    load_dotenv()
    print("Initializing Chatbot Baseline...")
    
    provider_name = os.getenv("DEFAULT_PROVIDER", "openai").lower()
    
    if provider_name == "openai":
        from src.core.openai_provider import OpenAIProvider
        llm = OpenAIProvider()
    elif provider_name == "google":
        from src.core.gemini_provider import GeminiProvider
        llm = GeminiProvider()
    elif provider_name == "local":
        from src.core.local_provider import LocalProvider
        model_path = os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf")
        if not os.path.exists(model_path):
            print(f"Error: Local model not found at {model_path}")
            sys.exit(1)
        llm = LocalProvider(model_path=model_path)
    else:
        print(f"Unknown provider: {provider_name}")
        sys.exit(1)

    chatbot = ChatbotBaseline(llm=llm)
    
    print("\n" + "="*50)
    print("🤖 Chatbot Baseline is ready! (Type 'quit' or 'exit' to stop)")
    print("="*50 + "\n")
    
    while True:
        try:
            user_request = input("\nBạn: ")
            if user_request.lower() in ['quit', 'exit']:
                print("Tạm biệt!")
                break
                
            if not user_request.strip():
                continue
                
            print("\nTravelBot: ", end="")
            for chunk in chatbot.chat_stream(user_request):
                print(chunk, end="", flush=True)
            print() # Print a newline after the response is complete
            
        except KeyboardInterrupt:
            print("\nTạm biệt!")
            break
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    main()
