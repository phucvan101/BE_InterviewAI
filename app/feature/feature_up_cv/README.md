# TRƯỚC KHI CHẠY "python run.py" THÌ CHẠY "alembic upgrade 20260422_0002" TRƯỚC ĐỂ ĐẢM BẢO ĐỒNG BỘ DATABASE




# Feature Up CV - Database Structure

Tài liệu này cung cấp các thông tin cần thiết về cấu trúc cơ sở dữ liệu (Database) của nhánh (feature) `feature_up_cv`. Tài liệu nhằm giúp các thành viên trong team nắm bắt được mối quan hệ giữa các bảng, ý nghĩa của các trường (cột) và cơ chế Caching đang được áp dụng để hoàn thiện hệ thống.

---

## 1. Tổng quan các bảng (Tables) & Mối quan hệ (Relationships)

Nhánh `feature_up_cv` tập trung vào luồng phân tích sự phù hợp giữa CV (Hồ sơ ứng viên), JD (Mô tả công việc) và thông tin về Công ty. Hệ thống bao gồm 4 bảng chính:

1. **`cv_profiles`**: Lưu trữ thông tin các file CV do người dùng upload.
2. **`job_descriptions`**: Lưu trữ các file Mô tả công việc (JD).
3. **`company_infos`**: Lưu trữ các file tài liệu nghiên cứu về công ty.
4. **`analysis_sessions`**: Là bảng trung tâm, lưu trữ kết quả của mỗi một lần "Bấm nút phân tích". Bảng này liên kết với 3 bảng trên và liên kết với người dùng.

**Mối quan hệ:**
- Tất cả các bảng đều có khóa ngoại (`user_id`) trỏ tới bảng `users` (quan hệ 1-N). Khi user bị xóa, các dữ liệu này sẽ tự động bị xóa theo (`ON DELETE CASCADE`).
- Một `analysis_sessions` bắt buộc phải có `id_cv` và `id_jd`. Trường `id_ci` (company_info) là tùy chọn (nullable).

---

## 2. Ý nghĩa chi tiết các cột (Schema)

### 2.1. Bảng `cv_profiles`
Lưu trữ lịch sử CV của người dùng.
- `id_cv` *(Integer, PK)*: ID tự tăng.
- `user_id` *(Integer, FK)*: ID của người dùng.
- `raw_file_url` *(String)*: Đường dẫn vật lý lưu trữ file PDF gốc của CV trên server (vd: `uploads/cv/raw/...`).
- `parser_file_url` *(String)*: Đường dẫn lưu trữ file JSON chứa kết quả mà LLM (Gemini) đã đọc và bóc tách từ CV. Dùng làm cache để không phải gọi LLM lại nhiều lần.
- `text_hashed` *(String)*: Mã băm SHA-256 của toàn bộ đoạn text đã extract được từ file PDF. Đây là chìa khóa cực kỳ quan trọng để hệ thống phát hiện xem nội dung file có bị thay đổi so với các lần upload trước đó hay không.
- `created_at` *(DateTime)*: Thời điểm upload. Nếu người dùng upload lại đúng file cũ, cột này sẽ được cập nhật thành thời gian hiện tại để đưa record đó lên đầu tiên.

### 2.2. Bảng `job_descriptions`
Lưu trữ lịch sử JD của người dùng.
- `id_jd` *(Integer, PK)*: ID tự tăng.
- `user_id` *(Integer, FK)*: ID của người dùng.
- `raw_file_url` *(String)*: Đường dẫn vật lý lưu trữ file JD gốc (có thể là PDF, DOCX, TXT).
- `parser_file_url` *(String)*: Đường dẫn lưu trữ file JSON kết quả bóc tách JD.
- `text_hashed` *(String)*: Tương tự như ở `cv_profiles`.
- `upload_at` *(DateTime)*: Thời điểm upload.

### 2.3. Bảng `company_infos`
Lưu trữ thông tin công ty do người dùng cung cấp (tùy chọn). Cấu trúc bảng tương tự như `job_descriptions`.
- `id_ci` *(Integer, PK)*: ID tự tăng.
- `user_id` *(Integer, FK)*: ID người dùng.
- `raw_file_url` *(String)*: Đường dẫn file gốc.
- `parser_file_url` *(String)*: File JSON bóc tách thông tin công ty.
- `text_hashed` *(String)*: Mã băm nội dung.
- `upload_at` *(DateTime)*: Thời điểm upload.

