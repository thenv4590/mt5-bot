# Hướng dẫn sử dụng — MT5 TradingView Webhook Bot

## 0. Đã kiểm tra chạy được chưa?

Đã kiểm tra trên máy hiện tại (Windows):

- Cài được package `MetaTrader5` (bản `5.0.6147`) qua `pip install -r requirements.txt`.
- `app.main:app` import thành công, không lỗi cú pháp/thiếu module.
- Chạy `uvicorn app.main:app` khởi động bình thường, `GET /health` trả `{"status":"ok"}`.
- Gọi `POST /api/order` với alert giả (dry run) → server không crash, trả lỗi rõ ràng (`config_error` vì chưa có mật khẩu MT5 trong `.env`) thay vì lỗi 500 mù mờ.
- Chạy `pytest` — 52/52 test pass (test dùng MT5 giả lập nên không cần cài MT5 thật/terminal thật để chạy test).

**Điều duy nhất chưa test được ở đây** là đặt lệnh thật vào MT5/Exness, vì máy này không có terminal MT5 đang đăng nhập tài khoản Exness thật. Phần đó bạn cần tự làm ở máy có MT5 (xem mục 3 và 4 bên dưới) — nhưng code, luồng xử lý, validate, log đều đã chạy đúng.

## 1. Về mật khẩu — mỗi tài khoản một mật khẩu

Đúng, mỗi **tài khoản MT5** có một mật khẩu. Trong code, mật khẩu được map theo **tên strategy** (key trong `config.json` → `strategies`), không map trực tiếp theo số tài khoản:

```
MT5_PASSWORD_<TÊN_STRATEGY_VIẾT_HOA>=mật khẩu MT5
```

Ví dụ strategy tên `eth_strategy_01` → biến env `MT5_PASSWORD_ETH_STRATEGY_01`.

- Nếu mỗi strategy dùng **một tài khoản MT5 riêng** → mỗi strategy một dòng mật khẩu, bình thường.
- Nếu **2 strategy dùng chung 1 tài khoản MT5** (cùng `login`) → bạn khai 2 dòng mật khẩu trong `.env`, cả hai đều gán **cùng một giá trị** (mật khẩu của tài khoản đó). Hơi lặp nhưng không sai, vì code tra mật khẩu theo tên strategy để tiện log/tách theo từng chiến lược.

## 2. Cấu trúc project

```
mt5_bot/
  app/                  code chính (FastAPI, MT5, logic đặt lệnh)
  config.json            cấu hình strategy (KHÔNG chứa mật khẩu)
  .env                    mật khẩu MT5, webhook secret (KHÔNG commit lên git)
  requirements.txt
  tests/
```

## 3. Cài đặt

### 3.1. Yêu cầu
- Windows, đã cài **MetaTrader 5 desktop** (terminal), đã thêm tài khoản Exness vào MT5 (không bắt buộc đăng nhập sẵn — bot sẽ tự đăng nhập bằng login/password/server trong config).
- Python 3.10+

### 3.2. Cài thư viện

