"""
【这个文件是干什么的？】
把 PDF 简历里的「文字」抠出来。用的工具叫 PyMuPDF（import 时叫 fitz，历史原因）。

注意两点：
1. 全程在内存里处理，PDF 文件不会保存到硬盘上（用完就丢，保护隐私）。
2. 有些 PDF 其实是「照片」——比如手机拍的简历扫描件，里面没有文字层，
   抠出来是空的。这种我们判定为「无法提取」，让用户改用粘贴文本的方式。
"""
import fitz  # PyMuPDF

# 抠出来的文字少于 30 个字，就认为这是扫描件 / 图片型 PDF
MIN_TEXT_LENGTH = 30


class PdfExtractError(Exception):
    """提取失败时抛出的「专属错误」，方便上层用 except 精确接住。"""

    pass


def extract_text(data: bytes) -> str:
    """输入 PDF 的原始字节，输出里面的纯文本。失败抛 PdfExtractError。"""
    try:
        # stream=data 表示「从内存里的字节打开」，而不是从硬盘上的文件路径打开
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:  # 文件损坏、根本不是 PDF 等情况
        raise PdfExtractError(f"无法打开 PDF 文件：{e}") from e
    try:
        # 一页一页抠文字，放进列表
        parts = [page.get_text("text") for page in doc]
    finally:
        doc.close()  # 不管成功失败都要关掉，释放内存
    text = "\n".join(parts).strip()  # 把每页文字用换行拼起来，去掉首尾空白
    if len(text) < MIN_TEXT_LENGTH:
        raise PdfExtractError("无法提取文本（可能是扫描件或图片型 PDF），请粘贴纯文本后重试")
    return text
