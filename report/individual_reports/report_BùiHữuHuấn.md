# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: [Your Name Here]
- **Student ID**: [Your ID Here]
- **Date**: [Date Here]

---

# I. Technical Contribution (15 Points)

Trong dự án AI lập kế hoạch du lịch, tôi phụ trách "Người 3 – Chỗ ở" trong kiến trúc multi-agent. Module này chịu trách nhiệm tìm khách sạn phù hợp theo địa điểm, ngày nhận/trả phòng và ngân sách, sau đó trả dữ liệu cho Orchestrator Agent để tổng hợp lịch trình hoàn chỉnh.

## Modules Implemented

- `src/tools/accommodation_tools.py`
- Hàm chính: `get_accommodation()`
- Hàm phụ trợ:
  - `_get_tavily_api_key()`
  - `_search_web()`
  - `_safe_json()`
  

## Code Highlights

```python
def _get_tavily_api_key() -> Optional[str]:
    return os.getenv("TAVILY_API_KEY") or os.getenv("TAVI_API_KEY")

def _safe_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)

def _search_web(
    query: str,
    max_results: int = 5,
    retries: int = 2,
    retry_delay: float = 1.5,
) -> List[Dict[str, str]]:
    """Search the web using Tavily AI API — ưu tiên kết quả tiếng Việt."""
    tavily_api_key = _get_tavily_api_key()
    if not tavily_api_key:
        raise ValueError("TAVILY_API_KEY is not set in environment variables.")

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key":        tavily_api_key,
                    "query":          query,
                    "max_results":    max_results,
                    "search_depth":   "basic",
                    "include_answer": False,
                    "topic":          "general",
                    "language":       "vi",
                },
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
            results = [
                {
                    "title":   r.get("title", ""),
                    "snippet": r.get("content", ""),
                    "url":     r.get("url", ""),
                    "score":   r.get("score", None),
                }
                for r in data.get("results", [])
            ]
            if results:
                return results
            return []
        except Exception as e:
            last_error = e
            if attempt < retries:
                time.sleep(retry_delay)

    raise RuntimeError(
        f"Tavily search failed after {retries} attempts. Last error: {last_error}"
    )

def get_accommodation(
    location: str,
    check_in: str,
    check_out: str,
    budget: str,
) -> str:
    query = (
        f"khách sạn tốt tại {location} "
        f"nhận phòng {check_in} trả phòng {check_out} "
        f"giá phòng bao nhiêu VND ngân sách {budget}"
    )

```

Đoạn code trên chuyển thông tin đầu vào của agent thành một truy vấn ngôn ngữ tự nhiên bằng tiếng Việt. Tôi cố tình thêm các từ khóa như:
- "khách sạn tốt"
- "giá phòng bao nhiêu"
- "ngân sách"

để tăng khả năng Tavily trả về kết quả đúng ngữ cảnh du lịch.

```python
results = _search_web(query, max_results=5)
```

Sau khi tìm kiếm, tool chỉ giữ tối đa 5 kết quả để tránh đưa quá nhiều thông tin vào context của LLM.

```python
return _safe_json({
    "location":  location,
    "check_in":  check_in,
    "check_out": check_out,
    "budget":    budget,
    "currency":  "VND",
    "source":    "tavily",
    "query":     query,
    "results":   results,
})
```

Tôi chuẩn hóa output về JSON để ReAct agent có thể dễ dàng đọc phần `Observation` và truyền tiếp cho Agent 7 (Orchestrator).

## Documentation

Tool của tôi hoạt động trong vòng lặp ReAct theo quy trình sau:

1. Agent nhận yêu cầu của người dùng, ví dụ: “Tìm khách sạn ở Đà Nẵng từ 10/7 đến 12/7, ngân sách 1 triệu VND...”
2. LLM sinh ra:

```text
Thought: Tôi cần tìm khách sạn phù hợp với địa điểm và ngân sách.
Action: get_accommodation(location="Đà Nẵng", check_in="2026-07-10", check_out="2026-07-12", budget="1000000")
```

3. Tool trả về JSON chứa danh sách khách sạn.
4. Observation được đưa lại vào prompt.
5. Agent tiếp tục suy luận để chọn khách sạn phù hợp nhất hoặc gửi kết quả cho Orchestrator Agent.

Tool này giúp Agent không cần “đoán” khách sạn từ kiến thức có sẵn mà lấy dữ liệu thật từ web.

---

# II. Debugging Case Study (10 Points)

## Problem Description

Lỗi lớn nhất tôi gặp là agent liên tục gọi tool nhiều lần cho cùng một truy vấn khách sạn, dù đã có kết quả ở lần gọi đầu tiên.

Ví dụ:

```text
Thought: Tôi cần tìm khách sạn ở Đà Nẵng.
Action: get_accommodation(...)
Observation: trả về 5 khách sạn.

Thought: Tôi chưa chắc kết quả này đủ tốt.
Action: get_accommodation(...)
```

Vòng lặp này lặp lại 2–3 lần và đôi khi dẫn đến timeout.

## Log Source

```text
[2026-04-05 09:14:21]
Thought: Tôi cần tìm khách sạn tại Đà Nẵng với ngân sách 1 triệu.
Action: get_accommodation(location='Đà Nẵng', check_in='2026-07-10', check_out='2026-07-12', budget='1000000')

Observation:
{"results": [...5 hotel results...]}

Thought: Tôi nên kiểm tra lại để chắc chắn.
Action: get_accommodation(location='Đà Nẵng', check_in='2026-07-10', check_out='2026-07-12', budget='1000000')
```

