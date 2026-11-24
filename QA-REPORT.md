# Kiểm tra chức năng KUN GLOBAL — 13/11/2026

## Chuyển sang OpenAI API dùng chung — 23/11/2026

Production dùng APIEngine, lấy khóa/model chung từ cấu hình admin (khóa lưu mã hóa ưu tiên hơn biến môi trường backend). Văn bản, ảnh trực tiếp, PDF gốc và bước nhóm nhãn–giá trị dùng cùng API; vẫn áp dụng hướng dẫn Translator Pro và các kiểm tra đủ trang/vùng, dựng khung Word. Không dùng OAuth cũ làm fallback. Tắt callback listener và bỏ port 17653 khỏi compose; endpoint OAuth cũ trả 410 trong chế độ triển khai. Giữ DB tài khoản/lịch sử/kết nối cũ, không xóa hoặc chuyển mật khẩu.

Admin có Lưu cấu hình API, Kiểm tra kết nối bằng một câu thử, Xóa khóa đã lưu; không trả/đọc lại khóa. Lưu khóa chỉ báo đã cấu hình, không giả xác nhận kết nối. User không thấy phần cấu hình API và không cần kết nối ChatGPT. Có chú thích phí API riêng. Kiểm thử API không mạng xác nhận khóa mã hóa/không lộ, phân quyền admin/user, API dùng chung, usage theo user, lỗi key/quota/provider, ảnh và nguyên PDF đi đúng endpoint, Word dùng lại kết quả, xác thực cấu hình và khóa từ env. UI fixture xác nhận trường khóa ẩn/clear sau save, giữ khóa khi bỏ trống, test chỉ gọi khi chủ động, báo lỗi, xóa khóa, user không thấy cấu hình và responsive 320/375/768/1280.

Suite cuối đạt **224 passed, 4 skipped** trong container không mạng/DB tạm; build TypeScript/Vite và Docker đạt. Không có khóa API thật được cung cấp trong lần chuyển đổi; chưa kiểm chứng inference tính phí bằng API. Phản hồi model trong test là fixture. Các kiểm thử OAuth cũ chỉ còn dùng adapter được inject tường minh trong fixture, không đại diện provider triển khai mới.

## Đối chiếu PDF scan mẫu thực tế — 17/11/2026

Đã kiểm tra mẫu người dùng 2 trang bằng luồng dịch thật. Bản dựng ban đầu kéo thành 10 trang do các cột hẹp và nhiều bảng sát nhau. Sửa nhóm dòng/cột theo vùng giao nhau, tách ranh giới các bảng DOCX, đặt chiều rộng rõ ràng và mở rộng bảng nhiều cột khi cần A4 dễ đọc. Giữ các khung đơn trong luồng đầu trang, tách chữ dấu dọc ra khỏi ô tiêu đề, giữ mọi bản dịch và cỡ chữ các hệ chữ. Biểu mẫu mở dày đặc được đối chiếu lại bằng lượt mô hình bố cục chỉ trả ID vùng; không chỉnh tay các trường của mẫu. Xuất Word và bộ xem trước dùng cùng nhóm nhãn–giá trị.

Mẫu thực tế có 221 vùng dịch; kiểm tra nội dung DOCX cuối không mất vùng nào, không đổi các chuỗi số từ 4 chữ số trở lên giữa văn bản đã đọc và bản dịch, khung Apostille có 24 ô. Có 4 vùng chữ mờ/chữ ký được đánh dấu không đọc rõ. Không coi OCR hoặc số vùng là bằng chứng mọi chữ nguồn đều đã đọc đúng. Tệp gốc được giữ nguyên. Bản Word kiểm tra bằng Microsoft Word có 4 trang A4 để giữ chữ rõ; bố cục tương đối, không trùng phân trang 2 trang scan. Cũng render bằng `render_docx.py`/LibreOffice để kiểm tra lỗi dàn trang. Tệp và nội dung cá nhân chỉ lưu trong thư mục QA cục bộ ngoài source repo, không đưa vào Git/Netlify/source ZIP.

