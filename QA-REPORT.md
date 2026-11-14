# Kiểm tra chức năng KUN GLOBAL — 13/11/2026

## Tự chọn định dạng và 20 ngôn ngữ — 14/11/2026

Bổ sung Ý, Bồ Đào Nha, Hà Lan, Ả Rập; endpoint, bộ phát hiện, schema đọc ảnh và cả ba bộ chọn giao diện dùng chung danh sách 20 ngôn ngữ. Container cài và kiểm tra thật traineddata OCR của đủ 20 ngôn ngữ. Các bộ chọn nguồn có thêm mục Tự phát hiện.

Giữ form chỉ được ưu tiên khi chữ vừa khung, không có vùng cần phụ lục và đạt khoảng 9 pt. Ảnh được đánh giá theo kích thước in A4 để DPI/màn hình không làm thay đổi lựa chọn. PDF ghi lại cỡ chữ thực sự đã dàn. Khi chữ quá nhỏ, tràn hoặc hệ chữ chưa xuất PDF ổn định, tự ưu tiên Word A4, hiển thị lý do và nút tải; vẫn cho chọn bản giữ form nếu đã có. Không gửi dịch lại chỉ để đổi cách xuất.

Bộ kiểm thử cuối: **147 passed, 4 skipped** trong container không mạng, DB tạm không dùng tài khoản thật. Bốn test cũ cần kết nối model thật bị bỏ qua có chủ đích. Build TypeScript/Vite và Docker thành công. Không có lượt inference thật mới để chứng nhận chất lượng cả 20 ngôn ngữ trong đợt bổ sung này.

Tài liệu chuyển sang hệ chữ phức tạp được hoàn tất bằng DOCX thật, không trả PDF giả; đổi đích dịch không dùng lại cache Word của đích cũ. Kiểm thử giao thức gửi đủ 20 đích cho văn bản/ảnh, kiểm thử PDF→Word Ả Rập rồi dịch lại sang Việt, cùng các trường hợp nguyên form/chữ nhỏ/tràn. Các phản hồi model trong test là fixture, không chứng minh chất lượng dịch thật của cả 20 ngôn ngữ.

Kiểm tra trình duyệt riêng: nguồn 21 lựa chọn gồm tự phát hiện, đích 20 trong cả ba chế độ; form rõ giữ nguyên; chữ nhỏ/tràn chọn A4; đổi xem form không gọi dịch lại; tài liệu hệ chữ phức tạp tải Word được, không hiện liên kết PDF không tồn tại. Responsive 320/375/768/1280 px và không lỗi JavaScript. Mẫu DOCX chứa đủ 20 hệ ngôn ngữ được render, kiểm tra một trang với glyph đầy đủ và chữ Ả Rập có RTL/Bidi.

## Bổ sung Word A4 — 14/11/2026

Đã thêm xuất DOCX cho văn bản, ảnh và PDF đã dịch. File có khổ A4, bảng/ô gộp Word thật và chữ chỉnh sửa được, nền trắng; không nhúng ảnh nền. Dò được 1 bảng gồm 24 ô trên mẫu Apostille thực tế. Nội dung dài tự xuống dòng/sang trang, không đặt chiều cao ô cố định gây cắt chữ. Giữ cột/ô và thứ tự tương đối, không cam kết tái tạo tọa độ tuyệt đối.

**137 test backend đạt, 4 test tích hợp cũ được bỏ qua** trong DB cách ly; bao gồm 11 test Word mới về A4, chữ Unicode, bảng gộp, nền trắng/không có ảnh nhúng, dữ liệu đầu vào, đăng nhập, quyền sở hữu phiên PDF, đích dịch và các chỉnh sửa mới nhất. Xuất Word bị kiểm tra không được gọi mô hình. Build frontend và kiểm tra browser tải Word từ ảnh/văn bản, cùng các luồng cũ, đều qua.

Mẫu Word từ bản dịch mô hình thật được tạo bằng bộ xuất của ứng dụng, render qua công cụ `render_docx.py` và kiểm tra cả 2 trang A4: bảng không đè/cắt chữ, các đoạn cuối không bị mất. Việc kiểm tra bố cục không xác nhận lại độ chính xác của bản dịch; phần mã không đọc rõ trong ảnh vẫn được đánh dấu.

## Sửa lỗi phần dưới ảnh — 14/11/2026

Đã tái hiện trên chính ảnh Apostille đang mở: phần chữ đã được mô hình dịch nhưng bộ ghép giữ chữ gốc khi thấy khung chồng vài pixel, rồi đưa bản dịch xuống phần tiếp nối. Kiểm tra trước đó chưa bắt được tình huống này trên ảnh dày chữ.

