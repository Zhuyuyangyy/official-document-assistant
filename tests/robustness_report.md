# 鲁棒性测试报告

> 自动生成自 `scripts/run_tests.py`，覆盖空输入、短文本、起草请求误投、
> 损坏/非 UTF-8 文件、批量混合文件、敏感信息、文种混用、会议督办等场景。

## 一、总览

- 测试用例：15 个
- 通过：15 个
- 失败：0 个
- 通过率：100.0%

## 二、用例明细

| 用例 | 模式 | 格式 | 预期 | 结果 | 说明 |
| --- | --- | --- | --- | --- | --- |
| 01_good_notice.md | review | markdown | 正常输出 | ✅ | — |
| 02_missing_sender.md | review | markdown | 正常输出 | ✅ | — |
| 03_bad_date.md | review | markdown | 正常输出 | ✅ | — |
| 04_report_with_request.md | review | markdown | 正常输出 | ✅ | — |
| 05_request_multi_matters.md | review | markdown | 正常输出 | ✅ | — |
| 06_phone_id_sensitive.md | review | markdown | 正常输出 | ✅ | — |
| 07_confidential.md | review | markdown | 正常输出 | ✅ | — |
| 08_meeting_actions.md | brief | markdown | 正常输出 | ✅ | — |
| 09_empty_input.txt | review | markdown | 友好提示 | ✅ | — |
| 10_short_input.txt | review | markdown | 友好提示 | ✅ | — |
| 11_draft_request_to_review.txt | review | markdown | 友好提示 | ✅ | — |
| 12_draft_json.txt | draft | markdown | 正常输出 | ✅ | — |
| 13_good_notice_long.md | review | markdown | 正常输出 | ✅ | — |
| 14_letter_wrong_tone.md | review | markdown | 正常输出 | ✅ | — |
| 15_level_mixing.md | review | markdown | 正常输出 | ✅ | — |

## 三、覆盖场景

| 场景 | 对应用例 |
| --- | --- |
| 规范通知（应通过审查） | 01_good_notice.md |
| 缺主送机关 | 02_missing_sender.md |
| 成文日期格式不规范（2026-07-01） | 03_bad_date.md |
| 报告夹带请示事项 | 04_report_with_request.md |
| 请示一文多事 | 05_request_multi_matters.md |
| 手机号 + 身份证号（脱敏预览） | 06_phone_id_sensitive.md |
| 涉密/内部资料 | 07_confidential.md |
| 会议纪要督办台账 | 08_meeting_actions.md |
| 空输入（友好提示） | 09_empty_input.txt |
| 过短输入（友好提示） | 10_short_input.txt |
| 起草请求误投审查模式（友好提示） | 11_draft_request_to_review.txt |
| JSON 起草需求 + 自动自检 | 12_draft_json.txt |
| 长篇规范通知 | 13_good_notice_long.md |
| 函语气不平行 | 14_letter_wrong_tone.md |
| 正文层级混用 | 15_level_mixing.md |

## 四、异常输入保护说明

脚本入口和所有读取路径均加保护：
- 非 UTF-8 文件用 `errors="replace"` 读取，不抛异常。
- 损坏 `.docx`（非 zip / 缺 word/document.xml / XML 解析失败）返回 `# 输入提示`，不抛 traceback。
- 空输入、过短输入、起草请求误投审查模式，均返回 `# 输入提示` 引导用户，不产出误导性 0/100 报告。
- 批量审查单文件出错不影响整体，错误文件记入跳过清单。
- 入口 `try/except` 兜底，任何未预期错误返回 `已安全退出`，不抛 raw traceback。

