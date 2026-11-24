# KUN GLOBAL · Dịch đa ngôn ngữ qua OpenAI API

Ứng dụng dùng **khóa OpenAI API chung do admin cấu hình**. User đăng nhập tài khoản app để dịch; không đăng nhập ChatGPT và không cung cấp khóa riêng. Backend FastAPI, frontend React/TypeScript, Docker; 20 ngôn ngữ, dịch văn bản/ảnh/PDF, Word A4 có bảng và ô gộp. Không có chức năng giọng nói.

## Chạy local

1. Cài Docker Desktop hoặc Docker Engine + Compose.
2. Trong thư mục này chạy `docker compose up -d --build`.
3. Mở [localhost:8080](http://localhost:8080). Tài khoản hiện có được giữ nguyên. Bản cài mới tạo admin bằng `./scripts/create-account.ps1 -Username ten-admin -Role admin`; nhập mật khẩu kín khi script hỏi.
4. Admin mở **Quản trị và tài khoản → OpenAI API**, nhập khóa và model, bấm **Lưu cấu hình API**, rồi **Kiểm tra kết nối**. Không gửi khóa trong chat. `gpt-4.1-mini` là giá trị mặc định có thể đổi; cần model hỗ trợ Responses, ảnh/PDF và Structured Outputs.
5. Tạo user trong **Người dùng**. Tất cả tài khoản đang hoạt động dùng API chung. Admin vẫn có thể sửa, khóa/mở khóa, thu hồi phiên và xóa user với xác nhận.

Khóa lưu trong SQLite được mã hóa bằng master key của volume `/data`, không trả lại qua API/giao diện. Có thể đặt `OPENAI_API_KEY` và `OPENAI_MODEL` trong `.env` backend thay cho form admin (xem `.env.example`). Khóa lưu ở quản trị ưu tiên hơn biến môi trường; xóa khóa đã lưu sẽ dùng khóa môi trường nếu có. Không đặt khóa vào biến `VITE_*` hoặc source frontend.

**API tính phí riêng theo tài khoản OpenAI API; không dùng hạn mức đăng nhập ChatGPT cũ.** Kiểm tra kết nối có gọi một câu thử; dịch ảnh/PDF và bước dựng biểu mẫu có thể dùng nhiều token. Hạ tầng VPS, lưu trữ và tên miền cũng có chi phí. Khi chưa có khóa, app báo chưa cấu hình, không giả kết quả. Lưu khóa chỉ chứng minh có cấu hình; nút kiểm tra phải nhận bản dịch hợp lệ mới báo kết nối thành công.

Các kết nối OAuth cũ trong DB được giữ nguyên nhưng không dùng làm phương án dự phòng. Không mở cổng callback 17653. Dữ liệu người dùng, lịch sử và mật khẩu app không bị chuyển đổi/xóa. Cập nhật bằng `docker compose up -d --build`; không dùng `down -v` nếu muốn giữ dữ liệu.

## Giao diện và tài liệu

Trang đăng nhập `/login` dùng bố cục thương hiệu vàng nâu, ảnh địa cầu và form nền kem; thu gọn phần hình ảnh trên điện thoại. Form hỗ trợ trình quản lý mật khẩu, hiện/ẩn mật khẩu, trạng thái đang đăng nhập và thông báo lỗi. Tài khoản đã đăng nhập vào `/login` được chuyển tới `/app`.

Trang dịch `/app` dùng cùng logo, ảnh địa cầu, phông Arial và nền họa tiết vàng nâu với landing page và đăng nhập. Thanh điều hướng giữ ở đầu màn hình; ba chế độ văn bản, hình ảnh và tài liệu dùng khu vực làm việc nền kem. Trên điện thoại, thanh tiện ích thu gọn bằng biểu tượng và hai ô đọc xếp dọc. Giao diện được đóng phạm vi trong `translator.css` để không ảnh hưởng trang chủ và đăng nhập.

Ở **Tài liệu → PDF sang Word**, chọn PDF để xem ngay file gốc, chọn nguồn/đích rồi bấm **Dịch tài liệu**. Ứng dụng tự tạo câu lệnh theo ngôn ngữ đích; không hiển thị ô nhập hay nội dung câu lệnh trong giao diện. Chọn file chưa gửi dịch; thao tác bấm nút mới chuẩn bị và gửi nguyên PDF gốc kèm yêu cầu tự động tới mô hình OpenAI API do admin cấu hình. Kết quả về ô bên phải và có nút **Tải Word**. Yêu cầu bên trong bắt đầu bằng “Áp dụng hướng dẫn Translator Pro. Dịch chuẩn toàn bộ văn bản trong tài liệu này sang tiếng … cho tôi”, tự điền tên tiếng Việt của 20 ngôn ngữ đích, rồi yêu cầu dịch cả chữ trong ảnh/scan, giữ tên/số và dựng lại bảng trên A4 trắng.

Luồng này dùng `input_file` Base64 trực tiếp trong Responses bằng khóa API backend, không dùng Files upload API, không mở/điều khiển một tab ChatGPT.com và không tạo lịch sử hội thoại trên website. Mô hình nhận được PDF gốc để đọc cả chữ và hình; tài khoản/mô hình phải hỗ trợ file PDF. Hướng dẫn chính thức: [File inputs](https://developers.openai.com/api/docs/guides/file-inputs). Nhà cung cấp từ chối file hoặc trả thiếu trang thì app báo lỗi; không âm thầm thay bằng OCR nhiễu hoặc tạo kết quả giả.

Bước chuẩn bị chỉ kiểm tra file/số trang và render ảnh xem trước cục bộ. Tesseract/PDFMiner không nằm trong luồng dịch PDF gốc. Mô hình được yêu cầu đọc đủ từng trang, trả nội dung gốc, bản dịch và cấu trúc bảng, rồi tự đối chiếu trước khi hoàn tất. Kiểm tra cấu trúc không chứng minh mọi dòng đã dịch đúng; cần đối chiếu nội dung quan trọng. Ghi chú không chắc chắn từ mô hình có trong phần **Ghi chú bản dịch**; không gán điểm OCR cho kết quả đọc trực tiếp.

Với biểu mẫu mở có ít ô kín nhưng nhiều vùng chữ (từ 24 vùng trong một ô lớn), app tự chạy thêm bước đối chiếu bố cục với PDF gốc: chỉ trả tham chiếu ID để ghép nhãn–giá trị thành hàng/cột, không viết lại bản dịch. Kiểm tra mỗi ID có đúng một lần và không có ID lạ rồi mới dựng Word; mọi vùng còn lại vẫn được xuất. Bước này dùng thêm một lượt mô hình qua cùng cấu hình API và có thể tăng thời gian chờ. Yêu cầu tài liệu qua Nginx có thời gian chờ tối đa 20 phút. Tải Word dùng kết quả đã lưu, không gọi lại bước này.

Kết quả Word dùng khổ A4 nền trắng, chữ và bảng chỉnh sửa được. Khi đọc PDF, mô hình trả vai trò từng đoạn, cỡ chữ tương đối, căn lề, đậm/nghiêng/gạch chân, khung/ô gộp và hàng tiêu đề bảng. Bộ xuất giữ các thông tin này, phân cấp Title/Heading, cột song song và khoảng cách tương đối; hàng tiêu đề có thể lặp khi bảng sang trang. Cột chữ ký căn giữa được chia theo không gian cột thay vì bó vào chiều rộng chữ gốc. Chữ Arial mặc định 11pt, giới hạn đọc rõ 10–24pt; ô/đoạn tự giãn hoặc sang trang để không cắt chữ. Không tái tạo nền màu/hoa văn hoặc nhúng dấu/chữ ký; không cam kết phông gốc, tọa độ và phân trang giống tuyệt đối. Ô bên phải xem trước cùng kiểu chữ/cột/bảng, còn phân trang đầy đủ nằm trong Word.

Xuất Word dùng lại phản hồi đã nhận, không gọi mô hình lần nữa. Đổi ngôn ngữ hoặc file vô hiệu bản tải cũ. Phiên file chỉ giữ trong RAM, tối đa 20 phút không thao tác hoặc tới khi backend khởi động lại; có thể chọn lại PDF để tạo phiên mới. Word đã chuẩn bị giữ trong bộ nhớ trình duyệt để tải lại ngay.

PDF tối đa 30 MB/10 trang, câu lệnh tối đa 6.000 ký tự. Nguồn tự phát hiện và đủ 20 ngôn ngữ đích. DOCX/TXT dùng chế độ **Trích xuất văn bản** riêng. Các endpoint OCR/PDF giữ form cũ vẫn được giữ để tương thích, nhưng không dùng trong thao tác **Dịch tài liệu** mới.

API mới: `POST /api/documents/prepare` nhận PDF và nguồn; `POST /api/documents/translate-original` nhận session_id, target, prompt; `POST /api/documents/export-word` tải bản Word của chính tài khoản. Chỉ publish kết quả sau response.completed, đủ số trang/cấu trúc hợp lệ và tạo Word thành công; thử lại lỗi không ghi đè kết quả đã hoàn tất ở máy chủ.

Mỗi yêu cầu dịch nạp ba hướng dẫn `translation-router`, `faithful-translation`, `translation-review` từ Translator Pro 0.1.1 tại `backend/app/translation_skills/translator-pro/`. Đây là việc áp dụng các skill được đóng gói cùng ứng dụng, không phải gọi trực tiếp plugin từ giao diện ChatGPT. Mô hình được yêu cầu dịch giữ ý nghĩa, tên, số liệu, cấu trúc, rồi tự đối chiếu bản nháp với nguồn trong cùng yêu cầu; không phải một lượt thẩm định độc lập. Kiểm thử giao thức xác nhận hướng dẫn và dữ liệu được gửi, không chứng minh chất lượng bản dịch thực tế.

Tab Hình ảnh gửi ảnh gốc đã chuẩn hóa hướng xoay tới mô hình đã kết nối qua Responses `input_image`, `detail: high`, cùng ba skill Translator Pro. Mô hình đọc chữ, dịch, trả tọa độ vùng theo bố cục; ứng dụng ghép ảnh và xuất PNG. Chọn ảnh hoặc bấm **Dịch ngay** đều dùng luồng này, không dịch từ riêng bản OCR nhiễu. Cần mô hình/tài khoản hỗ trợ ảnh; nếu nhà cung cấp từ chối, ứng dụng báo lỗi thay vì giả vờ đã đọc ảnh hoặc tự chuyển sang phương án khác. Chữ rất nhỏ, mờ hoặc khuất vẫn có thể đọc sai; không cam kết ảnh ghép hoặc bản dịch giống tuyệt đối trong ChatGPT. Tham khảo [Images and vision](https://developers.openai.com/api/docs/guides/images-vision).

Ảnh hỗ trợ PNG/JPG/JPEG/WEBP, tối đa 10 MB và 64 megapixel đầu vào; ảnh trên 16 megapixel tự thu nhỏ để xử lý. Xoay EXIF được áp dụng trước khi tính tọa độ, nền trong suốt ghép trên trắng, JPEG CMYK chuyển RGB. WEBP động chỉ xử lý khung đầu và có thông báo. HEIC/GIF/TIFF/BMP chưa hỗ trợ; đổi sang PNG/JPG trước khi tải. File được kiểm tra cả nội dung, không chỉ đuôi tên.

Ảnh không có chữ đọc được trả thông báo rõ và không tạo bản dịch giả. Phản hồi thiếu vùng, sai tọa độ hoặc chưa hoàn tất không được xuất thành kết quả thành công. Chuyển tab/chọn nguồn không tự gửi dịch lặp; bấm **Dịch ngay** để dịch lại với lựa chọn mới. Chữ đọc từ ảnh ở chế độ chỉ xem, tránh sửa văn bản nhưng thao tác dịch lại lại dùng ảnh gốc. Lỗi mạng giữ file để thử lại; không cho tải nhầm kết quả cũ.

Phần ghép ảnh chọn màu nền theo vùng mẫu bao quanh, điều chỉnh tương phản chữ và ngắt dòng theo cụm ký tự Unicode. Không đè chữ vào ô bên cạnh. Vùng không vừa hoặc có tọa độ chồng lấn vẫn xuất đầy đủ trong phần tiếp nối dưới ảnh; bố cục có thể dài hơn ảnh gốc. Nền phức tạp/hoa văn bị phủ chữ không thể phục hồi nguyên bản bằng cách ghép này. Xem kết quả và giới hạn kiểm thử tại [QA-REPORT.md](QA-REPORT.md).

Các đoạn chú thích liền nhau cùng cột được dàn chung; cỡ chữ đoạn nhiều dòng tính theo diện tích, không đo toàn đoạn như một dòng. Khung chỉ chồng nhỏ được chia tại ranh giới để chữ vẫn xuất hiện ngay trên ảnh; đoạn văn giữ căn trái. Phần tiếp nối chỉ dùng khi nội dung vẫn không vừa hoặc tọa độ chồng lấn đáng kể.

## VPS và Netlify

API mode hỗ trợ backend dùng chung. Triển khai Docker trên VPS, đặt `APP_ORIGIN=https://ten-mien-cua-ban`, `COOKIE_SECURE=true`, giữ volume `accounts` bền vững, sao lưu cả DB và master key cùng nhau. Giữ cổng app bind localhost và dùng reverse proxy HTTPS tới 127.0.0.1:8080. Tạo mật khẩu admin mạnh trước khi mở ra Internet; tài khoản thử local không phải cấu hình sản xuất.

Netlify dùng Functions và Blobs cho đăng nhập, quản trị tài khoản và API dùng chung do admin cấu hình tại https://kun-global-dichthuat-hoanganh.netlify.app. User chỉ đăng nhập app và dịch; không thấy phần kết nối, khóa, model hoặc hạn mức. Tài khoản và cấu hình online được mã hóa, lưu riêng với bản Docker local. Xem [DEPLOY-NETLIFY.md](DEPLOY-NETLIFY.md) để cấu hình bootstrap và triển khai. Không đặt khóa hoặc mật khẩu vào frontend `VITE_*`.

## Kiểm thử và lưu trữ

`docker compose -f compose.test.yaml run --build --rm tests` dùng container không mạng, DB tạm, không có khóa thật. `cd frontend; npm ci; npm run build` kiểm tra TypeScript và build giao diện. Test có phản hồi giả lập chỉ xác minh giao thức và xử lý; không chứng nhận chất lượng dịch.

Nguồn ZIP không bao gồm `.env`, DB, master key, token, file khách hàng, node_modules hoặc model weights. Dữ liệu file dịch giữ RAM theo phiên; backend khởi động lại cần chọn lại file. Không có giả lập chất lượng dịch hay tự chuyển về model cục bộ.