```bash
cd mt5_bot
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3.3. Tạo file cấu hình

```bash
copy config.example.json config.json
copy .env.example .env
```

## 4. Cấu hình `config.json`

```json
{
  "dryRun": true,
  "strategies": {
    "eth_strategy_01": {
      "price": 1,
      "deviation": 200,
      "magic": 100001,
      "comment": "ETH Strategy 01",
      "mt5": {
        "login": 12345678,
        "server": "Exness-MT5Trial8"
      },
      "telegram": {
        "enabled": true,
        "botToken": "123456789:AAExampleBotTokenXXXXXXXXXXXXXXXXXXX",
        "chatId": "-1001234567890"
      }
    }
  }
}
```

Giải thích từng trường:

| Trường | Ý nghĩa |
|---|---|
| `dryRun` (ngoài cùng) | Bật/tắt chế độ thử toàn hệ thống. `true` = không gửi lệnh thật, chỉ log. |
| `strategies.<key>` | Tên định danh 1 chiến lược/1 kết nối tài khoản. Đây là giá trị bạn sẽ gửi trong field `strategy` của webhook TradingView. |
| `price` | **Vốn gốc**, đơn vị **nghìn đô**. VD `price: 1` = $1,000 vốn cơ sở. Số tiền vào lệnh thực tế = `price × 1000 × order_ratio` (order_ratio lấy từ webhook TradingView). |
| `deviation` | Trượt giá tối đa **ban đầu** cho phép (tính bằng point) khi khớp lệnh market. Không phải con số cố định duy nhất — nếu MT5 từ chối vì trượt giá (Requote/Price Changed), bot tự lấy giá mới và **thử lại với deviation gấp 3 lần**, tối đa 5 lần thử (có trần ở 25x). Vừa bảo vệ giá lúc thị trường yên ả, vừa vẫn có cơ hội khớp khi thị trường biến động nhanh. Xem chi tiết mục 4.1. |
| `magic` | Mã số gắn vào mọi lệnh của strategy này, để bot chỉ đóng đúng lệnh do chính nó mở (không đụng vào lệnh tay hoặc EA khác trên cùng tài khoản). |
| `comment` | Ghi chú gắn vào lệnh, hiện trong lịch sử giao dịch MT5. |
| `mt5.login` | Số tài khoản MT5 (Exness cấp khi bạn mở account, ví dụ demo hoặc real). |
| `mt5.server` | Tên server MT5 của Exness (xem trong MT5 desktop: File → Login to Trade Account, hoặc email Exness gửi lúc mở tài khoản). VD: `Exness-MT5Trial8`, `Exness-MT5Real7`... |
| `dryRun` (trong 1 strategy) | Tuỳ chọn, ghi đè `dryRun` toàn cục — chỉ áp dụng riêng cho strategy này. |
| `telegram` | Tuỳ chọn. Có thì bot gửi thông báo Telegram mỗi khi thực hiện lệnh cho strategy này (xem mục 4.2). Không khai thì strategy đó không gửi thông báo. |

**Lưu ý quan trọng:**
- Không có field `symbol` trong `config.json`. Symbol để giao dịch **lấy trực tiếp từ webhook TradingView gửi lên** (field `symbol`). Bot tự động cắt hậu tố `.P` (kiểu hợp đồng tương lai của TradingView, ví dụ `BTCUSDT.P` → `BTCUSDT`) trước khi dùng để đặt lệnh — nên nếu bạn dùng `{{ticker}}` và nó trả về dạng `.P`, không cần sửa gì thêm. Nhưng nếu tên symbol bên MT5/Exness khác hẳn TradingView theo cách khác (không chỉ khác mỗi `.P`), bạn vẫn phải gõ cứng đúng tên MT5 trong Alert.
- Không có field `path` (đường dẫn `terminal64.exe`). Mặc định code dùng đường cài MT5 chuẩn của Windows (`C:\Program Files\MetaTrader 5\terminal64.exe`). Nếu bạn cài MT5 ở chỗ khác, khai báo trong `.env`:
  ```
  MT5_TERMINAL_PATH=D:\MT5-Exness\terminal64.exe
  ```
- Không có `stopLoss`/`takeProfit` — bot đặt lệnh market thuần, không kèm SL/TP tự động.

### 4.1. `deviation` — vừa tránh trượt giá, vừa đảm bảo vào được lệnh

Đây là 2 mục tiêu hơi ngược nhau: giá tốt (deviation nhỏ) vs. chắc chắn khớp lệnh (deviation lớn). Bot xử lý bằng cách **kết hợp cả hai** thay vì chọn 1:

1. **Lần thử đầu tiên**: gửi lệnh với đúng `deviation` bạn cấu hình (mặc định `200` point) — bảo vệ giá, không cho khớp giá quá xấu.
2. **Nếu bị từ chối vì trượt giá** (MT5 trả lỗi Requote / Price Changed — nghĩa là giá đã đổi giữa lúc bot đọc giá và lúc lệnh tới sàn): bot chờ 0,25 giây (để có giá mới thật sự, không gửi lại đúng giá vừa bị từ chối), lấy giá mới, rồi gửi lại với `deviation` **gấp 3 lần** lần trước.
3. Lặp lại tối đa **5 lần thử**, deviation tăng dần nhưng có **trần chặn ở 25 lần deviation gốc** (không tăng vô hạn). Ví dụ với `deviation: 200`: 200 → 600 → 1800 → 5000 (chạm trần) → 5000.
4. Nếu cả 5 lần đều bị từ chối (thị trường biến động cực mạnh, gần như hiếm khi xảy ra), lệnh mới thật sự thất bại và trả lỗi về — báo Telegram ngay (nếu đã bật) để bạn biết mà xử lý tay, không có chuyện chờ vô hạn hay khớp ở giá không kiểm soát được.

**Lưu ý:** cơ chế này chỉ retry khi lỗi liên quan tới giá (Requote/Price Changed). Các lỗi khác (hết tiền, volume không hợp lệ, symbol bị khoá giao dịch, thị trường đóng cửa...) sẽ **không** retry vì thử lại cũng không sửa được — trả lỗi ngay lần đầu cho nhanh, tránh tốn thời gian thử vô ích. Vì vậy bot **không đảm bảo 100% luôn vào được lệnh** (không gì đảm bảo được điều đó khi thị trường đóng cửa hoặc broker chặn), nhưng với những lần bị từ chối do trượt giá thông thường thì xác suất bỏ lỡ tín hiệu gần như bằng 0.

Nhờ vậy: **thị trường bình thường** → luôn khớp ở deviation nhỏ, giá tốt. **Thị trường biến động** (tin tức, mở phiên...) → tự nới dần qua nhiều lần thử để vẫn có cơ hội khớp, thay vì bị từ chối ngay hoặc chấp nhận trượt giá vô hạn ngay từ lần đầu.

Cách chọn `deviation` ban đầu hợp lý theo symbol:
- Symbol tính bằng point nhỏ (VD forex major, point = 0.00001) → deviation vài chục là đủ.
- Symbol crypto/kim loại biến động mạnh (VD ETHUSD, point thường = 0.01) → deviation `200`–`500` là mức khởi điểm hợp lý (tương đương $2–$5 trượt giá cho phép ở lần thử đầu).
- Không chắc point của symbol bạn dùng là bao nhiêu: mở MT5 desktop, xem trong Market Watch → chuột phải symbol → Specification → mục "Point size".

### 4.2. Thông báo Telegram khi bot đặt lệnh

Mỗi strategy có thể tự bật/tắt gửi thông báo Telegram — bot sẽ gửi tin sau **mọi lệnh đã xử lý** (mở lệnh thành công, đóng lệnh thành công, lệnh thất bại, hoặc cả dry run) vào đúng chat/group bạn chỉ định.

**Bước 1 — Tạo bot Telegram:**
1. Mở Telegram, chat với [@BotFather](https://t.me/BotFather).
2. Gõ `/newbot`, đặt tên → BotFather trả về một **token** dạng `123456789:AAExampleBotTokenXXXXXXXXXXXXXXXXXXX`.

**Bước 2 — Lấy `chatId`:**
- Muốn bot nhắn vào 1 nhóm/group: thêm bot vào group đó, gửi thử 1 tin nhắn bất kỳ trong group, sau đó mở trình duyệt vào:
  `https://api.telegram.org/bot<TOKEN>/getUpdates`
  Tìm trường `"chat":{"id": ...}` — số này (thường là số âm với group) chính là `chatId`.
