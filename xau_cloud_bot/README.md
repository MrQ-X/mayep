# XAU/USD Telegram Signal Bot – Bản Cloud

Bot chạy 24/7 trên cloud, **máy bạn không cần cài gì**.

## Cách deploy nhanh nhất (Railway – khuyên dùng)

### Bước 1: Chuẩn bị Token
1. Tạo bot Telegram qua [@BotFather](https://t.me/BotFather) → lấy **token**
2. Lấy **Chat ID** qua [@userinfobot](https://t.me/userinfobot)

### Bước 2: Deploy lên Railway
1. Vào [https://railway.app](https://railway.app) → đăng nhập bằng GitHub
2. Bấm **New Project** → **Deploy from GitHub repo**  
   (hoặc **Empty Project** rồi upload folder này)
3. Sau khi project được tạo:
   - Vào tab **Variables**
   - Thêm 2 biến:
     ```
     TELEGRAM_BOT_TOKEN = (token của bạn)
     TELEGRAM_CHAT_ID   = (chat id của bạn)
     ```
4. Vào tab **Settings** → **Deploy** → Start Command để:
   ```
   python bot.py
   ```
5. Bấm Deploy. Xong!

Bot sẽ tự chạy nền và gửi tín hiệu về Telegram của bạn.

---

## Cách khác: Render.com

1. Vào [render.com](https://render.com) → New → Background Worker
2. Kết nối GitHub hoặc upload code
3. Build Command: để trống
4. Start Command: `python bot.py`
5. Thêm Environment Variables giống như trên
6. Deploy

---

## Test nhanh trước khi deploy

Nếu bạn có Python tạm thời:
```bash
python bot.py --once
```

---

## Lưu ý

- Free tier của Railway/Render có thể ngủ nếu không có traffic, nhưng với Background Worker thường chạy ổn.
- Token và Chat ID nên để ở **Variables** (không hard-code trong code) để an toàn.
- Bot chỉ gửi gợi ý tham khảo, không phải lời khuyên đầu tư.
