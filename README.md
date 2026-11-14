# KUN GLOBAL · ChatGPT riêng cho từng người dùng

Web App dịch đa ngôn ngữ bằng gói ChatGPT của chính người dùng, không cần khóa API. React/TypeScript + FastAPI; OCR Tesseract, đọc tài liệu và ghép PDF chạy trên máy cài app. Giao diện vàng nâu, logo KUN GLOBAL. Không có chức năng giọng nói.

**Bản này chạy trên máy riêng của từng người, mở bằng localhost. Admin có thể hỗ trợ kết nối trên bản cài local đó.** Chưa hỗ trợ dùng luồng đăng nhập này trên một web/VPS chung. Admin quản lý tài khoản trong từng bản cài; các máy độc lập không tự đồng bộ danh sách người dùng. Muốn quản trị tập trung qua VPS cần thiết kế riêng và quyền tích hợp OpenAI phù hợp.

## Cài và chạy

1. Cài Docker Desktop (Windows/macOS) hoặc Docker Compose (Linux). Mỗi máy dùng một bản source và volume dữ liệu riêng.
2. Trong thư mục này chạy `docker compose up -d --build`.
3. Lần cài mới, tạo admin bằng PowerShell: `./scripts/create-account.ps1 -Username admin-cua-ban -Role admin`. Script hỏi mật khẩu kín, gửi qua stdin; không ghi mật khẩu lên dòng lệnh. Nếu dùng bản bàn giao trên máy hiện tại, tài khoản đã có trong file riêng `kun-global-tai-khoan.txt`, nằm ngoài source ZIP.
4. Mở http://localhost:8080/ trên **cùng máy cài app** để xem landing page, rồi chọn **Truy cập công cụ dịch** hoặc **Đăng nhập**. Trang chủ dùng banner KUN GLOBAL, màu nâu vàng và giới thiệu 5 nhóm dịch vụ: dịch thuật, công chứng, hợp pháp hóa Bộ Ngoại giao, hợp pháp hóa tại Đại sứ quán và hỗ trợ trọn gói; thông tin liên hệ lấy từ banner. Trang đăng nhập ở `/login`, không gian dịch ở `/app`. Người đã đăng nhập có thể chọn **Mở ứng dụng** trên trang chủ.
5. Admin mở **Người dùng → chọn user → Kết nối ChatGPT** rồi bấm **Continue with ChatGPT**. Chọn tài khoản ChatGPT của user và cấp quyền trên `auth.openai.com` khi được chủ tài khoản đồng ý. Nếu OpenAI hiện ô tên tác nhân trong lần kết nối đầu tiên, giữ tên gợi ý **KUN GLOBAL**. Mỗi user gắn với một tài khoản ChatGPT riêng.
6. OpenAI chuyển về đúng user trong trang quản trị. App xác minh danh tính OpenAI rồi tải các mô hình thực tế của tài khoản. Khi trạng thái **Sẵn sàng dịch**, user chỉ cần đăng nhập app và dùng dịch văn bản/ảnh/tài liệu, không cần tự thực hiện bước kết nối. Kết nối lại có thể cần thiết nếu quyền bị thu hồi hoặc hết hạn không gia hạn được.
7. Admin tạo, đổi tên, đổi vai trò, khóa hoặc đặt lại mật khẩu app trong **Người dùng → Thông tin tài khoản**. Tạo user xong app mở ngay mục Kết nối ChatGPT. User chỉ thấy tài khoản app và trạng thái quyền sử dụng; các nút đăng nhập/cấu hình ChatGPT chỉ hiện trong giao diện admin. Admin có mục ChatGPT của tôi để kết nối tài khoản riêng của admin.

Máy hiện tại giữ nguyên tài khoản đã tạo; cập nhật bằng `docker compose up -d --build`, không dùng `down -v` vì sẽ xóa tài khoản và lịch sử. Source ZIP không có mật khẩu, token, DB, master.key, weights hoặc node_modules.

