# 讯飞政务开发skill (official-document-assistant)

> 中文展示名：讯飞政务开发skill
> Agent 平台注册名（SKILL.md frontmatter）：`official-document-assistant`
> 当前版本：v0.5.0

## 升级日志

### v0.5（2026-06）

- **防崩溃加固**：`.docx` 解析、文件读取、批量逐文件、入口全部加保护；非 UTF-8 用替换字符读取；新增输入分诊（空输入、起草请求误投审查模式、过短/非公文文本→"# 输入提示"而非错误报告）；任何输入不再抛 traceback。
- **批处理也走分诊**：`--batch` 模式对 review/brief 调用 `triage_input`，起草请求/非公文文本不再被误判为高风险公文。
- **领域知识库** `references/`：`gongwen-checklist.md`（公文要素与文种规则速查）、`drafting-guide.md`（起草规范与异常输入引导话术），供智能体层查阅，可扩展为组织内部规则库。
- **AstronClaw 部署说明**：明确标准 Agent Skill 包结构与无依赖、无网络的调用方式。

### v0.4

- 重定位为"智能体判断 + 确定性校验"两层结构。
- 每条问题对照 GB/T 9704—2012 / 条例，新增 `basis` 依据字段。
- 修正成文日期规则（阿拉伯数字、不编虚位、不用分隔符）。
- 修复批量脚手架：自动跳过生成报告与起草需求 JSON；示例分目录。
- 主送机关识别鲁棒化 + 两个"脏"真实样本。

---

## 参赛定位

本 Skill 面向基层政务、办公室、人事行政、学生组织等高频正式材料场景，支持通知、请示、报告、函、会议纪要等材料的结构审查、风险提示、草稿起草和督办事项提取。

它不包装成"政务全场景大模型"，而是聚焦一个可落地的小场景，并明确分工：

- **智能体层（宿主大模型）**：语义理解、文种复核、修订润色、起草生成、异常输入引导。
- **确定性校验层（本仓库脚本）**：纯标准库、不调模型，做可复现、不幻觉的格式校验、敏感信息脱敏和结构化抽取。

判断与改写交给模型，合规校验与脱敏交给确定性程序——既避免模型在格式要素和敏感信息上幻觉，也让每条意见都能追溯到 GB/T 9704—2012《党政机关公文格式》与《党政机关公文处理工作条例》。

## 核心能力

- 公文审查：识别文种，检查标题、主送机关、正文、附件说明、发文机关署名、成文日期和用语规范。
- 专项规则：针对请示、报告、函、通知分别检查常见公文错误。
- 建议修订：输出"带依据的问题清单、修改建议、建议修订稿、督办事项、脱敏预览"。
- 模板起草：根据 JSON 或一句话需求生成通知、请示、报告、函、会议纪要草稿骨架。
- 会议督办：从会议纪要中提取责任方、截止时间和待办事项。
- 安全合规：识别手机号、身份证号、涉密/内部资料表述，并给出本地脱敏预览。

## 本地运行

```bash
python scripts/gov_doc_review.py --mode review --format markdown < examples/review/notice.md
python scripts/gov_doc_review.py --mode brief  --format json     < examples/brief/meeting.md
python scripts/gov_doc_review.py --mode draft  --format markdown < examples/draft/request.txt
python scripts/gov_doc_review.py --mode review --format markdown --input examples/review/notice.md
python scripts/gov_doc_review.py --mode review --format json     --batch examples/review
python scripts/gov_doc_review.py --mode review --format markdown --input demo.docx --output report.md
```

## 参数说明

- `--mode review`：公文格式和合规审查。
- `--mode draft`：根据 JSON 或自然语言需求生成公文草稿骨架。
- `--mode brief`：会议纪要/简报督办事项提取。
- `--format markdown`：输出适合复制粘贴的审查报告。
- `--format json`：输出结构化结果（含 `basis` 依据字段），便于二次处理。
- `--input`：读取 UTF-8 文本、Markdown、JSON 或 `.docx` 文件。
- `--batch`：批量审查文件夹内文本与 `.docx`，自动跳过生成的报告和起草需求 JSON，并对非公文/起草请求给出"输入提示"友好跳过。
- `--output`：把结果写入指定文件。

## 输出结构

审查模式默认输出 Markdown 报告：

1. 文种识别、综合评分、风险等级。
2. 标题、主送机关、发文机关署名、成文日期等结构识别。
3. 问题清单：每项含严重程度、问题名称、修改建议和对照依据。
4. 修改建议：按问题汇总可执行修改方向及依据。
5. 建议修订稿：给出一版可直接复制再人工复核的规范文本。
6. 督办事项：责任方、期限和事项。
7. 脱敏预览：对手机号、身份证号等字段进行本地脱敏展示。

## 示例与目录结构

```
SKILL.md         技能定义（frontmatter name 须与提交名一致）
scripts/         确定性校验层（纯标准库脚本）
references/       领域知识库（供智能体查阅，可扩展）
examples/
  review/    待审公文（含 dirty-* 真实脏样本）
  brief/     会议纪要督办提取输入
  draft/     起草需求（自然语言或 JSON）
  outputs/   各模式对应的输出
templates/       审查报告 Markdown 模板
```

## SkillHub / 平台提交

作品中文展示名：讯飞政务开发skill

Agent 平台 frontmatter 名称（必填，与目录名一致）：

```text
official-document-assistant
```

## 已知限制

- 本 Skill 是轻量、可解释、无外部依赖的参赛版，不替代人工公文审核、法律审核或保密审查。
- `.docx` 支持仅提取正文段落，不解析复杂表格、页眉页脚、版记、批注和修订痕迹。
- 问题依据指向 GB/T 9704—2012 与《党政机关公文处理工作条例》的要素和原则；具体条款序号以正式文本为准。
- 不编造政策依据。涉及政策、法规、涉密材料、个人隐私和未公开政务数据时，应由用户提供依据并进行人工复核。
