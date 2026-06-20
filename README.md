# 公文合规审查与督办助手 (official-document-assistant)

> 面向办公室、行政、人事、学生组织和基层单位的正式材料处理 Skill。
> 它不是简单“帮你写公文”，而是围绕正式材料流转中的真实痛点，完成：公文格式与文种规则审查、通知/请示/报告/函/会议纪要草稿起草、会议纪要待办事项提取、敏感信息与涉密风险提示、多版本修改说明、批量材料初审。

> 中文展示名：公文合规审查与督办助手
> Agent 平台注册名（SKILL.md frontmatter）：`official-document-assistant`
> 当前版本：v0.8.0

## 为什么不是“直接问大模型”？

办公室材料反复退回的真正原因，往往不是“写得不好”，而是**格式要素不齐、文种混用、敏感信息没脱敏、会议待办没人跟**——这些恰恰是大模型容易幻觉、难以可复现的地方。

本 Skill 把工作分成两层：

- **智能体层（宿主大模型）**：语义理解、文种复核、修订润色、起草生成、异常输入引导。
- **确定性校验层（本仓库脚本）**：纯标准库、不调模型，做可复现、不幻觉的格式校验、敏感信息脱敏和结构化抽取。

判断与改写交给模型，合规校验与脱敏交给确定性程序——既避免模型在格式要素和敏感信息上幻觉，也让每条意见都能追溯到 GB/T 9704—2012《党政机关公文格式》与《党政机关公文处理工作条例》。

## 核心能力

- **公文审查**：识别文种，检查标题、主送机关、正文、附件说明、发文机关署名、成文日期和用语规范；输出三层报告（领导摘要 / 承办人修改清单 / 建议修订稿）。
- **专项规则**：针对请示、报告、函、通知分别检查常见公文错误（一文一事、报告不夹带请示、函语气平行商洽、通知可执行性等）。
- **模板起草**：根据 JSON 或一句话需求生成通知、请示、报告、函、会议纪要草稿骨架，**草稿生成后自动跑一遍合规自检**，输出“草稿 + 信息缺口 + 自检报告”。
- **会议督办台账**：从会议纪要中提取责任方、截止时间和待办事项，输出可贴入 Excel 的督办台账表（Markdown 表格或 CSV）。
- **版本变更说明**：对比两版材料，输出核心变化、风险变化表和提交建议，覆盖办公流转协同场景。
- **批量材料体检**：批量审查文件夹内材料，输出风险排行表与跳过清单。
- **安全合规**：识别手机号、身份证号、涉密/内部资料表述，并给出本地脱敏预览；不联网、不外传。

## 本地运行

```bash
# 审查
python scripts/gov_doc_review.py --mode review --format markdown < examples/review/notice.md
python scripts/gov_doc_review.py --mode review --format markdown --input examples/review/notice.md
python scripts/gov_doc_review.py --mode review --format json     --batch examples/review

# 起草（自动跑合规自检）
python scripts/gov_doc_review.py --mode draft  --format markdown < examples/draft/request.txt

# 会议督办台账（支持 CSV 导出）
python scripts/gov_doc_review.py --mode brief  --format markdown < examples/brief/meeting.md
python scripts/gov_doc_review.py --mode brief  --format csv      < examples/brief/meeting.md

# 版本变更说明
python scripts/gov_doc_review.py --mode compare --old examples/compare/old.md --new examples/compare/new.md --format markdown

# docx
python scripts/gov_doc_review.py --mode review --format markdown --input demo.docx --output report.md
```

## 参数说明

- `--mode review`：公文格式和合规审查。
- `--mode draft`：根据 JSON 或自然语言需求生成公文草稿骨架，并自动跑合规自检。
- `--mode brief`：会议纪要/简报督办台账提取。
- `--mode compare`：两版材料版本变更说明，需配合 `--old` 与 `--new`。
- `--format markdown`：输出适合复制粘贴的审查报告。
- `--format json`：输出结构化结果（含 `basis` 依据字段），便于二次处理。
- `--format csv`：仅在 `brief` 模式下生效，输出可贴入 Excel 的督办台账 CSV。
- `--input`：读取 UTF-8 文本、Markdown、JSON 或 `.docx` 文件。
- `--old` / `--new`：`compare` 模式下指定两版材料文件路径。
- `--batch`：批量审查文件夹内文本与 `.docx`，自动跳过生成的报告和起草需求 JSON，并对非公文/起草请求给出"输入提示"友好跳过；输出材料包体检报告与风险排行。
- `--output`：把结果写入指定文件。

## 输出结构

### 审查模式（三层报告）

1. **领导摘要**：一句话风险结论 + 风险等级 + 三大主要问题。
2. **承办人修改清单**：表格形式，含序号、问题、严重程度、原文证据、修改建议、依据。
3. **建议修订稿**：给出一版可直接复制再人工复核的规范文本。
4. **督办事项**：责任方、期限、事项（表格形式）。
5. **脱敏预览**：对手机号、身份证号等字段进行本地脱敏展示。

### 起草模式

输出“可编辑草稿 + 起草信息缺口 + 自动合规自检报告”。

### brief 模式

输出督办台账表（Markdown 表格或 CSV），可直接贴入 Excel 或任务系统。

### compare 模式

输出“核心变化 + 风险变化表 + 提交建议”。

## 示例与目录结构

