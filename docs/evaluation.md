# 测试集与通过率

> 本文档说明「公文合规审查与督办助手」（`official-document-assistant`，v0.8.0）的测试集设计、运行方式、通过率、典型错误案例与鲁棒性保证。
> 测试运行器：`scripts/run_tests.py`。测试用例：`tests/cases/`。鲁棒性报告：`tests/robustness_report.md`。

## 一、测试集概览

测试集位于 `tests/cases/`，共 **15 个用例**，覆盖正常公文、异常输入、边界场景和脏样本。每个用例是一个独立的 `.md` 或 `.txt` 文件，模拟用户可能提交的真实输入。

### 用例清单

| 序号 | 文件 | 模式 | 覆盖场景 | 预期结果 |
| --- | --- | --- | --- | --- |
| 01 | `01_good_notice.md` | review | 规范通知（应通过审查） | 正常输出审查报告 |
| 02 | `02_missing_sender.md` | review | 缺主送机关 | 输出"缺少主送机关"问题 |
| 03 | `03_bad_date.md` | review | 成文日期格式不规范（`2026-07-01`） | 输出"成文日期格式不规范"问题 |
| 04 | `04_report_with_request.md` | review | 报告夹带请示事项 | 输出"报告疑似夹带申请事项"问题 |
| 05 | `05_request_multi_matters.md` | review | 请示一文多事 | 输出"一文一事"问题 |
| 06 | `06_phone_id_sensitive.md` | review | 手机号 + 身份证号（脱敏预览） | 输出"疑似个人敏感信息" + 脱敏预览 |
| 07 | `07_confidential.md` | review | 涉密/内部资料 | 输出"疑似涉密或内部资料"问题 |
| 08 | `08_meeting_actions.md` | brief | 会议纪要督办台账 | 输出"会议督办台账"含"办公室" |
| 09 | `09_empty_input.txt` | review | 空输入 | 返回 `# 输入提示` |
| 10 | `10_short_input.txt` | review | 过短输入 | 返回 `# 输入提示` |
| 11 | `11_draft_request_to_review.txt` | review | 起草请求误投审查模式 | 返回 `# 输入提示` |
| 12 | `12_draft_json.txt` | draft | JSON 起草需求 + 自动自检 | 输出"起草结果" + "自动合规自检" |
| 13 | `13_good_notice_long.md` | review | 长篇规范通知 | 正常输出审查报告 |
| 14 | `14_letter_wrong_tone.md` | review | 函语气不平行 | 输出"函的语气不够平行商洽"问题 |
| 15 | `15_level_mixing.md` | review | 正文层级混用 | 输出"正文层级可能混用"问题 |

### 用例分布

- **正常公文**（应通过审查）：01、13
- **格式要素缺失/不规范**：02（缺主送）、03（日期不规范）
- **文种规则违反**：04（报告夹带请示）、05（请示一文多事）、14（函语气）、15（层级混用）
- **敏感信息与涉密**：06（PII）、07（涉密）
- **会议督办**：08
- **异常输入分诊**：09（空）、10（过短）、11（起草请求误投）
- **起草自检**：12（JSON 起草）

## 二、如何运行

### 1. 运行全部测试

```bash
python scripts/run_tests.py
```

测试运行器会：

1. 遍历 `tests/cases/` 下的 15 个用例。
2. 对每个用例，按指定的 `--mode` 和 `--format` 调用 `scripts/gov_doc_review.py --input <用例文件>`。
3. 检查输出：
   - 是否抛出 traceback（不应抛出）。
   - 退出码是否为 0（应为 0）。
   - 输出是否包含预期的关键词（如"缺少主送机关""成文日期格式不规范"）。
   - 对于 `needs_clarification` 类用例，输出是否以 `# 输入提示` 开头。
4. 打印每个用例的 PASS/FAIL 结果。
5. 打印总通过率。
6. 将详细报告写入 `tests/robustness_report.md`。

### 2. 运行单个用例

