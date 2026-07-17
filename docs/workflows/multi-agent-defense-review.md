# Multi-agent defense review

Status: `ACTIVE`

Workflow này dùng ba custom agents để nâng chất lượng tài liệu và phần bảo vệ đồ
án. Primary Owner vẫn là thread chính, giữ context, quyết định scope và chịu
trách nhiệm kết luận cuối cùng.

## Vai trò

| Vai trò | Custom agent | Quyền | Trách nhiệm |
|---|---|---|---|
| Primary Owner | Main thread | Theo phiên người dùng | Chia slice, giữ context, điều phối, kiểm chứng cuối |
| Professor | `professor` (`Sol`) | GPT-5.6 Sol, read-only | Rubric, định hướng, phản biện thiết kế và chấm bài |
| Executor | `executor` (`Builder`) | GPT-5.5, workspace-write | Sửa code/tài liệu, chạy test và trả evidence |
| Examiner | `examiner` (`Reviewer`) | Codex Auto Review, read-only | Phản biện độc lập, hỏi vặn và tìm code-doc mismatch |

Tên hiển thị không phải model ID. Model của mỗi vai trò nằm trong
`.codex/agents/*.toml` và chỉ hoạt động khi tài khoản hiện tại có quyền dùng
model đó. Mapping hiện tại theo model picker của Codex Desktop; model ID của Sol
là `gpt-5.6-sol`. CLI 0.137 có thể chưa liệt kê dòng GPT-5.6 dù Desktop đã được
rollout. Nếu catalog của Desktop thay đổi, thay riêng trường `model`; không thay
đổi rubric hoặc developer instructions.

## Vòng thực hiện

```text
Primary Owner chia một slice có boundary rõ
                  |
                  v
Professor tạo rubric + acceptance criteria
                  |
                  v
Executor triển khai + test + evidence
                  |
                  v
Examiner phản biện độc lập
            |                 |
     NEEDS_REVISION          PASS
            |                 |
            v                 v
Professor hướng dẫn lại   Owner chạy gate cuối
            |
            v
Executor sửa vòng tiếp theo
```

Không chạy Professor và Executor song song trên cùng một slice vì Executor cần
rubric trước. Examiner chỉ bắt đầu sau khi Executor đã trả evidence. Có thể chạy
nhiều Examiner song song nếu mỗi người có phạm vi độc lập, nhưng tổng số thread
đang mở bị giới hạn bởi `.codex/config.toml`.

## Prompt khởi động

```text
Áp dụng multi-agent defense review cho [tên phần].

1. Spawn professor để lập rubric, câu hỏi phản biện và acceptance criteria.
2. Sau khi nhận rubric, spawn executor để triển khai đúng slice và trả evidence.
3. Spawn examiner để review độc lập kết quả, không cho xem kết luận của executor
   như nguồn sự thật.
4. Nếu examiner không PASS, gửi findings cho professor định hướng lại rồi giao
   executor sửa tiếp.
5. Lặp đến khi PASS hoặc blocker thực sự.
6. Primary Owner chạy test, kiểm tra link/anchor và tổng hợp rủi ro còn lại.

Không commit, push, merge hoặc deploy nếu tôi chưa yêu cầu rõ.
```

## Gate hoàn thành

- Professor xác nhận rubric đã được đáp ứng.
- Examiner không còn finding CRITICAL hoặc MAJOR.
- Mỗi claim quan trọng có code/SQL/test/evidence reference.
- Test phù hợp với blast radius đã chạy.
- Markdown links và line anchors hợp lệ.
- Giới hạn, deferred work và exploratory outputs được nói đúng trạng thái.
- Primary Owner kiểm tra diff và xác nhận không có thay đổi ngoài scope.

## Giới hạn vận hành

- Multi-agent tốn nhiều token và thời gian hơn một agent.
- Model khác nhau không bảo đảm ý kiến độc lập tuyệt đối; evidence vẫn là chuẩn
  quyết định cuối cùng.
- `max_depth = 1` ngăn agent con tự fan-out thêm agent khác.
- Read-only giảm rủi ro Professor/Examiner vô tình sửa bài.
- Approval và permission thực tế vẫn chịu cấu hình của phiên cha.