Trang đăng nhập `/login` dùng bố cục thương hiệu vàng nâu, ảnh địa cầu và form nền kem; thu gọn phần hình ảnh trên điện thoại. Form hỗ trợ trình quản lý mật khẩu, hiện/ẩn mật khẩu, trạng thái đang đăng nhập và thông báo lỗi. Tài khoản đã đăng nhập vào `/login` được chuyển tới `/app`.

Trang dịch `/app` dùng cùng logo, ảnh địa cầu, phông Arial và nền họa tiết vàng nâu với landing page và đăng nhập. Thanh điều hướng giữ ở đầu màn hình; ba chế độ văn bản, hình ảnh và tài liệu dùng khu vực làm việc nền kem. Trên điện thoại, thanh tiện ích thu gọn bằng biểu tượng và hai ô đọc xếp dọc. Giao diện được đóng phạm vi trong `translator.css` để không ảnh hưởng trang chủ và đăng nhập.

Chọn ảnh, PDF, DOCX hoặc TXT sẽ tự đọc và dịch theo ngôn ngữ đích đang chọn, rồi hiện kết quả trong khung bên phải. PDF giữ form tự tạo bản xem trước và file tải về. DOCX/TXT tự chuyển sang khung văn bản. Có thể bấm nút dịch để thử lại sau khi sửa nội dung hoặc đổi ngôn ngữ.

Ảnh dịch không bị chặn nếu một vùng OCR quá chật. Những đoạn vừa khung giữ vị trí; đoạn dài được đánh số tại vị trí gốc và ghi đầy đủ trong phần tiếp nối bên dưới ảnh, với cỡ chữ đọc được. Có thể cuộn/phóng to để xem; PNG tải về chứa cả phần tiếp nối và chú thích bản dịch máy. Kiểm thử bố cục: từ `frontend` chạy `npm run test:image-layout` bằng Node.js 22.6+ có hỗ trợ `--experimental-strip-types`.

Cỡ chữ ảnh được tính bằng chiều rộng và nét chữ thực tế, với mức mặc định 100%. Mỗi vùng được giới hạn trong khung OCR gốc. Vùng OCR gộp nhiều hàng hoặc chồng lấn không bị phủ bằng một khối màu lớn; nội dung gốc tại đó được giữ để đối chiếu và bản dịch đầy đủ nằm trong phần tiếp nối. Không phóng chữ theo chiều cao bất thường của vùng OCR.

PDF gốc có bản xem trước ngay từ file đã chọn trong trình duyệt, đồng thời máy chủ tiếp tục xử lý. PDF có lớp chữ đọc được sử dụng chữ và tọa độ sẵn có. Ảnh nhúng, trang scan và phần chữ cần khôi phục vẫn dùng OCR. Thời gian có bản dịch phụ thuộc nội dung, OCR và phản hồi của mô hình. Trình duyệt cần hỗ trợ xem PDF nhúng, hoặc có thể chọn Mở tài liệu gốc.

PDF tự nhúng phông bổ sung cho tên riêng và ký hiệu Unicode, gồm chữ Trung/Hàn và các chữ Hán mở rộng. Phông được chọn theo từng ký tự, dùng cho cả trang chính và phụ lục. Ký tự riêng hoặc mã chưa có glyph được giữ dưới dạng `[U+XXXX]` để không chặn xuất file hoặc bỏ mất mã ký tự đó. Ký hiệu được in theo phông đơn sắc của PDF.

**Tải PDF** và **Mở PDF** dùng liên kết trực tiếp tới bản PDF đã tạo, có kiểm tra tài khoản sở hữu và phiên bản bản dịch. Liên kết có hiệu lực trong phiên tài liệu đang giữ trên máy chủ. Sau khi phiên hết hạn hoặc máy chủ khởi động lại, hãy chọn file để xử lý lại.