- Muốn bot nhắn riêng cho bạn: chat trực tiếp với bot (bấm Start), rồi làm tương tự bước trên, hoặc dùng bot tiện ích như @userinfobot để lấy nhanh id cá nhân.

**Bước 3 — Khai vào `config.json`, trong đúng strategy cần thông báo:**

```json
"telegram": {
  "enabled": true,
  "botToken": "123456789:AAExampleBotTokenXXXXXXXXXXXXXXXXXXX",
  "chatId": "-1001234567890"
}
```

- `botToken` khai thẳng ở đây, không bắt buộc phải đặt trong `.env`.
- Nếu bạn không muốn để token trong `config.json` (ví dụ file này có thể bị chia sẻ), có thể bỏ trống `botToken` và khai `TELEGRAM_BOT_TOKEN=...` (dùng chung cho mọi strategy) hoặc `TELEGRAM_BOT_TOKEN_ETH_STRATEGY_01=...` (riêng cho 1 strategy) trong `.env` — `botToken` trong `config.json` nếu có sẽ luôn được ưu tiên trước.
- Không khai `telegram`, hoặc đặt `"enabled": false` → strategy đó không gửi thông báo gì cả.
- Nếu gửi thất bại (sai token, mất mạng...) bot chỉ ghi log cảnh báo, **không** làm ảnh hưởng tới việc đặt lệnh MT5 hay response trả về TradingView.