Suite backend đạt **216 passed, 4 skipped**; sau tinh chỉnh độ rộng trường dài và dấu dọc, **47 kiểm thử liên quan đạt**. Kiểm tra bao gồm đủ/thiếu/trùng/ID lạ trong bố cục, giữ nguyên văn bản, không gộp hai bảng liền nhau và không mất vùng khi dựng Word. Build frontend/Docker đạt; UI fixture kiểm tra nhóm trường trong ô kết quả, 20 ngôn ngữ, sửa nội dung và tải Word đạt.

## Định dạng Word theo cấu trúc PDF — 17/11/2026

Luồng đọc PDF yêu cầu metadata cho từng đoạn: vai trò, căn lề, cỡ chữ, đậm/nghiêng/gạch chân; bảng có số hàng tiêu đề lặp. Kiểm tra kiểu/enum/số hữu hạn trước khi công bố. Metadata đi xuyên qua kết quả, chỉnh sửa nội dung, bộ xem trước và Word. Giữ Title/Heading, định dạng chữ đen, cột song song, tỷ lệ cột, ô gộp và khoảng cách trước/sau bảng. Bỏ đường viền màu từ style Title của template; cột xác nhận căn giữa dùng không gian cột để tên không bị bó vào hộp chữ gốc. Ô giãn với nội dung và không dùng chiều cao exact.

Đã render mẫu tổng hợp có tiêu đề, bảng ô gộp, nhãn/giá trị, hai cột xác nhận và ghi chú bằng `render_docx.py`, xem ảnh một trang. Đã dịch thật thêm PDF tự tạo qua kết nối đang có: 15 vùng, 1 bảng, 1 ô gộp, nhận được metadata định dạng; xuất Word và render/kiểm tra một trang. Sau khi điều chỉnh chiều rộng cột, dựng lại cùng kết quả mô hình mà không gọi dịch lần nữa. Không gửi giấy tờ cá nhân để kiểm thử. Chất lượng cấu trúc trên mẫu không chứng minh mọi PDF hoặc bản dịch đều đúng tuyệt đối.

Build TypeScript/Vite và Docker đạt; UI fixture kiểm tra 20 đích, ẩn câu lệnh, định dạng tiêu đề, bảng, tải Word, sửa bản dịch, đổi đích, retry và responsive 320/375/768/1280px. Suite backend cuối đạt **209 passed, 4 skipped** trong container không mạng/DB tạm; một cảnh báo deprecated Starlette/AnyIO. Bộ kiểm thử bao gồm cả từ chối metadata lỗi, giữ kiểu chữ khi xuất, ô giãn, hàng tiêu đề và cột xác nhận đủ rộng.

## Tự áp dụng câu lệnh, bỏ ô nhập — 17/11/2026

Giao diện PDF sang Word chỉ cần chọn tài liệu, nguồn/đích và bấm dịch. Đã bỏ ô câu lệnh, lời nhắc nhập câu lệnh và CSS không còn dùng. Câu lệnh nội bộ vẫn được tạo tại thời điểm gửi theo đúng ngôn ngữ đích và áp dụng hướng dẫn Translator Pro; không thay đổi bộ dịch/backend.

Build TypeScript/Vite đạt. Kiểm tra browser bằng fixture xác nhận không có ô/nội dung câu lệnh trên màn hình, gửi đúng yêu cầu nội bộ cho đủ 20 đích, giữ PDF gốc, kết quả/bảng/Word, cache tải, đổi đích vô hiệu kết quả cũ, sửa nội dung bản dịch, thử lại lỗi và responsive 320/375/768/1280. Không gọi mô hình thật trong lượt kiểm tra giao diện này.

## Mở đăng nhập ChatGPT và nhận kết quả ở tab gốc — 16/11/2026

Lần kết nối được báo lỗi vẫn ở trạng thái pending, cổng callback phản hồi; chưa có callback xác thực thành công. Đã thay chuyển trang hiện tại bằng mở tab từ thao tác bấm, giữ tab app gốc; cung cấp liên kết OpenAI và nút sao chép khi popup/trình duyệt nhúng không mở được. Chỉ chấp nhận origin auth.openai.com. Tự kiểm tra trạng thái cùng phiên app mỗi 3 giây trong lúc chờ, tải mô hình khi callback completed, báo failed/hết hạn và dừng polling khi rời thành phần. Không đổi quyền, cookie, tài khoản hay vòng xác minh OAuth.

