> LƯU TRỮ PHIÊN BẢN CŨ. Ứng dụng hiện dùng OpenAI API và đăng nhập riêng. Các mô tả không gọi API bên ngoài dưới đây không áp dụng cho bản hiện tại. Xem README.md.

# KUN GLOBAL · Dịch thuật đa ngôn ngữ

Giao diện dùng logo KUN GLOBAL do người dùng cung cấp, nền nâu đậm, điểm nhấn vàng ánh kim và khung đọc nền kem. Tên PWA và biểu tượng được đồng bộ; khóa lịch sử trong trình duyệt vẫn giữ tên nội bộ `saeng` để bảo toàn dữ liệu đã lưu. Logo gốc ở `frontend/public/kun-global-logo.png`; chạy `frontend/scripts/prepare-brand.ps1` trên Windows khi cần tạo lại các biểu tượng vuông từ logo này. Nhận diện giao diện không thay đổi khả năng hay chất lượng của mô hình dịch/OCR.

Web App/PWA dịch thuật đa ngôn ngữ. React + Vite + TypeScript, FastAPI, M2M100 418M tự host bằng CTranslate2 INT8 trên CPU. Không gọi API AI ngoài; không có nhận diện/phát giọng nói, Whisper hay Piper.

## Chạy nhanh bằng Docker (Windows / Linux / macOS)

Cần Docker Engine + Compose v2 (Windows dùng Docker Desktop, Linux containers). Chạy các lệnh **tại thư mục chứa compose.yaml**. Dành khoảng 8 GB RAM cho Docker khi chuyển mô hình, khuyến nghị 15 GB dung lượng trống cho images, cache và weights. Đây là dự trù, không phải benchmark hay cam kết tài nguyên tối thiểu.

```sh
docker compose build backend prepare
docker compose run --rm prepare
docker compose up -d --build backend web
```

Mở **http://localhost:8080**. Lệnh `prepare` tải weights từ Hugging Face rồi chuyển thành INT8; chỉ hoàn tất khi in `Model converted successfully`. Không có dữ liệu người dùng được gửi trong bước tải weights. Model **không** kèm trong source ZIP. Lần đầu có thể mất nhiều phút; đừng đóng Docker giữa chừng.

Inference chạy trên mạng Docker `internal`, đọc model từ ổ đĩa và bật `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`. Backend không được publish cổng ra host; trình duyệt gọi `/api` qua Nginx cùng origin. Không có font/CDN/analytics từ bên ngoài.

```sh
docker compose logs -f backend
docker compose ps
docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/health').read().decode())"
docker compose down
```

`health.status=ok` chỉ xác nhận tiến trình còn sống. Chỉ `health.model=ready` xác nhận mô hình nạp thành công. Nếu model thiếu, UI báo chưa sẵn sàng và API trả 503; không có bản dịch dự phòng giả. Sau khi chuẩn bị weights, chạy `docker compose restart backend`.

## Chuẩn bị weights có thể tái lập

```sh
docker compose run --rm prepare --revision COMMIT_SHA --output /models/m2m100
```

