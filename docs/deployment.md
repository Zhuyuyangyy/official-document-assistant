# 部署说明（AstronClaw / SkillHub）

> 本文档说明如何在 AstronClaw / SkillHub 平台部署「公文合规审查与督办助手」（`official-document-assistant`，v0.8.0）。
> 主脚本：`scripts/gov_doc_review.py`。技能定义：`SKILL.md`。

## 一、Skill 包结构

本 Skill 是标准的 Agent Skill 包，目录结构如下：

```
official-document-assistant/
├── SKILL.md              技能定义（frontmatter 含 name=official-document-assistant）
├── README.md             项目说明
├── CHANGELOG.md          版本变更日志
├── LICENSE               开源协议（MIT）
├── scripts/              确定性校验层（纯标准库脚本）
│   ├── gov_doc_review.py 主脚本（review/draft/brief/compare/batch）
│   └── run_tests.py      测试运行器
├── references/           领域知识库（供智能体查阅，可扩展）
│   ├── gongwen-checklist.md   公文要素清单与易错点
│   ├── drafting-guide.md      分文种起草规范
│   ├── basis-map.json         问题→依据映射
│   └── safety-policy.md       安全合规策略
├── examples/             示例输入与输出
│   ├── review/           待审公文（含 dirty-* 真实脏样本）
│   ├── brief/            会议纪要督办提取输入
│   ├── draft/            起草需求（自然语言或 JSON）
│   ├── compare/          版本对比输入（old/new）
│   └── outputs/          各模式对应的输出
├── templates/            审查报告 Markdown 模板
│   └── review-report.md
├── tests/                测试集
│   ├── cases/            15 个异常/边界/脏样本测试用例
│   └── robustness_report.md  鲁棒性报告
├── docs/                 文档
│   ├── design.md         两层架构设计说明
│   ├── security.md       安全合规说明
│   ├── evaluation.md     测试集与通过率
│   ├── deployment.md     部署说明（本文件）
│   └── demo_script.md    3 分钟演示脚本
└── demo/                 演示场景
    ├── demo_prompt_1_review.md
    ├── demo_prompt_2_draft.md
    ├── demo_prompt_3_meeting_brief.md
    └── demo_prompt_4_compare.md
```

### 关键文件

| 文件 | 作用 | 部署时是否必需 |
| --- | --- | --- |
| `SKILL.md` | 技能定义，含 frontmatter（name、display_name、description、version） | **必需** |
| `scripts/gov_doc_review.py` | 确定性校验层主脚本 | **必需** |
| `references/` | 领域知识库，供智能体层查阅 | 推荐 |
| `examples/` | 示例输入与输出，便于智能体理解格式 | 推荐 |
| `scripts/run_tests.py` | 测试运行器，用于回归验证 | 可选 |
| `tests/` | 测试用例 | 可选 |
| `docs/` | 文档 | 可选 |
| `templates/` | 报告模板 | 可选（脚本内置模板） |

## 二、在 AstronClaw 上加载与调用

### 1. 智能体加载 Skill

AstronClaw 智能体加载本 Skill 的流程：

1. **读取 `SKILL.md` frontmatter**：
   - `name: official-document-assistant`（Agent 平台注册名，与目录名一致）
   - `display_name: 公文合规审查与督办助手`（中文展示名）
   - `description: 面向办公室、行政、人事、学生组织和基层单位的正式材料处理 Skill...`
   - `version: 0.8.0`

2. **注册 Skill 能力**：智能体根据 `SKILL.md` 中的"核心模式"章节，注册 5 个可调用模式（review/draft/brief/compare/batch）。

3. **加载知识库**：智能体可读取 `references/` 下的知识库文件，作为生成修订稿和起草内容时的参考。

4. **调用脚本**：智能体按用户意图，通过命令行调用 `scripts/gov_doc_review.py`，读取 stdin 或文件，获取结构化输出。

### 2. 调用方式

智能体通过 CLI 调用脚本，脚本仅依赖 Python 标准库，**无需 pip install**，**无需网络 egress**：

```bash
# 审查模式：从 stdin 读取
python scripts/gov_doc_review.py --mode review --format markdown < examples/review/notice.md

# 审查模式：从文件读取
python scripts/gov_doc_review.py --mode review --format markdown --input examples/review/notice.md

# 起草模式：自动跑合规自检
python scripts/gov_doc_review.py --mode draft --format markdown < examples/draft/request.txt

# 会议督办台账：Markdown 表格
python scripts/gov_doc_review.py --mode brief --format markdown < examples/brief/meeting.md

# 会议督办台账：CSV（带 UTF-8 BOM，Excel 直接打开）
python scripts/gov_doc_review.py --mode brief --format csv < examples/brief/meeting.md

# 版本变更说明
python scripts/gov_doc_review.py --mode compare --old examples/compare/old.md --new examples/compare/new.md --format markdown

# 批量材料体检
python scripts/gov_doc_review.py --mode review --format markdown --batch examples/review

# docx 文件审查
python scripts/gov_doc_review.py --mode review --format markdown --input demo.docx --output report.md

# JSON 结构化输出（含 basis 依据字段）
python scripts/gov_doc_review.py --mode review --format json --input examples/review/notice.md
```

