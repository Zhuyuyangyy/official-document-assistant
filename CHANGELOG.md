# Changelog

本文件记录「公文合规审查与督办助手」（`official-document-assistant`）的版本变更历史。

格式参照 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

暂无未发布变更。

## [0.8.0] - 2026-06

### Added

- **重定位与改名**：展示名从"讯飞政务开发 skill"改为"公文合规审查与督办助手"，叙事从"政务"扩展到"办公室/行政/人事/学生组织/基层单位"的正式材料协同。
- **新增 compare 版本变更说明模式**：对比两版材料，输出核心变化、风险变化表与提交建议，覆盖办公流转协同场景。支持 `--old` 与 `--new` 参数，输出 Markdown 或 JSON。
- **brief 升级为督办台账**：输出 Markdown 表格与 CSV，可直接贴入 Excel 或任务系统。CSV 带 UTF-8 BOM，Excel 直接打开中文不乱码。台账含序号/责任单位/待办事项/截止时间/原文依据/建议状态六列。
- **draft 自动合规自检**：草稿生成后自动跑一遍 review，输出"草稿 + 信息缺口 + 自检报告"。自检报告含问题表格、评分与风险等级。
- **batch 升级为材料包体检**：输出总览、文件风险排行表（按分数升序）与跳过清单。单文件出错不影响整体，记入跳过清单。
- **审查报告三层结构**：领导摘要（一句话结论 + 风险等级 + 综合评分 + 三大主要问题）/ 结构识别 / 承办人修改清单（表格）/ 建议修订稿 / 督办事项（表格）/ 脱敏预览，更贴合办公室实际使用。
- **.docx 增强**：提取表格文本（`w:tbl`），表格内容追加到正文之后以 `[表格内容]` 标注；检测批注（`word/comments.xml`）与修订痕迹（`w:ins`/`w:del`）并提示用户提交前确认。
- **依据映射**：新增 `references/basis-map.json`，问题→依据结构化映射（20 个映射项），保证输出依据统一可追溯。
- **测试集**：新增 `tests/` 目录，15 个异常/边界/脏样本测试用例与 `run_tests.py` 回归脚本，覆盖空输入、短文本、起草请求误投、损坏 docx、非 UTF-8、批量混合文件、敏感信息、文种混用、会议督办等场景。通过率 15/15。
- **文档体系**：新增 `docs/`（design/security/evaluation/deployment/demo_script）与 `demo/` 演示场景（4 个 demo prompt）。
- **CHANGELOG.md**：新增标准 Keep a Changelog 格式的版本变更日志。
- **LICENSE**：新增 MIT 开源协议。

### Changed

- 审查报告从"问题清单 + 修改建议"两层结构升级为"领导摘要 / 结构识别 / 承办人修改清单 / 建议修订稿 / 督办事项 / 脱敏预览"六节三层结构。
- brief 模式输出从 JSON 结构化结果升级为督办台账 Markdown 表格（或 CSV）。
- batch 模式输出从简单列表升级为材料包体检报告（总览 + 风险排行表 + 跳过清单）。
- `score_document()` 新增 PII/涉密风险等级强制提升规则：存在"疑似个人敏感信息"或"疑似涉密或内部资料"问题时，风险等级强制为"高"。
- `_top_issues()` 函数：按严重程度排序取前 N 条，用于领导摘要。

### Fixed

- 无（本版本以新增功能为主）。

## [0.5] - 2026-06

### Added

- **防崩溃加固**：`.docx` 解析、文件读取、批量逐文件、入口全部加保护；非 UTF-8 用 `errors="replace"` 读取，不抛异常。
- **输入分诊（triage_input）**：空输入、起草请求误投审查模式、过短/非公文文本 → 返回"# 输入提示"而非错误报告，避免产出误导性 0/100 报告。
- **批处理也走分诊**：`--batch` 模式对 review/brief 调用 `triage_input`，起草请求/非公文文本不再被误判为高风险公文。
- **领域知识库** `references/`：`gongwen-checklist.md`（公文要素清单与易错点）、`drafting-guide.md`（分文种起草规范），供智能体层查阅，可扩展为组织内部规则库。
- **AstronClaw 部署说明**：明确标准 Agent Skill 包结构与无依赖、无网络的调用方式。
- **`InputError` 异常类**：用于包装不可读/无效输入，由上层捕获并返回友好提示。

### Changed

- `read_input()` 对非 UTF-8 文件使用 `encoding="utf-8", errors="replace"` 读取。
- `read_docx_text()` 捕获 `BadZipFile`/`KeyError`/`OSError`/`ParseError`，包装为 `InputError`。
- 脚本入口 `__main__` 加 `try/except` 兜底，任何未预期错误返回"已安全退出"，不抛 raw traceback。
- stdin 与 stdout reconfigure 为 UTF-8 + errors="replace"。

### Fixed

- 修复空输入产出误导性 0/100 报告的问题（改为返回输入提示）。
- 修复起草请求误投审查模式被当成"问题公文"审查的问题（改为返回输入提示引导用户切换模式）。
- 修复非 UTF-8 文件导致 `UnicodeDecodeError` 崩溃的问题（改为 errors="replace" 读取）。
- 修复损坏 `.docx` 导致 `BadZipFile` traceback 的问题（改为友好提示）。

## [0.4] - 2026-06

### Added

- **重定位为两层架构**："智能体判断 + 确定性校验"两层结构，判断和改写交给模型，合规校验和脱敏交给确定性程序。
- **`basis` 依据字段**：每条问题对照 GB/T 9704—2012 / 条例，新增 `basis` 依据字段，指向国标/条例的要素名称和原则。
- **两个"脏"真实样本**：`examples/review/dirty-realistic.md`（报告夹带请示 + 日期格式不规范）、`examples/review/dirty-messy-notice.md`（口语化 + PII + 附件编号不一致 + 强制表述缺依据）。

### Changed

- 成文日期规则修正：用阿拉伯数字标注为"YYYY年M月D日"，不使用"-""/"等分隔符，月、日不编虚位。
- 主送机关识别鲁棒化：跳过抄送/附件/密级/签发/印发/联系等行，识别"以冒号结尾且长度 ≤60"的行。

### Fixed

- 修复批量脚手架误审自身生成的报告与起草需求 JSON 的问题：自动跳过以"# 公文材料审查报告"开头的文件和含 `doc_type`/`topic`/`requirements` 字段的 JSON 文件。
- 示例分目录：`examples/review/`、`examples/draft/`、`examples/brief/`、`examples/compare/`、`examples/outputs/`。

[Unreleased]: https://example.com/compare/v0.8.0...HEAD
[0.8.0]: https://example.com/compare/v0.5...v0.8.0
[0.5]: https://example.com/compare/v0.4...v0.5
[0.4]: https://example.com/compare/v0.3...v0.4