### 2.4. Bảng `analysis_sessions`
Lưu trữ kết quả đối chiếu, chấm điểm (Matching Score) giữa CV, JD và Công ty.
- `id_session` *(Integer, PK)*: ID của lượt phân tích.
- `user_id` *(Integer, FK)*: ID người dùng.
- `id_cv` *(Integer, FK)*: Link tới CV được đem đi phân tích.
- `id_jd` *(Integer, FK)*: Link tới JD.
- `id_ci` *(Integer, FK)*: Link tới thông tin công ty (nếu có).
- `company_info` *(Text)*: Snapshot text nghiên cứu công ty dùng để sinh câu hỏi phỏng vấn.
- `score` *(Numeric 5,2)*: Điểm phù hợp tổng quan (Overall Score).
- `experience_score` *(Numeric 5,2)*: Điểm kinh nghiệm.
- `skills_score` *(Numeric 5,2)*: Điểm kỹ năng.
- `education_score` *(Numeric 5,2)*: Điểm học vấn.
- `companyfit_score` *(Numeric 5,2)*: Điểm phù hợp với văn hóa công ty.
- `result_analysis_file_url` *(String)*: Đường dẫn file JSON chứa chi tiết kết quả phân tích (những kỹ năng còn thiếu, lời khuyên, ...).
- `create_at` *(DateTime)*: Thời gian thực hiện phân tích.

---

## 3. Cơ chế Caching & Upload Flow (Rất quan trọng)

Để giảm thiểu chi phí gọi API LLM (Gemini) và tiết kiệm tài nguyên hệ thống, nhánh này sử dụng cơ chế Caching 2 lớp, được điều phối bởi trường `text_hashed`.

**Luồng Upload:**
1. Khi user upload tài liệu (CV/JD/CI), hệ thống lập tức extract text và sinh ra `text_hashed`.
2. Hệ thống tìm kiếm trong Database xem user này đã từng có bản ghi nào chứa đoạn hash này chưa (tìm theo `text_hashed`).
3. **Nếu có:** Tái sử dụng (Reuse) ngay `id` của bản ghi đó và cập nhật lại thời gian `created_at` / `upload_at` thành hiện tại.
4. **Nếu không:** Tạo bản ghi mới trong DB.

**Luồng Phân tích (`/match-cv-jd`):**
1. Endpoint sẽ quét lại nội dung file gửi lên, lấy hash và tìm đúng các bản ghi (`id_cv`, `id_jd`, `id_ci`).
2. Từng tài liệu sẽ kiểm tra `parser_file_url`. Nếu file json bóc tách đã tồn tại (cache hit), bỏ qua bước gọi LLM bóc tách.
3. Chặn Cache Session: Nếu **tất cả** các tài liệu đều không thay đổi nội dung (Cache hit = True) $\rightarrow$ Tìm xem trong `analysis_sessions` đã từng có lượt phân tích nào giữa các ID này chưa. Nếu có $\rightarrow$ Đọc file json ở `result_analysis_file_url`.
4. Trả kết quả: Nếu file json đọc thành công $\rightarrow$ Trả thẳng kết quả ra cho FE (Hoàn thành ngay lập tức trong 0.1s).
5. **Trường hợp mất file vật lý (Fallback):** Mặc dù bản ghi trong DB báo là có cache, nhưng nếu hệ thống tìm đến đường dẫn `parser_file_url` hoặc `result_analysis_file_url` mà phát hiện file JSON đã bị xóa/mất khỏi ổ cứng, hàm `load_parser_result` hoặc `load_result_analysis` sẽ trả về `None`. Khi đó, hệ thống sẽ tự động chuyển sang trạng thái "Cache Miss" và **gọi lại LLM** để bóc tách/chấm điểm lại từ đầu, sau đó lưu thành file JSON mới.
6. Nếu có **bất kỳ 1 file nào bị thay đổi nội dung** $\rightarrow$ Bắt buộc phải gọi LLM bóc tách lại (nếu cần) và gọi LLM tính lại `MATCH_SCORE`, sau đó tạo ra 1 dòng `analysis_sessions` mới.

Cơ chế này đảm bảo:
- Khi User A đổi qua đổi lại giữa 2 file CV cũ để đối chiếu với cùng 1 cái JD, hệ thống sẽ bảo toàn toàn bộ kết quả cũ mà không phải chờ đợi hay tốn quota AI.
- Hệ thống có khả năng tự phục hồi (Self-healing) nếu vô tình thư mục `uploads/` bị dọn dẹp hoặc mất dữ liệu vật lý.