```bash
# 运行 02_missing_sender.md
python scripts/gov_doc_review.py --mode review --format markdown --input tests/cases/02_missing_sender.md

# 运行 09_empty_input.txt（空输入分诊）
python scripts/gov_doc_review.py --mode review --format markdown --input tests/cases/09_empty_input.txt

# 运行 12_draft_json.txt（起草自检）
python scripts/gov_doc_review.py --mode draft --format markdown --input tests/cases/12_draft_json.txt
```

### 3. 查看鲁棒性报告

```bash
# 报告由 run_tests.py 自动生成
cat tests/robustness_report.md
```

## 三、通过率

截至 v0.8.0，**15/15 用例全部通过，通过率 100.0%**。

| 指标 | 数值 |
| --- | --- |
| 测试用例总数 | 15 |
| 通过数 | 15 |
| 失败数 | 0 |
| 通过率 | 100.0% |

### 用例明细（v0.8.0）

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

## 四、典型错误案例与处理方式

以下展示脚本如何用"友好引导"代替"traceback 崩溃"。

### 案例 1：空输入（用例 09）

**输入**：空文件。

**如果没加分诊**：脚本可能产出一份"0/100 分、所有要素都缺失"的误导性报告，让用户以为自己的材料"一无是处"。

**实际处理**：`triage_input()` 检测到 `text.strip()` 为空，返回：

```
# 输入提示

未检测到正文内容。审查模式请粘贴完整的公文或会议纪要；起草模式请用一句话或 JSON 说明文种、主题、主送机关和要求。
```

智能体层据此引导用户："看起来您没有粘贴正文，请提供完整的公文材料。"

### 案例 2：起草请求误投审查模式（用例 11）

**输入**：`帮我写一份关于开展培训的通知`（这是一句起草请求，但用户用了 `--mode review`）。

**如果没加分诊**：脚本会把这句话当成"公文正文"审查，产出"标题三要素不完整""缺少主送机关""正文内容过短"等一系列问题，让用户困惑——"我只是想让你帮我写，你怎么批评我写得不好？"

**实际处理**：`triage_input()` 检测到输入匹配 `^\s*(请\s*)?(帮我?|麻烦)\s*(写|起草|生成|拟|出)` 且长度 < 60，返回：

```
# 输入提示

这看起来是一句起草请求，当前为审查模式。请改用 --mode draft 生成草稿，或粘贴已写好的公文正文再审查。
```

智能体层据此引导用户："您是想起草一份通知吗？我帮您切换到起草模式。"

### 案例 3：过短输入（用例 10）

**输入**：`通知`（只有一个词）。

**如果没加分诊**：脚本会把它当成公文审查，产出"标题三要素不完整""缺少主送机关""缺少成文日期""正文内容过短"等问题——技术上没错，但对用户毫无帮助。

**实际处理**：`triage_input()` 检测到输入长度 < 15 且不含文种信号/冒号，返回：

```
# 输入提示

输入内容过短，难以判断为公文材料。请提供包含标题、主送机关、正文和落款的完整材料。
```

### 案例 4：损坏 docx

**输入**：一个 `.txt` 文件被改名为 `.docx`，或一个真实的损坏 docx。

**如果没加保护**：`zipfile.ZipFile()` 抛 `BadZipFile`，脚本崩溃，用户看到一串 Python traceback。

**实际处理**：`read_docx_text()` 捕获 `BadZipFile`/`KeyError`/`OSError`，包装成 `InputError`，上层捕获后返回：

```
# 输入提示

无法解析 .docx 文件（可能不是有效的 Word 文档或文件已损坏）：demo.docx
```

### 案例 5：非 UTF-8 文件

**输入**：一个 GBK 编码的文本文件。

**如果没加保护**：`Path.read_text(encoding="utf-8")` 抛 `UnicodeDecodeError`，脚本崩溃。

**实际处理**：`read_input()` 用 `encoding="utf-8", errors="replace"` 读取，遇到非法字节用替换字符（U+FFFD）代替，**不抛异常**，脚本继续运行。虽然输出中可能有少量乱码字符，但不会崩溃。