Đã sửa việc đo cỡ chữ cho đoạn nhiều dòng, ghép các đoạn liền nhau cùng cột và chia ranh giới chồng nhỏ trước khi dàn chữ. Đoạn văn giữ căn trái. Không ghép xuyên qua cột hoặc trường riêng; vùng chồng lấn lớn vẫn được xử lý thận trọng.

Kiểm tra lại ảnh thực tế sau một lượt kết nối thất bại và một lượt dịch thành công (40 vùng, 75,6 giây): **cả 10 khối cuối ảnh sau khi ghép đều được vẽ bản dịch tại chỗ**, gồm các chú thích, dòng xác minh và chữ con dấu cạnh dưới. Tất cả chữ trong kết quả mô hình vẫn có trong PNG; các pixel bên trong QR và chữ ký được so sánh bằng nhau với ảnh gốc được render cùng tỉ lệ. Chỗ mô hình không đọc rõ vẫn ghi không đọc rõ, không khôi phục được mã bị thiếu chỉ nhờ sửa bố cục.

Build frontend và ba nhóm test layout/background/Unicode/footer đều qua. Kiểm tra trình duyệt về dàn chữ, PNG/TXT/clipboard, thử lại sau lỗi, lịch sử, phân quyền, xác nhận xóa và responsive tiếp tục qua. Backend/model không thay đổi trong bản sửa này; bộ 126 test backend bên dưới là kết quả lần kiểm tra 13/11, không ghi thành một lần chạy mới.

Bản Docker mới đã chạy tại http://localhost:8080/. Kiểm tra gồm backend thật với dữ liệu tạm, giao diện trình duyệt riêng và ba lượt đọc ảnh qua kết nối ChatGPT đã có. Không đổi mật khẩu, xóa tài khoản thật hoặc ngắt kết nối thật. Không ghi token vào báo cáo/source.

## Kết quả kỹ thuật

| Phạm vi | Kết quả thực tế |
| --- | --- |
| Backend | **126 passed, 4 skipped**; không lỗi. 4 test tích hợp cũ cần kết nối thật bị bỏ qua trong DB kiểm thử cách ly. Một cảnh báo thư viện TestClient bị deprecated, không ảnh hưởng kết quả. |
| TypeScript/Vite/Docker | Build thành công. Backend healthy, web chạy cổng 8080. |
| Đọc ảnh thật | PNG, JPEG, WEBP; alpha RGBA/LA/palette; EXIF xoay; CMYK; ảnh 20/36 MP tự thu về tối đa 16 MP; WEBP động thông báo khung đầu. |
| File lỗi/giới hạn | File trống, hỏng, đổi đuôi giả, định dạng chưa hỗ trợ, >10 MB, ngôn ngữ sai và máy chủ đang bận được xử lý có thông báo. Không gọi mô hình cho file không hợp lệ. |
| Giao thức mô hình | Gửi ảnh gốc chuẩn hóa và ba skill Translator Pro thật; JSON/vùng/tọa độ/chữ thiếu hoặc sai bị từ chối. Khóa xử lý được giải phóng sau lỗi. |
| Hình ảnh | Tự dịch khi tải; Dịch ngay dùng lại ảnh gốc. Không gửi lại khi chuyển tab. Hai click cùng lượt chỉ gửi một yêu cầu. Lỗi 422/429/502/mất mạng đều thử lại được, giữ file gốc, xóa kết quả cũ. |
| Xuất ảnh | Tải PNG thật, đầy đủ chữ dài trong phần tiếp nối, font +/- và chế độ ảnh/văn bản; lỗi xuất PNG có thông báo và cho tải lại. Kiểm tra nền vàng không bị lấy nhầm màu đường kẻ; chữ có tương phản trên nền tối; không tách dấu Unicode khỏi ký tự. |
| Văn bản và lịch sử | Chọn/đảo chiều, clipboard, tải TXT đúng UTF-8, lưu/mở lịch sử và phân tách theo tài khoản. Giới hạn 30 mục. |
| Tài liệu | Test PDF có text, OCR chữ trong ảnh, DOCX/TXT, giữ vị trí trang; xuất PDF hợp lệ, phụ lục chữ dài, dịch lại tải đúng bản mới, không công bố PDF dở dang. Đây là kiểm thử kỹ thuật, không chứng nhận chất lượng mọi PDF thực tế. |
| Đăng nhập/quản trị | Đăng nhập đúng/sai, hiện/ẩn mật khẩu, đăng xuất, chuyển trang, phiên hết hạn và phân quyền backend. User không có thao tác quản trị. Xóa user chỉ gửi DELETE sau Xác nhận xóa; Hủy không gửi. Test xóa dùng DB/giao diện fixture, không xóa user thật. |
| Responsive | Ba chế độ và đăng nhập đã thử ở độ rộng 320, 375, 620/768, 820, 1024, 1440 px; không tràn ngang, không lỗi JavaScript trong các lượt kiểm tra. |
| PWA | Manifest/icon hợp lệ, service worker hoạt động; trang chủ tải được khi offline trong Chrome kiểm thử. Cache không chứa endpoint API/tài khoản. Chưa thử cài trên điện thoại thật. |