```
SKILL.md              技能定义（frontmatter name 须与提交名一致）
README.md             项目说明
CHANGELOG.md          版本变更日志
LICENSE               开源协议
scripts/              确定性校验层（纯标准库脚本）
  gov_doc_review.py   主脚本（review/draft/brief/compare/batch）
  run_tests.py        测试运行器
references/           领域知识库（供智能体查阅，可扩展）
  gongwen-checklist.md
  drafting-guide.md
  basis-map.json      问题→依据映射
  safety-policy.md    安全合规策略
examples/
  review/             待审公文（含 dirty-* 真实脏样本）
  brief/              会议纪要督办提取输入
  draft/              起草需求（自然语言或 JSON）
  compare/            版本对比输入（old/new）
  outputs/            各模式对应的输出
templates/            审查报告 Markdown 模板
tests/
  cases/              30+ 异常/边界/脏样本测试用例
  expected/           预期输出
  robustness_report.md 鲁棒性报告
docs/
  design.md           两层架构设计说明
  security.md         安全合规说明
  evaluation.md       测试集与通过率
  deployment.md       AstronClaw / SkillHub 部署步骤
  demo_script.md      3 分钟演示脚本
demo/                 演示场景与截图
```

## 鲁棒性与测试

已内置 30+ 个异常/边界/脏样本测试，覆盖空输入、短文本、损坏 docx、非 UTF-8、批量混合文件、敏感信息、文种混用、会议督办等情况。运行：

```bash
python scripts/run_tests.py
```

详细通过率与典型错误案例见 `tests/robustness_report.md` 与 `docs/evaluation.md`。

## SkillHub / 平台提交

作品中文展示名：**公文合规审查与督办助手**

一句话介绍：**面向办公室、行政、人事、基层单位和学生组织的正式材料处理 Skill，支持公文审查、草稿起草、会议待办提取、敏感信息脱敏和版本变更说明。**

核心卖点：

1. **可解释**：每条问题给出依据，不只给泛泛修改建议。
2. **可落地**：审查、修订、起草、督办、版本对比五步覆盖办公室真实流程。
3. **可控安全**：确定性脚本本地运行，不联网，敏感信息先脱敏。

Agent 平台 frontmatter 名称（必填，与目录名一致）：

```text
official-document-assistant
```

## 已知限制

- 本 Skill 是轻量、可解释、无外部依赖的参赛版，不替代人工公文审核、法律审核或保密审查。
- `.docx` 解析提取正文段落与表格文本；页眉、页脚、版记不纳入自动审查；检测到批注或修订痕迹时会提示用户提交前确认，但不解析具体修订内容。
- 问题依据指向 GB/T 9704—2012 与《党政机关公文处理工作条例》的要素和原则；具体条款序号以正式文本为准。
- 不编造政策依据。涉及政策、法规、涉密材料、个人隐私和未公开政务数据时，应由用户提供依据并进行人工复核。

## 升级日志

### v0.8.0（2026-06，比赛冲奖版）

- **重定位与改名**：展示名从"讯飞政务开发skill"改为"公文合规审查与督办助手"，叙事从"政务"扩展到"办公室/行政/人事/学生组织/基层单位"的正式材料协同。
- **新增 compare 版本变更说明模式**：对比两版材料，输出核心变化、风险变化表与提交建议，覆盖办公流转协同场景。
- **brief 升级为督办台账**：输出 Markdown 表格与 CSV，可直接贴入 Excel 或任务系统。
- **draft 自动合规自检**：草稿生成后自动跑一遍 review，输出"草稿 + 信息缺口 + 自检报告"。
- **batch 升级为材料包体检**：输出风险排行表与跳过清单。
- **审查报告三层结构**：领导摘要 / 承办人修改清单 / 建议修订稿，更贴合办公室实际使用。
- **.docx 增强**：提取表格文本；检测批注/修订痕迹并提示用户提交前确认。
- **依据映射**：新增 `references/basis-map.json`，问题→依据结构化映射，保证输出依据统一可追溯。
- **测试集**：新增 `tests/` 目录，30+ 异常/边界/脏样本测试用例与 `run_tests.py` 回归脚本。
- **文档体系**：新增 `docs/`（design/security/evaluation/deployment/demo_script）与 `demo/` 演示场景。

### v0.5（2026-06）

- **防崩溃加固**：`.docx` 解析、文件读取、批量逐文件、入口全部加保护；非 UTF-8 用替换字符读取；新增输入分诊（空输入、起草请求误投审查模式、过短/非公文文本→"# 输入提示"而非错误报告）；任何输入不再抛 traceback。
- **批处理也走分诊**：`--batch` 模式对 review/brief 调用 `triage_input`，起草请求/非公文文本不再被误判为高风险公文。
- **领域知识库** `references/`：`gongwen-checklist.md`、`drafting-guide.md`，供智能体层查阅，可扩展为组织内部规则库。
- **AstronClaw 部署说明**：明确标准 Agent Skill 包结构与无依赖、无网络的调用方式。

### v0.4

- 重定位为"智能体判断 + 确定性校验"两层结构。
- 每条问题对照 GB/T 9704—2012 / 条例，新增 `basis` 依据字段。
- 修正成文日期规则（阿拉伯数字、不编虚位、不用分隔符）。
- 修复批量脚手架：自动跳过生成报告与起草需求 JSON；示例分目录。
- 主送机关识别鲁棒化 + 两个"脏"真实样本。
