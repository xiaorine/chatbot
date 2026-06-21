# GPM Messenger Chatbot & Control Panel

Hệ thống chatbot tự động phản hồi tin nhắn trên Facebook Messenger thông qua trình duyệt chống phát hiện **GPM Login**, tích hợp các mô hình ngôn ngữ lớn (LLM) và đi kèm giao diện quản trị Web Control Panel trực quan, hiện đại.

---

## ✨ Tính năng nổi bật

- 🖥️ **Giao diện Web Control Panel (Dashboard):**
  - **Bật/Tắt Bot:** Điều khiển khởi động hoặc dừng hoạt động chatbot trực tiếp từ giao diện web bằng một nút bấm.
  - **Cấu hình trực quan:** Quản lý dễ dàng các API Key, cài đặt GPM API Url, Profile ID hay cổng Debug trực tiếp trên web (tự động cập nhật vào `.env` và `settings.yaml`).
  - **Danh sách Whitelist:** Thêm/xóa thủ công danh sách ID luồng (Thread ID) hoặc tên người dùng được phép chatbot phản hồi để tránh Spam.
  - **Lịch sử & Logs:** Xem trực quan danh sách các câu trả lời gần nhất của bot cùng log hoạt động thời gian thực từ terminal.
- 🤖 **Bộ não AI đa dạng (LiteLLM):**
  - Tích hợp linh hoạt các API như Gemini, OpenAI, DeepSeek, Claude,...
  - Hỗ trợ endpoint tùy chỉnh (như XiaomiMiMo API).
  - Tự động chuyển đổi dự phòng (Fallback) sang mô hình khác nếu mô hình chính gặp lỗi hoặc mất kết nối.
- 🛡️ **Giả lập hành vi giống người thật (Anti-Ban):**
  - **Debounce tin nhắn:** Đợi đối phương kết thúc chuỗi tin nhắn liên tiếp (mặc định 10s) mới tiến hành gửi dữ liệu cho AI phản hồi.
  - **Giả lập gõ phím (Human-like typing):** Tự động mô phỏng tốc độ gõ phím theo ký tự và tạo thời gian chờ ngẫu nhiên trước khi bấm gửi.
- 🌐 **Tích hợp sâu GPM Login:**
  - Tự động giải phóng cổng debug và đóng các tiến trình Chromium bị treo của profile cũ trước khi khởi động qua API GPM để tránh lỗi `SingletonLock` hay cổng bận.

---

## 📁 Cấu trúc thư mục dự án

```text
Chatbot/
├── config/
│   ├── settings.yaml         # Cấu hình AI Model, prompt hệ thống và thời gian chờ
│   ├── whitelist.json        # Danh sách tài khoản được phép phản hồi
│   └── sent_messages.json    # Lịch sử ghi nhận các tin nhắn đã trả lời
├── src/
│   ├── static/               # CSS, JS phục vụ giao diện Control Panel
│   ├── templates/            # HTML mẫu giao diện Control Panel
│   ├── browser.py            # Quản lý Playwright kết nối CDP & tương tác DOM Messenger
│   ├── llm_gateway.py        # Gateway định tuyến API qua LiteLLM
│   ├── logic.py              # Xử lý Whitelist và các bộ lọc tin nhắn
│   ├── web_server.py         # Flask Web server quản trị giao diện Control Panel
│   └── main.py               # Vòng lặp chính xử lý tiến trình chatbot
├── test/                     # Các file script chẩn đoán và kiểm thử hệ thống
├── .env.example              # File cấu hình mẫu môi trường
├── requirements.txt          # Danh sách thư viện Python cần thiết
└── start_control_panel.bat   # File khởi chạy nhanh hệ thống bằng 1 click
```

---

## 🛠️ Hướng dẫn cài đặt và sử dụng

### 1. Yêu cầu hệ thống
- Hệ điều hành: Windows
- Đã cài đặt [Python (phiên bản 3.10 trở lên)](https://www.python.org/downloads/)
- Đã cài đặt phần mềm **GPM Login**

### 2. Các bước cài đặt ban đầu
1. Mở Terminal (PowerShell hoặc Command Prompt) trong thư mục dự án.
2. Tạo và kích hoạt môi trường ảo Python (Virtual Environment):
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```
3. Cài đặt các thư viện cần thiết:
   ```powershell
   pip install -r requirements.txt
   playwright install
   ```
4. Đổi tên file `.env.example` thành `.env` và điền các API Key của bạn (hoặc bạn có thể điền chúng sau trực tiếp trên trang quản trị giao diện Web):
   ```powershell
   copy .env.example .env
   ```

### 3. Cách khởi chạy nhanh
Bạn chỉ cần nhấp đúp (Double-click) vào file **`start_control_panel.bat`** ở thư mục gốc của dự án. 
File này sẽ tự động:
1. Khởi chạy Flask Web Server.
2. Tự động mở trình duyệt mặc định truy cập địa chỉ quản lý: **`http://127.0.0.1:5000`**

---

## ⚙️ Hướng dẫn cấu hình hoạt động
- **Nếu chạy trực tiếp trên trình duyệt Messenger đã mở:**
  1. Hãy chắc chắn rằng bạn đã khởi động Profile Messenger trên phần mềm GPM Login trước.
  2. Bật trang Control Panel lên, điền cổng debug (mặc định của GPM là `9222`) vào phần Cấu hình.
  3. Nhấn **START BOT** để bắt đầu.
- **Nếu chạy tự động hóa hoàn toàn qua GPM API:**
  1. Đảm bảo phần mềm GPM Login đang mở ở chế độ nền (mặc định API chạy ở `http://127.0.0.1:9495`).
  2. Copy **Profile ID** của nick cần chạy trong danh sách GPM.
  3. Điền Profile ID vào phần Cấu hình trên Control Panel.
  4. Nhấn **START BOT**. Hệ thống sẽ tự động tắt Chromium cũ (nếu bị kẹt), bật profile mới lên và bắt đầu quét tin nhắn.