Build TypeScript/Vite và Docker web đạt. Kiểm tra browser cô lập xác nhận mở popup bình thường, fallback khi popup bị chặn, giữ tab, sao chép, completed/tải mô hình, failed/hết hạn, chặn URL sai origin. Toàn bộ OAuth của test là fixture; chưa xác nhận chủ tài khoản hoàn tất đăng nhập thật sau thay đổi này.

## Sửa nhận kết quả streaming — 16/11/2026

Tái hiện thật lỗi PDF: máy chủ nhận `response.output_item.done` có bản dịch nhưng `response.completed` trả `output: []`, khiến parser cũ bỏ mất nội dung và endpoint trả 502. Thu các item đã hoàn tất theo `output_index` và dùng khi output cuối rỗng; vẫn bắt buộc trạng thái response completed, đủ thứ tự item và message completed. Không dùng delta hoặc kết quả dở dang.

93 kiểm thử trong `test_chatgpt.py` và `test_original_document.py` đạt ở container không mạng/DB tạm, gồm khôi phục item đúng thứ tự, tính usage, từ chối thiếu completed/failed/incomplete/message chưa xong và PDF→Word. Bản triển khai mới đã dịch thật một PDF tự tạo có câu tiếng Anh cùng ảnh chứa số tham chiếu 12345 sang hai đoạn tiếng Việt, giữ số và tạo DOCX 36.842 byte trong 6,6 giây. Không gửi tài liệu cá nhân để thử; kết quả này chỉ xác nhận mẫu kiểm tra, không chứng nhận mọi tài liệu/ngôn ngữ.

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

## PDF sang Word — cập nhật 14/11/2026

Luồng tài liệu mặc định đã chuyển sang Word: tải PDF → phân tích từng trang và ảnh chèn/scan → dịch → tạo DOCX trực tiếp. Analyze/complete nhận output_format=word; complete không gọi export_pdf, không inpaint nền, không phụ thuộc phông PDF hoặc khoảng trống trên ảnh gốc. API PDF giữ form cũ vẫn tương thích nhưng không nằm trong luồng tài liệu chính.

Dò bảng trước khi nhóm OCR để tách nhãn/giá trị theo ô; giữ chữ chú thích nhỏ đã nhận diện, không bỏ chữ hoa thông thường và không bỏ qua ảnh đính kèm. Word dùng A4 trắng, chữ 11pt, khung/bảng native có ô gộp và hàng tự giãn. Preview hiển thị cấu trúc bảng; Word tải về chứa toàn bộ các trang nhận diện được. OCR mờ không được tự bịa nội dung.

Kiểm chứng: 170 passed, 4 skipped trong container không mạng/DB tạm; frontend build đạt; test trình duyệt kiểm tra đủ 20 ngôn ngữ, tự phân tích, xuất Word, cache tải lại, đổi ngôn ngữ vô hiệu kết quả cũ, chỉnh sửa mới nhất, lỗi dịch/Word và thử lại, bố cục 320/375/768/1280px. Không gọi mô hình trong các test này. File Word layout fixture đã được Microsoft Word render thành hai trang và xem cả hai PNG: bảng/khung, tiếng Việt, chữ cuối trang, không nền vàng và không cắt chữ.

Kiểm tra trực tiếp localhost với PDF tự tạo hai trang xác nhận native text, ảnh chèn, full-page scan và bảng được phân tích. Tài khoản admin đang unconfigured; không thực hiện inference thật và không dùng fixture để khẳng định chất lượng dịch. PDF vẫn được phân tích khi chưa có kết nối; bước dịch/xuất bản dịch yêu cầu tài khoản đã được admin cấp kết nối hợp lệ. Dữ liệu tài khoản sản xuất được giữ nguyên.

## Sửa PDF hiển thị 2 trang nhưng báo giới hạn 10 trang — 14/11/2026

Nguyên nhân: PDFium/pypdf đọc được 2 trang nhưng PDFMiner/pdfplumber trả 0 trang từ cấu trúc tham chiếu của PDF. Giới hạn trang giờ đối chiếu số trang renderer; khi bộ trích xuất không thống nhất, pypdf dựng bản chỉ dùng cho phân tích trong RAM rồi kiểm tra lại đủ số trang. Bytes gốc lưu trong phiên và file gốc trên đĩa không thay đổi. PDF thật vượt 10 trang và PDF không phục hồi được có thông báo riêng.

