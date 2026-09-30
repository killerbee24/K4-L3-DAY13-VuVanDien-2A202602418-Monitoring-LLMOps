# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên: Vũ Văn Điền**
- **MSSV: 2A202602418**
- **Lớp:** K4-L3B
- **Repository URL:** [github.com/killerbee24/K4-L3-DAY13-VuVanDien-2A202602418-Monitoring-LLMOps](https://github.com/killerbee24/K4-L3-DAY13-VuVanDien-2A202602418-Monitoring-LLMOps)
- **Commit SHA cuối:** `32b318462eaf1fa4291b769021e0183dcf44c5da`
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602418`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence            | Đường dẫn                             |
| ------------------- | ------------------------------------- |
| Pytest cuối         | [01-pytest.png](evidence/01-pytest.png)                         |
| Log validator       | [02-log-validator.png](evidence/02-log-validator.png)             |
| Dashboard validator | [03-dashboard-validator.png](evidence/03-dashboard-validator.png) |
| Structured log      | [04-structured-log.png](evidence/04-structured-log.png)           |
| PII redaction       | [05-pii-redaction.png](evidence/05-pii-redaction.png)             |
| Trace list          | [06-trace-list.png](evidence/06-trace-list.png)                   |
| Trace waterfall     | [07-trace-waterfall.png](evidence/07-trace-waterfall.png)         |
| Trace metadata      | [08-trace-metadata.png](evidence/08-trace-metadata.png)           |
| Prompt versions     | [09-prompt-versions.png](evidence/09-prompt-versions.png)         |
| Prompt rollback     | [10-prompt-rollback.png](evidence/10-prompt-rollback.png)         |
| Dashboard runtime   | [11-dashboard-overview.png](evidence/11-dashboard-overview.png)   |
| Incident metric     | [12-incident-metric.png](evidence/12-incident-metric.png)         |
| Incident log        | [13-incident-log.png](evidence/13-incident-log.png)               |
| Incident trace      | [14-incident-trace.png](evidence/14-incident-trace.png)           |

## 3. Kết quả kỹ thuật

| Nội dung                | Baseline        | Kết quả cuối    | Nhận xét                                                           |
| ----------------------- | --------------- | --------------- | ------------------------------------------------------------------ |
| `validate_logs.py`      |                 | 100/100         | 146 records, 73 correlation IDs, không thiếu enrichment, 0 PII leak |
| `validate_dashboard.py` |                 | 6/6 panel       | Contract và dashboard runtime cùng dùng`config/dashboard.yaml`     |
| `pytest`                |                 | 32 passed       | Chạy trong Python 3.11 với đúng`requirements.txt`                  |
| Số traces hợp lệ        |                 | 10              | Mỗi trace có root, retrieval và generation                         |
| Số PII leak             |                 | 0               | Validator và kiểm tra trace đều không phát hiện PII thô            |
| Latency P95 / TTFT P95  | 903 ms / 50 ms  | 2652 ms / 50 ms | Snapshot trước/sau challenge từ `data/logs.jsonl`                  |
| Retrieval success rate  | 100%            | 100%            | Incident làm retrieval chậm nhưng không làm retrieval lỗi          |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** middleware xóa context của
  request trước đó, nhận `x-request-id` từ client hoặc sinh ID dạng
  `req-<8-hex>`, rồi bind vào `structlog.contextvars`. Cùng ID được truyền vào
  `LabAgent.run`, metadata của trace và response header `x-request-id`; header
  `x-response-time-ms` ghi thời gian xử lý phía API.
- **Các metadata được ghi vào structured log:** mọi request có `ts`, `event`,
  `correlation_id`, `service`, `user_id_hash`, `session_id`, `feature`,
  `model` và `env`. Event kết quả bổ sung latency, TTFT, input/output token,
  cost, quality proxy, tên retrieval tool và trạng thái thành công hoặc lỗi.
- **Cách bảo đảm PII được scrub trước khi ghi:** `app/pii.py` nhận diện email,
  số điện thoại Việt Nam, CCCD 12 số và thẻ thanh toán 16 số. Processor scrub
  đệ quy trong `app/logging_config.py` chạy trên toàn bộ event dictionary trước
  bước render JSON và ghi file; user ID chỉ được lưu dưới dạng SHA-256 rút gọn,
  còn prompt/output trên log và trace chỉ dùng preview đã scrub.
- **Cách kiểm chứng kết quả:** dùng input giả chứa đủ bốn loại PII, đối chiếu
  event `request_received` theo `correlation_id` và xác nhận chỉ còn các marker
  `[REDACTED_*]`. `python scripts/validate_logs.py` đạt `100/100`, không thiếu
  context và phát hiện `0` PII leak; test riêng kiểm tra cả pattern, cấu trúc
  lồng nhau và propagation của request ID.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** chạy
  `python scripts/generate_trace_evidence.py --per-label 5`, sau đó kiểm tra
  Observations API v2 và Langfuse UI. Kết quả có 10 trace, 30 observations và
  không phát hiện PII trong input/output/metadata đã lưu.
- **Cấu trúc root/retrieval/generation observations:** mỗi trace có root
  `lab-agent-run` loại `AGENT`; hai child cùng cấp là `retrieval` loại
  `RETRIEVER` và `generation` loại `GENERATION`. Generation có model
  `claude-sonnet-4-5`, input/output token và cost; chỉ lưu preview đã scrub.
- **Cách nối trace với log:** `correlation_id` được bind ở middleware, xuất
  hiện trong structured log và metadata của root/retrieval/generation.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** version 1, labels `baseline` và `production`
  sau rollback.
- **Version/label candidate:** version 2, label `candidate`.
- **Trace ID của mỗi version:** baseline v1:
  `bd76f11fed7addc110c50f37e4ac32bc` (`req-0a014030`); candidate v2:
  `29d912a0999405b102d4da25c44699dc` (`req-1575f1a4`).
- **Cách promote và rollback `production`:** dùng Langfuse
  `update_prompt` chuyển `production` từ v1 sang v2, xác nhận production
  trả version 2, rồi chuyển `production` về v1 và xác nhận trả version 1.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** `/dashboard` hiển thị đúng sáu panel từ
  `data/logs.jsonl`: latency P50/P95/P99 + TTFT P95, traffic, error rate +
  retrieval success, cost, input/output tokens và quality proxy.
  `/dashboard/data` cung cấp cùng snapshot ở dạng JSON. Cửa sổ là 60 phút,
  refresh 30 giây, có đơn vị và threshold/SLO trên từng panel.
- **SLO và lý do chọn:** trong `config/slo.yaml`, 99.5% request trong cửa sổ
  28 ngày phải có `response_sent` với latency không vượt 3000 ms. Ngưỡng này
  đồng thời bao phủ availability và trải nghiệm chờ của người dùng.
- **Cách tính error budget:** `(100% - 99.5%) × tổng request = 0.5% × tổng request`. Với 10,000 request, tối đa 50 request được phép lỗi hoặc chậm hơn
  3000 ms.
- **Ba alert và runbook tương ứng:** `HighLatencyP95` (>3000 ms trong 5m),
  `HighRequestErrorRate` (>2% trong 5m) và `LowRetrievalSuccess` (<90%
  trong 10m). Cả ba gửi Slack `#k4-l3b-alerts`, owner
  `student-2A202602418`; quy trình kiểm tra và mitigation nằm trong
  `docs/alerts.md`.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (cohort `K4`, workload 5 request, concurrency 5).
- **Khoảng thời gian điều tra:** `2026-09-30T15:19:19.637536Z` đến
  `2026-09-30T15:19:32.961386Z` (`22:19:19`–`22:19:32`, UTC+7). Baseline
  được đo trước khi bật incident; incident đã được tắt sau khi thu thập evidence.
- **Triệu chứng từ metrics:** latency P95 tăng từ `903 ms` lên `2652 ms`
  (`+193.7%`), vượt ngưỡng challenge `2000 ms`; P99 cũng tăng lên
  `2652 ms`. Error rate vẫn `0%`, retrieval success `100%` và TTFT P95
  giữ ở `50 ms`, nên triệu chứng được khoanh vùng là latency chứ không phải
  error, retrieval failure hay generation TTFT.
- **Log line và correlation ID liên quan:** log `response_sent` lúc
  `2026-09-30T15:19:32.961386Z` có `correlation_id=req-369d576a`,
  `feature=monitoring`, `latency_ms=2651`, `tool_name=retrieval`,
  `tool_success=true`, `ttft_ms=50`, `tokens_in=35`, `tokens_out=85` và
  `cost_usd=0.00138`. Bốn request challenge còn lại có latency
  `2651`–`2657 ms`.
- **Trace ID và span gây ảnh hưởng:** trace
  `cb463b524ba7f0f514709c21ffba5c27` cùng `correlation_id=req-369d576a`
  có root `lab-agent-run` `2.65 s`; child `retrieval` (`RETRIEVER`)
  `2.50 s`, trong khi child `generation` chỉ `0.15 s`. Trace baseline
  `688d6b29ba8013eb3b4e53aa0148b971` (`req-90980a51`) có retrieval
  `0.001 s` và generation `0.151 s`, xác nhận phần tăng thêm nằm ở retrieval.
- **Root cause:** incident `rag_slow` chèn một lệnh chờ blocking `2.5 s`
  trong `app/mock_rag.py::retrieve`; retrieval chiếm khoảng `94%` thời gian
  của trace incident và chậm hơn baseline khoảng `2500` lần. Generation,
  token và cost không có mức tăng tương ứng.
- **Fix action:** đã chạy `python scripts/inject_incident.py --disable` để
  khôi phục ngay. Với hệ thống thật, rollback thay đổi retrieval gây chậm,
  đặt timeout dưới budget latency, dùng fallback khi vector store chậm và
  chuyển I/O retrieval sang non-blocking để không tuần tự hóa request đồng thời.
- **Preventive measure:** thêm early-warning cho request/retrieval P95 vượt
  `2000 ms`, theo dõi riêng duration của span retrieval, chạy canary/load test
  trước release và bổ sung timeout + circuit breaker + fallback vào runbook.

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** đặt PII scrubber ở pipeline
  logging chung thay vì gọi thủ công tại từng log statement. Cách này tạo một
  lớp bảo vệ cuối áp dụng đồng nhất cho string, dictionary và list trước khi dữ
  liệu được render hoặc ghi xuống file.
- **Một lỗi/blocker đã gặp:** validator đọc toàn bộ `data/logs.jsonl`, nên log
  cũ và nhiều lần chạy workload làm số liệu thay đổi; môi trường Python cục bộ
  cũng từng mất interpreter mà `.venv` tham chiếu tới.
- **Cách tìm nguyên nhân và xử lý:** tôi tách lỗi môi trường khỏi lỗi source,
  chạy lại bằng Python 3.11 trong container với đúng `requirements.txt`, kiểm
  tra validator trên log mới, rồi đối chiếu từng request bằng correlation ID.
- **Cách hiểu luồng Metrics → Logs → Traces:** metrics dùng để xác định loại
  triệu chứng và khoảng thời gian; structured log chọn một request đại diện;
  trace có cùng correlation ID cho biết child observation nào tạo ra phần lớn
  latency hoặc lỗi. Chỉ sau ba bước này mới kết luận root cause.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
  prompt version và label cho biết chính xác cấu hình nào tạo ra response và
  cho phép rollback không cần deploy code. Token/cost giúp phát hiện prompt
  phình bất thường; SLO và error budget chuyển kỳ vọng chất lượng thành ngưỡng
  đo được, còn alert/runbook giúp phản ứng nhất quán khi ngưỡng bị vi phạm.
- **Điều quan trọng nhất đã học:** một dashboard chỉ chỉ ra triệu chứng; khả
  năng nối metric, log và trace bằng cùng correlation ID mới giúp điều tra có
  bằng chứng và tránh đoán nguyên nhân.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** dashboard hiện đọc JSONL trong
  cửa sổ 60 phút và fake LLM/RAG chỉ mô phỏng production. Alert mới ở mức cấu
  hình/runbook, chưa kết nối Slack thật; hệ thống thực tế cần metrics backend,
  lưu trữ dài hạn và kiểm thử alert end-to-end.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
