import re
import streamlit as st
from resume_parser import extract_text_from_pdf
from llm_client import analyze_resume_jd


st.set_page_config(
    page_title="JobMatch AI",
    page_icon="🎯",
    layout="wide"
)


def get_score(value) -> int:
    """
    将模型返回的匹配度转换成 0-100 的整数。
    """
    if isinstance(value, int):
        return max(0, min(100, value))

    if isinstance(value, float):
        return max(0, min(100, int(value)))

    if isinstance(value, str):
        match = re.search(r"\d+", value)
        if match:
            return max(0, min(100, int(match.group())))

    return 0


def render_tags(items):
    """
    渲染关键词标签。
    """
    if not items:
        st.info("暂无关键词")
        return

    tag_html = ""
    for item in items:
        tag_html += f"""
        <span style="
            display:inline-block;
            padding:6px 12px;
            margin:4px;
            background-color:#f0f2f6;
            border-radius:16px;
            font-size:14px;
        ">{item}</span>
        """
    st.markdown(tag_html, unsafe_allow_html=True)


def render_text_list(items):
    """
    渲染普通文本列表。
    """
    if not items:
        st.info("暂无内容")
        return

    for item in items:
        st.markdown(f"- {item}")


def render_resume_suggestions(items):
    """
    渲染简历优化建议。
    """
    if not items:
        st.info("暂无简历优化建议")
        return

    for idx, item in enumerate(items, start=1):
        with st.expander(f"建议 {idx}：{item.get('target', '简历优化方向')}"):
            st.markdown("**修改建议：**")
            st.write(item.get("suggestion", ""))

            st.markdown("**可直接写进简历的表达：**")
            st.info(item.get("resume_expression", ""))


def render_interview_questions(items):
    """
    渲染面试问题。
    """
    if not items:
        st.info("暂无面试问题")
        return

    for idx, item in enumerate(items, start=1):
        question_type = item.get("type", "面试问题")
        question = item.get("question", "")

        st.markdown(f"**{idx}. [{question_type}] {question}**")


st.title("🎯 JobMatch AI：AI应用开发实习岗位匹配助手")

st.markdown(
    """
    这是一个面向 **AI 应用开发实习** 的求职辅助工具。

    你可以上传自己的 PDF 简历，并粘贴目标岗位 JD。系统会自动生成：
    - 岗位匹配度评分
    - 岗位关键词与简历关键词
    - 候选人优势与能力短板
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
        4. 查看结构化分析结果  
        """
    )

    st.warning("建议使用中文 JD 或中英混合 JD，分析效果更稳定。")

    st.divider()

    st.markdown(
        """
        **当前版本：v2-ui**

        本版本新增：
        - 匹配度评分卡
        - 关键词标签
        - 分模块结果展示
        - 简历建议折叠面板
        """
    )


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

                if "raw_result" in result:
                    st.warning("模型没有返回标准 JSON，以下展示原始分析结果：")
                    st.markdown(result["raw_result"])
                else:
                    score = get_score(result.get("match_score", 0))

                    metric_col1, metric_col2, metric_col3 = st.columns(3)

                    with metric_col1:
                        st.metric("综合匹配度", f"{score}/100")

                    with metric_col2:
                        if score >= 80:
                            level = "较高"
                        elif score >= 70:
                            level = "中等"
                        elif score >= 60:
                            level = "基础相关"
                        else:
                            level = "需明显补充"
                        st.metric("匹配等级", level)

                    with metric_col3:
                        st.metric("分析维度", "8 项")

                    st.progress(score)

                    st.markdown("### 🧭 总体结论")
                    st.info(result.get("summary", "暂无总结"))

                    tab1, tab2, tab3, tab4, tab5 = st.tabs(
                        [
                            "关键词匹配",
                            "优势分析",
                            "能力短板",
                            "简历优化",
                            "面试准备"
                        ]
                    )

                    with tab1:
                        c1, c2 = st.columns(2)

                        with c1:
                            st.markdown("#### 岗位关键词")
                            render_tags(result.get("position_keywords", []))

                        with c2:
                            st.markdown("#### 简历关键词")
                            render_tags(result.get("resume_keywords", []))

                    with tab2:
                        st.markdown("#### 候选人已有优势")
                        render_text_list(result.get("strengths", []))

                    with tab3:
                        st.markdown("#### 当前能力短板")
                        render_text_list(result.get("weaknesses", []))

                    with tab4:
                        st.markdown("#### 简历优化建议")
                        render_resume_suggestions(result.get("resume_suggestions", []))

                        st.markdown("#### 可补充的小项目建议")
                        project = result.get("project_suggestion", {})

                        if project:
                            st.markdown(f"**项目名称：** {project.get('name', '')}")
                            st.markdown(f"**推荐原因：** {project.get('reason', '')}")

                            st.markdown("**核心功能：**")
                            render_text_list(project.get("features", []))

                            st.markdown("**技术栈：**")
                            render_tags(project.get("tech_stack", []))

                            st.markdown("**可写进简历的表达：**")
                            st.info(project.get("resume_expression", ""))

                    with tab5:
                        st.markdown("#### 模拟面试问题")
                        render_interview_questions(result.get("interview_questions", []))

                        st.markdown("#### 面试表达建议")
                        st.info(result.get("self_intro_advice", "暂无建议"))

            except Exception as e:
                st.error(f"分析失败：{e}")
                st.info("请检查 API Key、DeepSeek 账户余额和网络连接。")


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