Các phản hồi giả lập chỉ dùng cho kiểm thử giao thức/UI trong phiên riêng, chặn mọi mạng ngoài. Không dùng chúng làm bản dịch thật hoặc làm bằng chứng về chất lượng mô hình.

## Kiểm tra mô hình thật

Dùng đúng mô hình đang được tài khoản duy nhất đã kết nối chọn, không đổi mô hình và không fallback. Ba ảnh tự tạo chỉ chứa nội dung kiểm thử, không có giấy tờ cá nhân. Có ghi nhận mức sử dụng của ba yêu cầu thật; không thêm bản dịch thử vào lịch sử user.

| Ảnh | Kết quả |
| --- | --- |
| PNG tiếng Anh, nền trắng, 6 dòng/ô | Nhận đúng `en`, đủ 6 vùng; bản Việt giữ NGUYEN ANH, KG-2026-001, ngày 13/11/2026 và 1,250 USD. **10,5 giây**. |
| JPEG tiếng Hàn kèm nhãn Anh, nền vàng, 6 dòng/ô | Nhận đúng `ko`, đủ 6 vùng; bản Việt giữ KIM MINJI, 2026-11-13, 50 USD, KR-001. **8,5 giây**. |
| PNG trắng không chữ | Nhận đúng không có chữ đọc được, không tạo nội dung dịch. **3,9 giây**. |

Hai kết quả mô hình thật được đưa vào chính thành phần xuất PNG của app; kiểm tra toàn bộ chữ được vẽ, tải PNG thành công và xem lại ảnh. Bản Hàn có một tiêu đề dài hơn khung gốc nên được đưa đầy đủ xuống phần tiếp nối. Các thời gian trên chỉ áp dụng cho mẫu này, không phải cam kết cho mọi ảnh.

Trước đợt này, ảnh chụp biểu mẫu Apostille của người dùng cũng đã được dịch thật, nhận đúng tiếng Tây Ban Nha và tải PNG. Chữ nhỏ/mờ trong ảnh đó vẫn có nội dung không đọc rõ, cho thấy kiểm thử ảnh rõ không đại diện cho mọi giấy tờ thực tế.

## Giới hạn còn lại

- Không thể bảo đảm dịch đúng mọi ảnh: ảnh mờ, mất chữ, bị cắt, chữ viết tay/trang trí, dấu đè chữ hoặc chữ quá nhỏ có thể sai/bỏ sót. Mô hình cũng có thể đặt tọa độ chưa chính xác.
- Ghép bố cục gần đúng. Chữ dài có thể chuyển xuống phần tiếp nối; vùng chồng lấn giữ phần gốc để tránh phá khung. Nền hoa văn dưới chữ không được phục hồi chính xác.
- Chỉ hỗ trợ ảnh PNG/JPEG/WEBP trong giới hạn nêu ở README, và 16 lựa chọn ngôn ngữ hiện có. Chưa hỗ trợ HEIC/GIF/TIFF/BMP.
- Không có kiểm thử chất lượng bởi chuyên gia cho toàn bộ 16 ngôn ngữ; không có chứng nhận pháp lý/độ chính xác 100%. Các giấy tờ quan trọng cần đối chiếu bản gốc.
- PWA có manifest, service worker và cache giao diện; chưa xác nhận cài trên điện thoại thật. Cần mạng để dịch và đăng nhập; đây vẫn là bản chạy local theo cấu hình hiện tại.
- App áp dụng nội dung skill Translator Pro đã đóng gói, không tự gọi plugin đang mở trong ChatGPT và không cam kết kết quả giống hoàn toàn giao diện chat.

## Chạy lại kiểm thử

```powershell
docker compose -f compose.test.yaml run --build --rm tests
cd frontend
npm ci
npm run build
npm run test:image-layout
```

Container test không có mạng, không gắn volume tài khoản sản xuất. Bộ kiểm thử trình duyệt và ảnh mẫu thực tế của đợt kiểm tra nằm trong thư mục `work` của workspace, ngoài ZIP source ứng dụng; không chạy inference thật tự động khi chạy pytest.
