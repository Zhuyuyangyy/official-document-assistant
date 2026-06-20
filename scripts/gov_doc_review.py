#!/usr/bin/env python3
"""Official document assistant v0.8.

Lightweight, dependency-free reviewer/drafter/comparator for
official-document-like Chinese materials. It is the deterministic
verification layer of the skill: it performs format checks, PII
redaction, structured extraction and version comparison without calling
any model, so the host agent can rely on it for non-hallucinating
results.

v0.8 highlights:
- Three-layer review report (leader summary / editor checklist / revision).
- New `compare` mode for version change notes.
- `brief` mode now emits a supervision ledger (Markdown table or CSV).
- `draft` mode auto-runs a review self-check on the generated skeleton.
- `batch` mode emits a package health-check report with risk ranking.
- `.docx` parsing now extracts table text and detects comments / tracked
  changes (w:ins / w:del / comments.xml) to warn the user.
- Friendly input triage for off-topic/invalid input; never raises a raw
  traceback.

Rules are anchored to GB/T 9704-2012 / the official-document regulation.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


DOC_TYPES = ["通知", "请示", "报告", "函", "纪要", "简报", "方案", "通报"]
DEFAULT_DATE = "XXXX年XX月XX日"
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
DATE_RE = re.compile(r"(\d{4}年\d{1,2}月\d{1,2}日(?:前)?|\d{1,2}月\d{1,2}日(?:前)?)")
ALT_DATE_RE = re.compile(r"(?<!\d)(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})(?!\d)")
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
ID_CARD_RE = re.compile(r"(?<!\d)(?:\d{17}[\dXx]|\d{15})(?!\d)")
CONFIDENTIAL_RE = re.compile(r"(涉密|绝密|机密|秘密|内部资料|不得外传|知悉范围|敏感材料)")
OWNER_RE = re.compile(r"(?:请|由|会议要求，?)?([\u4e00-\u9fa5A-Za-z0-9（）()]{0,12}(?:办公室|中心|部门|单位|小组|处|科|局|办))(?=于|负责|牵头|完成|提交|，|,|$)")


REPORT_HEADER = "# 公文材料审查报告"
G9704 = "GB/T 9704—2012《党政机关公文格式》"
REGULATION = "《党政机关公文处理工作条例》"


@dataclass
class Issue:
    name: str
    severity: str
    evidence: str
    suggestion: str
    basis: str = ""


@dataclass
class SupervisionItem:
    owner: str
    task: str
    due_date: str
    source: str


class InputError(Exception):
    """Raised for unreadable/invalid input so callers can show friendly guidance."""


def sanitize_text(text: str) -> str:
    return CONTROL_CHAR_RE.sub("", text or "")


def normalize_lines(text: str) -> list[str]:
    return [line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if line.strip()]


def read_docx_text(path: Path) -> tuple[str, dict]:
    """Extract text from a docx with stdlib only. Never raises a raw traceback.

    Returns (text, meta) where meta carries signals about tables, comments
    and tracked changes so the reviewer can warn the user.
    """
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
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", ns):
        texts = [node.text or "" for node in paragraph.findall(".//w:t", ns)]
        if texts:
            paragraphs.append("".join(texts))

    # v0.8: also pull text out of tables so table-only content is not lost.
    table_texts: list[str] = []
    for table in root.findall(".//w:tbl", ns):
        row_cells: list[str] = []
        for cell in table.findall(".//w:tc", ns):
            cell_text = "".join(node.text or "" for node in cell.findall(".//w:t", ns))
            if cell_text.strip():
                row_cells.append(cell_text.strip())
        if row_cells:
            table_texts.append(" | ".join(row_cells))

    meta = {
        "has_tables": bool(table_texts),
        "table_count": len(root.findall(".//w:tbl", ns)),
        "has_comments": "word/comments.xml" in names,
        "has_tracked_changes": bool(
            root.findall(".//w:ins", ns) or root.findall(".//w:del", ns)
        ),
    }
    body = "\n".join(paragraphs)
    if table_texts:
        body += "\n\n[表格内容]\n" + "\n".join(table_texts)
    return body, meta


def read_input(path: str | None) -> tuple[str, dict]:
    """Return (text, meta). meta is {} for plain text inputs."""
    if not path:
        return sanitize_text(sys.stdin.read()), {}
    input_path = Path(path)
    if not input_path.exists():
        raise InputError(f"文件不存在：{path}")
    if not input_path.is_file():
        raise InputError(f"路径不是文件：{path}")
    if input_path.suffix.lower() == ".docx":
        text, meta = read_docx_text(input_path)
        return sanitize_text(text), meta
    try:
        # errors="replace" so non-UTF-8 bytes never crash the reader
        return sanitize_text(input_path.read_text(encoding="utf-8", errors="replace")), {}
    except OSError as exc:
        raise InputError(f"无法读取文件：{path}") from exc


def detect_doc_type(lines: list[str]) -> str:
    title = lines[0] if lines else ""
    for doc_type in DOC_TYPES:
        if doc_type in title:
            return "会议纪要" if doc_type == "纪要" else doc_type
    if "会议" in title:
        return "会议纪要"
    fallback = " ".join(lines[1:3]) if len(lines) > 1 else ""
    for doc_type in DOC_TYPES:
        if doc_type in fallback:
            return "会议纪要" if doc_type == "纪要" else doc_type
    if "会议" in fallback:
        return "会议纪要"
    return "通用材料"


def find_sender(lines: list[str]) -> str:
    skip_prefixes = ("抄送", "附件", "密", "签发", "印发", "联系")
    for line in lines[1:6]:
        if line.startswith(skip_prefixes):
            continue
        if line.endswith(("：", ":")) and 1 < len(line) <= 60:
            return line.rstrip("：:")
    return ""


def find_signature_and_date(lines: list[str]) -> tuple[str, str]:
    date = ""
    signature = ""
    for index in range(len(lines) - 1, -1, -1):
        date_match = DATE_RE.search(lines[index]) or ALT_DATE_RE.search(lines[index])
        if date_match:
            date = date_match.group(1)
            if index > 0 and len(lines[index - 1]) <= 40:
                signature = lines[index - 1]
            break
    return signature, date


def extract_structure(text: str) -> dict:
    lines = normalize_lines(text)
    signature, date = find_signature_and_date(lines)
    attachments = [line for line in lines if line.startswith("附件")]
    body_lines = lines[2:] if find_sender(lines) else lines[1:]
    return {
        "title": lines[0] if lines else "",
        "sender": find_sender(lines),
        "signature": signature,
        "date": date,
        "attachments": attachments,
        "body": "\n".join(body_lines),
        "paragraph_count": max(0, len(lines) - 1),
    }


def body_without_closing(structure: dict) -> str:
    body_lines = [line for line in structure["body"].splitlines() if line.strip()]
    if structure["date"] and body_lines and structure["date"] in body_lines[-1]:
        body_lines.pop()
    if structure["signature"] and body_lines and body_lines[-1] == structure["signature"]:
        body_lines.pop()
    return "\n".join(body_lines).strip()


def title_matches_official_pattern(title: str, doc_type: str) -> bool:
    return bool(re.fullmatch(rf".{{0,30}}关于.+的{re.escape(doc_type)}", title))


def clean_topic_for_action(topic: str) -> str:
    cleaned = re.sub(r"^(关于|申请|商请|请求|开展|组织|推进|落实|报送|加强)", "", topic.strip())
    return cleaned.strip("，。；; 的") or topic.strip()


def add_issue(issues: list[Issue], name: str, severity: str, evidence: str, suggestion: str, basis: str = "") -> None:
    issues.append(Issue(name=name, severity=severity, evidence=evidence, suggestion=suggestion, basis=basis))


def check_common_rules(text: str, doc_type: str, structure: dict, issues: list[Issue]) -> None:
    title = structure["title"]
    official_types = {"通知", "请示", "报告", "函", "通报"}

    if not title:
        add_issue(issues, "缺少标题", "high", "未识别到第一行标题",
                  "补充规范标题，如“关于……的通知”。",
                  f"{G9704} 主体·标题")
    elif doc_type in official_types:
        if not title_matches_official_pattern(title, doc_type):
            add_issue(issues, "标题三要素不完整", "medium", title,
                      "标题建议采用“发文机关 + 关于 + 事由 + 文种”或“关于 + 事由 + 文种”的结构。",
                      f"{G9704} 主体·标题")
        if len(title.replace("关于", "").replace(f"的{doc_type}", "")) < 4:
            add_issue(issues, "标题事由不够明确", "medium", title,
                      "标题事由应能说明办理对象、事项或工作主题。",
                      f"{G9704} 主体·标题")

    if doc_type in official_types and not structure["sender"]:
        add_issue(issues, "缺少主送机关", "high", "标题后未发现以冒号结尾的主送机关",
                  "在正文前补充主送机关，如“各部门：”。",
                  f"{G9704} 主体·主送机关")

    if doc_type in official_types and not structure["signature"]:
        add_issue(issues, "缺少落款单位", "medium", "文末未识别到落款单位",
                  "在成文日期上一行补充发文机关署名。",
                  f"{G9704} 主体·发文机关署名")

    if doc_type in official_types and not structure["date"]:
        add_issue(issues, "缺少成文日期", "high", "文末未识别到日期",
                  "补充成文日期，用阿拉伯数字标注为“YYYY年M月D日”，月、日不编虚位。",
                  f"{G9704} 主体·成文日期")
    elif doc_type in official_types and ALT_DATE_RE.fullmatch(structure["date"]):
        add_issue(issues, "成文日期格式不规范", "medium", structure["date"],
                  "成文日期应用阿拉伯数字标注为“YYYY年M月D日”，不使用“-”“/”等分隔符，月、日不编虚位。",
                  f"{G9704} 主体·成文日期")

    if "附件" in text and not structure["attachments"]:
        add_issue(issues, "附件说明不完整", "medium", "正文提到附件但未发现独立附件说明行",
                  "正文后空一行补充“附件：……”并列明附件顺序号和名称。",
                  f"{G9704} 主体·附件说明")

    if structure["attachments"]:
        attachment_text = "\n".join(structure["attachments"])
        numbered_refs = re.findall(r"附件\s*(\d+)", text)
        listed_numbers = re.findall(r"附件\s*[:：]?\s*(\d+)[.．、]", attachment_text)
        if numbered_refs and listed_numbers and sorted(set(numbered_refs)) != sorted(set(listed_numbers)):
            add_issue(issues, "附件编号不一致", "medium", attachment_text,
                      "正文引用的附件顺序号应与文末附件说明一致。",
                      f"{G9704} 主体·附件说明")

    if re.search(r"(^|\n)一、", text) and re.search(r"(^|\n)\d+[.．]", text) and not re.search(r"(^|\n)（一）", text):
        add_issue(issues, "正文层级可能混用", "medium", "同时出现“一、”和“1.”但缺少“（一）”层级",
                  "正文层次序数依次用“一、”“（一）”“1.”“（1）”，避免层级跳跃。",
                  f"{G9704} 主体·正文")

    if re.search(r"(差不多|尽快弄|搞一下|随便|赶紧|弄一弄)", text):
        add_issue(issues, "口语化表达", "medium", "发现口语化措辞",
                  "替换为庄重、规范、可执行的机关事务表达。",
                  f"{REGULATION} 公文用语庄重、准确、简洁")

    if re.search(r"(必须|严禁|不得|一律|务必)", text) and not re.search(r"(根据|依据|按照|贯彻|落实|依照)", text):
        add_issue(issues, "强制性表述缺少依据", "medium", "发现必须/严禁/不得等表述",
                  "补充政策、制度或上级文件依据后再作强制性要求。",
                  f"{REGULATION} 行文应当确有必要、依据充分")

    if PHONE_RE.search(text) or ID_CARD_RE.search(text) or re.search(r"(身份证号|联系电话|手机号|个人信息)", text):
        add_issue(issues, "疑似个人敏感信息", "high", "发现手机号、身份证号或个人信息相关表述",
                  "提交或上传前先脱敏；涉及个人信息的材料建议本地处理并人工复核。",
                  "《个人信息保护法》个人信息处理的合法、必要、最小化原则")

    if CONFIDENTIAL_RE.search(text):
        add_issue(issues, "疑似涉密或内部资料", "high", "发现涉密、内部资料或不得外传相关表述",
                  "不要上传涉密或未公开材料到外部平台；在本地环境处理，并按单位保密要求标注密级、人工复核。",
                  "《保守国家秘密法》及涉密公文密级标注要求")


def check_doc_type_rules(text: str, doc_type: str, structure: dict, issues: list[Issue]) -> None:
    body = structure["body"]
    if doc_type == "请示":
        possible_matters = len(re.findall(r"(^|\n)[一二三四五六七八九十]、", text))
        if possible_matters >= 3 or re.search(r"(同时申请|并申请|以及申请|另申请)", text):
            add_issue(issues, "请示可能不符合一文一事", "medium", "请示中出现多个并列申请事项",
                      "请示应坚持一文一事，多个事项建议拆分或明确主次。",
                      f"{REGULATION} 请示一文一事")
        if "妥否，请批示" not in text and "请批示" not in text:
            add_issue(issues, "请示结语不规范", "medium", "未发现“妥否，请批示”等请示结语",
                      "请示文末建议使用“妥否，请批示”等规范结语。",
                      "公文写作惯例·请示结语")

    if doc_type == "报告":
        if re.search(r"(请批示|请审批|妥否|报请审批|请求批准|请予批准)", text):
            add_issue(issues, "报告夹带请示事项", "high", "报告中出现请批示/请审批等请示性结语",
                      "报告不得夹带请示事项，需审批事项请另行行文请示。",
                      f"{REGULATION} 报告与请示分立")
        elif re.search(r"(拟申请|申请追加|恳请支持|请予支持)", text):
            add_issue(issues, "报告疑似夹带申请事项", "medium", "报告中出现拟申请、申请追加、请予支持等申请性表述",
                      "报告应以陈述情况为主，需审批或支持事项建议另行请示。",
                      f"{REGULATION} 报告与请示分立")

    if doc_type == "函" and re.search(r"(命令|必须立即|责令)", text):
        add_issue(issues, "函的语气不够平行商洽", "medium", "函中出现命令式表达",
                  "函适用于不相隶属机关之间商洽、询问、答复或请求协助，语气应平实、商洽。",
                  f"{REGULATION} 函的适用范围")

    if doc_type == "通知":
        has_target = bool(structure["sender"] or re.search(r"(各部门|各单位|全体|相关人员)", text))
        has_time = bool(DATE_RE.search(text) or ALT_DATE_RE.search(text))
        has_action = bool(re.search(r"(完成|提交|报送|落实|开展|参加|整改|反馈)", body))
        if not (has_target and has_time and has_action):
            add_issue(issues, "通知事项可执行性不足", "medium", body[:80],
                      "通知正文应尽量明确对象、事项、时间节点和办理要求。",
                      f"{REGULATION} 通知的适用范围")


def check_document(text: str, doc_type: str, structure: dict, meta: dict | None = None) -> list[Issue]:
    issues: list[Issue] = []
    check_common_rules(text, doc_type, structure, issues)
    check_doc_type_rules(text, doc_type, structure, issues)
    if len(text.strip()) < 50:
        add_issue(issues, "正文内容过短", "medium", "正文不足50字", "补充背景、事项、要求、时间节点和责任单位。")
    # v0.8: warn about comments / tracked changes in docx
    if meta:
        if meta.get("has_comments") or meta.get("has_tracked_changes"):
            flags = []
            if meta.get("has_comments"):
                flags.append("批注")
            if meta.get("has_tracked_changes"):
                flags.append("修订痕迹")
            add_issue(issues, f"检测到{'/'.join(flags)}", "medium",
                      f"docx 中存在{'/'.join(flags)}",
                      "提交正式材料前请确认是否接受全部修订并删除批注，避免遗留修改痕迹。",
                      f"{G9704} 公文正式性要求")
    return issues


def score_document(issues: Iterable[Issue]) -> dict:
    issues = list(issues)
    total = 100
    detail = {"format": 100, "structure": 100, "language": 100, "risk": 100}
    for issue in issues:
        penalty = {"high": 14, "medium": 8, "low": 4}.get(issue.severity, 6)
        total -= penalty
        if any(key in issue.name for key in ["标题", "日期", "落款", "附件", "层级"]):
            detail["format"] -= penalty
        elif any(key in issue.name for key in ["主送", "请示", "报告", "通知", "函", "正文"]):
            detail["structure"] -= penalty
        elif "口语" in issue.name:
            detail["language"] -= penalty
        else:
            detail["risk"] -= penalty
    total = max(0, min(100, total))
    for key in list(detail):
        detail[key] = max(0, min(100, detail[key]))
    risk_level = "低" if total >= 85 else "中" if total >= 70 else "高"
    if risk_level == "低" and any(issue.severity == "high" for issue in issues):
        risk_level = "中"
    if any(issue.name in {"疑似个人敏感信息", "疑似涉密或内部资料"} for issue in issues):
        risk_level = "高"
    detail["total"] = total
    return {"scores": detail, "risk_level": risk_level}


def build_redacted_preview(text: str) -> str:
    redacted = PHONE_RE.sub(lambda match: f"{match.group(0)[:3]}****{match.group(0)[-4:]}", text)

    def redact_id(match: re.Match[str]) -> str:
        value = match.group(0)
        return f"{value[:6]}{'*' * max(0, len(value) - 10)}{value[-4:]}" if len(value) > 8 else "*" * len(value)

    redacted = ID_CARD_RE.sub(redact_id, redacted)
    return redacted if redacted != text else ""


def extract_supervision_items(text: str) -> list[SupervisionItem]:
    items: list[SupervisionItem] = []
    for raw in normalize_lines(text):
        for sentence in re.split(r"[。；;]\s*", raw):
            sentence = sentence.strip("，。；; ")
            if not sentence or not re.search(r"(完成|提交|报送|落实|整改|发布|牵头|负责|截止|前)", sentence):
                continue
            owner_match = OWNER_RE.search(sentence)
            date_match = DATE_RE.search(sentence)
            if not owner_match and not date_match:
                continue
            owner = owner_match.group(1) if owner_match else "待明确"
            due = date_match.group(1) if date_match else "待明确"
            task = sentence
            task = re.sub(r"^会议要求，?", "", task)
            task = re.sub(r"^请", "", task)
            if owner != "待明确":
                task = re.sub(rf"^{re.escape(owner)}", "", task)
            if due != "待明确":
                task = task.replace(f"于{due}", "").replace(due, "")
            task = re.sub(r"^负责", "", task).strip("，。；; ")
            items.append(SupervisionItem(owner=owner, task=task or sentence, due_date=due, source=sentence))
    return items


def triage_input(text: str, mode: str) -> str:
    """Return a friendly guidance message when the input cannot be meaningfully
    handled in the requested mode; otherwise return an empty string.
    """
    stripped = text.strip()
    if not stripped:
        return ("未检测到正文内容。审查模式请粘贴完整的公文或会议纪要；"
                "起草模式请用一句话或 JSON 说明文种、主题、主送机关和要求。")
    if mode in {"review", "brief"}:
        if stripped.startswith("{") and re.search(r'"(doc_type|topic|requirements)"', stripped):
            return ("这看起来是一份起草需求（JSON），当前为审查模式。"
                    "请改用 --mode draft 生成草稿，或粘贴已成文的公文再审查。")
        if re.match(r"^\s*(请\s*)?(帮我?|麻烦)\s*(写|起草|生成|拟|出)", stripped) and len(stripped) < 60:
            return ("这看起来是一句起草请求，当前为审查模式。"
                    "请改用 --mode draft 生成草稿，或粘贴已写好的公文正文再审查。")
        if re.match(r"^\s*(写|起草|生成|拟)\s*[一]?\s*[份个篇]", stripped) and len(stripped) < 60:
            return ("这看起来是一句起草请求，当前为审查模式。"
                    "请改用 --mode draft 生成草稿，或粘贴已写好的公文正文再审查。")
        has_doc_signal = any(t in stripped for t in DOC_TYPES) or "：" in stripped or ":" in stripped
        if len(stripped) < 15 and not has_doc_signal:
            return ("输入内容过短，难以判断为公文材料。"
                    "请提供包含标题、主送机关、正文和落款的完整材料。")
    return ""


def parse_draft_request(text: str) -> dict:
    stripped = text.strip()
    request: dict = {}
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            loaded = json.loads(stripped)
        except json.JSONDecodeError:
            loaded = {}
        if isinstance(loaded, dict):
            request.update(loaded)
    if "doc_type" not in request:
        for doc_type in ["会议纪要", "通知", "请示", "报告", "函", "简报", "方案", "通报"]:
            if doc_type in stripped:
                request["doc_type"] = doc_type
                break
    request.setdefault("doc_type", "通知")
    if "topic" not in request:
        for pattern in [r"主题是([^，。；;\n]+)", r"关于([^，。；;\n]+)", r"写一份[^，。；;\n]*，([^，。；;\n]+)"]:
            match = re.search(pattern, stripped)
            if match:
                request["topic"] = match.group(1).strip()
                break
    request.setdefault("topic", "待补充事项")
    if "sender" not in request:
        match = re.search(r"(?:报给|提交给|发送给|发给|呈报|主送|给)([^，。；;\n]+)", stripped)
        if match:
            request["sender"] = match.group(1).strip()
    if "issuer" not in request:
        match = re.search(r"(?:落款|发文单位|起草单位|由)([^，。；;\n]+)", stripped)
        if match:
            request["issuer"] = match.group(1).strip()
    requirements = request.get("requirements", [])
    if isinstance(requirements, str):
        requirements = [item.strip() for item in re.split(r"[，、\n]", requirements) if item.strip()]
    elif not isinstance(requirements, list):
        requirements = []
    request["requirements"] = [str(item).strip() for item in requirements if str(item).strip()]
    return request


def title_for(doc_type: str, topic: str) -> str:
    if doc_type == "会议纪要":
        return f"{topic}会议纪要"
    return f"关于{topic}的{doc_type}"


def generate_template(request: dict) -> str:
    doc_type = str(request.get("doc_type") or "通知")
    topic = str(request.get("topic") or "待补充事项").strip()
    action_topic = clean_topic_for_action(topic)
    sender = str(request.get("sender") or ("有关单位" if doc_type == "函" else "各部门")).strip()
    issuer = str(request.get("issuer") or "发文单位").strip()
    deadline = str(request.get("deadline") or "明确时间节点").strip()
    requirements = request.get("requirements") or ["明确责任分工", "按时报送进展", "确保工作落实"]
    requirements = [str(item).strip() for item in requirements if str(item).strip()]
    title = title_for(doc_type, topic)

    if doc_type == "请示":
        lines = [
            title,
            "",
            f"{sender}：",
            "",
            f"为保障{action_topic}相关工作顺利开展，现就有关事项请示如下：",
            "",
            "一、请示事项",
            f"拟申请{action_topic}，用于保障日常办公和业务办理需要。",
            "",
            "二、主要理由",
            f"当前相关工作对{action_topic}提出了实际需求，现有条件难以充分满足后续工作开展。为提高工作效率、保障任务落实，建议予以支持。",
            "",
            "三、拟办建议",
        ]
        for index, item in enumerate(requirements, 1):
            lines.append(f"{index}. {item}。")
        lines.extend(["", "妥否，请批示。", "", issuer, DEFAULT_DATE])
        return "\n".join(lines) + "\n"

    if doc_type == "会议纪要":
        lines = [
            title,
            "",
            f"会议主题：{topic}",
            "会议时间：XXXX年XX月XX日",
            "会议地点：待补充",
            "参会人员：待补充",
            "",
            "一、会议基本情况",
            f"会议围绕{topic}进行了研究部署。",
            "",
            "二、会议议定事项",
        ]
        for index, item in enumerate(requirements, 1):
            lines.append(f"{index}. {item}，请责任单位于{deadline}完成。")
        lines.extend(["", "三、督办要求", "请相关责任单位按节点推进，及时反馈办理进展。"])
        return "\n".join(lines) + "\n"

    if doc_type == "函":
        body_head = f"为推进{topic}相关工作，现商请贵单位协助支持有关事项如下："
        closing = "专此函达，请予支持。"
    elif doc_type == "报告":
        body_head = f"现将{topic}有关情况报告如下："
        closing = "特此报告。"
    else:
        body_head = f"为做好{topic}相关工作，现将有关事项通知如下："
        closing = "请结合实际认真抓好落实。"

    lines = [title, "", f"{sender}：", "", body_head, "", "一、工作事项", f"围绕{topic}，统筹推进相关安排。", "", "二、具体要求"]
    for index, item in enumerate(requirements, 1):
        suffix = f"，请于{deadline}完成" if deadline and deadline != "明确时间节点" else ""
        lines.append(f"{index}. {item}{suffix}。")
    lines.extend(["", closing, "", issuer, DEFAULT_DATE])
    return "\n".join(lines) + "\n"


def build_suggested_revision(text: str, doc_type: str, structure: dict) -> str:
    if not text.strip():
        return ""
    if doc_type == "会议纪要":
        title = structure["title"] or "会议纪要"
        body = body_without_closing(structure)
        items = extract_supervision_items(text)
        lines = [
            title,
            "",
            "会议主题：待补充",
            "会议时间：XXXX年XX月XX日",
            "会议地点：待补充",
            "参会人员：待补充",
            "",
            "一、会议基本情况",
            "会议围绕相关事项进行了研究部署。",
            "",
            "二、会议议定事项",
        ]
        if items:
            for index, item in enumerate(items, 1):
                due = "" if item.due_date == "待明确" else f"，请于{item.due_date}完成"
                if item.owner == "待明确":
                    lines.append(f"{index}. {item.task}{due}。")
                else:
                    lines.append(f"{index}. {item.owner}负责{item.task}{due}。")
        elif body:
            for index, line in enumerate(body.splitlines(), 1):
                lines.append(f"{index}. {line.rstrip('。')}。")
        else:
            lines.append("1. 请结合会议记录补充议定事项。")
        lines.extend(["", "三、督办要求", "请相关责任单位按时间节点推进落实，及时反馈办理进展。"])
        return "\n".join(lines) + "\n"

    title = structure["title"] or title_for(doc_type if doc_type != "通用材料" else "通知", "待补充事项")
    sender = structure["sender"] or ("各部门" if doc_type != "函" else "有关单位")
    signature = structure["signature"] or "发文单位"
    date = structure["date"] if structure["date"] and not ALT_DATE_RE.fullmatch(structure["date"]) else DEFAULT_DATE
    body = body_without_closing(structure) or "请结合实际补充具体事项、办理要求、时间节点和责任分工。"
    body = re.sub(r"(差不多|尽快弄|搞一下|随便|赶紧|弄一弄)", "按要求推进落实", body)
    listed_numbers = re.findall(r"附件\s*[:：]?\s*(\d+)[.．、]", "\n".join(structure["attachments"]))
    if listed_numbers:
        body = re.sub(r"附件\s*\d+", f"附件{listed_numbers[0]}", body)
    if doc_type == "请示" and "请批示" not in body:
        body = body.rstrip("。") + "。\n\n妥否，请批示。"
    if doc_type == "报告":
        body = re.sub(r"(妥否，请批示。?|请批示。?|请审批。?)", "特此报告。", body)
    return "\n".join([title, "", f"{sender}：", "", body.strip(), "", signature, date]) + "\n"


def analyze(text: str, mode: str = "review", meta: dict | None = None) -> dict:
    lines = normalize_lines(text)
    structure = extract_structure(text)
    doc_type = detect_doc_type(lines)
    if not text.strip():
        doc_type = "通用材料"
    if doc_type == "会议纪要":
        structure["sender"] = ""
        structure["signature"] = ""
        structure["date"] = ""
    issues = check_document(text, doc_type, structure, meta)
    if not text.strip():
        add_issue(issues, "缺少正文内容", "high", "输入为空", "请提供需要审查的公文、通知、会议纪要或正式材料。")
    score = score_document(issues)
    result = {
        "mode": mode,
        "doc_type": doc_type,
        "risk_level": score["risk_level"],
        "scores": score["scores"],
        "sections": {"structure": structure},
        "issues": [asdict(issue) for issue in issues],
        "revision_table": [
            {
                "issue": issue.name,
                "evidence": issue.evidence,
                "suggestion": issue.suggestion,
                "basis": issue.basis,
            }
            for issue in issues
        ],
        "suggested_revision": build_suggested_revision(text, doc_type, structure),
        "supervision_items": [asdict(item) for item in extract_supervision_items(text)],
        "redacted_preview": build_redacted_preview(text),
    }
    if meta:
        result["docx_meta"] = meta
    result["markdown_report"] = build_markdown(result)
    return result


def _top_issues(issues: list[dict], n: int = 3) -> list[dict]:
    """Pick the top-N most severe issues for the leader summary."""
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    return sorted(issues, key=lambda i: severity_rank.get(i.get("severity", "low"), 3))[:n]


def build_markdown(result: dict) -> str:
    """Three-layer review report: leader summary / editor checklist / revision."""
    structure = result["sections"]["structure"]
    issues = result["issues"]
    top = _top_issues(issues)
    risk = result["risk_level"]
    total = result["scores"]["total"]

    # Conclude in one sentence.
    if risk == "高":
        conclusion = "存在高风险问题，建议修改后再提交。"
    elif risk == "中":
        conclusion = "存在中风险问题，建议按修改清单完善后提交。"
    else:
        conclusion = "未发现明显合规问题，可进入人工复核。"

    lines = [
        "# 公文材料审查报告",
        "",
        "## 一、领导摘要",
        "",
        f"- 结论：{conclusion}",
        f"- 风险等级：{risk}",
        f"- 综合评分：{total}/100",
        f"- 文种识别：{result['doc_type']}",
    ]
    if top:
        lines.append("- 主要问题：")
        for issue in top:
            lines.append(f"  - [{issue['severity']}] {issue['name']}：{issue['suggestion']}")
    else:
        lines.append("- 主要问题：无")

    lines.extend([
        "",
        "## 二、结构识别",
        f"- 标题：{structure['title'] or '未识别'}",
        f"- 主送机关：{structure['sender'] or '未识别'}",
        f"- 发文机关署名：{structure['signature'] or '未识别'}",
        f"- 成文日期：{structure['date'] or '未识别'}",
    ])
    if result.get("docx_meta"):
        meta = result["docx_meta"]
        notes = []
        if meta.get("has_tables"):
            notes.append(f"含 {meta.get('table_count', 0)} 个表格（已提取文本）")
        if meta.get("has_comments"):
            notes.append("含批注")
        if meta.get("has_tracked_changes"):
            notes.append("含修订痕迹")
        if notes:
            lines.append(f"- Word 解析：{'; '.join(notes)}；页眉/页脚/版记未纳入自动审查，请人工复核。")

    # Editor checklist as a table — directly usable in an office workflow.
    lines.extend(["", "## 三、承办人修改清单", ""])
    if issues:
        lines.append("| 序号 | 严重程度 | 问题 | 原文证据 | 修改建议 | 依据 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for index, issue in enumerate(issues, 1):
            evidence = (issue["evidence"] or "").replace("|", "\\|").replace("\n", " ")[:60]
            suggestion = (issue["suggestion"] or "").replace("|", "\\|").replace("\n", " ")
            basis = (issue.get("basis") or "").replace("|", "\\|")
            lines.append(f"| {index} | {issue['severity']} | {issue['name']} | {evidence} | {suggestion} | {basis} |")
    else:
        lines.append("未发现明显格式或合规问题，可进入人工复核。")

    if result.get("suggested_revision"):
        lines.extend(["", "## 四、建议修订稿", "", "```text", result["suggested_revision"].strip(), "```"])

    lines.extend(["", "## 五、督办事项", ""])
    if result["supervision_items"]:
        lines.append("| 序号 | 责任方 | 待办事项 | 截止时间 | 原文依据 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for index, item in enumerate(result["supervision_items"], 1):
            task = (item["task"] or "").replace("|", "\\|").replace("\n", " ")
            source = (item["source"] or "").replace("|", "\\|").replace("\n", " ")[:80]
            lines.append(f"| {index} | {item['owner']} | {task} | {item['due_date']} | {source} |")
    else:
        lines.append("未识别到明确责任方和截止时间的督办事项。")

    if result.get("redacted_preview"):
        lines.extend([
            "",
            "## 六、脱敏预览",
            "以下为手机号、身份证号等字段的本地脱敏预览，正式提交前仍需人工复核：",
            "",
            "```text",
            result["redacted_preview"].strip(),
            "```",
        ])
    return "\n".join(lines) + "\n"


def build_brief_markdown(result: dict) -> str:
    """Supervision ledger as a Markdown table — drop-in for Excel/任务系统."""
    items = result["supervision_items"]
    lines = ["# 会议督办台账", ""]
    if not items:
        lines.append("未识别到明确责任方和截止时间的督办事项。")
        return "\n".join(lines) + "\n"
    lines.append("| 序号 | 责任单位 | 待办事项 | 截止时间 | 原文依据 | 建议状态 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for index, item in enumerate(items, 1):
        task = (item["task"] or "").replace("|", "\\|").replace("\n", " ")
        source = (item["source"] or "").replace("|", "\\|").replace("\n", " ")[:80]
        lines.append(f"| {index} | {item['owner']} | {task} | {item['due_date']} | {source} | 未开始 |")
    return "\n".join(lines) + "\n"


def build_brief_csv(result: dict) -> str:
    """Supervision ledger as CSV — paste straight into Excel or a task system."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["序号", "责任单位", "待办事项", "截止时间", "原文依据", "建议状态"])
    for index, item in enumerate(result["supervision_items"], 1):
        writer.writerow([index, item["owner"], item["task"], item["due_date"], item["source"], "未开始"])
    # Prepend a UTF-8 BOM so Excel opens Chinese correctly.
    return "\ufeff" + buffer.getvalue()