Thử đúng tài liệu gây lỗi trong container không mạng xác nhận 2 trang, giữ nguyên bytes gốc. Đồng thời sửa chọn ngôn ngữ trên biểu mẫu có nền hoa văn: lấy bằng chứng rõ từ từng trang, giữ ngữ cảnh OCR đa ngôn ngữ và xác nhận nguồn Latin trên các ảnh tổng quan độc lập. Kết quả kiểm tra cuối: hai trang đều es, 0 ký tự Thái trong nội dung OCR; không gọi mô hình dịch hoặc đưa giấy tờ vào source/GitHub/Netlify.

Kiểm thử sau thay đổi cuối: 45 passed, 1 skipped cho PDF/OCR/Word, gồm phục hồi cây trang rỗng, giới hạn thật, lỗi phục hồi, trang đầu nhiễu và tài liệu xen kẽ ngôn ngữ. Đây là kiểm tra phân tích/OCR, không phải chứng nhận chất lượng bản dịch. Backend local đã build/cập nhật; tài khoản và dữ liệu trong volume giữ nguyên.

## Gửi PDF gốc và câu lệnh riêng — 14/11/2026

Luồng tài liệu mới chỉ gửi dịch khi người dùng bấm Dịch tài liệu. File được chọn hiển thị ngay tại trình xem local. Câu lệnh mặc định có thể sửa; đúng nội dung nhập được gửi cùng toàn bộ bytes PDF gốc qua input_file Base64/high detail, store=false, stream=true, bằng tài khoản ChatGPT của user. Không gọi Files upload API, không dùng Tesseract/PDFMiner cho luồng này, không tự điều khiển ChatGPT.com hoặc tạo lịch sử hội thoại trên website.

Kết quả phải có đủ số trang, dữ liệu vùng/bảng hợp lệ và response.completed trước khi tạo Word rồi cập nhật phiên. File Word dùng lại phản hồi; tải lại không gọi dịch thêm. Đổi file/câu lệnh/ngôn ngữ vô hiệu kết quả cũ ở UI. Nội dung đọc trực tiếp không được gán điểm OCR giả. Ghi chú không chắc chắn từ mô hình hiển thị riêng. Phiên/Word vẫn có kiểm tra chủ sở hữu.

Bộ đầy đủ đạt 189 passed, 4 skipped. Sau bổ sung giữ lựa chọn auto khi dịch lại và chỉnh nhãn nguồn, nhóm original-document/Word đạt 25 passed; frontend build đạt. Browser protocol fixtures kiểm chứng bytes PDF tại máy chủ HTTP nhận upload, bấm nút rõ ràng mới gửi, đúng câu lệnh nhiều dòng, đủ 20 lựa chọn, cập nhật ô kết quả/bảng, Word tải lặp không gọi lại, sửa bản dịch, thử lại lỗi, quyền truy cập và responsive 320–1280px. Đây là kiểm thử giao thức, không chứng minh chất lượng dịch thực tế.

Bản local mới đã chạy: endpoint prepare nhận PDF tự tạo hai trang và tạo preview mà không sinh khối OCR. Admin hiện unconfigured, nên chưa gọi mô hình thật cho luồng PDF gốc; không sử dụng tài liệu cá nhân làm đầu vào dịch trong đợt kiểm thử này. Netlify vẫn chỉ là bản xem giao diện đã xuất bản trước đó.
# Bản thử Netlify dùng API riêng ngày 23/11/2026

- Đã build TypeScript/Vite và kiểm tra 20 test cho validation, quyền gọi, file gốc, API key riêng từng request, phản hồi hoàn tất, quota và lỗi provider. Test hoàn toàn dùng fixture, không dùng khóa thật.
- Kiểm tra trình duyệt riêng: landing → bản thử, 20 ngôn ngữ, kiểm tra kết nối có chủ đích, dịch văn bản/ảnh/PDF/TXT, Word có bảng, xử lý lỗi và file quá dung lượng, giao diện 320/375/768/1280 px, xóa khóa khi tải lại, không lưu khóa vào localStorage/sessionStorage. Không có lệnh gọi OpenAI tính phí trong bài kiểm tra.
- Word mẫu kiểm thử xuất đúng A4 portrait, 1 bảng 2 hàng 4 ô, Arial 12 pt; đã render kiểm tra khung và tiêu đề màu đen. Đây là tài liệu fixture, không phải bản dịch thật của khách.
- Draft Netlify xác nhận `/api/trial` hoạt động, thiếu khóa trả 401, sai Origin trả 403, khóa giả được OpenAI từ chối và app trả 401 rõ ràng. Không công bố kết nối thành công bằng khóa thật khi chưa có khóa.
- Giới hạn bản thử: file 3 MB, văn bản 12.000 ký tự, thời gian chờ provider 50 giây; không xuất phản hồi incomplete, không tự lặp yêu cầu có thể tính phí. Quản trị local không được công khai.