Mỗi yêu cầu dịch nạp ba hướng dẫn `translation-router`, `faithful-translation`, `translation-review` từ Translator Pro 0.1.1 tại `backend/app/translation_skills/translator-pro/`. Đây là việc áp dụng các skill được đóng gói cùng ứng dụng, không phải gọi trực tiếp plugin từ giao diện ChatGPT. Mô hình được yêu cầu dịch giữ ý nghĩa, tên, số liệu, cấu trúc, rồi tự đối chiếu bản nháp với nguồn trong cùng yêu cầu; không phải một lượt thẩm định độc lập. Kiểm thử giao thức xác nhận hướng dẫn và dữ liệu được gửi, không chứng minh chất lượng bản dịch thực tế.

Tab Hình ảnh gửi ảnh gốc đã chuẩn hóa hướng xoay tới mô hình đã kết nối qua Responses `input_image`, `detail: high`, cùng ba skill Translator Pro. Mô hình đọc chữ, dịch, trả tọa độ vùng theo bố cục; ứng dụng ghép ảnh và xuất PNG. Chọn ảnh hoặc bấm **Dịch ngay** đều dùng luồng này, không dịch từ riêng bản OCR nhiễu. Cần mô hình/tài khoản hỗ trợ ảnh; nếu nhà cung cấp từ chối, ứng dụng báo lỗi thay vì giả vờ đã đọc ảnh hoặc tự chuyển sang phương án khác. Chữ rất nhỏ, mờ hoặc khuất vẫn có thể đọc sai; không cam kết ảnh ghép hoặc bản dịch giống tuyệt đối trong ChatGPT. Tham khảo [Images and vision](https://developers.openai.com/api/docs/guides/images-vision).

Ảnh hỗ trợ PNG/JPG/JPEG/WEBP, tối đa 10 MB và 64 megapixel đầu vào; ảnh trên 16 megapixel tự thu nhỏ để xử lý. Xoay EXIF được áp dụng trước khi tính tọa độ, nền trong suốt ghép trên trắng, JPEG CMYK chuyển RGB. WEBP động chỉ xử lý khung đầu và có thông báo. HEIC/GIF/TIFF/BMP chưa hỗ trợ; đổi sang PNG/JPG trước khi tải. File được kiểm tra cả nội dung, không chỉ đuôi tên.

Ảnh không có chữ đọc được trả thông báo rõ và không tạo bản dịch giả. Phản hồi thiếu vùng, sai tọa độ hoặc chưa hoàn tất không được xuất thành kết quả thành công. Chuyển tab/chọn nguồn không tự gửi dịch lặp; bấm **Dịch ngay** để dịch lại với lựa chọn mới. Chữ đọc từ ảnh ở chế độ chỉ xem, tránh sửa văn bản nhưng thao tác dịch lại lại dùng ảnh gốc. Lỗi mạng giữ file để thử lại; không cho tải nhầm kết quả cũ.

Phần ghép ảnh chọn màu nền theo vùng mẫu bao quanh, điều chỉnh tương phản chữ và ngắt dòng theo cụm ký tự Unicode. Không đè chữ vào ô bên cạnh. Vùng không vừa hoặc có tọa độ chồng lấn vẫn xuất đầy đủ trong phần tiếp nối dưới ảnh; bố cục có thể dài hơn ảnh gốc. Nền phức tạp/hoa văn bị phủ chữ không thể phục hồi nguyên bản bằng cách ghép này. Xem kết quả và giới hạn kiểm thử tại [QA-REPORT.md](QA-REPORT.md).

Các đoạn chú thích liền nhau cùng cột được dàn chung; cỡ chữ đoạn nhiều dòng tính theo diện tích, không đo toàn đoạn như một dòng. Khung chỉ chồng nhỏ được chia tại ranh giới để chữ vẫn xuất hiện ngay trên ảnh; đoạn văn giữ căn trái. Phần tiếp nối chỉ dùng khi nội dung vẫn không vừa hoặc tọa độ chồng lấn đáng kể.

## Xuất Word A4 nền trắng

Ứng dụng tự ưu tiên **giữ form gốc** khi toàn bộ bản dịch vừa khung và cỡ chữ đạt mức đọc được. Nếu có vùng tràn/chồng lấn không dàn được, hoặc chữ nhỏ hơn khoảng 9 pt ở kích thước trang, giao diện tự ưu tiên **Word A4 nền trắng**. Bạn vẫn có thể chọn xem/tải bản giữ form hoặc Word theo nhu cầu. Việc chọn định dạng không gọi dịch lại.

Sau khi dịch, chọn **Word A4** ở cuối ô Bản dịch; tài liệu PDF đã hoàn tất có nút **Tải Word A4** trên thanh tải file. Văn bản, ảnh và PDF đều xuất `.docx` chỉnh sửa được. Xuất Word dùng lại nội dung dịch hiện có, không gửi thêm ảnh/văn bản tới OpenAI và không tiêu hao thêm lượt dịch.

Ảnh/PDF được dò đường kẻ tại máy chủ để dựng bảng Word thật, gồm các ô gộp; chữ đặt vào ô tương ứng, đoạn ngoài bảng giữ thứ tự và vị trí cột tương đối. Nền giấy trắng, chữ/khung đen, khổ 210 × 297 mm, không nhúng nền vàng hoặc toàn bộ ảnh gốc. Không sao chép đồ họa con dấu/chữ ký vào Word; chữ đọc được trên dấu vẫn được xuất. Các nhãn ngắn lặp cùng ý do bản gốc đa ngôn ngữ được gộp, không rút gọn đoạn nội dung hoặc tên/số liệu.

Chiều cao dòng/ô tự tăng và nội dung dài có thể sang trang A4 tiếp theo để không bị cắt. Đây là bảng/chữ Word, không phải phục chế chính xác từng pixel. Đường kẻ mờ/đứt, ảnh nghiêng, khung không nhận diện được có thể chỉ xuất chữ theo thứ tự/cột; cần đối chiếu tài liệu gốc. Nội dung mô hình không đọc rõ vẫn được đánh dấu như trong bản dịch, không tự đoán lại khi xuất Word.

API: `POST /api/export-word` (văn bản), `POST /api/export-word-image` (ảnh + bố cục đã dịch) và `POST /api/documents/export-word` (phiên PDF của chính tài khoản). Xuất file không yêu cầu gọi lại mô hình. Container production không cần cài Microsoft Word hay LibreOffice.

## Đăng nhập ChatGPT chính thức

Theo [Registration and sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in), bản local dùng public-client OAuth: PKCE S256, state/nonce ngẫu nhiên, đăng ký động với tên KUN GLOBAL và mã máy ổn định. Callback HTTP đúng `http://127.0.0.1:17653/auth/callback`, không dùng localhost thay cho 127.0.0.1 tại callback. Listener chạy trước khi mở trang đăng nhập.

App xác minh chữ ký ID token từ JWKS, issuer, audience của client ID được cấp, thời hạn và nonce. Callback gắn với phiên app đang hoạt động, dùng một lần. Khi admin hỗ trợ, app lưu riêng người khởi tạo (actor) và user sở hữu kết nối (target); việc đổi user trên giao diện không đổi đích của callback. Backend kiểm tra admin còn quyền, phiên còn hiệu lực và user đích còn hoạt động trước/sau trao đổi token. Hủy hoặc bắt đầu lại lượt kết nối sẽ vô hiệu callback cũ. Email không khớp thì không ghi đè kết nối hiện có. Client ID được OpenAI cấp được lưu riêng theo user để kết nối lại. Quyền dùng gói lấy từ scope trong phản hồi token, không lấy từ query của callback; chỉ đăng nhập nhận diện chưa đủ để dịch. Một danh tính ChatGPT không được gắn cho nhiều user trong cùng bản cài.

Token truy cập/gia hạn lưu mã hóa Fernet trong SQLite; khóa mã hóa ở `/data/master.key`, quyền 0600. Không trả token cho frontend, không lưu token trong localStorage hoặc log callback. Token chỉ gửi qua HTTPS tới endpoint OpenAI cố định. Gia hạn tuần tự theo user, lưu refresh token đã xoay vòng. Nút **Ngắt kết nối ChatGPT** xóa token local và thử thu hồi tại OpenAI; nếu chưa xác nhận thu hồi, giao diện báo rõ để bạn ngắt app trong ChatGPT Settings → Usage. Đăng xuất tài khoản app không tự ngắt kết nối ChatGPT.

Bản này giữ một đăng ký ChatGPT cho mỗi user. Kết nối lại yêu cầu đúng danh tính đã đăng ký; chưa có trình quản lý nhiều profile/workspace hay chuyển một user sang danh tính ChatGPT khác.

Theo [Models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference), backend lấy model từ catalog của chính tài khoản, dùng slug được trả về, gọi Responses công khai với OAuth bearer, `store:false`, `stream:true`. Chỉ nhận thành công sau sự kiện `response.completed` và đủ mọi vùng dịch. Không gọi endpoint ChatGPT nội bộ, không dùng API key, không tự fallback sang mô hình khác. Cấu hình API key chung của bản cũ đã ngừng hoạt động.

Văn bản, thuật ngữ và ảnh chọn trong tab Hình ảnh được gửi đến OpenAI để dịch. PDF gốc và OCR của luồng PDF vẫn xử lý tại máy bạn; văn bản trích xuất được gửi tới mô hình. Hạn mức, mô hình và quyền truy cập phụ thuộc gói/tài khoản và khả năng cấp quyền của OpenAI. Đây là luồng preview; đăng nhập hoặc inference có thể bị từ chối nếu tài khoản chưa đủ điều kiện. Không hứa mọi tài khoản đều dùng được. Phí gói ChatGPT, điện, dung lượng và vận hành máy vẫn có; không có nghĩa dịch không giới hạn.

## Cấu hình và xử lý lỗi

Sao chép `.env.example` thành `.env` nếu cần đổi cổng:

- `PORT=8080`, `APP_ORIGIN=http://localhost:8080`: đổi cả hai khi đổi cổng giao diện. Dùng localhost nhất quán khi đăng nhập và quay lại để cookie app khớp.
- `BIND_ADDRESS=127.0.0.1`: giữ truy cập trên máy local.
- `CHATGPT_CALLBACK_PORT=17653`: đổi nếu cổng bận, rồi chạy lại Docker. Compose chỉ mở cổng callback trên loopback của máy chủ. Không chuyển tiếp cổng này ra Internet.
- `COOKIE_SECURE=false`: localhost HTTP. Luồng này không hỗ trợ triển khai web công khai chỉ bằng cách đổi APP_ORIGIN sang tên miền; app tự tắt kết nối ChatGPT cá nhân khi origin không phải loopback.

Nếu sau đăng nhập vẫn chưa dịch được: mở ChatGPT của tôi, kiểm tra đã cấp quyền dùng gói chưa, bấm Làm mới trạng thái hoặc kết nối lại. Nếu không có catalog/model thì không có mô hình mặc định giả. Hết hạn mức: xem [ChatGPT Usage](https://chatgpt.com/#settings/Usage). Lỗi stream/mất mạng/thiếu vùng sẽ không xuất bản dịch dở như bản hoàn chỉnh.

Máy dùng Docker chứa SQLite và master.key trong volume `saeng_accounts`. Sao lưu cả hai, hạn chế quyền truy cập; quản trị viên hệ điều hành có thể truy cập dữ liệu trên máy. Không sao chép volume chứa token và host ID sang bản cài của người khác: mỗi máy phải đăng ký host riêng và tự kết nối ChatGPT. Source mới không mang theo volume. Mất master.key cần khôi phục từ bản sao lưu để đọc token cũ.

Không Docker: Python 3.11+, Tesseract và các font cần thiết; `pip install -r backend/requirements.txt`. Đặt DATABASE_PATH vào thư mục ghi được và APP_ORIGIN=http://localhost:5173. Từ backend chạy `uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1`; frontend chạy `npm ci` và `npm run dev`. Listener mặc định bind 127.0.0.1:17653. Không chạy nhiều worker vì phiên PDF trong RAM và listener callback chỉ có một cổng.

## Giao diện user và quyền sử dụng

Khi chưa có kết nối hợp lệ/mô hình khả dụng, user thấy **Vui lòng liên hệ admin để được trợ giúp cấp quyền sử dụng.** User không có tab/nút kết nối ChatGPT. Trạng thái sẵn sàng cập nhật tự động sau khi admin kết nối thành công. Nút dịch văn bản/ảnh/PDF tự động bị vô hiệu khi chưa được cấp quyền; backend cũng chặn, không chỉ ẩn nút.

Lỗi quyền/hết hạn tới user được chuyển thành hướng dẫn liên hệ admin, còn admin giữ thông tin chẩn đoán kết nối. Các thông tin email, client ID và thao tác OAuth không được hiển thị trong giao diện user. Theo cấu hình giao diện được yêu cầu, nhãn sử dụng gói ChatGPT và liên kết hạn mức chỉ xuất hiện với admin, không còn trong màn hình dịch hay Tài khoản của user. Thông tin xử lý dữ liệu vẫn được giữ. Thay đổi giao diện không làm thay đổi chủ tài khoản, hạn mức thực tế hoặc yêu cầu chủ tài khoản đồng ý sử dụng gói. Trước khi phân phối tích hợp SIWC, cần rà soát lại yêu cầu hiển thị trong tài liệu OpenAI; bản giao diện này không được coi là xác nhận đã đáp ứng toàn bộ yêu cầu thương hiệu/UX của OpenAI.

## Quản lý toàn bộ tài khoản

Admin mở nút tài khoản ở đầu trang để vào mục Người dùng. Trang này liệt kê tất cả tài khoản trong cùng bản cài, gồm admin/user và tài khoản đã khóa. Có thống kê tổng/hoạt động/khóa/admin, tìm theo tên, lọc vai trò/trạng thái và phân trang 20 mục.

Chọn một tài khoản để đổi tên, phân vai trò, khóa/mở khóa hoặc đặt lại mật khẩu; mật khẩu hiện tại không đọc lại được. Admin không thể tự khóa tài khoản đang dùng hoặc bỏ quản trị viên hoạt động cuối cùng. Tạo tài khoản mới xong có thể kết nối ChatGPT riêng cho user đó trong tab Kết nối ChatGPT.

Danh sách hiển thị số phiên app còn hạn và số mục lịch sử, không trả về nội dung lịch sử/mật khẩu/token. Nút Đăng xuất mọi thiết bị thu hồi toàn bộ phiên app của tài khoản đã chọn; giữ nguyên dữ liệu và kết nối dịch đã lưu. Nếu admin chọn chính mình, phiên hiện tại cũng đăng xuất và cần đăng nhập lại. Yêu cầu đã bắt đầu xử lý có thể hoàn tất; các yêu cầu mới phải đăng nhập lại. Đổi mật khẩu/vai trò/khóa tài khoản cũng thu hồi các phiên cũ.

Phạm vi quản lý là cơ sở dữ liệu của bản cài hiện tại, không tự đồng bộ tài khoản giữa nhiều máy độc lập.

## Tài khoản và tài liệu

User quản lý tên/mật khẩu, lịch sử 30 mục và tài liệu của mình; các thao tác cấu hình kết nối nằm ở trang admin. Admin thêm quyền kết nối ChatGPT hộ theo từng user, chọn mô hình/ngắt kết nối, quản lý user và xem số lượt/token ghi nhận trong 30 ngày, không có giao diện đọc token ChatGPT của user. Đổi mật khẩu/khóa/đổi vai trò thu hồi phiên app; giữ admin hoạt động cuối cùng. Password scrypt có salt, phiên HttpOnly/SameSite 12 giờ, kiểm tra Origin/header và giới hạn đăng nhập sai. Quyền/lịch sử/PDF được kiểm tra ở backend theo user.

- 20 ngôn ngữ dùng chung cho văn bản/ảnh/tài liệu: Việt, Lào, Anh, Thái, Trung, Khmer, Nhật, Hàn, Pháp, Đức, Tây Ban Nha, Nga, Indonesia, Malay, Myanmar, Hindi, Ý, Bồ Đào Nha, Hà Lan và Ả Rập. Tự phát hiện nguồn, chọn/đảo chiều, sao chép, tải TXT. Văn bản nhập/trích xuất tối đa 12.000 ký tự; luồng đọc ảnh trực tiếp nhận tối đa 1.000 vùng và còn phụ thuộc giới hạn mô hình. Lịch sử quá giới hạn ký tự có thể không lưu được nhưng kết quả dịch vẫn được giữ để tải.
- Docker cài traineddata Tesseract cho đủ 20 ngôn ngữ trên, thêm Gothic cho tài liệu chữ trang trí. Có traineddata không đồng nghĩa OCR sẽ đọc đúng mọi ảnh mờ/viết tay.
- Trích xuất PDF có text, DOCX, TXT; ảnh tối đa 10 MB.
- PDF: 30 MB, 10 trang, 400 vùng, 24.000 ký tự; đọc cả chữ trong ảnh. PDF giữ form hỗ trợ Việt/Anh/Pháp/Đức/Tây Ban Nha/Indonesia/Malay/Nga/Ý/Bồ Đào Nha/Hà Lan. Các hệ chữ còn lại tự xuất Word A4, vẫn dịch đầy đủ nội dung đã đọc được. PDF tràn có thể có phụ lục; giao diện ưu tiên Word A4 thay vì ép chữ nhỏ. Word Ả Rập có thuộc tính RTL/Bidi.
- Phiên PDF giữ 20 phút không thao tác, tối đa 3 phiên/user và tổng 100 MB nguồn trên máy. Sau khi hoàn tất, frontend lấy sẵn bản PDF để tải/mở; dịch lại hoặc đổi đích sẽ xóa bản tải cũ. Bản tạm mất khi rời mục Tài liệu/đăng xuất/reload.
- OCR và mô hình đọc ảnh đều có thể bỏ sót chữ nhỏ/mờ. Bố cục ghép gần đúng, chưa bảo đảm giống tuyệt đối hoặc dịch chuẩn mọi hồ sơ. Không có phương pháp nào bảo đảm khôi phục nội dung đã mất trong ảnh nguồn.

PWA có manifest, cache giao diện và icon; dịch cần mạng. Chưa xác nhận cài trên điện thoại thật. Bản đăng nhập local này cần trình duyệt trên máy cài app; mở từ điện thoại khác qua LAN không phải luồng được hỗ trợ.

## Kiểm thử

`docker compose -f compose.test.yaml run --build --rm tests`

Môi trường test không gắn volume tài khoản thật, không mở cổng và không có mạng. Test dùng DB tạm, JWT ký bằng khóa fixture và MockTransport; không gửi dữ liệu/tài khoản thật tới OpenAI, không dùng bản dịch giả để chứng minh chất lượng. Xem VERIFICATION.md. Cần người dùng tự đăng nhập và cấp quyền trước khi xác nhận inference thật. M2M100 và code API-key cũ chỉ còn lưu trữ, không fallback tự động; README-LOCAL-LEGACY.md không áp dụng cho bản hiện tại.
