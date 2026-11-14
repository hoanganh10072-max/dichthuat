# Kiểm chứng hiện tại — Quản lý toàn bộ tài khoản (07/11/2026)

- Đã triển khai Docker local tại localhost:8080; backend healthy. Giữ nguyên hai tài khoản đang có và thông tin đăng nhập. Trang quản trị mở mặc định vào Người dùng; các phần kết nối và gói vẫn chỉ hiện cho admin.
- Danh sách toàn bộ tài khoản trong cùng bản cài có thống kê tổng/hoạt động/khóa/admin, tìm tên, lọc vai trò/trạng thái, phân trang 20 mục, ngày tạo, số phiên app còn hạn và số mục lịch sử. API chỉ trả thông tin tài khoản công khai và số đếm, không trả nội dung lịch sử, mật khẩu hoặc token.
- Admin có thể tạo, đổi tên, đổi vai trò, khóa/mở khóa và đặt lại mật khẩu; các ràng buộc không tự khóa và giữ admin hoạt động cuối cùng được giữ. Thêm nút Đăng xuất mọi thiết bị và endpoint chỉ dành cho admin; thu hồi phiên theo user, giữ lịch sử/kết nối. Thu hồi phiên của chính admin xóa cookie và cần đăng nhập lại.
- Kết nối ChatGPT riêng nằm trong tab của tài khoản được chọn. Tạo tài khoản mới xong mở mục kết nối hộ; callback quay về tài khoản đích, còn callback cho admin được đưa về ChatGPT của tôi để tải mô hình như trước.
- Suite cuối: 80 passed, 4 skipped trong 36.16 giây; một cảnh báo deprecated từ Starlette/AnyIO. Chạy bằng compose.test.yaml, DB tạm, không gắn volume triển khai và không có mạng. Test mới bao gồm liệt kê admin/user/đã khóa, số phiên chỉ tính còn hạn, không lộ bí mật/nội dung lịch sử, tạo/sửa/đặt lại mật khẩu/phân vai trò/khóa/mở khóa, thu hồi phiên đúng user, tự đăng xuất admin, biên quyền user/admin/CSRF và chặn callback khi phiên admin đã thu hồi.
- Frontend TypeScript/Vite build thành công; đã render kiểm tra user với quyền bật/tắt vẫn không lộ điều khiển gói và admin còn điều khiển riêng. Không chạy lại backend suite sau thay đổi nhỏ chống phản hồi tải danh sách cũ ở frontend; backend không thay đổi sau lần suite đạt 80 bài.
- UI thật đã kiểm tra bằng phiên admin hiện có: danh sách 2 tài khoản, tìm admin ra 1 mục, lọc Đã khóa ra 0 mục, lọc User ra 1 mục, chọn user xem biểu mẫu vai trò/mật khẩu/trạng thái/phiên, mở tab kết nối đúng user, mở biểu mẫu tạo mới rồi quay lại tài khoản cũ. Không submit tạo/sửa/khóa/reset/thu hồi phiên trên tài khoản triển khai để thử nghiệm.
- Kiểm tra responsive 390×844: viewport 390px, document 375px, panel 355px; không tràn ngang. Đã trả viewport desktop và để sẵn bảng quản lý tài khoản.
- Ảnh: kun-global-admin-quan-ly-tai-khoan.png, kun-global-admin-chi-tiet-tai-khoan.png, kun-global-admin-quan-ly-mobile.png trong outputs. Phạm vi quản lý là dữ liệu trong bản cài hiện tại, không tự gom tài khoản từ nhiều máy độc lập. Không có xác nhận inference/OAuth ChatGPT thật mới trong phiên này.

---
# Nhật ký bản trước — Thông tin gói chỉ dành cho admin (07/11/2026)

- Đã ẩn nhãn sử dụng gói ChatGPT và liên kết hạn mức trong màn hình dịch của user; dòng đó chỉ render cho admin khi sẵn sàng. Đã bỏ phần tương tự khỏi mục Tài khoản của user. Thông báo liên hệ admin khi chưa đủ quyền vẫn được giữ.
- Chỉ cập nhật frontend và hướng dẫn. Không thay đổi mô hình, phạm vi OAuth, chủ kết nối, quyền backend, giới hạn thực tế hoặc dữ liệu tài khoản. Thông tin gửi văn bản tới OpenAI vẫn giữ trong phần xử lý dữ liệu.
- TypeScript/Vite production build thành công cả local và Docker. Đã cập nhật riêng service web tại localhost:8080, backend hiện có healthy.
- Đã render component Tài khoản thật bằng React server renderer với fixture canTranslate=false và true: cả hai không có nhãn ChatGPT, URL quản lý hạn mức hoặc nút đăng nhập. Render vai trò admin vẫn có phần ChatGPT/hạn mức. Đây là kiểm tra UI với props fixture, không phải mô phỏng kết nối hoặc chất lượng dịch.
- Đã đăng nhập user hiện có qua trình duyệt và kiểm tra màn hình dịch/Tài khoản. Bundle thực tế index-C0m34Xap.js đã tải. Ảnh: kun-global-user-giao-dien-toi-gian.png và kun-global-user-tai-khoan-toi-gian.png trong outputs. Đã trả lại phiên admin và xác nhận trang quản trị còn các điều khiển kết nối.
- Không giả lập trạng thái ready trong DB triển khai và không đăng nhập ChatGPT/cấp quyền/inference thật. Chưa xác nhận UI trình duyệt với một kết nối ChatGPT thật sẵn sàng; trạng thái Tài khoản đã cấp quyền được kiểm tra bằng render fixture. Suite backend 74 passed/4 skipped là kết quả phiên trước, không chạy lại cho thay đổi hiển thị này.
- Thay đổi hiển thị không được coi là xác nhận đáp ứng toàn bộ yêu cầu thương hiệu/UX của OpenAI SIWC. Chủ tài khoản vẫn phải đồng ý việc dùng gói và các hạn mức thực tế vẫn áp dụng. Xem README trước khi phân phối.