# Giữ đúng loại đầu ra ngày 24/11/2026

- Văn bản → nội dung chữ/TXT; Word văn bản là lựa chọn thêm. Ảnh → PNG giữ đúng kích thước; PDF → PDF đủ trang, đúng kích thước cả trang ngang; DOCX → chỉnh chữ trong gói Word gốc thay vì dựng lại form.
- Backend: 232 passed, 4 skipped trong container riêng không mạng/không gắn volume tài khoản thật. Netlify: 26 kiểm thử validation, completeness, run IDs, tọa độ và schema parity đạt. Không có khóa hay lượt dịch tính phí trong bộ test.
- Kiểm thử trình duyệt với fixture riêng đạt xuất TXT/Word/PNG/PDF/DOCX, Word nhiều lô và ảnh nhúng, preview trước API, chặn PDF thiếu trang, 20 ngôn ngữ và 320/375/768/1280 px.
- File thực xuất từ trình duyệt: PNG 1000×700, đối chiếu điểm ảnh ngoài mọi vùng chữ hoàn toàn không đổi; PDF 3 trang A4 dọc/A4 ngang/A5 dọc khớp kích thước; DOCX giữ cấu trúc XML ngoài chữ, 93 run, header/footer, ô gộp và các phần không chỉnh sửa. Đã render và xem 3 trang Word cùng 3 trang PDF.
- Mẫu kiểm thử chỉ kiểm tra giao thức và cách xuất file, không phải minh chứng chất lượng dịch/OCR của OpenAI. Chưa có khóa API thật được sử dụng để đánh giá dịch cuối cùng.

# API chỉ dành cho admin — 24/11/2026

- Đã thay bản BYOK công khai bằng đăng nhập thật trên Netlify Functions; tài khoản và cấu hình dùng chung lưu mã hóa tại Netlify Blobs. Bootstrap tạo admin online riêng bằng mật khẩu mạnh, không đổi tài khoản local. File thông tin đăng nhập nằm ngoài repo và thư mục publish.
- 33 kiểm thử Node đạt: quyền admin/user, khóa không trả về, mã hóa, giới hạn đăng nhập sai, CSRF, ghi đồng thời, thu hồi phiên, khóa/xóa tài khoản và chặn xóa admin cuối cùng. Backend 232 passed / 4 skipped; nhóm API dùng chung 8 passed sau bổ sung xác minh lỗi user không hiện provider/model/quota.
- UI fixtures kiểm tra đăng nhập/đăng xuất, cả ba tab dịch và tài khoản user không có API/OpenAI/ChatGPT/model/hạn mức; không gọi endpoint admin. Admin có cấu hình, ô khóa dạng password, xóa nội dung khóa sau khi lưu, kiểm tra kết nối và quản lý user. Responsive 375/1280 px đạt. Bộ xuất văn bản/PNG/PDF/DOCX/ảnh nhúng/20 ngôn ngữ cũng đạt.
- Đã kiểm tra HTTP thật trên draft và production: khởi tạo kho mã hóa, admin đăng nhập, tạo user tạm, user đăng nhập, endpoint quản trị trả 403, khi chưa cấu hình chỉ báo liên hệ admin, khóa tài khoản vô hiệu phiên và xóa user tạm. Không gửi khóa giả lên production và không gọi OpenAI tính phí.
- Production: `6b059c9f4e2a26e3172edb2b`, https://kun-global-dichthuat-hoanganh.netlify.app. Chưa cấu hình khóa OpenAI thật; admin phải lưu và kiểm tra kết nối trước khi user dịch. Không coi các fixture là kết quả kiểm định chất lượng dịch thật.
