# Netlify — tài khoản riêng, API do admin quản lý

Trang online: https://kun-global-dichthuat-hoanganh.netlify.app

## Sử dụng

1. Admin đăng nhập tại `/login`, mở **Quản trị → OpenAI API**, nhập khóa và model, lưu rồi bấm **Kiểm tra kết nối**. Chỉ bật dịch sau khi máy chủ nhận phản hồi hợp lệ. Thao tác kiểm tra có thể phát sinh phí API nhỏ.
2. Trong **Người dùng**, admin tạo tài khoản app, khóa/mở khóa, đổi mật khẩu, phân quyền, đăng xuất thiết bị và xóa user có xác nhận. Không đọc lại mật khẩu hiện tại. Không xóa/hạ quyền tài khoản quản trị cuối cùng.
3. User đăng nhập bằng tài khoản do admin cấp và dùng dịch. Giao diện user không có khóa, model, kết nối, sử dụng API hay hạn mức. Máy chủ từ chối thao tác quản trị từ user. Nếu chưa cấu hình dịch, user nhận thông báo liên hệ admin.
4. Admin xem số lượt/token tại tab **Sử dụng**. Chi phí thực tế xem trong OpenAI API Dashboard. Phí API và hạ tầng vẫn có.

## Cấu hình triển khai

`netlify.toml` đặt `VITE_HOSTED_APP=true`, `VITE_PUBLIC_PREVIEW=false`, `VITE_PUBLIC_TRIAL=false`. `/api/*` chuyển vào function `frontend/netlify/functions/api.mjs`. Không còn endpoint BYOK công khai. `trial-core.mjs` là hàm vận chuyển nội bộ, nhận khóa do máy chủ cấp sau khi xác thực.

Cài các biến sau trong **Netlify environment variables**, không dùng tiền tố `VITE_` và không ghi vào source:

- `KUN_MASTER_KEY`: 32 byte ngẫu nhiên, mã hóa base64. Giữ nguyên khi triển khai lại; đổi/mất khóa sẽ không đọc được dữ liệu cũ. Sao lưu riêng trong nơi quản lý bí mật.
- `KUN_BOOTSTRAP_USERNAME`: tên admin khởi tạo, mặc định `admin`.
- `KUN_BOOTSTRAP_PASSWORD_HASH`: hash scrypt của mật khẩu admin mạnh, dạng `scrypt$<salt-base64>$<key-base64>`, tạo bằng `passwordHash` trong `hosted-store.mjs`. Không dùng mật khẩu thử local trên mạng.

Bootstrap chỉ tạo admin khi kho dữ liệu chưa tồn tại; không tự đặt lại mật khẩu của tài khoản đã khởi tạo. Mật khẩu cần ít nhất 12 ký tự. Tài khoản online và local có kho dữ liệu riêng.

Netlify Blobs dùng site-wide store `kun-global-private`, strong consistency và ghi có điều kiện theo ETag để tránh ghi đè thay đổi đồng thời. Dữ liệu tài khoản, khóa dùng chung, lịch sử và số lượt được mã hóa AES-256-GCM trước khi lưu. Mật khẩu hash scrypt có salt; phiên chỉ lưu hash token. Cookie `__Host-kun_session` có Secure, HttpOnly, SameSite=Lax; yêu cầu thay đổi dữ liệu kiểm tra Origin và header riêng. Khóa OpenAI không trả về trình duyệt, không đặt trong bundle hoặc lưu localStorage/sessionStorage. Đăng nhập sai bị giới hạn theo IP; khóa tài khoản, đổi mật khẩu, thu hồi phiên và xóa user vô hiệu hóa phiên cũ.

Build: `npm --prefix frontend ci` rồi đặt ba cờ trên trước `npm --prefix frontend run build`. Deploy bằng Netlify CLI từ root repo với `--dir=frontend/dist --functions=frontend/netlify/functions --no-build`; thêm `--prod` khi xuất bản bản đã kiểm tra. Cập nhật biến môi trường cần triển khai lại function.

## Định dạng và giới hạn thực tế

- 20 ngôn ngữ; văn bản 12.000 ký tự, ảnh/PDF/DOCX 3 MB, PDF tối đa 30 trang mỗi lượt. TXT tối đa 12.000 ký tự.
- Văn bản ra văn bản/TXT, có tùy chọn Word; ảnh ra PNG đúng kích thước gốc; PDF giữ số trang, kích thước và hướng trang; DOCX thay chữ trong file gốc, giữ bảng, ô gộp, header/footer và style. Dịch cả ảnh nhúng PNG/JPEG. Định dạng ảnh không hỗ trợ hoặc nội dung chưa hoàn tất được báo lỗi, không giả vờ đã dịch đủ.
- PDF đầu ra gồm các trang ảnh, không giữ lớp chữ chỉnh sửa, liên kết hay trường tương tác. Ngoài vùng chữ, ảnh gốc giữ nguyên pixel; nền phía dưới chữ được ước lượng, hoa văn có thể không khôi phục chính xác. Văn bản dài hơn có thể làm DOCX giãn dòng/trang. Cần kiểm tra ảnh scan mờ và nội dung quan trọng.
- Mỗi lần gọi cần hoàn tất trong khoảng 50 giây; PDF gọi lần lượt từng trang, DOCX theo lô chữ/ảnh. Không tự lặp yêu cầu tính phí khi có lỗi. Nội dung được gửi tới OpenAI; không cam kết zero data retention của hạ tầng bên thứ ba.
- Kiểm thử tự động dùng khóa/phản hồi giả lập, không chứng nhận chất lượng dịch thật. Kiểm tra đăng nhập, lưu trữ và phân quyền online dùng tài khoản thử tạm đã xóa; không gọi OpenAI trong bước đó.

FastAPI/Docker local tiếp tục dùng kho SQLite/volume riêng và API do admin cấu hình. Xem README.md để chạy local hoặc VPS.