---
# Nhật ký bản trước — Giao diện user theo quyền sử dụng (06/11/2026)

- Đã cập nhật Docker local và giữ nguyên tài khoản, lịch sử, kết nối hiện có. Tài khoản admin tạm thời đã đổi ở volume theo yêu cầu trước đó; không thêm mật khẩu mặc định vào source hoặc nới lỏng chính sách mật khẩu chung.
- User không có tab/nút đăng nhập hoặc cấu hình ChatGPT. Khi chưa đủ quyền, màn hình dịch và Tài khoản hiển thị: Vui lòng liên hệ admin để được trợ giúp cấp quyền sử dụng. Trạng thái kỹ thuật của kết nối được thay bằng trạng thái quyền sử dụng. Admin vẫn thấy ChatGPT của tôi và quản lý kết nối hộ từng user.
- Nút dịch văn bản/ảnh và PDF tự động bị vô hiệu khi chưa được cấp quyền. Backend chặn cả text/image/PDF; các lỗi cấp quyền hết hạn/hạn mức/dịch vụ được chuyển thành hướng dẫn cho user, còn admin giữ thông tin chẩn đoán. Nội dung tự phát hiện cùng ngôn ngữ chỉ được trả nguyên văn sau khi kiểm tra quyền.
- Khi đã được cấp quyền và dùng gói ChatGPT riêng, UI giữ dòng thông tin sử dụng gói và liên kết quản lý hạn mức theo hướng dẫn OpenAI; vẫn công bố việc gửi văn bản tới OpenAI. Đây là ẩn thao tác kết nối khỏi UI user, không phải che giấu nhà cung cấp hay mức sử dụng gói.
- Suite cuối: 74 passed, 4 skipped trong 43.31 giây. Một cảnh báo deprecated từ Starlette/AnyIO. Test chạy bằng compose.test.yaml với DB tạm, không gắn volume triển khai, không có mạng. Phản hồi nhà cung cấp là fixture, không chứng minh chất lượng dịch hoặc quyền ChatGPT thật.
- Kiểm thử mới đối chiếu thông báo user trên health/text/image/PDF, chặn bypass qua tự phát hiện cùng ngôn ngữ, ánh xạ lỗi401/403/429/500, giữ chẩn đoán riêng cho admin và giữ nguyên văn bản cùng ngôn ngữ khi user đã được cấp quyền.
- Frontend TypeScript/Vite production build thành công. Đã đăng nhập user thật của bản cài và xác nhận UI không có phần kết nối; màn hình dịch và mục Tài khoản đều hiện đúng thông báo liên hệ admin. Không thay đổi kết nối hoặc giả lập trạng thái ready trong dữ liệu thật. Đã đăng nhập lại admin và xác nhận các tab quản trị vẫn hiện.
- Ảnh UI thực tế: kun-global-user-lien-he-admin.png và kun-global-user-tai-khoan.png trong outputs. Chưa kiểm tra UI với kết nối ChatGPT thật sẵn sàng và chưa xác nhận lượt dịch OpenAI thật. Giữ các giới hạn OCR/bố cục/local/PWA đã ghi ở README.

---
# Nhật ký bản trước — Admin kết nối hộ từng user (06/11/2026)

