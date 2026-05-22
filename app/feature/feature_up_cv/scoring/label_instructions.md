# Hướng dẫn gán nhãn JD ↔ Project

Mục đích: thu thập nhãn do con người gán cho từng cặp (JD, Project) để huấn luyện
hệ thống Learning-to-Rank (LTR).

File chuẩn dùng để gán nhãn: `label_candidates_for_review.csv` (UTF-8).

Format CSV:
- `jd_file`: tên file JD (ví dụ `jd_20260521124012_7_28.json`)
- `project_index`: chỉ số dự án trong CV (0-based)
- `project_name`: tên dự án
- `project_description`: mô tả dự án (đọc kỹ)
- `current_label`: nhãn tự động hiện có (0.0-1.0) — chỉ tham khảo
- `sem_sim`: độ tương tự embedding (tham khảo)
- `ce_score`: score cross-encoder (tham khảo)
- `human_label`: (TRỐNG) điền 0 / 1 / 2 theo thang bên dưới
- `human_notes`: (tùy chọn) ghi chú ngắn về lý do gán nhãn

Thang gán nhãn (rõ ràng, dùng cho nhiều reviewer):
- `2` = Highly relevant — dự án chứng minh rõ năng lực cho các nhiệm vụ chính của JD.
- `1` = Partially relevant — dự án liên quan 1 phần (kỹ thuật tương tự hoặc 1-2 nhiệm vụ trùng).
- `0` = Not relevant — dự án không có bằng chứng liên quan thiết yếu tới JD.

Hướng dẫn nhanh khi gán nhãn:
1. Đọc tiêu đề JD và phần `responsibilities` / `requirements` (nếu có) trước.
2. Đọc `project_name` và `project_description` — tìm bằng chứng trực tiếp cho nhiệm vụ JD.
3. Nếu dự án dùng công nghệ bắt buộc trong `skills_required` và làm đúng nhiệm vụ → gán `2`.
4. Nếu dự án chỉ dùng công nghệ tương tự hoặc giải quyết bài toán gần kề → gán `1`.
5. Nếu dự án thuộc domain khác, hoặc không có evidence → gán `0`.

Ví dụ (tham khảo từ dataset hiện có):
- JD: AI Intern (Computer Vision)
  - `SYSTEM SCORING IMAGE SCAN ANSWER SHEET` → gán `2` (mạnh về CV, YOLO)
  - `TRAFFIC SIGN RECOGNITION` → gán `2` hoặc `1` tùy mức độ yêu cầu JD (thường `2` vì cũng là CV)

Ghi chú:
- Nếu không chắc, chọn `1` (partially relevant) thay vì bỏ trống.
- Ghi `human_notes` ngắn gọn nếu quyết định không rõ ràng.
- Labeled file sẽ được ingest bằng script `ingest_human_labels.py` (script chuẩn hoá và chuyển
  `human_label` → nhãn [0.0, 1.0] bằng cách chia cho 2 trước khi huấn luyện).

Thời gian ước tính: ~10-30 giây / hàng tùy độ dài mô tả.

Xong thì trả file CSV (UTF-8) về repo hoặc gửi cho người thu thập.

--
Scoring team