Ví dụ tin nhắn bot gửi khi mở lệnh thành công:

```
✅ ETHUSD-openLong: 4.125,10
Strategy: eth_strategy_01
Volume: 0.24
Message: Request executed
```

Dòng đầu tiên theo format `<symbol>-<hành động>: <giá khớp lệnh>` (số viết kiểu Việt Nam: chấm ngăn hàng nghìn, phẩy cho phần thập phân — ví dụ giá 4125.1 hiển thị `4.125,10`, giá tròn 12996 hiển thị `12.996`). Symbol hiển thị ở đây chính là symbol **thật sự đã dùng để đặt lệnh** (hậu tố `.P` nếu có đã bị cắt từ trước khi đặt lệnh, không phải chỉ cắt lúc hiển thị), còn `❌`/`🧪` thay cho `✅` khi lệnh thất bại/dry run.

## 5. Cấu hình `.env`

```
MT5_PASSWORD_ETH_STRATEGY_01=mat-khau-tai-khoan-mt5
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
# MT5_TERMINAL_PATH=C:/Program Files/MetaTrader 5/terminal64.exe
# DRY_RUN=true
# TELEGRAM_BOT_TOKEN=... (chỉ cần nếu không khai botToken trực tiếp trong config.json)
```

- `DRY_RUN`: nếu đặt trong `.env` sẽ **ghi đè tất cả** cấu hình `dryRun` trong `config.json` (dùng để bật/tắt nhanh khi test mà không sửa `config.json`).
- API `/api/order` **không có xác thực** (không cần header gì cả, chỉ cần đúng body) — đúng như bạn yêu cầu, để gọi từ TradingView cho đơn giản nhất. Nếu sau này public server ra internet, nên tự giới hạn ai gọi được bằng firewall/VPN thay vì để hoàn toàn mở.

## 6. Chạy server

```bash
venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Kiểm tra sống:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

## 7. Gọi thử API (test tay bằng curl/Postman)

Request phải gửi `Content-Type: text/plain`, body là **chuỗi JSON** (đúng như TradingView gửi):

```bash
curl -X POST http://localhost:8000/api/order ^
  -H "Content-Type: text/plain" ^
  -d "{\"symbol\":\"ETHUSD\",\"price\":\"4123.45\",\"order_id\":\"openLong\",\"order_ratio\":1,\"strategy\":\"eth_strategy_01\"}"
```

(Trên Windows cmd/PowerShell nhớ escape dấu `"` như trên; nếu dùng Git Bash thì bỏ dấu `^` cuối dòng và dùng `\` thay cho nối dòng, hoặc gõ một dòng.)

Các giá trị `order_id` hợp lệ:

| `order_id` | Hành động |
|---|---|
| `openLong` | Mở lệnh BUY |
| `closeLong` | Đóng (các) lệnh LONG đang mở của strategy đó |
| `openShort` | Mở lệnh SELL |
| `closeShort` | Đóng (các) lệnh SHORT đang mở của strategy đó |

Response mẫu khi `dryRun: true`:

```json
{
  "success": true,
  "dry_run": true,
  "strategy": "eth_strategy_01",
  "symbol": "ETHUSD",
  "action": "openLong",
  "volume": 0.24,
  "price": 4125.1,
  "order_ticket": null,
  "message": "Dry run: no order sent to MT5"
}
```

> Lưu ý: kể cả `dryRun: true`, bot **vẫn kết nối MT5 thật** để lấy giá bid/ask hiện tại (tính volume cho chính xác) — chỉ là **không gửi lệnh**. Vì vậy `dryRun` vẫn cần: MT5 terminal đã cài, tài khoản/mật khẩu đúng trong `.env`.

## 8. Đấu nối với TradingView

1. Vào chiến lược/indicator trên TradingView → tạo **Alert**.
2. Webhook URL: `https://<domain-hoặc-ip-máy-bạn>:8000/api/order` (server phải public được ra internet — dùng ngrok/Cloudflare Tunnel/VPS nếu chạy tại nhà; TradingView không gọi được `localhost`).
3. Message (nội dung alert), điền đúng format sau — **TradingView tự gửi dạng `text/plain`, không cần chỉnh gì thêm**:

```json
{
  "symbol": "ETHUSD",
  "price": "{{strategy.order.price}}",
  "alert_name": "{{alert_name}}",
  "timenow": "{{timenow}}",
  "order_id": "{{strategy.order.comment}}",
  "order_action": "{{strategy.order.action}}",
  "comment": "{{strategy.order.comment}}",
  "alert_message": null,
  "order_ratio": 1,
  "strategy": "eth_strategy_01"
}
```

- `symbol`: gõ **cứng đúng tên symbol bên MT5/Exness** (ví dụ `ETHUSD`). Nếu dùng `{{ticker}}` và nó trả về dạng có hậu tố `.P` (ví dụ `BTCUSDT.P`), bot tự cắt `.P` trước khi đặt lệnh nên vẫn dùng được — nhưng nếu tên khác nhau theo cách khác (không chỉ khác mỗi `.P`), vẫn phải gõ cứng đúng tên MT5.
- `order_id`: lấy từ `{{strategy.order.comment}}` — nghĩa là trong Pine Script, bạn phải đặt comment của lệnh strategy đúng bằng 1 trong 4 giá trị: `openLong`, `closeLong`, `openShort`, `closeShort`.
  ```pine
  strategy.entry("Long", strategy.long, comment="openLong")
  strategy.close("Long", comment="closeLong")
  strategy.entry("Short", strategy.short, comment="openShort")
  strategy.close("Short", comment="closeShort")
  ```
- `strategy`: gõ đúng key strategy trong `config.json` (ví dụ `eth_strategy_01`).
- `order_ratio`: hệ số nhân vốn so với `price` gốc trong config (1 = full vốn cấu hình, 0.5 = nửa vốn, 2 = gấp đôi...).

API không yêu cầu header hay xác thực gì cả — TradingView chỉ cần gửi đúng body JSON như trên là được, đúng theo cách TradingView webhook hoạt động (không hỗ trợ custom header). Nếu sau này muốn giới hạn ai gọi được server, nên chặn ở tầng mạng (firewall/VPN) thay vì thêm xác thực ở tầng ứng dụng.

## 9. Chuyển từ thử (dry run) sang chạy lệnh thật

1. Mở MT5 desktop, thêm tài khoản Exness (Login → nhập số tài khoản, mật khẩu, chọn đúng server) **ít nhất một lần** để chắc chắn login/server đúng và MT5 nhận được symbol đó (Market Watch có hiển thị `ETHUSD`).
2. Trong `config.json`, đặt `"dryRun": false` (toàn cục hoặc riêng từng strategy).
3. Đảm bảo `.env` có đúng `MT5_PASSWORD_<STRATEGY>`.
4. Khởi động lại server (`uvicorn ...`).
5. Bắn thử 1 lệnh volume nhỏ (dùng tài khoản **demo** trước, hoặc `order_ratio` rất nhỏ) để kiểm tra lệnh thật sự vào đúng bên MT5.
6. Theo dõi log tại `logs/app.log` — mọi lệnh gửi đi, kết quả, lỗi đều được ghi lại đầy đủ.

## 10. Các lỗi thường gặp

| Lỗi trả về | Nguyên nhân | Cách xử lý |
|---|---|---|
| `invalid_json` | Body không phải JSON hợp lệ | Kiểm tra lại nội dung Alert message trên TradingView |
| `validation_error` | Thiếu field, `order_id` không đúng 1 trong 4 giá trị, `price`/`order_ratio` không parse được số | Xem chi tiết `detail` trong response |
| `unknown_strategy` | `strategy` gửi lên không khớp key nào trong `config.json` | Kiểm tra chính tả, hoa/thường |
| `config_error` (thiếu mật khẩu) | Chưa khai `MT5_PASSWORD_<STRATEGY>` trong `.env` | Thêm biến env đúng tên (viết hoa, thay `_` cho khớp tên strategy) |
| `order_execution_failed` (502) | MT5 từ chối kết nối/lệnh (sai login-password-server, chưa mở terminal, symbol không có trong Market Watch, market đóng cửa...) | Mở MT5 desktop, thử login tay bằng đúng login/password/server để xem lỗi cụ thể; kiểm tra symbol có tồn tại đúng tên trên tài khoản đó không |
| `order_execution_failed` (502), báo "No live price yet" | Symbol vừa được thêm vào Market Watch (lần đầu tra tới), MT5 chưa kịp nhận báo giá đầu tiên. Bot đã tự chờ tối đa 3 giây trước khi báo lỗi này. | Gọi lại lệnh lần nữa (thường lần 2 sẽ có giá ngay); hoặc mở MT5 desktop, tự thêm symbol đó vào Market Watch trước và để yên vài giây cho có giá. |