- Đã cập nhật Docker local tại http://localhost:8080/, backend healthy. Các cổng vẫn chỉ mở 127.0.0.1:8080 và 127.0.0.1:17653. Giữ nguyên hai tài khoản và volume hiện có; không reset mật khẩu.
- Trong Người dùng, chọn user sẽ mở Kết nối ChatGPT; Thông tin user giữ các thao tác sửa tài khoản. Tạo user mới xong tự mở phần kết nối. Admin nhập email ChatGPT riêng của user rồi mở OAuth OpenAI. Không thu thập mật khẩu/cookie ChatGPT trong app.
- Backend tách actor_id (admin khởi tạo) và user_id (chủ kết nối). Callback kiểm tra nonce/chữ ký/danh tính/email, phiên admin, vai trò hiện tại và trạng thái user đích. Kiểm tra lại sau trao đổi token; lượt đã hủy/khởi tạo lại/hết hạn không được ghi đè token. Không dùng kết nối của admin làm fallback cho user.
- Callback quay về user đã chọn bằng dữ liệu lưu ở server, bỏ qua target giả trong query. User thường không truy cập endpoint hỗ trợ của admin; kết nối và token vẫn mã hóa riêng theo user. Giữ chặn cùng một danh tính ChatGPT dùng cho nhiều user.
- Suite cuối: 68 passed, 4 skipped trong 43.00 giây; một cảnh báo deprecation từ Starlette/AnyIO. Compose test không có mạng, không gắn volume tài khoản thật và không mở cổng. Test dùng JWT ký bằng khóa fixture và MockTransport, không chứng minh chất lượng dịch hoặc kết nối OpenAI thật.
- Test mới xác nhận admin kết nối cho user rồi user dịch được bằng kết nối đó mà không tự chạy OAuth; usage ghi đúng user, admin không bị đổi kết nối. Có test email sai không ghi đè kết nối cũ, thiếu quyền, user khóa/xóa, admin mất quyền/đăng xuất, hủy/khởi tạo lại giữa trao đổi token, hai lượt cho hai user không nhầm đích, migration schema cũ giữ tài khoản, HTTP loopback khôi phục đúng user và không làm lộ code/state.
- Frontend TypeScript/Vite build thành công cả local và Docker. Đã đăng nhập admin hiện có qua UI, thấy đúng hai tài khoản, chọn user và thấy biểu mẫu email/kết nối hộ. Kiểm tra URL quay về với trạng thái failed khôi phục đúng user; trạng thái kết nối hiển thị lấy từ backend. Không nhập tài khoản ChatGPT hoặc duyệt cấp quyền thay người dùng.
- Kiểm tra responsive 390×844: document rộng375px, panel355px, viewport390px; không tràn ngang. Đã khôi phục viewport desktop và để sẵn phần ChatGPT của user trong trình duyệt. Ảnh: kun-global-admin-ket-noi-ho.png và kun-global-admin-ket-noi-ho-mobile.png trong outputs.
- Chưa xác nhận callback/token/inference ChatGPT thật cho bất kỳ user nào trong luồng hỗ trợ mới. Chủ tài khoản cần đồng ý và admin/người dùng hoàn tất đăng nhập/cấp quyền trên OpenAI. Bản cài vẫn local; chức năng hỗ trợ không biến luồng này thành dịch vụ VPS dùng chung.

---
# Nhật ký bản trước — ChatGPT cá nhân (05/11/2026)

- Đã triển khai Docker tại http://localhost:8080/. Backend healthy; web chỉ mở 127.0.0.1:8080, callback chỉ mở 127.0.0.1:17653. Không đổi/xóa volume tài khoản hiện có.
- Mỗi user có kết nối OAuth ChatGPT riêng, mã hóa tại backend. Không có API key chung hoặc fallback sang M2M100. Admin vẫn quản lý user; tài khoản giữa các máy không tự đồng bộ.
- Nút Continue with ChatGPT đã gọi discovery thật và mở trang OpenAI chính thức: “Use ChatGPT to sign in to KUN GLOBAL”. Chưa chọn tài khoản hoặc đồng ý cấp quyền, chưa có callback/token thật và chưa xác nhận lượt dịch ChatGPT thật.
- Đã đăng nhập bằng hai tài khoản app hiện có. Admin thấy Người dùng và Sử dụng; user chỉ có Tài khoản và ChatGPT của tôi. Tài khoản được giữ nguyên sau cập nhật. Đã trả lại phiên admin và để sẵn mục ChatGPT của tôi.
- Frontend TypeScript/Vite production build thành công. Đã xem UI desktop và 390×844; màn hình kết nối không tràn ngang, viewport đã khôi phục. Đây là kiểm tra responsive, không phải xác nhận cài PWA trên điện thoại thật.
- Suite cuối: 54 passed, 4 skipped trong 30.11 giây. Một cảnh báo deprecated từ Starlette/AnyIO. Chạy với compose.test.yaml: không gắn volume triển khai, không mở cổng, không có mạng, DATABASE_PATH trong /tmp. 4 test inference thật được bỏ qua vì DB test không có kết nối ChatGPT thật.
- Test dùng JWT ký RSA bằng khóa fixture và httpx MockTransport. Đã kiểm tra PKCE/state/nonce, client ID được cấp, sai issuer/audience/hết hạn, callback dùng lại hoặc phiên app hết hạn, quyền lấy từ token response, catalog model riêng, chặn chia sẻ cùng danh tính giữa user, refresh tuần tự và xoay token, thu hồi thất bại báo rõ, origin remote bị chặn, SSE chưa hoàn tất không thành công, số vùng dịch đầy đủ, token usage theo user và quyền admin.
- Test PDF dùng tài liệu tổng hợp và nội dung fixture: dịch/xuất lại vi rồi fr, đọc PDF xác nhận bản mới, chặn tải nhầm đích cũ. Không dùng file cá nhân trong browser upload và không giao fixture như bản dịch thật.
- Giới hạn OCR, bố cục/font và chất lượng dịch vẫn áp dụng. Chưa đo chất lượng chuyên ngành/ảnh Gothic hoặc kiểm chứng mọi model có Structured Outputs qua gói ChatGPT thật. Không hứa mọi tài khoản đều có quyền dùng preview.
- Ảnh hiện tại: kun-global-chatgpt-ca-nhan.png, kun-global-chatgpt-admin-users.png, kun-global-chatgpt-user-mobile.png trong outputs. Các ảnh admin-api trước đây là bản cũ.

---
# Nhật ký bản trước — API key chung và tài khoản (05/11/2026)

