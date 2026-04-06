# Lab 3: Chatbot vs ReAct Agent (Industry Edition)

Chào mừng bạn đến với Lab 3! Dự án này tập trung vào việc xây dựng một **ReAct Agent** theo kiến trúc Dual-Agent (có tích hợp công cụ gọi API thực tế) và so sánh nó với một Chatbot LLM cơ bản.

Hệ thống được thiết kế theo chuẩn **Production-Grade** với Telemetry (ghi log chi tiết), đo lường Metrics (Latency, Token, TTFT) và kiến trúc Agent chịu lỗi tốt (Error Handling).

---

## 🚀 Hướng Dẫn Cài Đặt

### 1. Cài đặt Môi trường & Thư viện
Bạn cần Python 3.10+ để chạy dự án. Hãy cài đặt các thư viện cần thiết:
```bash
pip install -r requirements.txt
```

### 2. Cấu hình Biến môi trường (`.env`)
Copy file `.env.example` thành `.env` (hoặc tạo file `.env` mới ở thư mục gốc) và điền các API Key của bạn.
Dự án này được tối ưu tốt nhất cho **OpenAI (GPT-4o)** và công cụ tìm kiếm **Tavily**.

Mẫu file `.env` chuẩn để chạy:
```env
# Lựa chọn LLM Provider và Model
DEFAULT_PROVIDER=openai
DEFAULT_MODEL=gpt-4o

# API Keys
OPENAI_API_KEY=sk-proj-your-openai-api-key-here
TAVILY_API_KEY=tvly-your-tavily-api-key-here

# Tùy chọn Debug (bật 'true' để in chi tiết quá trình Agent suy luận)
AGENT_DEBUG=false
```
*Lưu ý: Bạn bắt buộc phải có `TAVILY_API_KEY` (tạo miễn phí tại tavily.com) để Agent có thể tìm kiếm giá vé và khách sạn thực tế.*

---

## 🎮 Hướng Dẫn Sử Dụng

### 1. Chạy CLI Tương tác (Terminal)
Để chat trực tiếp với Agent và yêu cầu lên lịch trình du lịch, hãy chạy file `main.py`:
```bash
python3 main.py
```
**Cách sử dụng:**
- Nhập câu hỏi của bạn (VD: *Tôi muốn đi Đà Nẵng 3 ngày 2 đêm từ Hà Nội*).
- Gõ `/debug on` nếu bạn muốn xem chi tiết luồng "Thought - Action - Observation" của Agent dưới nền.
- Gõ `exit` để thoát.

### 2. Chạy Giao diện Web (UI)
Dự án có đi kèm một giao diện Web (Next.js) và Backend API (FastAPI) hỗ trợ Streaming.
1. **Khởi động Backend Python:**
   ```bash
   python3 -m uvicorn python_ai_api:app --host 0.0.0.0 --port 8001
   ```
---

## 📊 Hướng Dẫn Đánh Giá (Evaluation)

Hệ thống cung cấp một script đánh giá tự động (`test_evaluate_systems.py`) để chạy 5 test cases mặc định trên cả Chatbot Baseline và Agent v2. Script này sẽ đo đạc Token, Latency, Số vòng lặp và xuất ra báo cáo.

Để chạy script đánh giá, sử dụng lệnh:
```bash
python3 tests/test_evaluate_systems.py
```
**Kết quả:** 
Sau khi chạy xong, kết quả sẽ được lưu vào thư mục `report/evaluation_results/` dưới dạng file `.json` và `.md`.

---

## 📁 Cấu Trúc Thư Mục Chính

- `main.py`: File chạy chính giao diện Terminal.
- `python_ai_api.py`: Backend FastAPI (SSE) kết nối với Web.
- `src/agent/`: Chứa logic cốt lõi của ReAct Agent (Dual-Agent architecture) và System Prompts.
- `src/tools/`: Chứa các Tools gọi API bên ngoài (Weather, Transport, Accommodation, v.v.).
- `src/telemetry/`: Module ghi log theo chuẩn công nghiệp ra thư mục `logs/`.
- `tests/`: Chứa các script test, bao gồm `test_evaluate_systems.py` dùng để benchmark hệ thống.
- `report/`: Nơi lưu trữ báo cáo nhóm, báo cáo cá nhân và kết quả benchmark.