def build_draft_markdown(request: dict, draft_text: str, self_check: dict) -> str:
    """Draft + information gaps + self-check report."""
    gaps: list[str] = []
    if request.get("topic") in {"待补充事项", ""}:
        gaps.append("未提供主题/事由，已暂用“待补充事项”。")
    if not request.get("sender"):
        gaps.append("未提供主送机关，已暂用默认称谓。")
    if not request.get("issuer"):
        gaps.append("未提供落款单位，已暂用“发文单位”。")
    if request.get("deadline") in {"明确时间节点", "", None}:
        gaps.append("未提供截止时间，已标注为“明确时间节点”。")
    if not request.get("requirements"):
        gaps.append("未提供具体要求，已使用默认工作要求占位。")

    lines = ["# 起草结果", "", "## 一、可编辑草稿", "", "```text", draft_text.strip(), "```", ""]
    lines.append("## 二、起草信息缺口")
    if gaps:
        for gap in gaps:
            lines.append(f"- {gap}")
    else:
        lines.append("- 已提供全部要素，无信息缺口。")

    lines.extend(["", "## 三、自动合规自检"])
    sc_issues = self_check.get("issues", [])
    if sc_issues:
        lines.append("| 序号 | 严重程度 | 问题 | 修改建议 |")
        lines.append("| --- | --- | --- | --- |")
        for index, issue in enumerate(sc_issues, 1):
            suggestion = (issue.get("suggestion") or "").replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {index} | {issue['severity']} | {issue['name']} | {suggestion} |")
    else:
        lines.append("草稿通过自动合规自检，未发现明显问题。")
    lines.append("")
    lines.append(f"> 自检评分：{self_check['scores']['total']}/100；风险等级：{self_check['risk_level']}。")
    return "\n".join(lines) + "\n"


