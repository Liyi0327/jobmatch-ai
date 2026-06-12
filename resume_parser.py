import fitz


def extract_text_from_pdf(uploaded_file) -> str:
    """
    从上传的 PDF 简历中提取文本。

    参数：
        uploaded_file: Streamlit 上传的 PDF 文件对象

    返回：
        str: PDF 中提取出的文本内容
    """
    try:
        file_bytes = uploaded_file.read()
        doc = fitz.open(stream=file_bytes, filetype="pdf")

        text_list = []

        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text()
            if page_text:
                text_list.append(page_text)

        doc.close()

        return "\n".join(text_list).strip()

    except Exception as e:
        raise RuntimeError(f"PDF 文本提取失败：{e}")