- Docker đã cập nhật tại http://localhost:8080/. Backend runtime dùng OpenAI Responses API; không mount/chạy weights M2M100.
- Đã tạo hai tài khoản ngẫu nhiên riêng, admin và user; mật khẩu nằm trong file bàn giao riêng, không trong source ZIP. Đã đăng nhập cả hai qua UI, kiểm tra user chỉ có trang tài khoản còn admin có Người dùng/OpenAI API/Sử dụng.
- Đã khởi động lại backend và xác nhận tài khoản vẫn còn trong SQLite volume. Đăng nhập admin sau restart thành công.
- Toàn bộ suite: 36 passed, 4 skipped (25 giây). Test API sử dụng httpx MockTransport với phản hồi fixture, không chứng minh chất lượng dịch. 4 bài cần inference thật được bỏ qua khi thiếu cấu hình API.
- Đã kiểm tra cookie HttpOnly, CSRF, giới hạn đăng nhập sai, thu hồi phiên khi đổi mật khẩu/khóa user, giữ admin cuối cùng, lịch sử và PDF theo owner_id, user bị chặn API admin, khóa API mã hóa và không trả về cho client.
- Test PDF hợp đồng API đã tạo/xuất hai lần với hai ngôn ngữ đích, đối chiếu nội dung PDF và bản cache mới nhất; không giao PDF fixture như bản dịch thật.
- Frontend TypeScript/Vite build thành công. UI đã kiểm tra đăng nhập desktop, admin API/users, tài khoản user ở 390 × 844; viewport đã trả lại mặc định.
- Cấu hình triển khai hiện KHÔNG CÓ khóa OpenAI API. Không có lượt dịch OpenAI thật hoặc kết nối trả phí được xác nhận. Trang cấu hình được để sẵn cho admin nhập khóa.
- Giới hạn OCR, dàn trang và tập font PDF trước đây vẫn áp dụng. Chưa đánh giá chất lượng dịch chuyên ngành/ảnh Gothic với OpenAI.
- Bản PDF được chuẩn bị sẵn ngay sau khi hoàn tất; liên kết tải không gọi lại phiên máy chủ, và bản cũ được xóa khỏi UI khi dịch lại/đổi đích/sửa nội dung. Chỉ lưu tạm khi mục Tài liệu còn mở.
- Ảnh: outputs/kun-global-dang-nhap.png, outputs/kun-global-admin-api.png, outputs/kun-global-admin-users.png, outputs/kun-global-user-mobile.png.

---

# Nhật ký các phiên bản trước (M2M100, chưa áp dụng cho backend OpenAI)
# Biên bản kiểm thử — 04/11/2026

## Đã thực hiện

- Dựng Docker images backend, prepare, web thành công trên Docker Desktop Linux amd64.
- Tải weights thật `facebook/m2m100_418M`, snapshot **55c2e61bbf05dfb8d7abccdc3fae6fc8512fd636**. Chuyển CTranslate2 INT8 thành công; tokenizer và model tồn tại tại `models/m2m100` ở workspace bàn giao (ZIP source không chứa weights).
- FastAPI khởi động với `model=ready`. Backend chạy với cờ offline và mạng Docker internal; không gọi dịch vụ AI ngoài.
- TypeScript và production build frontend thành công trong Docker. `npm audit`: **0 vulnerabilities** ở lần kiểm tra cuối. Không phải chứng nhận toàn bộ hệ thống không có lỗ hổng; dependencies Python và base images chưa được audit toàn diện.
- **9 tests passed**, không skip trong lần kiểm tra cập nhật OCR tiếng Hàn: lỗi thiếu model, validation, TXT UTF-8, thứ tự DOCX, PDF scan, giới hạn file, Tesseract OCR ảnh tiếng Anh/Hàn thật, inference Việt↔Lào thật.
- Đã thêm `tesseract-ocr-kor`. Ảnh mẫu Nanum Gothic chứa `안녕하세요 한국어 번역` được OCR tiếng Hàn; test xác nhận đọc đúng `안녕하세요` và `한국어`. Chế độ tự nhận bố cục mặc định từng bỏ sót ảnh này; OCR Hàn dùng chế độ sparse text (`--psm 11`). Đây là kiểm thử ảnh tổng hợp rõ nét, chưa phải bộ đánh giá ảnh chụp thực tế.
- Giao diện gọi API dịch thật thành công. Chọn ngôn ngữ và lịch sử xuất hiện; lịch sử tồn tại sau reload. Đã xem ảnh desktop và viewport điện thoại 390 × 844; không tràn ngang (document 375px, viewport 390px gồm scrollbar).
- Nginx phục vụ `/sw.js`, manifest, icon; cấu hình PWA cache shell và bỏ qua mọi request `/api/`.

## Mẫu output thật (không sửa cho đẹp)

| Nguồn | Đích | Input | Output mô hình | Thời gian một lần |
|---|---|---|---|---|
| Việt | Lào | Xin chào, bạn khỏe không? | ທີ່ດີຕ້ອນຮັບ, ທ່ານມີຄຸນນະພາບທີ່ດີ? | 491 ms |
| Lào | Việt | ສະບາຍດີ | Chào mừng bạn | 144 ms |

Đây là đo câu ngắn sau khi nạp weights, không phải benchmark tải, không bao gồm thời gian download/cold start. Những output này cho thấy chất lượng chưa đáng tin cậy: ví dụ lời chào Lào đã được dịch thành “Chào mừng bạn”. Cần người biết cả hai ngôn ngữ đánh giá và cân nhắc fine-tune/thu thập dữ liệu song ngữ trước khi dùng nghiêm túc. MVP không sửa output bằng bảng tra hoặc dùng API AI khác.