def compare_documents(old_text: str, new_text: str, old_meta: dict, new_meta: dict) -> dict:
    """Compare two versions and produce change notes + risk delta."""
    old_struct = extract_structure(old_text)
    new_struct = extract_structure(new_text)
    old_lines = normalize_lines(old_text)
    new_lines = normalize_lines(new_text)
    old_type = detect_doc_type(old_lines)
    new_type = detect_doc_type(new_lines)

    changes: list[dict] = []
    if old_struct["title"] != new_struct["title"]:
        changes.append({
            "field": "标题",
            "old": old_struct["title"] or "（缺失）",
            "new": new_struct["title"] or "（缺失）",
            "note": "标题已修改",
        })
    if old_struct["sender"] != new_struct["sender"]:
        changes.append({
            "field": "主送机关",
            "old": old_struct["sender"] or "（缺失）",
            "new": new_struct["sender"] or "（缺失）",
            "note": "主送机关已调整",
        })
    if old_struct["signature"] != new_struct["signature"]:
        changes.append({
            "field": "落款单位",
            "old": old_struct["signature"] or "（缺失）",
            "new": new_struct["signature"] or "（缺失）",
            "note": "落款单位已调整",
        })
    if old_struct["date"] != new_struct["date"]:
        changes.append({
            "field": "成文日期",
            "old": old_struct["date"] or "（缺失）",
            "new": new_struct["date"] or "（缺失）",
            "note": "成文日期已调整",
        })
    if old_type != new_type:
        changes.append({
            "field": "文种",
            "old": old_type,
            "new": new_type,
            "note": "文种已变更",
        })

    # Body length delta as a rough signal.
    old_len = len(old_struct["body"])
    new_len = len(new_struct["body"])
    if abs(new_len - old_len) >= 20:
        changes.append({
            "field": "正文字数",
            "old": str(old_len),
            "new": str(new_len),
            "note": "正文篇幅明显变化",
        })

    # Risk delta — run a light review on each side and compare risk levels.
    old_result = analyze(old_text, "review", old_meta)
    new_result = analyze(new_text, "review", new_meta)
    risk_rank = {"低": 0, "中": 1, "高": 2}
    old_risk = old_result["risk_level"]
    new_risk = new_result["risk_level"]
    if risk_rank[new_risk] > risk_rank[old_risk]:
        risk_delta = "风险上升"
    elif risk_rank[new_risk] < risk_rank[old_risk]:
        risk_delta = "风险下降"
    else:
        risk_delta = "风险持平"

    # Per-issue risk changes.
    old_issue_names = {issue["name"] for issue in old_result["issues"]}
    new_issue_names = {issue["name"] for issue in new_result["issues"]}
    added = sorted(new_issue_names - old_issue_names)
    removed = sorted(old_issue_names - new_issue_names)

    return {
        "changes": changes,
        "old_risk": old_risk,
        "new_risk": new_risk,
        "risk_delta": risk_delta,
        "old_score": old_result["scores"]["total"],
        "new_score": new_result["scores"]["total"],
        "added_risks": added,
        "removed_risks": removed,
        "old_doc_type": old_type,
        "new_doc_type": new_type,
    }