### 3. 智能体编排示例

智能体可按用户意图编排多个模式：

| 用户意图 | 智能体编排 |
| --- | --- |
| "帮我审查这份通知" | `review` 模式，输出三层报告 |
| "帮我起草一份请示" | `draft` 模式（自动自检），输出草稿 + 信息缺口 + 自检报告 |
| "把这份会议纪要的待办整理成台账" | `brief` 模式，输出督办台账表 |
| "对比这两版通知" | `compare` 模式，输出核心变化 + 风险变化表 |
| "帮我审查这批材料" | `batch` 模式，输出材料包体检报告 |
| "审查这份通知并提取督办" | `review` 模式（自带督办事项），输出三层报告 + 督办台账 |

## 三、环境要求

### 1. Python 版本

- **Python 3.8+**（使用了 `from __future__ import annotations`、`dataclasses`、`pathlib`、`typing` 等特性）。
- 推荐 Python 3.10+（使用了 `str | None` 等 PEP 604 语法，但通过 `from __future__ import annotations` 兼容 3.8+）。

### 2. 无需 pip install

脚本仅依赖 Python 标准库，**不需要安装任何第三方包**：

- 不需要 `python-docx`（`.docx` 解析用标准库 `zipfile` + `xml.etree.ElementTree`）。
- 不需要 `openpyxl`（CSV 输出用标准库 `csv`）。
- 不需要 `requests` / `httpx`（不联网）。
- 不需要 `pytest`（测试运行器用标准库 `subprocess`）。

### 3. 无需网络 egress

- 脚本不发起任何网络请求。
- 部署时无需配置出网白名单、无需配置代理。
- 适合在内网、离线环境运行。

### 4. 文件系统权限

- 脚本需要读取用户指定的输入文件（`--input` 或 `--batch` 目录）。
- 如果使用 `--output`，需要写入指定输出文件的权限。
- 如果不使用 `--output`，结果输出到 stdout，无需文件写入权限。

## 四、各模式调用示例

### 1. review 模式（公文审查）

```bash
# 从 stdin 读取
python scripts/gov_doc_review.py --mode review --format markdown < examples/review/notice.md

# 从文件读取
python scripts/gov_doc_review.py --mode review --format markdown --input examples/review/notice.md

# 审查 docx
python scripts/gov_doc_review.py --mode review --format markdown --input demo.docx --output report.md

# JSON 输出（含 basis 依据字段）
python scripts/gov_doc_review.py --mode review --format json --input examples/review/notice.md
```

输出：三层报告（领导摘要 / 结构识别 / 承办人修改清单 / 建议修订稿 / 督办事项 / 脱敏预览）。

### 2. draft 模式（起草 + 自检）

```bash
# 自然语言需求
python scripts/gov_doc_review.py --mode draft --format markdown < examples/draft/request.txt

# JSON 需求
echo '{"doc_type":"通知","topic":"开展办公技能培训","sender":"各部门","issuer":"办公室","requirements":["明确参训人员","6月30日前完成报名"]}' | python scripts/gov_doc_review.py --mode draft --format markdown
```

输出：可编辑草稿 + 起草信息缺口 + 自动合规自检报告。

### 3. brief 模式（会议督办台账）

```bash
# Markdown 表格
python scripts/gov_doc_review.py --mode brief --format markdown < examples/brief/meeting.md

# CSV（带 UTF-8 BOM，Excel 直接打开）
python scripts/gov_doc_review.py --mode brief --format csv < examples/brief/meeting.md

# JSON
python scripts/gov_doc_review.py --mode brief --format json < examples/brief/meeting.md
```

输出：督办台账表（序号/责任单位/待办事项/截止时间/原文依据/建议状态）。CSV 带 UTF-8 BOM，Excel 直接打开中文不乱码。

### 4. compare 模式（版本变更说明）

```bash
python scripts/gov_doc_review.py --mode compare --old examples/compare/old.md --new examples/compare/new.md --format markdown

# JSON 输出
python scripts/gov_doc_review.py --mode compare --old examples/compare/old.md --new examples/compare/new.md --format json
```

输出：核心变化 + 风险变化表 + 提交建议。

### 5. batch 模式（批量材料体检）