## Chưa kiểm chứng

- Chưa cài PWA trên thiết bị Android/iPhone thật; chưa thử toàn bộ luồng khi tắt mạng. Có manifest, icon PNG và service worker nhưng không coi đó là bằng chứng cài đặt thành công trên mọi trình duyệt.
- Chưa benchmark nhiều người dùng, nội dung 12.000 ký tự, chất lượng dài/chuyên ngành hay toàn bộ 16 ngôn ngữ.
- OCR thật đã chạy tiếng Anh và Hàn trên ảnh mẫu rõ nét; traineddata Việt/Lào được cài nhưng độ chính xác trên ảnh Việt/Lào chưa chấm với bộ ảnh chuẩn.
- Chưa deploy VPS/domain/HTTPS; app đang phục vụ local tại http://localhost:8080.
- Không có đánh giá chất lượng định lượng hoặc nghiệm thu người bản ngữ; chưa có đăng nhập, queue phân tán hoặc lưu trữ backend.

## Trạng thái bàn giao

Browser đã kiểm tra mẫu nhỏ chứa vùng Gothic khó đọc: kết quả có 1 vùng uncertain, hiện PDF bản nháp/chưa đầy đủ, nút Tải PDF bản nháp và ô cam trên cả nguồn/lược đồ PDF dịch. Mẫu này chỉ kiểm tra cảnh báo bằng một vùng trích, không phải toàn bộ hồ sơ 7 trang. Ảnh kiểm tra tại `outputs/saeng-ocr-coverage.png`; không dùng ảnh này để tuyên bố dịch hết.

Cập nhật xử lý chữ bị sót: tìm dòng chữ in độc lập, thử lại vùng Latin yếu bằng PSM7 và Fraktur cục bộ. Thử thật trên mẫu Gothic cho thấy Fraktur đọc rõ Otorga a và dòng họ tên tốt hơn bộ spa; tiêu đề vẫn có chữ chưa chắc, không coi là hoàn thành 100%. Sửa nhánh thuật ngữ trước đây giữ nguyên các đoạn ASCII bao quanh khi dịch ngôn ngữ Latin. Thêm nhãn học thuật chung/giữ tên riêng theo OCR; không lưu họ tên, tên trường cụ thể hoặc bản dịch nguyên trang của mẫu vào app. Nền chữ xanh được xóa bằng độ sáng; chân dung được tránh bằng bộ Haar trong OpenCV, không gửi ảnh ra ngoài.

Lần chạy tự động cuối trên 7 trang: 52,4 giây phân tích, 81,8 giây trọn pipeline một lần (không benchmark); 8 vùng OCR chưa chắc, 10 vùng được heuristic coi là tên riêng. Tên riêng được giữ không đồng nghĩa OCR đã viết đúng tên. Đầu ra thật chưa biên tập nằm ở `outputs/unison-dich-ban-nhap.pdf` (8.051.073 byte). Đã render lại bằng Poppler; các mục chính Trao cho/Bằng/Hóa sinh lâm sàng và tên người được ghép bằng chữ rõ hơn. Vẫn còn lỗi dịch, chữ gốc/viết tắt hoặc vùng Gothic chưa đọc; không tuyên bố đã dịch hết. Hình đầu chữ lớn còn ở vùng tiêu đề chưa đọc chắc là một ví dụ giới hạn còn tồn tại. Giao diện nay báo rõ PDF bản nháp/chưa đầy đủ và có ô cam cho vùng nghi còn sót, thay vì chỉ báo PDF đã tạo.

29 kiểm thử toàn bộ qua sau thêm kiểm tra dòng bị bỏ sót, thất bại OCR phải đánh dấu uncertain, xóa mực xanh, Latin quanh thuật ngữ vẫn được dịch, nhãn học thuật/tên riêng tách biệt. 13 kiểm thử tài liệu được chạy lại trên bản cuối trong Docker và qua. TypeScript/Vite build qua, backend healthy. Không có phép chấm độ phủ hay chất lượng bằng ground truth; đếm vùng là heuristic, có cả báo nhầm/bỏ sót. Bản nháp chưa đủ để dùng làm bản dịch hồ sơ chính thức.

Sửa lỗi hồ sơ UNISON 7 trang: log thật cho thấy trước đó toàn bộ hồ sơ bị nhận là Thái và dừng do chạm 512 token sinh. Bổ sung OCR spa/fra/deu; nhận diện từng trang rồi truyền đúng nguồn vào mô hình: es, es, en, en, es, en, en. Chống sinh lặp trong chế độ tài liệu và tự chia đoạn nếu vẫn chạm giới hạn. Sửa lỗi dàn chữ chú thích ảnh nhỏ và cột đặt cạnh nhau; bảo vệ vòng dấu xanh/khối chữ liên tiếp thay vì nhận toàn bộ chữ xanh là dấu. Tài liệu thực tế đã qua analyze→complete→export không edits, tạo 7 trang tại `outputs/unison-dich-tu-dong.pdf`, 7.730.497 byte, 68,9 giây một lần chạy (không phải benchmark). Không có mảnh bị giữ gốc do mô hình trả rỗng trong lần cuối (`untranslated_count=0`), nhưng OCR vẫn có thể bỏ sót chữ nhỏ và còn lỗi dịch nghiêm trọng, ví dụ tên cơ quan/chữ Gothic bị hiểu sai. Không coi đây là bản dịch được chấm đạt chất lượng.

