import re
import pandas as pd
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


def get_match_level(score: int) -> str:
    """
    根据分数返回匹配等级。
    """
    if score >= 80:
        return "较高"
    if score >= 70:
        return "中等"
    if score >= 60:
        return "基础相关"
    return "需明显补充"


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


def generate_markdown_report(result: dict) -> str:
    """
    根据结构化分析结果生成单岗位 Markdown 报告。
    """
    score = get_score(result.get("match_score", 0))

    lines = []

    lines.append("# JobMatch AI 岗位匹配分析报告\n")

    lines.append("## 一、综合匹配度\n")
    lines.append(f"**综合匹配度：{score}/100**\n")

    lines.append("## 二、总体结论\n")
    lines.append(result.get("summary", "暂无总结"))
    lines.append("\n")

    lines.append("## 三、岗位关键词\n")
    for item in result.get("position_keywords", []):
        lines.append(f"- {item}")
    lines.append("\n")

    lines.append("## 四、简历关键词\n")
    for item in result.get("resume_keywords", []):
        lines.append(f"- {item}")
    lines.append("\n")

    lines.append("## 五、候选人优势\n")
    for item in result.get("strengths", []):
        lines.append(f"- {item}")
    lines.append("\n")

    lines.append("## 六、能力短板\n")
    for item in result.get("weaknesses", []):
        lines.append(f"- {item}")
    lines.append("\n")

    lines.append("## 七、简历优化建议\n")
    for idx, item in enumerate(result.get("resume_suggestions", []), start=1):
        lines.append(f"### 建议 {idx}：{item.get('target', '')}")
        lines.append(f"- 修改建议：{item.get('suggestion', '')}")
        lines.append(f"- 可写进简历的表达：{item.get('resume_expression', '')}")
        lines.append("\n")

    project = result.get("project_suggestion", {})
    if project:
        lines.append("## 八、推荐补充项目\n")
        lines.append(f"**项目名称：{project.get('name', '')}**\n")
        lines.append(f"推荐原因：{project.get('reason', '')}\n")

        lines.append("核心功能：")
        for item in project.get("features", []):
            lines.append(f"- {item}")

        lines.append("\n技术栈：")
        for item in project.get("tech_stack", []):
            lines.append(f"- {item}")

        lines.append("\n可写进简历的表达：")
        lines.append(project.get("resume_expression", ""))
        lines.append("\n")

    lines.append("## 九、模拟面试问题\n")
    for idx, item in enumerate(result.get("interview_questions", []), start=1):
        lines.append(f"{idx}. 【{item.get('type', '面试问题')}】{item.get('question', '')}")
    lines.append("\n")

    lines.append("## 十、面试表达建议\n")
    lines.append(result.get("self_intro_advice", "暂无建议"))
    lines.append("\n")

    return "\n".join(lines)


def generate_multi_jd_report(compare_results: list) -> str:
    """
    生成多岗位对比 Markdown 报告。
    """
    lines = []
    lines.append("# JobMatch AI 多岗位匹配对比报告\n")

    sorted_results = sorted(
        compare_results,
        key=lambda x: x.get("score", 0),
        reverse=True
    )

    if sorted_results:
        best = sorted_results[0]
        lines.append("## 一、最推荐岗位\n")
        lines.append(f"**最推荐：{best.get('job_name', '')}**")
        lines.append(f"**匹配度：{best.get('score', 0)}/100**")
        lines.append(f"**匹配等级：{best.get('level', '')}**\n")
        lines.append(best.get("summary", "暂无总结"))
        lines.append("\n")

    lines.append("## 二、岗位对比表\n")
    lines.append("| 排名 | 岗位名称 | 匹配度 | 匹配等级 | 总体结论 |")
    lines.append("|---|---|---:|---|---|")

    for idx, item in enumerate(sorted_results, start=1):
        summary = item.get("summary", "").replace("\n", " ")
        lines.append(
            f"| {idx} | {item.get('job_name', '')} | {item.get('score', 0)} | {item.get('level', '')} | {summary} |"
        )

    lines.append("\n")

    lines.append("## 三、各岗位详细分析\n")

    for idx, item in enumerate(sorted_results, start=1):
        result = item.get("result", {})
        lines.append(f"### {idx}. {item.get('job_name', '')}\n")
        lines.append(f"- 匹配度：{item.get('score', 0)}/100")
        lines.append(f"- 匹配等级：{item.get('level', '')}")
        lines.append(f"- 总体结论：{item.get('summary', '')}\n")

        lines.append("岗位关键词：")
        for kw in result.get("position_keywords", []):
            lines.append(f"- {kw}")

        lines.append("\n候选人优势：")
        for s in result.get("strengths", []):
            lines.append(f"- {s}")

        lines.append("\n能力短板：")
        for w in result.get("weaknesses", []):
            lines.append(f"- {w}")

        lines.append("\n")

    return "\n".join(lines)