```bash
python scripts/gov_doc_review.py --mode review --format markdown --batch examples/review

# JSON 输出
python scripts/gov_doc_review.py --mode review --format json --batch examples/review
```

输出：总览 + 文件风险排行表 + 跳过清单。批量请指向只含待审文档的目录。

## 五、扩展组织内部规则

### 1. 在 references/ 追加组织规则

组织可在 `references/` 目录追加本单位行文规则：

- **`gongwen-checklist.md`**：追加本单位行文细则。例如：
  ```markdown
  ## 我单位行文细则
  - 通知必须抄送纪检处。
  - 请示金额超过 50 万元的，须附预算明细。
  - 函件落款须加盖单位公章电子影像。
  ```
- **`drafting-guide.md`**：追加本单位常用表述模板。
- **`basis-map.json`**：追加本单位内部制度作为依据来源。例如：
  ```json
  "missing_cc_jijian": {
    "basis": "《XX单位公文处理办法》 第十二条 抄送规则",
    "human_readable": "我单位通知必须抄送纪检处。"
  }
  ```
- **`safety-policy.md`**：追加本单位保密要求。

智能体层在生成修订稿或起草时，可查阅这些文件，确保输出符合组织内部规则。

### 2. 在脚本中追加检查规则

如需脚本自动检查组织内部规则，可在 `scripts/gov_doc_review.py` 的 `check_common_rules()` 或 `check_doc_type_rules()` 中追加检查逻辑：

```python
# 示例：检查通知是否抄送纪检处
if doc_type == "通知" and "抄送" in text and "纪检" not in text:
    add_issue(issues, "未抄送纪检处", "medium", "通知未抄送纪检处",
              "我单位通知须抄送纪检处。",
              "《XX单位公文处理办法》 第十二条 抄送规则")
```

### 3. 扩展文种支持

当前支持：通知、请示、报告、函、纪要、简报、方案、通报。

如需扩展（如"决定""意见""批复"）：

1. 在 `DOC_TYPES` 列表追加文种名。
2. 在 `check_doc_type_rules()` 追加该文种的行文规则检查。
3. 在 `generate_template()` 追加该文种的草稿模板。
4. 在 `references/basis-map.json` 追加该文种相关的问题→依据映射。

## 六、回归测试

部署后建议运行回归测试，确认脚本行为正常：

```bash
python scripts/run_tests.py
```

预期输出：

```
[PASS] 01_good_notice.md (review/markdown) — ok
[PASS] 02_missing_sender.md (review/markdown) — ok
...
[PASS] 15_level_mixing.md (review/markdown) — ok

15/15 passed. Report written to tests/robustness_report.md.
```

如出现 FAIL，请检查：

- Python 版本是否 ≥ 3.8。
- 测试用例文件是否完整（`tests/cases/` 下应有 15 个文件）。
- 脚本是否有写权限（`run_tests.py` 需要写 `tests/robustness_report.md`）。

## 七、常见问题

### Q1：脚本运行报 `ModuleNotFoundError`？

A：本脚本仅依赖 Python 标准库，不应出现此错误。请检查：
- Python 版本是否 ≥ 3.8（`python --version`）。
- 是否在正确的目录下运行（脚本路径 `scripts/gov_doc_review.py` 应存在）。
- 是否误装了同名第三方包覆盖标准库。

### Q2：CSV 用 Excel 打开中文乱码？

A：本脚本输出的 CSV 已带 UTF-8 BOM（`\ufeff`），Excel 应能正确识别中文。如仍乱码，请检查：
- Excel 版本是否过旧（建议 Excel 2016+）。
- 是否用"数据 → 从文本/CSV"导入而非直接打开。

### Q3：docx 文件审查报"无法解析"？

A：请检查：
- 文件是否是真正的 `.docx`（OOXML 格式），而非 `.doc`（旧版二进制格式）或改名的文本文件。
- 文件是否损坏（尝试用 Word 打开确认）。
- 脚本对 `.doc` 格式不支持，请先另存为 `.docx`。

### Q4：批量审查跳过了某些文件？

A：批量模式会自动跳过：
- 本工具生成的审查报告（以 `# 公文材料审查报告` 开头）。
- 起草需求 JSON（含 `doc_type`/`topic`/`requirements` 字段）。
- 非公文/起草请求（分诊未通过）。
- 损坏文件（读取失败）。

跳过原因会在"三、已跳过文件"章节列出。如需审查这些文件，请改用单文件 `--input` 模式。

### Q5：可以在容器中运行吗？

A：可以。本脚本零依赖、零联网，适合在最小化容器中运行。Dockerfile 示例：

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . /app
# 无需 pip install
CMD ["python", "scripts/run_tests.py"]
```