Đã render cả 7 trang bằng Poppler và đối chiếu bố cục: ảnh chân dung, khung, vị trí dấu/mã vẫn hiện; các cột chữ không bị dồn chồng nhau hoặc tràn khỏi trang. Trang 1/2/5 của nguồn có MediaBox ngang và Rotate=270; đầu ra chuẩn hóa rotation về trang dọc, kích thước nhìn giữ nguyên, không thể so sánh MediaBox thô để kết luận giữ khổ. Các chữ trong hình dấu/hoa văn/kiểu cổ có thể giữ nguyên hoặc bị OCR bỏ sót; không cam kết dịch được từng nét chữ. Bộ kiểm thử cuối 25 passed (22,88 giây), gồm PDF scan chữ xanh xen kẽ es/es/en, OCR Hàn/Anh thật, dịch mô hình thật, chia đoạn không bỏ nội dung, pixel dấu đỏ/xanh và mã máy. Docker/TypeScript build qua, backend healthy. Browser thử mẫu hai trang es/en qua bản đang chạy: hiển thị Đa ngôn ngữ: Español / English, Trang 1 ES/Trang 2 EN, PDF đã tạo và preview thật. Không tải lại PDF 7 trang qua browser trong lần kiểm tra này; file thật chạy toàn bộ API trong TestClient trên cùng code/model.

Cập nhật một nút dịch tự động: giao diện chỉ cần chọn file → Dịch tự động → Tải PDF. Phân tích/dịch/dàn chữ/preview chạy liên tục; bảng chỉnh sửa nằm trong phần tùy chọn đóng mặc định. Backend `/complete` dùng M2M100 cục bộ, thuật ngữ chung, quy tắc tách loại hình doanh nghiệp/phiên âm Pinyin, chuẩn hóa một số nhãn OCR, giữ nguyên số/mã; không nhập bản dịch thủ công. Xuất thô thực tế của chính mẫu người dùng tại `outputs/mau-pdf-dich-tu-dong.pdf`: 19 vùng, 12 vùng trong ảnh, một trang A4, 19.983.414 byte; 16,9 giây trên lần chạy đã nạp mô hình (không phải benchmark). So sánh pixel xác nhận dấu đỏ và hai vùng mã máy không đổi. Kiểm tra tọa độ tự dàn xác nhận không chồng dòng, gồm mã V8.0 được giữ nội dung nhưng dời xuống theo các dòng dịch. Đã render bằng Poppler và kiểm tra bản tự động cuối; chữ nằm trong khung, nhưng có các câu chưa tự nhiên, lỗi OCR và tên phiên âm không phải tên pháp nhân được xác minh. Không chỉnh sửa nội dung file này để tạo ấn tượng chất lượng máy tốt hơn.

Bộ kiểm thử đầy đủ 23 passed; sau tinh chỉnh cuối giữ mã đăng ký/chứng nhận, chạy lại 7 kiểm thử tài liệu trên container đang phục vụ và đều qua. Gồm luồng tự động bằng weights thật không truyền edits, xuất đúng PDF đã tạo trong phiên, từ chối xuất sai đích, và không commit kết quả dở dang khi mô hình lỗi. TypeScript/Vite và Docker build qua; backend healthy. Trình duyệt thử PDF tổng hợp 26.703 byte có chữ ngoài/trong ảnh: chỉ chọn file rồi bấm Dịch tự động, hiện PDF đã tạo và preview thật; không mở phần chỉnh sửa. Tải thành công `automatic-browser-test-dich.pdf` vào Downloads. Mẫu người dùng 19MB đã chạy toàn bộ qua API thật trong tiến trình test, không thử lại truyền file lớn qua browser do lần trước rất chậm. Không có nghiệm thu chất lượng dịch định lượng, chữ trong logo quá nhỏ/dấu vẫn có thể còn nguyên hoặc OCR bỏ sót; không bảo đảm mọi trang/bảng hoặc bố cục giống tuyệt đối.

Kiểm tra browser cập nhật dịch cả ảnh: mặc định checkbox dịch toàn bộ bật; file mẫu thật phân tích thành 19 vùng, các vùng ảnh xuất hiện trong danh sách chỉnh sửa; dịch thật trả nội dung Việt và đánh dấu tên công ty còn chữ nguồn. Đã nhập bản dịch minh họa đã rà soát qua giao diện cho các vùng, giữ mã V8.0, dựng preview PDF thật thành công. Ảnh đối chiếu giao diện lưu tại `outputs/saeng-document-with-image-text.png`. Nội dung minh họa được biên tập riêng, không phải bằng chứng mô hình tự dịch chuẩn.