def build_compare_markdown(comparison: dict) -> str:
    lines = ["# 文档版本变更说明", ""]
    lines.extend([
        "## 一、核心变化",
        "",
    ])
    if comparison["changes"]:
        for change in comparison["changes"]:
            lines.append(f"- **{change['field']}**：由“{change['old']}”改为“{change['new']}”（{change['note']}）。")
    else:
        lines.append("- 两版核心要素一致，未发现标题/主送机关/落款/日期/文种层面的变更。")

    lines.extend(["", "## 二、风险变化", ""])
    lines.append("| 项目 | 旧版本 | 新版本 | 变化 |")
    lines.append("| --- | --- | --- | --- |")
    lines.append(f"| 风险等级 | {comparison['old_risk']} | {comparison['new_risk']} | {comparison['risk_delta']} |")
    lines.append(f"| 综合评分 | {comparison['old_score']}/100 | {comparison['new_score']}/100 | "
                 f"{'上升' if comparison['new_score'] > comparison['old_score'] else '下降' if comparison['new_score'] < comparison['old_score'] else '持平'} |")
    if comparison["added_risks"]:
        lines.append(f"| 新增风险点 | — | {', '.join(comparison['added_risks'])} | 需关注 |")
    if comparison["removed_risks"]:
        lines.append(f"| 已解决风险点 | {', '.join(comparison['removed_risks'])} | — | 风险降低 |")

    lines.extend(["", "## 三、提交建议", ""])
    if comparison["risk_delta"] == "风险上升":
        lines.append("新版本风险上升，建议先处理新增风险点（如脱敏、补主送机关、修正日期格式）后再提交。")
    elif comparison["risk_delta"] == "风险下降" and comparison["new_risk"] == "低":
        lines.append("新版本风险已下降至低风险，建议使用新版本提交，提交前仍做一次人工复核。")
    else:
        lines.append("两版风险相当，建议使用新版本提交，并按修改清单做人工复核。")
    return "\n".join(lines) + "\n"