def render_single_result(result: dict):
    """
    渲染单岗位结构化分析结果。
    """
    if "raw_result" in result:
        st.warning("模型没有返回标准 JSON，以下展示原始分析结果：")
        st.markdown(result["raw_result"])
        return

    score = get_score(result.get("match_score", 0))
    level = get_match_level(score)

    metric_col1, metric_col2, metric_col3 = st.columns(3)

    with metric_col1:
        st.metric("综合匹配度", f"{score}/100")

    with metric_col2:
        st.metric("匹配等级", level)

    with metric_col3:
        st.metric("分析维度", "8 项")

    st.progress(score)

    st.markdown("### 🧭 总体结论")
    st.info(result.get("summary", "暂无总结"))

    report_md = generate_markdown_report(result)

    st.download_button(
        label="📥 下载岗位匹配分析报告",
        data=report_md,
        file_name="JobMatch_AI_岗位匹配分析报告.md",
        mime="text/markdown",
        use_container_width=True
    )

    st.markdown("### 📄 报告预览与结果复用")

    with st.expander("查看 Markdown 报告预览"):
        st.markdown(report_md)

    project = result.get("project_suggestion", {})

    if project:
        st.markdown("### 📌 可复制的简历项目描述")

        resume_project_text = project.get("resume_expression", "")

        st.text_area(
            "下面这段内容可作为简历项目经历的参考表达",
            value=resume_project_text,
            height=140
        )

    st.markdown("### ✅ 下一步行动建议")

    action_items = [
        "根据能力短板补充 1 个 AI 应用开发小项目",
        "将简历项目描述从“学习/实验”改成“功能实现/应用落地”",
        "围绕生成的面试问题准备 3-5 分钟项目介绍",
        "优先投递要求 Python、Prompt Engineering、RAG、Streamlit/FastAPI 的岗位"
    ]

    for item in action_items:
        st.markdown(f"- {item}")

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


st.title("🎯 JobMatch AI：AI应用开发实习岗位匹配助手")

st.markdown(
    """
    这是一个面向 **AI 应用开发实习** 的求职辅助工具。

    你可以上传自己的 PDF 简历，并粘贴目标岗位 JD。系统会自动生成：
    - 单岗位匹配分析
    - 多岗位 JD 匹配对比
    - 岗位关键词与简历关键词
    - 候选人优势与能力短板
    - 简历优化建议与模拟面试问题
    - Markdown 分析报告
    """
)

st.divider()


with st.sidebar:
    st.header("使用说明")
    st.markdown(
        """
        1. 上传 PDF 简历  
        2. 选择分析模式  
        3. 粘贴一个或多个岗位 JD  
        4. 点击“开始分析”  
        5. 查看结构化分析结果  
        6. 下载 Markdown 分析报告  
        """
    )

    st.warning("建议使用中文 JD 或中英混合 JD，分析效果更稳定。")

    st.divider()

    st.markdown(
        """
        **当前版本：v3-report**

        本版本新增：
        - 单岗位分析模式
        - 多岗位 JD 对比模式
        - 岗位匹配度排序
        - 最推荐岗位提示
        - 多岗位对比报告导出
        """
    )


analysis_mode = st.radio(
    "请选择分析模式",
    ["单岗位分析", "多岗位对比"],
    horizontal=True
)

st.divider()


left_col, right_col = st.columns(2)

with left_col:
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


if analysis_mode == "单岗位分析":
    with right_col:
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
                    render_single_result(result)

                except Exception as e:
                    st.error(f"分析失败：{e}")
                    st.info("请检查 API Key、DeepSeek 账户余额和网络连接。")