### 案例 6：批量审查中的单文件失败

**输入**：`--batch examples/review`，目录中混有正常文件和损坏文件。

**如果没加保护**：遇到第一个损坏文件就崩溃，后面的文件全部跳过。

**实际处理**：`main()` 的 batch 分支对每个文件单独 `try/except`，损坏文件记入 `skipped` 列表，继续处理下一个文件。最终输出"批量材料体检报告"，含"三、已跳过文件"章节列出跳过原因。

## 五、鲁棒性保证

脚本通过以下机制保证鲁棒性：

### 1. 非 UTF-8 文件用 errors="replace" 读取

```python
# read_input() 中
return sanitize_text(input_path.read_text(encoding="utf-8", errors="replace")), {}
```

stdin 同样 reconfigure：

```python
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
```

### 2. 损坏 docx 返回友好错误

```python
# read_docx_text() 中
try:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
        names = archive.namelist()
except (zipfile.BadZipFile, KeyError, OSError) as exc:
    raise InputError(f"无法解析 .docx 文件（可能不是有效的 Word 文档或文件已损坏）：{path}") from exc
try:
    root = ET.fromstring(xml)
except ET.ParseError as exc:
    raise InputError(f".docx 文档结构异常，无法提取正文：{path}") from exc
```

### 3. 批量单文件失败不影响整体

```python
# main() 的 batch 分支
for file_path in sorted(folder.iterdir()):
    try:
        text, meta = read_input(str(file_path))
    except InputError as exc:
        skipped.append(f"{file_path.name}（{exc}）")
        continue
    # ... 处理该文件
```

### 4. 顶层 try/except 兜底

```python
# 脚本入口
if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断。\n")
        raise SystemExit(130)
    except Exception as exc:  # last-resort guard: never emit a raw traceback
        sys.stderr.write(f"处理时发生未预期错误，已安全退出：{type(exc).__name__}\n")
        raise SystemExit(1)
```

任何未预期错误都返回"已安全退出"，**不抛 raw traceback**。

### 5. 输入分诊（triage_input）

`triage_input()` 在 `run_one()` 最开始调用，对空输入、起草请求误投、过短非公文文本返回 `# 输入提示`，避免产出误导性的 0/100 报告。批量模式（`--batch`）也走分诊，对每个文件单独 triage。

### 6. 控制字符清理

`sanitize_text()` 用正则 `[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]` 去除控制字符，避免控制字符干扰后续正则匹配和 Markdown 表格渲染。

## 六、测试运行器实现说明

`scripts/run_tests.py` 是一个轻量回归测试运行器：

- **不依赖第三方测试框架**（不用 pytest、unittest），仅用 `subprocess` 调用主脚本。
- 每个用例的预期用"关键词包含"判断（如输出包含"缺少主送机关"即视为通过）。
- 对 `needs_clarification` 类用例，判断输出是否以 `# 输入提示` 开头。
- 同时检查 stderr 和 stdout 中是否出现 `Traceback`（不应出现）。
- 生成 `tests/robustness_report.md` 报告，含总览、用例明细、覆盖场景、异常输入保护说明。

### CASES_SPEC 设计

`CASES_SPEC` 是一个元组列表，每个元组 `(filename, mode, format, expected_substrings, expected_status)`：

- `expected_substrings`：输出中应包含的关键词列表。
- `expected_status`：`"pass"`（正常输出）或 `"needs_clarification"`（友好提示）。

新增用例时，只需在 `tests/cases/` 添加文件，并在 `CASES_SPEC` 追加一行即可。

## 七、已知限制

- 测试用例的预期判断基于"关键词包含"，不是严格的语义对比。对于"输出是否合理"这类主观判断，仍需人工复核。
- 测试集目前覆盖 15 个场景，但未覆盖所有边界（如超大文件、超长行、特殊 Unicode 字符等），后续可扩展。
- `.docx` 测试用例目前未纳入自动化测试（需要准备二进制 docx 文件），后续可补充。
- 测试运行器本身不测试 `compare` 模式（需要两个文件），后续可扩展。
