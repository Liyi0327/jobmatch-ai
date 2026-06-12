import streamlit as st
from resume_parser import extract_text_from_pdf
from llm_client import analyze_resume_jd


st.set_page_config(
    page_title="JobMatch AI",
    page_icon="🎯",
    layout="wide"
)


st.title("🎯 JobMatch AI：AI应用开发实习岗位匹配助手")

st.markdown(
    """
    这是一个面向 **AI 应用开发实习** 的求职辅助工具。

    你可以上传自己的 PDF 简历，并粘贴目标岗位 JD。
    系统会自动分析：
    - 岗位核心要求
    - 简历已有优势
    - 岗位匹配度
    - 能力短板
    - 简历优化建议
    - 模拟面试问题
    """
)

st.divider()


with st.sidebar:
    st.header("使用说明")
    st.markdown(
        """
        1. 上传 PDF 简历  
        2. 粘贴 AI 应用开发岗位 JD  
        3. 点击“开始分析”  
        4. 查看匹配度和优化建议  
        """
    )

    st.warning("建议先使用中文 JD 或中英混合 JD，分析效果更稳定。")


col1, col2 = st.columns(2)

with col1:
    st.subheader("📄 上传简历")
    uploaded_file = st.file_uploader(
        "请上传 PDF 格式简历",
        type=["pdf"]
    )

    resume_text = ""

    if uploaded_file is not None:
        try:
            resume_text = extract_text_from_pdf(uploaded_file)

            if resume_text.strip():
                st.success("简历解析成功")
                with st.expander("查看解析出的简历文本"):
                    st.text_area(
                        "简历文本",
                        value=resume_text,
                        height=300
                    )
            else:
                st.error("没有从 PDF 中解析出文本，请确认简历不是纯图片格式。")

        except Exception as e:
            st.error(f"简历解析失败：{e}")

with col2:
    st.subheader("💼 粘贴岗位 JD")
    jd_text = st.text_area(
        "请粘贴目标岗位描述",
        height=380,
        placeholder="""示例：
岗位：AI应用开发实习生
职责：
1. 参与大模型应用开发；
2. 负责 Prompt 设计、RAG 流程搭建；
3. 使用 Python/FastAPI/Streamlit 完成原型开发；
4. 参与模型效果评估和优化。

要求：
1. 熟悉 Python；
2. 了解大语言模型、RAG、向量数据库；
3. 有 PyTorch 或机器学习基础优先。
"""
    )


st.divider()

analyze_button = st.button("🚀 开始分析", type="primary", use_container_width=True)


if analyze_button:
    if uploaded_file is None:
        st.warning("请先上传 PDF 简历。")
    elif not resume_text.strip():
        st.warning("简历文本为空，请检查 PDF 是否可以复制文字。")
    elif not jd_text.strip():
        st.warning("请粘贴岗位 JD。")
    else:
        with st.spinner("正在分析简历与岗位匹配情况，请稍等..."):
            try:
                result = analyze_resume_jd(
                    resume_text=resume_text,
                    jd_text=jd_text
                )

                st.subheader("📊 分析结果")
                st.markdown(result)

            except Exception as e:
                st.error(f"分析失败：{e}")
                st.info("请检查 API Key 是否正确，以及网络是否正常。")


st.divider()

st.markdown(
    """
    ### 项目说明

    本项目是一个 AI 应用开发方向的求职作品 MVP，主要展示：
    - PDF 文档解析能力
    - 大语言模型 API 调用能力
    - Prompt Engineering 能力
    - Streamlit 应用开发能力
    - 面向真实求职场景的 AI 产品设计能力
    """
)