def build_batch_markdown(results: list[dict], skipped: list[str]) -> str:
    """Package health-check report with risk ranking."""
    total = len(results) + len(skipped)
    risk_counts = {"高": 0, "中": 0, "低": 0}
    for item in results:
        risk_counts[item["risk_level"]] = risk_counts.get(item["risk_level"], 0) + 1

    lines = [
        "# 批量材料体检报告",
        "",
        "## 一、总览",
        f"- 共扫描：{total} 个文件",
        f"- 可审查：{len(results)} 个",
        f"- 跳过：{len(skipped)} 个",
        f"- 高风险：{risk_counts.get('高', 0)} 个",
        f"- 中风险：{risk_counts.get('中', 0)} 个",
        f"- 低风险：{risk_counts.get('低', 0)} 个",
        "",
        "## 二、文件风险排行",
        "",
        "| 文件 | 文种 | 分数 | 风险 | 主要问题 |",
        "| --- | --- | ---: | --- | --- |",
    ]
    ranked = sorted(results, key=lambda r: r["scores"]["total"])
    for item in ranked:
        name = Path(item.get("file", "")).name
        top_issue = _top_issues(item["issues"], 1)
        top_text = top_issue[0]["name"] if top_issue else "—"
        lines.append(f"| {name} | {item['doc_type']} | {item['scores']['total']}/100 | {item['risk_level']} | {top_text} |")

    if skipped:
        lines.extend(["", "## 三、已跳过文件", ""])
        for name in skipped:
            lines.append(f"- {name}")
    return "\n".join(lines) + "\n"