Thay `COMMIT_SHA` bằng commit đã kiểm tra tại [facebook/m2m100_418M](https://huggingface.co/facebook/m2m100_418M/commits/main). Mặc định dùng `main`; SHA tải thật được lưu ở `models/m2m100/provenance.json`. Dependencies cấp cao được cố định trong requirements và package-lock; Docker base tags và dependencies Python gián tiếp chưa khóa toàn bộ. Trước vận hành production cần kiểm tra/cập nhật bản vá, khóa digest và tạo lock đầy đủ theo môi trường triển khai.

Mô hình đã tồn tại sẽ không bị ghi đè. Để nâng cấp, chuẩn bị vào `/models/m2m100-v2`, đổi `MODEL_DIR` trong compose rồi tái tạo backend. Nếu chuyển đổi bị ngắt, kiểm tra `ct2-building` và xóa **chỉ thư mục tạm đó** trước khi thử lại. Khi thiếu RAM, tăng RAM Docker hoặc chuyển weights trên máy mạnh hơn rồi chép cả thư mục `m2m100` sang VPS.

## Tính năng MVP

- Dịch 16 ngôn ngữ được chọn trong UI, mặc định Tự phát hiện → Việt; vẫn có thể chọn Việt ↔ Lào, đảo chiều, sao chép, tải TXT, phím tắt Ctrl/Cmd + Enter.
- Tự phát hiện văn bản bằng hệ chữ và `langid` chạy offline với dữ liệu nhận diện đi kèm thư viện, không gọi API ngoài. UI nhận diện sau khi dừng nhập khoảng 750 ms; hiện ngôn ngữ đã phát hiện và nhắc chọn thủ công khi không chắc. Nội dung đã cùng ngôn ngữ đích được giữ nguyên và thông báo rõ. Số, ký hiệu hoặc chữ quá ít sẽ yêu cầu nhập thêm/chọn thủ công. Văn bản/ảnh dùng một ngôn ngữ chính; PDF giữ form tự nhận diện riêng từng trang, hỗ trợ xen kẽ trang gốc và trang dịch. Chưa tách nhiều ngôn ngữ bên trong cùng một trang.
- OCR Tự phát hiện thử các traineddata đã cài (Việt, Lào, Anh, Thái, Trung giản thể, Hàn, Tây Ban Nha, Pháp, Đức) trên ảnh thu nhỏ. Kết hợp độ tin cậy và đồng thuận nhận diện từ nhiều bộ OCR, không ưu tiên chỉ vì một bộ sinh ra hệ chữ riêng. PDF xem bằng chứng chữ Latin trên nhiều trang rồi xác nhận và chọn ngôn ngữ độc lập cho từng trang. Đây là điểm ước lượng, có thể nhầm trên ảnh mờ/chữ kiểu cổ; không coi là xác suất chính xác. Không tải thêm mô hình nhận diện lúc runtime. [Nguồn langid](https://github.com/saffsd/langid.py).
- CTranslate2 INT8, chia theo token để không cắt âm thầm; giữ ngắt dòng. Đoạn dài có thể bị chia giữa câu, giảm ngữ cảnh.
- OCR PNG/JPG/WEBP bằng Tesseract. Docker cài sẵn Việt, Lào, Anh, Thái, Trung giản thể, Hàn, Tây Ban Nha, Pháp và Đức; các ngôn ngữ khác dịch được nhưng OCR cần thêm traineddata. Với ảnh tiếng Hàn, có thể chọn ngôn ngữ nguồn `한국어 · Tiếng Hàn` trước khi tải ảnh.
- Chế độ Trích xuất văn bản đọc PDF có chữ (tối đa 30 trang), DOCX (đoạn và bảng theo thứ tự), TXT UTF-8; không xuất lại Word giữ định dạng. PDF scan và xuất PDF giữ bố cục dùng chế độ PDF giữ form bên dưới.
- Chế độ văn bản/ảnh: file tối đa 10 MB, ảnh 16 megapixel, nội dung tối đa 12.000 ký tự. File chỉ đọc trong RAM, không lưu trên máy chủ. Chế độ PDF giữ form có giới hạn và phiên RAM riêng bên dưới.
- Tab Hình ảnh hiển thị ảnh gốc ngay trong khung trái. Dùng nút `Ảnh gốc` / `Chữ OCR` để đổi giữa xem ảnh và sửa văn bản nhận diện; bản dịch nằm ở khung phải. Ảnh xem trước dùng URL cục bộ, không lưu trong lịch sử và cần chọn lại sau khi tải lại trang. Chọn ảnh mới sẽ xóa nội dung/bản dịch cũ để tránh dịch nhầm khi OCR lỗi.
- Đổi ngôn ngữ nguồn khi đang giữ ảnh sẽ tự chạy OCR lại và xóa chữ/bản dịch cũ. Nếu chọn Trung hoặc Hàn nhưng OCR không có ký tự thuộc hệ chữ tương ứng, app báo lỗi thay vì nhận văn bản rác là hợp lệ. Kiểm tra hệ chữ chỉ phát hiện một số lỗi rõ ràng, không bảo đảm chất lượng OCR hoặc dịch.
- Sau khi dịch ảnh, khung phải mặc định hiện `Ảnh dịch`, có chuyển sang `Văn bản` và nút tải PNG. Tesseract cung cấp tọa độ từng dòng, M2M100 dịch từng dòng, trình duyệt ghép bản dịch vào đúng vùng đó bằng canvas. Chỉ sửa chữ OCR trong cùng số dòng để giữ ánh xạ; nếu thêm/bớt dòng thì chỉ dịch văn bản, cần chọn lại ảnh để lấy bố cục mới. Tối đa 300 vùng, 2.000 ký tự mỗi dòng, tổng 12.000 ký tự.
- Ảnh dịch giữ nền ngoài vùng chữ; vùng chữ được phủ bằng màu lấy mẫu xung quanh, không có khôi phục hoa văn/inpainting. Chữ dịch có thể nhỏ hơn để vừa vùng gốc. Chữ OCR bỏ sót sẽ còn trong ảnh; các vùng chứa dấu, mã QR hoặc họa tiết chồng chữ có thể bị ảnh hưởng. Không cam kết bản sao giữ nguyên kiểu chữ/bố cục tuyệt đối. PNG xuất thêm dòng `Saeng · Bản dịch máy tham khảo` ngoài mép ảnh gốc. Không lưu ảnh dịch trong lịch sử; chưa có nghiệm thu trên giấy chứng nhận cụ thể của người dùng.
- Ảnh dịch dùng chữ đậm vừa, tận dụng khoảng trống quanh dòng với giới hạn là cột/dòng OCR kế bên; giữ điểm đầu dòng và tự căn giữa tiêu đề nằm giữa trang. Có A−/A+ điều chỉnh cỡ chữ mong muốn và Phóng to để xem ảnh lớn. Cỡ thực tế vẫn bị giới hạn bởi khoảng trống; nếu không đủ sẽ báo thay vì thu xuống 2px. Render tối đa 2× (giới hạn 24 megapixel) để PNG nét hơn, giữ tỷ lệ ảnh gốc. Các tọa độ do OCR cung cấp có thể sai, nên không cam kết giữ bố cục chính xác tuyệt đối.
- Lịch sử tối đa 30 bản dịch thành công, lưu localStorage trên thiết bị; có tắt lưu và xóa. Bật chế độ riêng tư của trình duyệt hoặc xóa lịch sử nếu dùng chung thiết bị. Đây không phải kho lưu trữ mã hóa.
- PWA cache giao diện. Offline xem lịch sử; **dịch mới và trích xuất file vẫn cần kết nối máy chủ**. Model không chạy trên điện thoại.

## PDF giữ form cho hồ sơ có logo, chứng nhận đính kèm

Trong **Tài liệu → PDF giữ form**:

1. Chọn PDF, nguồn (hoặc Tự phát hiện) và đích, rồi bấm **Dịch tự động**. App tự chạy OCR → dịch toàn bộ → dàn chữ → tạo PDF và preview, không cần sửa từng vùng hoặc bấm thêm bước phân tích/dịch/xem trước.
2. Mặc định bật **Dịch toàn bộ, gồm chữ trong ảnh đính kèm**: OCR cả trang và từng ảnh nhúng, dịch chữ trong ảnh chứng nhận rồi ghép lại vào vị trí tương ứng. Bỏ chọn chỉ khi chủ động muốn giữ ảnh gốc. Dấu đỏ, QR và mã vạch/mã ma trận được phát hiện để tránh OCR/ghi đè; chữ nằm trong dấu được giữ nguyên vì thuộc hình dấu, không phải nội dung dịch thông thường. Nhận diện có thể bỏ sót hoặc nhầm; cần đối chiếu bản xem trước.
3. Khi báo **PDF đã tạo**, bấm **Tải PDF**. Preview là bản PDF thực đã xuất, không phải mô phỏng giao diện. Chỉnh sửa tay là tùy chọn, được thu gọn trong **Tùy chọn: thuật ngữ và chỉnh sửa thêm**. Có thể lưu thuật ngữ và bấm Dịch tự động lại; nếu tự sửa bản dịch, bấm Cập nhật PDF từ chỉnh sửa.
4. Bộ dàn chữ tự xuống dòng, chọn cỡ ≥7pt và dịch các dòng tiếp theo xuống vùng trống trong cùng ảnh, giữ khung/ảnh/dấu. Mã phiên bản như V8.0 được giữ nội dung và dàn cùng các dòng để không bị đè. Nếu không thể đặt đầy đủ nội dung ở cỡ đọc được, app báo chưa hoàn tất thay vì cắt/bỏ chữ hoặc tạo file giả thành công.

Giới hạn: PDF tĩnh tối đa 30 MB / 10 trang / 400 vùng / 24.000 ký tự nguồn. PDF mã hóa, có widget/AcroForm hoặc chữ ký tương tác bị từ chối để tránh làm mất trường hoặc chữ ký. Xuất giữ form hỗ trợ Việt, Anh, Pháp, Đức, Tây Ban Nha, Indonesia, Malay, Nga; các đích khác vẫn dùng chế độ văn bản. Chưa hỗ trợ xuất DOCX giữ nguyên form, bảng nhiều cột phức tạp, chữ dọc, trang lệch nhiều hoặc chứng nhận PDF số có chữ ký.

PDF gốc được giữ nguyên làm nền, bản dịch được đặt lên vùng chữ; giữ kích thước trang, vị trí ảnh, quy tắc căn trái/phải/giữa, thụt đầu dòng ước lượng và đường kẻ thẳng. Vùng chữ ngoài ảnh dùng mask trắng. Vùng chữ trong ảnh được xóa bằng OpenCV inpainting cục bộ từ các ô chữ OCR rồi đặt bản dịch vào; phần hoa văn phục hồi là gần đúng, không bảo đảm giống từng pixel. Không dùng AI/API ngoài cho bước này. OCR có thể sai vị trí hoặc gom đoạn; không cam kết giữ bố cục 100% trên mọi PDF. Vùng dấu/QR được phát hiện bằng màu đỏ, QR detector và mật độ/nhịp mã máy; đây là heuristic, cần kiểm tra trước khi sử dụng.

Luồng tự động bổ sung thuật ngữ chung cho hồ sơ phần mềm/ngân hàng Trung→Việt; từ khớp dùng giá trị đã cấu hình, phần còn lại chạy M2M100. Không lưu bản dịch nguyên trang của mẫu người dùng vào code. Tên pháp nhân Trung Quốc được tách loại hình doanh nghiệp, dịch mô tả và phiên âm phần tên bằng `pypinyin` chạy offline; đây không phải tên pháp nhân tiếng Việt được xác minh. Một số nhãn trường OCR gần đúng được chuẩn hóa tự động, không sửa mã/số; số đăng ký/chứng nhận không được dịch thành câu văn. Nếu mô hình trả rỗng hoặc lặp từ, app tự thử chia câu và dịch lại. Cách này không bảo đảm sửa hết lỗi dịch/OCR. Phần rà soát không bắt buộc để xuất file, nhưng chất lượng máy dịch vẫn chưa tương đương bản biên tập chuyên môn và không phải bản dịch pháp lý được chứng nhận. [Tài liệu pypinyin](https://pypinyin.readthedocs.io/zh-cn/master/usage.html).

API: `/api/documents/analyze` nhận file; `/complete` tự dịch và xuất PDF với `session_id`, `target`, thuật ngữ tùy chọn. Thành công trả `ready:true`, metadata và preview. `/export` với `automatic:true` và không truyền edits trả đúng bản đã tạo trong phiên. Khi đổi ngôn ngữ phải chạy Dịch tự động lại; request xuất sai ngôn ngữ bị từ chối. Nếu `/complete` lỗi, không ghi nhận bản dịch dở dang là kết quả. Phiên giữ thêm PDF đầu ra trong RAM cho tới khi hết hạn.

Phiên PDF nằm trong RAM với token ngẫu nhiên, hết hạn sau 20 phút không thao tác và được dọn định kỳ mỗi phút; tối đa 3 phiên và 100 MB file gốc tổng cộng. Quá trình nhận upload có thể dùng bộ đệm file tạm của Nginx/FastAPI trong container; file tạm được đóng/xóa sau khi đọc, không dùng làm kho tài liệu. Khởi động lại backend sẽ mất phiên; cần tải lại file. Token phiên không thay thế đăng nhập: chỉ dùng MVP trong phạm vi tin cậy hoặc thêm xác thực ở reverse proxy. Đầu ra có dòng “Bản dịch máy tham khảo” ở chân trang. Không chỉnh sửa file gốc.

Luồng tài liệu dùng chống lặp khi giải mã (`no_repeat_ngram_size=4`, `repetition_penalty=1.1`), tự chia đoạn nhỏ hơn nếu chạm giới hạn sinh thay vì tăng giới hạn rồi cắt chữ. Điều này không phải bảo đảm nội dung đúng nghĩa. Mảnh Latin rất ngắn mà mô hình trả rỗng được giữ gốc và có cảnh báo rõ/số lượng chưa dịch; đoạn dài bị lỗi vẫn không được coi là hoàn tất. Dấu xanh có vòng tròn và khối chữ liền kề cũng được bảo vệ; chữ xanh thông thường vẫn OCR. Bộ dàn tránh đẩy cột trái xuống theo cột phải và không đặt chú thích máy dịch lên vùng cuối trang đã có chữ/dấu. Trang PDF xoay được chuẩn hóa rotation để ghép tọa độ; khổ giấy theo hướng nhìn giữ nguyên, MediaBox/Rotate nội bộ có thể thay đổi.

## Vùng chưa đọc rõ và chữ Gothic

OCR thường có thể bỏ sót chữ Gothic, chữ nhỏ hoặc đọc thành từ sai. Docker bổ sung bộ `Fraktur`/`frk` từ Debian; app phát hiện các dòng in độc lập rồi thử OCR theo dòng với bộ thường và Fraktur, không ghi đè kết quả bằng một đoạn ngắn mất nhiều ký tự chỉ vì điểm cao hơn. Có thuật ngữ học thuật chung Trung/Anh/Tây Ban Nha→Việt, chuẩn hóa một số nhãn phổ biến; không chứa bản dịch nguyên trang hay họ tên của mẫu người dùng. Tên người nhận dạng được được giữ nội dung và ghép lại bằng chữ dễ đọc, nhưng chính tả OCR chưa được xác minh. Ảnh chân dung, hình dấu và chữ ký vẫn có thể giữ như đồ họa.

Với các nguồn Latin đã kiểm tra vùng, API trả `ocr_unread_count` và `pages[].unread_regions`; đây là ước lượng hình học/độ tin cậy, có thể báo nhầm hoặc bỏ sót, không phải chứng nhận đọc đủ từng chữ. Khi còn vùng chưa rõ, giao diện ghi **PDF bản nháp, chưa đầy đủ**, có ô cam ở vùng nguồn, nút tải/filename mang nhãn bản nháp và chân trang có ghi chú tương ứng nếu có chỗ. Không đánh đồng tạo được PDF với dịch hết/đúng. Không có cảnh báo cũng không bảo đảm OCR/dịch chính xác 100%; các hệ chữ chưa có kiểm tra vùng này vẫn có thể sót. M2M100 có thể dịch sai nghĩa cả khi OCR đúng.

Kiểm tra chân dung dùng bộ Haar cục bộ đi kèm OpenCV để tránh OCR nhầm khuôn mặt thành chữ; không nhận dạng danh tính và không gửi ảnh ra ngoài. Xóa chữ in xanh dựa vào độ sáng thay vì yêu cầu cả ba kênh màu tối, tránh để nét xanh còn phía sau bản dịch. Các cơ chế này vẫn có thể ảnh hưởng nền, nên đối chiếu trước khi dùng hồ sơ quan trọng. [Mô hình Fraktur](https://packages.debian.org/trixie/tesseract-ocr-script-frak).

## PWA trên điện thoại và VPS

Localhost được trình duyệt xem là secure context. Trên điện thoại, truy cập qua HTTPS tên miền của VPS, rồi Android Chrome → Cài ứng dụng; iPhone Safari → Chia sẻ → Thêm vào MH chính. Clipboard và service worker cần secure context. IP LAN qua HTTP có thể xem giao diện nhưng không đủ điều kiện cài PWA. Hai icon PNG 192/512 px nằm trong `frontend/public`.

Triển khai VPS Ubuntu: cài Docker/Compose từ tài liệu Docker chính thức, chép source, chạy ba lệnh quickstart. Mặc định chỉ bind `127.0.0.1:8080`; đặt reverse proxy HTTPS (Caddy/Nginx) trên host trỏ đến cổng này. Ví dụ Caddyfile:

```caddyfile
translate.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

Thay tên miền, cấu hình DNS, mở 80/443. Chỉ mở cho người dùng tin cậy ở MVP; thêm đăng nhập tại reverse proxy trước khi đưa lên Internet công khai. Nginx có giới hạn request theo IP và backend chỉ xử lý một yêu cầu dịch tại một thời điểm; khi bận trả 429. Nếu dùng proxy phía trước, cấu hình real IP từ **proxy tin cậy** để rate limit đúng người dùng. Chưa có tài khoản, hàng đợi bền vững, billing hoặc tách tenant. API docs có ở `/docs` trong backend, không được route công khai qua web.

Có thể đặt `.env` từ `.env.example`: `PORT=8080`, `MODEL_THREADS=4`. Để truy cập LAN phục vụ phát triển, đặt `BIND_ADDRESS=0.0.0.0` rồi tái tạo web; nên giới hạn firewall trong mạng riêng.

Khởi đầu thử nghiệm với 4 vCPU / 8 GB RAM, SSD 15–20 GB trống; đo thực tế trên VPS trước khi quyết định. M2M100 có thể dịch sai, lặp hoặc bỏ ý, đặc biệt Việt–Lào và văn bản chuyên ngành. INT8 không bảo đảm giữ nguyên chất lượng; chưa có đánh giá BLEU/COMET hay người bản ngữ. Phần mềm không thu phí API AI, **vẫn có chi phí VPS, điện, dung lượng, mạng, tên miền và vận hành**; giá tùy nhà cung cấp. Không dùng bản dịch chưa kiểm tra cho nội dung quan trọng.

## Phát triển local không Docker

Cần Python 3.11, Node 22+, Tesseract 5 và traineddata. Trong `backend`:

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install torch==2.7.0 --index-url https://download.pytorch.org/whl/cpu
python prepare_model.py --output ../models/m2m100
# Linux/macOS:
MODEL_DIR=../models/m2m100 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uvicorn app.main:app --host 127.0.0.1 --port 8000
```

PowerShell dùng `$env:MODEL_DIR='../models/m2m100'`, `$env:HF_HUB_OFFLINE='1'`, `$env:TRANSFORMERS_OFFLINE='1'` trước lệnh `uvicorn app.main:app --host 127.0.0.1 --port 8000`. Giữ một worker để không nhân bản weights trong RAM. Tesseract phải có trong PATH.

Terminal khác, trong `frontend`:

```sh
npm ci
npm run dev
# Production static build:
npm run build
```

Vite chuyển `/api` sang localhost:8000. `vite preview` chỉ xem static build; không thay thế Nginx production và không có proxy API.

## Kiểm thử

```sh
docker compose run --rm backend python -m pytest -q
```

Kiểm thử giới hạn input/file, TXT, thứ tự bảng DOCX, PDF scan, trạng thái thiếu mô hình; kiểm thử tích hợp Việt↔Lào dùng weights thật nếu đã chuẩn bị (nếu thiếu weights sẽ báo SKIP). Test tích hợp chỉ kiểm tra inference có output, không chấm chất lượng dịch. Xem `VERIFICATION.md` để biết những gì đã thực sự được chạy trong lần bàn giao.

## Cấu trúc và tham khảo

`backend/app/engine.py`: inference; `extract.py`: OCR/tài liệu; `main.py`: API. `frontend/src`: UI. `compose.yaml`: dịch vụ và cách ly mạng. `models/`: weights (không commit/đóng ZIP).

Nguồn chính thức: [M2M100 model card](https://huggingface.co/facebook/m2m100_418M), [CTranslate2 Transformers](https://opennmt.net/CTranslate2/guides/transformers.html), [Tesseract languages](https://tesseract-ocr.github.io/tessdoc/Data-Files-in-different-versions.html), [Docker Engine](https://docs.docker.com/engine/install/ubuntu/). Quyền sử dụng mô hình và các thư viện tuân theo giấy phép riêng của từng thành phần.