Cập nhật dịch cả ảnh trong tài liệu (thay thế mặc định giữ nguyên ảnh ở phiên trước): `preserve_images=false` mặc định ở API và giao diện. OCR tách trang/ảnh nhúng, đọc được 19 vùng trên mẫu đã thử, trong đó 12 vùng trong ảnh chứng nhận. Đã chạy M2M100 thật cho các vùng này; bản thô vẫn có tên công ty giữ nguyên tiếng Trung và các câu dịch chưa đúng. Xuất thô bị từ chối khi còn glyph nguồn không hỗ trợ; không coi đó là xuất dịch hoàn chỉnh. Giao diện đánh dấu vùng rỗng/còn chữ nguồn/lặp từ để rà soát. Mã/số giữ nguyên, chữ trong dấu đỏ được nhận diện và giữ như một phần hình dấu. Chữ quá nhỏ/mờ hoặc bị OCR nhận nhầm là hoa văn có thể chưa được dịch.

Đầu ra minh họa mới ở `outputs/mau-pdf-dich-ca-anh.pdf` là bản đã biên tập riêng, gồm cả 12 vùng trong ảnh; không phải output tự động hoàn toàn, không đưa bản dịch mẫu vào code/thuật ngữ của app. OpenCV inpainting và màu nền cục bộ xóa chữ gốc; đã sửa lỗi vết chữ còn sót và thứ tự patch làm chồng dòng. Kiểm tra ảnh render bằng Poppler lần cuối: chữ Việt ở trong khung, các dòng không chồng nhau, vị trí trang/ảnh giữ nguyên. So sánh pixel vùng dấu đỏ và hai mã máy với nguồn đều không đổi. Hoa văn dưới vùng chữ chỉ phục hồi gần đúng; không bảo đảm mọi PDF. Bộ kiểm thử đầy đủ 20 passed; 4 kiểm thử PDF được chạy lại sau tinh chỉnh cuối và đều qua, gồm OCR ảnh thực, xóa mực nguồn và giữ pixel mã/dấu. TypeScript/Vite production build và Docker build qua, backend healthy.

Cập nhật PDF giữ form theo mẫu đính kèm: file gốc 19.120.722 byte, 1 trang 595×842 pt, không có lớp text, có 2 ảnh nhúng. Phân tích thực tế đọc tiếng Trung và tách 7 vùng ngoài ảnh. API thật đã nhận file >10MB, dịch, dựng preview và xuất PDF thành công (bản máy thô), không dùng API AI ngoài. Kiểm tra cuối trong container đang chạy: **19 passed**, không skip (10,63 giây); gồm từ chối PDF có AcroForm để không flatten/mất trường, giữ kích thước trang và ảnh nhúng, glyph tiếng Việt và thuật ngữ. Frontend production build và Docker build qua; backend healthy. Trình duyệt đã thử chọn file 19MB, phân tích, sửa chữ OCR, dịch thật, sửa bản dịch và xem trước PDF thực tế thành công. Chưa thử tải file qua nút tải trên trình duyệt; endpoint xuất PDF đã trả file thành công.

Xuất mẫu minh họa đã rà soát riêng tại `outputs/mau-pdf-dich-giu-form.pdf`: kích thước trang không đổi; so sánh ảnh render xác nhận pixel bên trong cả logo và giấy chứng nhận nhúng không đổi. Đã render bằng Poppler và kiểm tra lại lề, thụt đầu dòng, đường kẻ, tiêu đề, footer và glyph tiếng Việt. Phần chứng nhận trong ảnh và tên công ty cuối trang vẫn giữ gốc. Nội dung Việt trong bản minh họa được biên tập riêng để kiểm tra luồng review, **không phải output M2M100 tự động hoàn toàn, không được đóng vào bộ thuật ngữ/mẫu app và không được chứng nhận pháp lý**. Chưa bảo đảm mọi loại PDF/bảng nhiều cột hoặc bản scan có dấu lẫn chữ.

Cập nhật Tự phát hiện ngôn ngữ: 16 kiểm thử backend qua, bao gồm phát hiện Việt/Lào/Anh/Trung/Hàn/Nhật/Thái, từ chối nội dung chỉ có số/ký hiệu, giữ nguyên khi nguồn tự phát hiện trùng đích, dịch thật auto Anh→Việt và tự phát hiện/OCR ảnh mẫu Hàn thật. TypeScript/Vite và Docker build qua. Browser hiển thị mặc định Tự phát hiện→Việt; nhập câu tiếng Anh hiện `Đã phát hiện: English`, dịch thật trả văn bản Việt. Chưa benchmark khả năng nhận diện toàn bộ 16 ngôn ngữ, ảnh chứng nhận thực tế, tiếng Việt không dấu hay nội dung trộn ngôn ngữ. OCR auto so sánh điểm các traineddata cài sẵn, không bảo đảm luôn chọn đúng. `langid==1.1.6` chạy offline; không gọi dịch vụ nhận diện bên ngoài. Nginx tách quota `/api/detect` và bỏ quota polling `/api/health` để việc nhận diện khi gõ không dùng hết quota dịch.

Cập nhật cỡ chữ: sáu kiểm tra bố cục qua với mô phỏng độ rộng ký tự (không thay thế kiểm tra thị giác): căn giữa tiêu đề, tăng cỡ so với renderer cũ, tránh cột và dòng kế bên, báo tràn thay vì chữ 2px, giữ nội dung xuống dòng. TypeScript/Vite và Docker web build qua. Browser thử ảnh mẫu Hàn, canvas dịch nạp thành công ở 2400×440 so với ảnh nguồn 1200×220; A+ đổi 115%→130%, Phóng to đổi sang Vừa khung. Chưa kiểm chứng cách dàn chữ mới trên giấy chứng nhận người dùng. Renderer dùng vùng trống ước lượng từ OCR, không phải phục dựng typography gốc.

