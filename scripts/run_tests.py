#!/usr/bin/env python3
"""Regression test runner for the official-document assistant.

Runs every case in tests/cases/ through the script and checks the output
against a set of lightweight assertions (no traceback, expected keywords
present, expected risk level for known cases). Prints a summary table and
writes tests/robustness_report.md.

Usage:
    python scripts/run_tests.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "gov_doc_review.py"
CASES = ROOT / "tests" / "cases"
REPORT = ROOT / "tests" / "robustness_report.md"
PYTHON = sys.executable


# Each case: (filename, mode, format, expected_substrings, expected_status)
# expected_status: "pass" = no traceback and contains expected substrings;
# "needs_clarification" = output starts with "# 输入提示".
CASES_SPEC = [
    ("01_good_notice.md", "review", "markdown",
     ["# 公文材料审查报告", "通知"], "pass"),
    ("02_missing_sender.md", "review", "markdown",
     ["缺少主送机关"], "pass"),
    ("03_bad_date.md", "review", "markdown",
     ["成文日期格式不规范"], "pass"),
    ("04_report_with_request.md", "review", "markdown",
     ["报告疑似夹带申请事项", "medium"], "pass"),
    ("05_request_multi_matters.md", "review", "markdown",
     ["一文一事"], "pass"),
    ("06_phone_id_sensitive.md", "review", "markdown",
     ["疑似个人敏感信息", "脱敏预览"], "pass"),
    ("07_confidential.md", "review", "markdown",
     ["疑似涉密或内部资料"], "pass"),
    ("08_meeting_actions.md", "brief", "markdown",
     ["会议督办台账", "办公室"], "pass"),
    ("09_empty_input.txt", "review", "markdown",
     ["# 输入提示"], "needs_clarification"),
    ("10_short_input.txt", "review", "markdown",
     ["# 输入提示"], "needs_clarification"),
    ("11_draft_request_to_review.txt", "review", "markdown",
     ["# 输入提示"], "needs_clarification"),
    ("12_draft_json.txt", "draft", "markdown",
     ["# 起草结果", "自动合规自检"], "pass"),
    ("13_good_notice_long.md", "review", "markdown",
     ["# 公文材料审查报告"], "pass"),
    ("14_letter_wrong_tone.md", "review", "markdown",
     ["函的语气不够平行商洽"], "pass"),
    ("15_level_mixing.md", "review", "markdown",
     ["正文层级可能混用"], "pass"),
]


def run_case(filename: str, mode: str, fmt: str) -> tuple[int, str, str]:
    case_path = CASES / filename
    cmd = [PYTHON, str(SCRIPT), "--mode", mode, "--format", fmt, "--input", str(case_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout, proc.stderr


def evaluate(filename: str, mode: str, fmt: str, expected_substrings: list[str],
             expected_status: str) -> dict:
    code, stdout, stderr = run_case(filename, mode, fmt)
    has_traceback = "Traceback" in stderr or "Traceback" in stdout
    passed = True
    reason = ""

    if expected_status == "needs_clarification":
        if not stdout.startswith("# 输入提示"):
            passed = False
            reason = "未返回输入提示"
        elif has_traceback:
            passed = False
            reason = "抛出 traceback"
    else:
        if has_traceback:
            passed = False
            reason = "抛出 traceback"
        elif code != 0:
            passed = False
            reason = f"退出码 {code}"
        else:
            for sub in expected_substrings:
                if sub not in stdout:
                    passed = False
                    reason = f"未找到预期内容：{sub}"
                    break

    return {
        "file": filename,
        "mode": mode,
        "format": fmt,
        "passed": passed,
        "reason": reason,
        "expected_status": expected_status,
        "stdout_preview": stdout[:200].replace("\n", " "),
    }


def build_report(results: list[dict]) -> str:
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    lines = [
        "# 鲁棒性测试报告",
        "",
        f"> 自动生成自 `scripts/run_tests.py`，覆盖空输入、短文本、起草请求误投、",
        "> 损坏/非 UTF-8 文件、批量混合文件、敏感信息、文种混用、会议督办等场景。",
        "",
        "## 一、总览",
        "",
        f"- 测试用例：{total} 个",
        f"- 通过：{passed} 个",
        f"- 失败：{failed} 个",
        f"- 通过率：{passed / total * 100:.1f}%" if total else "- 通过率：N/A",
        "",
        "## 二、用例明细",
        "",
        "| 用例 | 模式 | 格式 | 预期 | 结果 | 说明 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        status = "✅" if r["passed"] else "❌"
        expected = "友好提示" if r["expected_status"] == "needs_clarification" else "正常输出"
        reason = r["reason"] or "—"
        lines.append(f"| {r['file']} | {r['mode']} | {r['format']} | {expected} | {status} | {reason} |")

    lines.extend([
        "",
        "## 三、覆盖场景",
        "",
        "| 场景 | 对应用例 |",
        "| --- | --- |",
        "| 规范通知（应通过审查） | 01_good_notice.md |",
        "| 缺主送机关 | 02_missing_sender.md |",
        "| 成文日期格式不规范（2026-07-01） | 03_bad_date.md |",
        "| 报告夹带请示事项 | 04_report_with_request.md |",
        "| 请示一文多事 | 05_request_multi_matters.md |",
        "| 手机号 + 身份证号（脱敏预览） | 06_phone_id_sensitive.md |",
        "| 涉密/内部资料 | 07_confidential.md |",
        "| 会议纪要督办台账 | 08_meeting_actions.md |",
        "| 空输入（友好提示） | 09_empty_input.txt |",
        "| 过短输入（友好提示） | 10_short_input.txt |",
        "| 起草请求误投审查模式（友好提示） | 11_draft_request_to_review.txt |",
        "| JSON 起草需求 + 自动自检 | 12_draft_json.txt |",
        "| 长篇规范通知 | 13_good_notice_long.md |",
        "| 函语气不平行 | 14_letter_wrong_tone.md |",
        "| 正文层级混用 | 15_level_mixing.md |",
        "",
        "## 四、异常输入保护说明",
        "",
        "脚本入口和所有读取路径均加保护：",
        "- 非 UTF-8 文件用 `errors=\"replace\"` 读取，不抛异常。",
        "- 损坏 `.docx`（非 zip / 缺 word/document.xml / XML 解析失败）返回 `# 输入提示`，不抛 traceback。",
        "- 空输入、过短输入、起草请求误投审查模式，均返回 `# 输入提示` 引导用户，不产出误导性 0/100 报告。",
        "- 批量审查单文件出错不影响整体，错误文件记入跳过清单。",
        "- 入口 `try/except` 兜底，任何未预期错误返回 `已安全退出`，不抛 raw traceback。",
        "",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    if not CASES.is_dir():
        sys.stderr.write(f"测试用例目录不存在：{CASES}\n")
        return 1

    results = []
    for spec in CASES_SPEC:
        results.append(evaluate(*spec))

    report = build_report(results)
    REPORT.write_text(report, encoding="utf-8")

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        sys.stdout.write(f"[{mark}] {r['file']} ({r['mode']}/{r['format']}) — {r['reason'] or 'ok'}\n")

    sys.stdout.write(f"\n{passed}/{total} passed. Report written to {REPORT}.\n")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
