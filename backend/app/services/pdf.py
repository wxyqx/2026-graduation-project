import fitz  # PyMuPDF

# 低于该长度视为扫描件/无文字层
MIN_TEXT_LENGTH = 30


class PdfExtractError(Exception):
    pass


def extract_text(data: bytes) -> str:
    """从 PDF 字节流提取纯文本，全程在内存中完成，不落盘。"""
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:  # 非法/损坏文件
        raise PdfExtractError(f"无法打开 PDF 文件：{e}") from e
    try:
        parts = [page.get_text("text") for page in doc]
    finally:
        doc.close()
    text = "\n".join(parts).strip()
    if len(text) < MIN_TEXT_LENGTH:
        raise PdfExtractError("无法提取文本（可能是扫描件或图片型 PDF），请粘贴纯文本后重试")
    return text