## 11. Chạy test tự động

```bash
pytest -q
```

52 test đã viết sẵn, không cần MT5 thật hay terminal đang chạy (dùng MT5 giả lập trong `tests/conftest.py`), dùng để kiểm tra nhanh mỗi khi sửa code có làm hỏng logic hiện tại không.

## 12. Các cải tiến "chuẩn chuyên gia" đã thêm

Đây là những lỗi/rủi ro rất hay gặp khi build bot MT5 thực chiến mà bot này đã xử lý sẵn:

| Vấn đề | Rủi ro nếu không xử lý | Cách bot xử lý |
|---|---|---|
| **Filling mode sai** | Rất nhiều symbol/broker (kể cả Exness) không hỗ trợ `IOC` — nếu hardcode, lệnh bị từ chối thẳng với lỗi "Unsupported filling mode", không vào được lệnh dù mọi thứ khác đúng. | Bot tự dò `symbol_info.filling_mode` để chọn đúng filling mode symbol đó hỗ trợ (`IOC` → `FOK` → `RETURN`), không hardcode nữa. |
| **Sai số làm tròn volume** | Với các symbol có `volume_step` lẻ (VD `0.05`), làm tròn bằng số thực (float) có thể lệch khỏi step do sai số dấu phẩy động, khiến MT5 từ chối lệnh vì volume không hợp lệ. | Chuyển sang tính bằng `Decimal` (chính xác tuyệt đối), đảm bảo volume luôn khớp đúng lưới step. |
| **Đụng độ khi có nhiều webhook tới cùng lúc** | Package `MetaTrader5` chỉ giữ 1 kết nối/tiến trình. Nếu 2 webhook (2 strategy khác tài khoản) tới cùng lúc mà không khoá, có thể gây lệnh gửi nhầm tài khoản. | Toàn bộ thao tác MT5 (kết nối, lấy giá, gửi lệnh) được bọc trong 1 khoá (`lock`), đảm bảo tại 1 thời điểm chỉ có 1 lệnh đang được xử lý — webhook khác phải đợi tới lượt, không chen ngang giữa chừng. |
| **Server bị "đứng" khi đang chờ MT5** | Gọi MT5 là thao tác chặn (blocking); nếu xử lý ngay trên luồng chính, cả server (kể cả `/health`) sẽ bị treo trong lúc chờ MT5/broker phản hồi. | Các lệnh gọi MT5/Telegram được đẩy sang thread pool (`asyncio.to_thread`), server vẫn phản hồi các request khác trong lúc chờ. |
| **TradingView gửi trùng webhook** | TradingView tự động gửi lại alert nếu không nhận phản hồi 2xx đủ nhanh (mất mạng, server chậm...) — dễ khiến bot **vào lệnh 2 lần** cho cùng 1 tín hiệu. | Bot nhớ lại các alert đã xử lý gần đây (theo strategy + order_id + symbol + comment + timenow) trong 30 giây; nếu trùng, trả về ngay `200 OK` với thông báo "Duplicate alert ignored" mà **không** gửi lệnh lại. |
| **Giá đổi giữa lúc lấy tick và lúc gửi lệnh (Requote)** | Thị trường biến động nhanh, giá lúc gửi lệnh khác giá lúc bot đọc — MT5 trả lỗi Requote/Price Changed, lệnh bị từ chối. | Bot tự động lấy giá mới, nới `deviation` dần và gửi lại (tối đa 5 lần, có trần) nếu gặp đúng 2 lỗi này — xem mục 4.1. |
| **Gửi lệnh vào symbol đang bị khoá giao dịch** | Gửi lệnh vô ích vào symbol bị sàn tạm khoá (đóng phiên, hạn chế giao dịch...), tốn thời gian chờ phản hồi lỗi từ MT5. | Bot kiểm tra `trade_mode` của symbol trước, báo lỗi rõ ràng ngay lập tức thay vì cố gửi lệnh. |

Những cải tiến này không đổi cách bạn cấu hình/dùng bot — vẫn `config.json` + `.env` như hướng dẫn ở trên, chỉ là phần xử lý bên trong chắc chắn và an toàn hơn khi chạy thật.