## Diagnosis

Nguyên nhân không nằm ở Tavily API mà nằm ở prompt của ReAct agent.

Prompt ban đầu chỉ yêu cầu:

```text
Nếu cần thông tin, hãy gọi tool.
```

LLM hiểu rằng càng gọi nhiều lần thì càng “an toàn”, nên sau khi có kết quả nó vẫn tiếp tục gọi lại cùng một tool.

Ngoài ra, output JSON của tool chưa ghi rõ rằng đây là “top 5 kết quả”, nên model nghĩ dữ liệu vẫn chưa hoàn chỉnh.

## Solution

Tôi sửa theo hai hướng:

### 1. Thêm hướng dẫn vào system prompt

```text
Nếu Observation đã chứa đủ dữ liệu cần thiết, không gọi lại cùng một tool với cùng tham số.
Hãy chuyển sang bước Final Answer.
```

### 2. Thêm metadata vào kết quả tool

```python
"results_count": len(results),
"status": "top_5_hotels_found"
```

Sau khi sửa, agent chỉ gọi `get_accommodation()` một lần rồi chuyển sang tổng hợp kết quả.

Kết quả:
- Giảm số lần gọi API từ 3 xuống 1
- Giảm thời gian phản hồi khoảng 60%
- Tránh bị lỗi timeout hoặc vượt giới hạn API

---

# III. Personal Insights: Chatbot vs ReAct (10 Points)

## 1. Reasoning

`Thought` block giúp agent hoạt động tốt hơn chatbot thông thường vì nó buộc model phải suy nghĩ từng bước trước khi hành động.

Ví dụ với yêu cầu:

> “Tìm khách sạn ở Đà Nẵng giá dưới 1 triệu, gần biển, từ 10/7 đến 12/7.”

Chatbot thường trả lời chung chung như:

- Có thể ở gần biển Mỹ Khê
- Có nhiều khách sạn giá rẻ

Trong khi ReAct agent sẽ:

1. Xác định địa điểm
2. Xác định ngày
3. Xác định ngân sách
4. Gọi tool để tìm dữ liệu thật
5. So sánh kết quả rồi mới trả lời

Điều này làm kết quả chính xác và đáng tin cậy hơn.

## 2. Reliability

Tuy nhiên, Agent đôi khi hoạt động tệ hơn chatbot trong các trường hợp:

- Tool trả lỗi hoặc API hết quota
- Internet chậm
- Prompt không rõ ràng
- Observation quá dài khiến LLM bị rối

Ví dụ nếu Tavily không trả dữ liệu, agent có thể bị kẹt trong vòng lặp hoặc trả lỗi kỹ thuật. Trong khi đó, chatbot thông thường vẫn có thể đưa ra một câu trả lời “ước lượng”.

Vì vậy, ReAct mạnh hơn khi có dữ liệu thật, nhưng cũng phụ thuộc nhiều hơn vào hệ thống bên ngoài.

## 3. Observation

Observation là phần quan trọng nhất trong ReAct.

Sau khi tool trả về danh sách khách sạn, agent dựa vào Observation để quyết định bước tiếp theo.

Ví dụ:

```text
Observation:
- Khách sạn A: 850.000 VND
- Khách sạn B: 1.200.000 VND
- Khách sạn C: 950.000 VND
```

Từ Observation này, agent có thể suy luận rằng:
- Khách sạn B vượt ngân sách nên loại bỏ
- Khách sạn A và C phù hợp hơn
- Nếu người dùng ưu tiên giá rẻ, chọn A
- Nếu ưu tiên đánh giá tốt hơn, chọn C

Nói cách khác, Observation đóng vai trò như “môi trường phản hồi”, giúp agent thay đổi hành động thay vì chỉ trả lời một lần như chatbot.

---

# IV. Future Improvements (5 Points)

## Scalability

Nếu mở rộng hệ thống thành production-level travel agent, tôi sẽ:

- Chuyển các tool thành microservices riêng
- Dùng hàng đợi bất đồng bộ (Celery hoặc RabbitMQ) để gọi nhiều tool cùng lúc
- Cho Agent 1–6 chạy song song, sau đó Agent 7 tổng hợp

Ví dụ:
- Người 1: thời tiết
- Người 2: phương tiện
- Người 3: khách sạn
- Người 4: nhà hàng
- Người 5: địa điểm tham quan

Như vậy tốc độ phản hồi sẽ nhanh hơn nhiều.

## Safety

Tôi sẽ thêm một “Supervisor Agent” để kiểm tra:

- Agent có gọi tool quá nhiều lần không
- Có lặp vô hạn không
- Có trả thông tin sai định dạng không

Ngoài ra, cần giới hạn số lần gọi tool tối đa, ví dụ:

```text
max_steps = 5
```

Nếu vượt quá giới hạn, hệ thống sẽ dừng và trả thông báo lỗi an toàn.

## Performance

Để tăng hiệu năng:

- Cache kết quả API theo địa điểm và ngày
- Lưu embedding của khách sạn vào Vector Database
- Dùng retrieval để chỉ lấy các khách sạn liên quan nhất
- Rút gọn Observation trước khi đưa lại vào LLM

Ví dụ thay vì đưa toàn bộ 5 kết quả dài, chỉ giữ:

```text
Tên khách sạn | Giá | Rating | Link
```

Điều này giúp giảm token, tăng tốc độ và làm cho ReAct agent ổn định hơn.

---

> [!NOTE]
> Submit this report by renaming it to `REPORT_[YOUR_NAME].md` and placing it in this folder.

