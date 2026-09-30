# Alert và runbook

Ba alert dưới đây dựa trên triệu chứng mà người dùng quan sát được và khớp với
`config/alert_rules.yaml`. Kênh nhận cảnh báo là Slack `#k4-l3b-alerts`;
owner trực tiếp là `student-2A202602418`.

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Điều kiện: P95 của `response_sent.latency_ms` lớn hơn 3000 ms liên tục 5 phút.
- SLI/SLO: latency của SLO `fast_successful_requests`.
- Ảnh hưởng: người dùng phải chờ lâu hơn ngưỡng cam kết để nhận câu trả lời.
- Kiểm tra:
  1. Mở panel Latency, xác nhận P95/P99, TTFT P95 và khoảng thời gian tăng.
  2. Lọc các `response_sent` có `latency_ms > 3000`, lấy một `correlation_id`.
  3. Mở trace cùng ID, so sánh thời gian của retrieval và generation; kiểm tra prompt version nếu generation tăng.
- Mitigation: tắt practice scenario nếu đang demo; nếu generation tăng sau đổi prompt thì rollback label `production`; nếu retrieval chậm thì khôi phục cấu hình retrieval hoặc giảm tải.
- Xác nhận phục hồi: P95 dưới 3000 ms ít nhất 5 phút và request kiểm tra có cả hai child observations thành công.

## Alert 2

- Tên: `HighRequestErrorRate`
- Severity: `critical`
- Duration: `5m`
- Điều kiện: `request_failed / request_received * 100 > 2%` liên tục 5 phút.
- SLI/SLO: tỷ lệ good event của SLO `fast_successful_requests`.
- Ảnh hưởng: hơn 2% người dùng không nhận được câu trả lời.
- Kiểm tra:
  1. Mở panel Errors, xác nhận error rate và breakdown theo `error_type`.
  2. Lọc `request_failed` trong cửa sổ cảnh báo, chọn `correlation_id` đại diện.
  3. Mở trace cùng ID, tìm observation có trạng thái lỗi và đối chiếu log chi tiết đã scrub.
- Mitigation: tắt scenario gây lỗi, rollback prompt/cấu hình vừa thay đổi hoặc cô lập dependency lỗi; không ghi raw input vào log trong lúc debug.
- Xác nhận phục hồi: error rate không vượt 2% trong 5 phút và request canary trả HTTP 200.

## Alert 3

- Tên: `LowRetrievalSuccess`
- Severity: `warning`
- Duration: `10m`
- Điều kiện: tỷ lệ `tool_success=true` của retrieval thấp hơn 90% liên tục 10 phút.
- SLI/SLO: guardrail `retrieval_success_rate_pct_min: 90`.
- Ảnh hưởng: câu trả lời có thể thiếu context phù hợp hoặc request thất bại ở retrieval.
- Kiểm tra:
  1. Mở panel Errors, xác nhận retrieval success và error breakdown.
  2. Lọc log có `tool_name=retrieval` và `tool_success=false`, lấy `correlation_id`.
  3. Mở trace cùng ID, kiểm tra child observation `retrieval` trước khi xem generation.
- Mitigation: tắt scenario `tool_fail`, khôi phục vector store/cấu hình retrieval và dùng fallback an toàn nếu dependency chưa phục hồi.
- Xác nhận phục hồi: retrieval success đạt ít nhất 90% trong 10 phút và trace canary có retrieval rồi generation.