def run_one(text: str, mode: str, output_format: str, meta: dict | None = None) -> str:
    guidance = triage_input(text, mode)
    if guidance:
        if output_format == "json":
            return json.dumps({"mode": mode, "status": "needs_clarification", "guidance": guidance},
                              ensure_ascii=False, indent=2) + "\n"
        return f"# 输入提示\n\n{guidance}\n"
    if mode == "draft":
        request = parse_draft_request(text)
        draft_text = generate_template(request)
        # v0.8: auto self-check — run review on the generated draft.
        self_check = analyze(draft_text, "review", {})
        if output_format == "json":
            return json.dumps(
                {"mode": "draft", "request": request, "draft_text": draft_text, "self_check": self_check},
                ensure_ascii=False, indent=2,
            ) + "\n"
        return build_draft_markdown(request, draft_text, self_check)
    if mode == "brief":
        result = analyze(text, mode, meta)
        if output_format == "csv":
            return build_brief_csv(result)
        if output_format == "json":
            return json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        return build_brief_markdown(result)
    result = analyze(text, mode, meta)
    if output_format == "json":
        return json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    return result["markdown_report"]


def run_compare(old_path: str, new_path: str, output_format: str) -> str:
    try:
        old_text, old_meta = read_input(old_path)
        new_text, new_meta = read_input(new_path)
    except InputError as exc:
        return f"# 输入提示\n\n{exc}\n"
    comparison = compare_documents(old_text, new_text, old_meta, new_meta)
    if output_format == "json":
        return json.dumps(comparison, ensure_ascii=False, indent=2) + "\n"
    return build_compare_markdown(comparison)