Cập nhật ảnh dịch theo bố cục: 12 kiểm thử backend qua. OCR trả tọa độ dòng và kích thước ảnh; API `/api/translate-image` dịch bằng weights thật và giữ tọa độ cho từng dòng. TypeScript/Vite production build và Docker đã qua. Trên trình duyệt, ảnh mẫu Hàn 1200×220 được dịch thành chữ Việt, canvas render thành công và nút Tải ảnh dịch PNG tạo file `saeng-vi.png` trong Downloads. Đây là mẫu tổng hợp, không phải kiểm chứng phục dựng giấy chứng nhận của người dùng; phương pháp phủ màu nền không phục hồi hoa văn. Ảnh minh họa nằm ở `outputs/saeng-translated-image.jpg` ngoài ZIP source.

Cập nhật lỗi OCR/ngôn ngữ: 10 kiểm thử backend qua, thêm kiểm thử từ chối chuỗi Latin nhiễu khi nguồn OCR là Trung/Hàn. Production build đã qua. Đối chiếu API với input Trung sạch `中华人民共和国国家版权局` trả `Văn phòng quyền tác giả quốc gia Cộng hòa Nhân dân Trung Quốc` (318 ms một lần). Không coi đây là nghiệm thu chất lượng tài liệu. Ảnh chứng nhận người dùng chưa được kiểm chứng đọc đúng từ file gốc; màn hình Chữ OCR đang chứa ký tự nhiễu. Sửa UI giữ File trong RAM để tự OCR lại khi đổi nguồn, tránh tái sử dụng OCR của ngôn ngữ trước.

Cập nhật xem trước ảnh: production build TypeScript/Vite và Docker web đã qua. Kiểm tra qua trình duyệt bằng ảnh mẫu Hàn: ảnh gốc nạp thành công (naturalWidth=1200), nút Chữ OCR hiện đúng `안녕하세요 한국어 번역`, chuyển lại Ảnh gốc hiển thị ảnh, Xóa nội dung loại bỏ ảnh và xóa chữ. Tab đang dùng của người dùng được giữ nguyên; cần reload và chọn lại ảnh để thấy giao diện mới. Ảnh minh họa lưu tại `outputs/saeng-image-preview.jpg` bên ngoài gói source.

Docker services `saeng-backend-1`, `saeng-web-1` để chạy phục vụ dùng thử local. Dừng bằng `docker compose down` trong thư mục source. Weights nằm ngoài ZIP và được giữ lại để không phải tải lại trên máy này. Không thay đổi các Docker services khác của người dùng.

## Giao diện vàng nâu
Đã đổi bảng màu dùng chung cho Văn bản, Hình ảnh, Tài liệu và Lịch sử: nền kem, chữ/nút nâu, điểm nhấn vàng. Đồng bộ theme-color, manifest và biểu tượng PWA. Frontend build thành công; web Docker đã được cập nhật. Kiểm tra trình duyệt ở kích thước mặc định và 390 × 844: các tab và bảng lịch sử hiển thị đúng, không thấy tràn ngang. Ảnh giao diện: outputs/saeng-vang-nau.png. Thay đổi giao diện không cải thiện chất lượng OCR hoặc dịch máy.


## Nhận diện KUN GLOBAL
Đã tích hợp nguyên bản logo người dùng vào header và phần giới thiệu. Thiết kế lại nền nâu đậm/vàng ánh kim, khung dịch nền kem; đồng bộ tên trang, tên PWA, favicon, icon cài đặt và tên file TXT/PNG. Giữ khóa lịch sử để không mất dữ liệu. Web Docker build thành công (TypeScript + Vite). Đã xem giao diện thực tế ở kích thước mặc định và 390 × 844, gồm tab Văn bản/Tài liệu/Hình ảnh; không thấy tràn ngang. Ảnh: outputs/kun-global-desktop.png và outputs/kun-global-mobile.png. Không chạy lại kiểm thử mô hình vì thay đổi này chỉ liên quan nhận diện và giao diện.


## Thiết kế lại khung dịch
Thanh tab nâu với mục chọn vàng, thẻ chọn nguồn/đích, hai khung Nội dung gốc/Bản dịch tách biệt và vùng thao tác dưới. Responsive 390 × 844 xếp hai khung dọc và nút dịch toàn chiều ngang. Đã build TypeScript/Vite và cập nhật web Docker. Kiểm tra trình duyệt: chọn ngôn ngữ, nhập nội dung, trạng thái nút, đảo chiều, xóa và chuyển ba tab; không tạo bản dịch hay lịch sử giả. Ảnh kết quả: outputs/kun-global-khung-dich.png. Không thay đổi backend hoặc mô hình.


## Mô tả ứng dụng đa ngôn ngữ
Đã bỏ thông điệp ưu tiên Việt–Lào khỏi phần giới thiệu, thẻ tính năng, footer, mô tả trang và manifest PWA. Dòng ngôn ngữ minh họa có Việt/Anh/Trung/Hàn; không giới hạn lựa chọn nguồn/đích. Docker build thành công; trình duyệt xác nhận nội dung mới và danh sách 16 ngôn ngữ. Ảnh: outputs/kun-global-da-ngon-ngu.png.