else:
    with right_col:
        st.subheader("📌 多岗位 JD 输入")

        jd_count = st.slider(
            "选择需要对比的岗位数量",
            min_value=2,
            max_value=5,
            value=3
        )

        jd_inputs = []

        for i in range(jd_count):
            with st.expander(f"岗位 {i + 1} JD", expanded=(i == 0)):
                job_name = st.text_input(
                    f"岗位 {i + 1} 名称",
                    value=f"岗位 {i + 1}",
                    key=f"job_name_{i}"
                )

                jd_text = st.text_area(
                    f"岗位 {i + 1} 描述",
                    height=220,
                    key=f"jd_text_{i}",
                    placeholder="请粘贴该岗位 JD，包括职责、要求和加分项。"
                )

                jd_inputs.append(
                    {
                        "job_name": job_name.strip(),
                        "jd_text": jd_text.strip()
                    }
                )

    st.divider()

    compare_button = st.button("🚀 开始多岗位对比", type="primary", use_container_width=True)

    if compare_button:
        valid_jds = [
            item for item in jd_inputs
            if item["job_name"] and item["jd_text"]
        ]

        if uploaded_file is None:
            st.warning("请先上传 PDF 简历。")
        elif not resume_text.strip():
            st.warning("简历文本为空，请检查 PDF 是否可以复制文字。")
        elif len(valid_jds) < 2:
            st.warning("请至少填写 2 个完整岗位 JD。")
        else:
            compare_results = []

            progress_bar = st.progress(0)
            status_text = st.empty()

            for idx, item in enumerate(valid_jds, start=1):
                status_text.info(f"正在分析第 {idx}/{len(valid_jds)} 个岗位：{item['job_name']}")

                try:
                    result = analyze_resume_jd(
                        resume_text=resume_text,
                        jd_text=item["jd_text"]
                    )

                    score = get_score(result.get("match_score", 0))
                    level = get_match_level(score)
                    summary = result.get("summary", "暂无总结")

                    compare_results.append(
                        {
                            "job_name": item["job_name"],
                            "score": score,
                            "level": level,
                            "summary": summary,
                            "result": result
                        }
                    )

                except Exception as e:
                    compare_results.append(
                        {
                            "job_name": item["job_name"],
                            "score": 0,
                            "level": "分析失败",
                            "summary": str(e),
                            "result": {}
                        }
                    )

                progress_bar.progress(idx / len(valid_jds))

            status_text.success("多岗位对比分析完成")

            sorted_results = sorted(
                compare_results,
                key=lambda x: x.get("score", 0),
                reverse=True
            )

            st.subheader("📊 多岗位匹配度对比结果")

            if sorted_results:
                best = sorted_results[0]

                st.success(
                    f"最推荐投递：{best.get('job_name')}，匹配度 {best.get('score')}/100，匹配等级：{best.get('level')}"
                )

            table_data = []

            for idx, item in enumerate(sorted_results, start=1):
                table_data.append(
                    {
                        "排名": idx,
                        "岗位名称": item.get("job_name"),
                        "匹配度": item.get("score"),
                        "匹配等级": item.get("level"),
                        "总体结论": item.get("summary")
                    }
                )

            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True)

            report_md = generate_multi_jd_report(sorted_results)

            st.download_button(
                label="📥 下载多岗位对比报告",
                data=report_md,
                file_name="JobMatch_AI_多岗位对比报告.md",
                mime="text/markdown",
                use_container_width=True
            )

            st.markdown("### 🔍 各岗位详细分析")

            for idx, item in enumerate(sorted_results, start=1):
                with st.expander(f"{idx}. {item.get('job_name')}｜匹配度 {item.get('score')}/100｜{item.get('level')}"):
                    result = item.get("result", {})

                    st.markdown("#### 总体结论")
                    st.info(item.get("summary", ""))

                    c1, c2 = st.columns(2)

                    with c1:
                        st.markdown("#### 岗位关键词")
                        render_tags(result.get("position_keywords", []))

                    with c2:
                        st.markdown("#### 简历关键词")
                        render_tags(result.get("resume_keywords", []))

                    st.markdown("#### 候选人优势")
                    render_text_list(result.get("strengths", []))

                    st.markdown("#### 能力短板")
                    render_text_list(result.get("weaknesses", []))


st.divider()

st.markdown(
    """
    ### 项目说明

    本项目是一个 AI 应用开发方向的求职作品 MVP，主要展示：
    - PDF 文档解析能力
    - 大语言模型 API 调用能力
    - Prompt Engineering 能力
    - Streamlit 应用开发能力
    - 结构化结果展示能力
    - Markdown 分析报告导出能力
    - 多岗位 JD 批量对比能力
    - 面向真实求职场景的 AI 产品设计能力
    """
)