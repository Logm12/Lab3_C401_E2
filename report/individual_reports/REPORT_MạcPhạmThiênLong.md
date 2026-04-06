# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: [Your Name Here]
- **Student ID**: [Your ID Here]
- **Date**: April 6, 2026

---

## I. Technical Contribution (15 Points)

My specific contribution to the codebase involved implementing the weather forecasting capability for the travel agent. Travel planning requires climate awareness, and providing the LLM with location-specific data significantly improves its itinerary recommendations.

- **Modules Implemented**: `src/tools/travel_tools.py`
- **Code Highlights**:
  I integrated two APIs to construct the `get_weather` tool. The tool utilizes the Nominatim API to map a location string to geographic coordinates, and subsequently fetches the weather from Open-Meteo. I also implemented a temporal validation layer to handle API constraints:

  ```python
  forecast_date     = _normalize_date(date)
  forecast_date_obj = datetime.strptime(forecast_date, "%Y-%m-%d").date()
  delta             = (forecast_date_obj - date_type.today()).days

  if delta < 0 or delta > 16:
      return _safe_json({
          "error": (
              f"Date {forecast_date} is out of forecasting range. "
              f"Open-Meteo only supports forecasting from 0 to 16 days from today."
          )
      })
  ```
- **Documentation**: The `get_weather` tool exposes weather tracking capabilities to the ReAct loop. When a user input requires weather data, the agent constructs a `Thought` recognizing this dependency, issues an `Action` providing the target location and date, and receives a JSON string back as an `Observation` containing the forecast context. This grounds the LLM generation on actual data rather than hallucinated responses.
---

## II. Debugging Case Study (10 Points)

- **Problem Description**: The agent encountered fatal failures when requesting weather forecasts far in the future. The Open-Meteo API enforces a strict 16-day limit from the current date.
- **Log Source**: `Observation: {"error": "Lỗi Weather API: HTTP Error 400: Bad Request"}`
  Following this log, the agent would either enter an infinite loop attempting the same call or fail out to a hallucinated answer.
- **Diagnosis**: The LLM lacked implicit knowledge of the tool's 16-day constraint and issued valid but unresolvable dates. The primitive tool implementation passed HTTP errors directly to the agent without semantic descriptions, causing confusion.
- **Solution**: I implemented an explicit date boundary check before executing API requests. By calculating the difference between the target date and `date_type.today()`, requests falling outside the `0 <= delta <= 16` range are intercepted, returning a clear error dictionary back to the ReAct `Observation` layer. This allows the LLM to successfully process the constraint and appropriately inform the user.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

1.  **Reasoning**: The `Thought` mechanism fundamentally transforms the AI from a text generator into a logic orchestrator. When tasked with providing details for a trip, a simple chatbot generates a statistically plausible response immediately. The ReAct agent identifies its knowledge gaps, delays final response framing, and actively mitigates those gaps by retrieving real-world data first.
2.  **Reliability**: The ReAct agent exhibited greater fragility than the Chatbot during execution. If an API request timed out or returned unexpected JSON structures, the rigid `Thought-Action-Observation` cycle frequently degraded or stalled. In such scenarios, the baseline Chatbot provided smoother conversational continuity.
3.  **Observation**: Feedback from the environment acts as a crucial grounding mechanism. When the agent receives a descriptive constraint error as an `Observation`, it adapts its logical flow dynamically, resulting in an honest final assessment rather than generating fabricated data.

---

## IV. Future Improvements (5 Points)

- **Scalability**: Executing discrete HTTP calls per agent request is inefficient. I propose implementing a caching layer (e.g., Redis) to store weather forecast data for geographically clustered search queries over short timeframes (e.g., 2 hours). This reduces external API load and limits latency.
- **Safety**: Introduce a secondary, lower-latency parsing model acting as an initial router. This system could sanitize geographic inputs, normalize dates, and catch edge queries before they enter the primary, more expensive ReAct reasoning pipeline.
- **Performance**: As the system scales to include dozens of tools (flights, currency, translations), injecting the complete tool schema into every system prompt becomes an excessive token burden. We should implement Semantic Tool Retrieval, embedding the tool definitions and dynamically pulling only relevant tools based on user context.
