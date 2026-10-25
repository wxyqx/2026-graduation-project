"""
【数据备份】把 12 张表导成 CSV + 候选人文件原件，打成一个 ZIP。

结构：
  ats_backup_YYYYmmdd_HHMMSS.zip
  ├── manifest.json          版本、导出时间、各表行数、文件数
  ├── csv/User.csv ...       12 张表逐表 CSV（候选人文件表不含 BLOB 内容）
  └── files/12_简历.pdf ...  Candidate_File 的文件内容

只做导出，恢复是手工操作（文档里写步骤）。技术管理员专用。
"""
import csv
import io
import json
import re
import zipfile
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

# 导出顺序：父表在前，便于人工核对
TABLES = [
    "Candidate",
    "Position",
    "User",
    "Application",
    "AI_API_Config",
    "App_Setting",
    "Candidate_File",
    "Form_Template",
    "Form_Field",
    "Form_Submission",
    "Form_Answer",
    "Operation_Log",
]

FILE_TABLE = "Candidate_File"


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return f"<binary {len(value)} bytes>"
    return str(value)


def _safe_name(name: str) -> str:
    safe = re.sub(r'[\\/:*?"<>|]+', "_", name or "file")
    return safe[:120] or "file"


def export_zip(db: Session) -> tuple[bytes, dict]:
    """返回 (ZIP 字节, 每张表行数)。"""
    buf = io.BytesIO()
    counts: dict[str, int] = {}
    file_count = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for table in TABLES:
            result = db.execute(text(f"SELECT * FROM `{table}`"))
            columns = list(result.keys())
            rows = result.fetchall()
            counts[table] = len(rows)

            write_columns = columns
            content_idx = columns.index("Content") if table == FILE_TABLE and "Content" in columns else -1
            if content_idx >= 0:
                write_columns = [c for c in columns if c != "Content"]

            text_buf = io.StringIO(newline="")
            writer = csv.writer(text_buf)
            writer.writerow(write_columns)
            for row in rows:
                values = []
                for i, col in enumerate(columns):
                    if col == "Content":
                        continue
                    values.append(_cell(row[i]))
                writer.writerow(values)
            zf.writestr(f"csv/{table}.csv", text_buf.getvalue().encode("utf-8-sig"))

            if content_idx >= 0:
                id_idx = columns.index("ID") if "ID" in columns else 0
                name_idx = columns.index("Original_Name") if "Original_Name" in columns else None
                for row in rows:
                    content = row[content_idx]
                    if not content:
                        continue
                    name = _safe_name(row[name_idx] if name_idx is not None else "file")
                    zf.writestr(f"files/{row[id_idx]}_{name}", bytes(content))
                    file_count += 1

        manifest = {
            "app": "ATS 招聘管理系统",
            "schema_version": "v3.15",
            "exported_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
            "tables": counts,
            "files": file_count,
            "note": "候选人文件内容在 files/ 目录；csv/Candidate_File.csv 只含元数据。",
        }
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))

    return buf.getvalue(), counts