def main() -> int:
    parser = argparse.ArgumentParser(description="Review, draft, brief and compare official document materials.")
    parser.add_argument("--input", help="UTF-8 txt/md/json or .docx file. Defaults to stdin.")
    parser.add_argument("--batch", help="Folder of txt/md/docx files to review.")
    parser.add_argument("--output", help="Write output to a file instead of stdout.")
    parser.add_argument("--mode", choices=["review", "draft", "brief", "compare"], default="review")
    parser.add_argument("--format", choices=["json", "markdown", "csv"], default="markdown")
    parser.add_argument("--old", help="Old version file path for compare mode.")
    parser.add_argument("--new", help="New version file path for compare mode.")
    args = parser.parse_args()

    if args.mode == "compare":
        if not args.old or not args.new:
            sys.stdout.write("# 输入提示\n\ncompare 模式需要同时提供 --old 与 --new 两个文件路径。\n")
            return 0
        output = run_compare(args.old, args.new, args.format)
        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
        else:
            sys.stdout.write(output)
        return 0

    if args.batch:
        folder = Path(args.batch)
        if not folder.is_dir():
            sys.stdout.write(f"# 输入提示\n\n批量目录不存在或不是文件夹：{args.batch}\n")
            return 0
        results = []
        skipped: list[str] = []
        for file_path in sorted(folder.iterdir()):
            if not file_path.is_file() or file_path.suffix.lower() not in {".txt", ".md", ".json", ".docx"}:
                continue
            try:
                text, meta = read_input(str(file_path))
            except InputError as exc:
                skipped.append(f"{file_path.name}（{exc}）")
                continue
            stripped = text.lstrip()
            if stripped.startswith(REPORT_HEADER):
                skipped.append(f"{file_path.name}（疑似审查报告输出，已跳过）")
                continue
            if file_path.suffix.lower() == ".json" and re.search(r'"(doc_type|topic|requirements)"', stripped):
                skipped.append(f"{file_path.name}（疑似起草需求，已跳过）")
                continue
            if args.mode in {"review", "brief"}:
                guidance = triage_input(text, args.mode)
                if guidance:
                    skipped.append(f"{file_path.name}（疑似非公文/起草请求，已跳过：{guidance.splitlines()[0]}）")
                    continue
            result = analyze(text, args.mode, meta)
            result["file"] = str(file_path)
            results.append(result)
        if args.format == "json":
            output = json.dumps(results, ensure_ascii=False, indent=2) + "\n"
        else:
            output = build_batch_markdown(results, skipped)
    else:
        try:
            text, meta = read_input(args.input)
        except InputError as exc:
            sys.stdout.write(f"# 输入提示\n\n{exc}\n")
            return 0
        output = run_one(text, args.mode, args.format, meta)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


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
