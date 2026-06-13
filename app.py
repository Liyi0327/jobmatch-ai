import re
import pandas as pd
import streamlit as st

from resume_parser import extract_text_from_pdf
from llm_client import analyze_resume_jd

from db import (
    init_db,
    add_job,
    get_all_jobs,
    get_job_by_id,
    update_job_status,
    update_job_note,
    update_job_match_result,
    delete_job,
    save_analysis_result,
    get_analysis_history,
    get_dashboard_stats,
    search_jobs
)


st.set_page_config(
    page_title="JobMatch AI",
    page_icon="🎯",
    layout="wide"
)

init_db()


STATUS_OPTIONS = [
    "待分析",
    "待投递",
    "已投递",
    "笔试",
    "面试",
    "已拒绝",
    "Offer"
]


if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""

if "resume_file_name" not in st.session_state:
    st.session_state.resume_file_name = ""

if "single_result" not in st.session_state:
    st.session_state.single_result = None

if "multi_results" not in st.session_state:
    st.session_state.multi_results = []


def get_score(value) -> int:
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
    if score >= 80:
        return "较高"
    if score >= 70:
        return "中等"
    if score >= 60:
        return "基础相关"
    return "需明显补充"


def render_tags(items):
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
    if not items:
        st.info("暂无内容")
        return

    for item in items:
        st.markdown(f"- {item}")


def render_resume_suggestions(items):
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
    if not items:
        st.info("暂无面试问题")
        return

    for idx, item in enumerate(items, start=1):
        question_type = item.get("type", "面试问题")
        question = item.get("question", "")
        st.markdown(f"**{idx}. [{question_type}] {question}**")


def generate_markdown_report(result: dict) -> str:
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
        lines.append(f"**公司：{best.get('company', '')}**")
        lines.append(f"**匹配度：{best.get('score', 0)}/100**")
        lines.append(f"**匹配等级：{best.get('level', '')}**\n")
        lines.append(best.get("summary", "暂无总结"))
        lines.append("\n")

    lines.append("## 二、岗位对比表\n")
    lines.append("| 排名 | 岗位名称 | 公司 | 匹配度 | 匹配等级 | 总体结论 |")
    lines.append("|---|---|---|---:|---|---|")

    for idx, item in enumerate(sorted_results, start=1):
        summary = item.get("summary", "").replace("\n", " ")
        lines.append(
            f"| {idx} | {item.get('job_name', '')} | {item.get('company', '')} | {item.get('score', 0)} | {item.get('level', '')} | {summary} |"
        )

    lines.append("\n")

    lines.append("## 三、各岗位详细分析\n")

    for idx, item in enumerate(sorted_results, start=1):
        result = item.get("result", {})
        lines.append(f"### {idx}. {item.get('job_name', '')}\n")
        lines.append(f"- 公司：{item.get('company', '')}")
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


def render_single_result(result: dict, job_id=None):
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

    if job_id is not None:
        st.markdown("### 📌 投递状态更新")
        new_status = st.selectbox(
            "将该岗位状态更新为",
            STATUS_OPTIONS,
            key=f"single_status_{job_id}"
        )
        if st.button("保存岗位状态", use_container_width=True, key=f"save_status_{job_id}"):
            update_job_status(job_id, new_status)
            st.success("岗位状态已更新。")

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


def analyze_job_and_save(resume_text: str, job: dict):
    result = analyze_resume_jd(
        resume_text=resume_text,
        jd_text=job.get("jd_text", "")
    )

    if "raw_result" in result:
        return result

    score = get_score(result.get("match_score", 0))
    level = get_match_level(score)
    summary = result.get("summary", "暂无总结")

    update_job_match_result(
        job_id=job["id"],
        match_score=score,
        match_level=level
    )

    save_analysis_result(
        job_id=job["id"],
        job_name=job.get("job_name", ""),
        company=job.get("company", ""),
        match_score=score,
        match_level=level,
        summary=summary,
        result=result
    )

    return result


def render_resume_section():
    st.markdown("## ① 我的简历")

    uploaded_file = st.file_uploader(
        "上传一份 PDF 简历，后续所有岗位分析都会使用这份简历",
        type=["pdf"],
        key="main_resume"
    )

    if uploaded_file is not None:
        try:
            resume_text = extract_text_from_pdf(uploaded_file)

            if resume_text.strip():
                st.session_state.resume_text = resume_text
                st.session_state.resume_file_name = uploaded_file.name
                st.success(f"简历解析成功：{uploaded_file.name}")
            else:
                st.error("没有从 PDF 中解析出文本，请确认简历不是纯图片格式。")

        except Exception as e:
            st.error(f"简历解析失败：{e}")

    if st.session_state.resume_text:
        with st.expander("查看当前简历解析文本"):
            st.text_area(
                "简历文本",
                value=st.session_state.resume_text,
                height=220
            )
    else:
        st.info("请先上传简历。上传后，后续分析无需重复上传。")


def render_job_pool_section():
    st.markdown("## ② 我的岗位池")

    with st.expander("新增岗位到岗位池", expanded=False):
        with st.form("add_job_form"):
            c1, c2 = st.columns(2)

            with c1:
                job_name = st.text_input("岗位名称 *")
                company = st.text_input("公司名称")
                city = st.text_input("城市")

            with c2:
                source = st.text_input("岗位来源", placeholder="例如：BOSS直聘 / 实习僧 / 公司官网")
                job_url = st.text_input("岗位链接")
                status = st.selectbox("当前状态", STATUS_OPTIONS, index=0)

            jd_text = st.text_area("岗位 JD *", height=220)
            note = st.text_area("备注", height=80)

            submitted = st.form_submit_button("保存岗位", use_container_width=True)

            if submitted:
                if not job_name.strip():
                    st.warning("请填写岗位名称。")
                elif not jd_text.strip():
                    st.warning("请填写岗位 JD。")
                else:
                    job_id = add_job(
                        job_name=job_name.strip(),
                        company=company.strip(),
                        city=city.strip(),
                        source=source.strip(),
                        job_url=job_url.strip(),
                        jd_text=jd_text.strip(),
                        status=status,
                        note=note.strip()
                    )
                    st.success(f"岗位已保存，岗位 ID：{job_id}")

    jobs = get_all_jobs()

    if not jobs:
        st.info("暂无岗位。请先新增岗位。")
        return []

    filter_col1, filter_col2 = st.columns(2)

    with filter_col1:
        keyword = st.text_input("搜索岗位", placeholder="搜索岗位、公司、城市或 JD 内容")

    with filter_col2:
        status_filter = st.selectbox("状态筛选", ["全部"] + STATUS_OPTIONS)

    jobs = search_jobs(keyword=keyword, status=status_filter)

    table_data = []

    for job in jobs:
        table_data.append(
            {
                "ID": job.get("id"),
                "岗位名称": job.get("job_name"),
                "公司": job.get("company"),
                "城市": job.get("city"),
                "状态": job.get("status"),
                "匹配度": job.get("match_score"),
                "匹配等级": job.get("match_level"),
                "更新时间": job.get("updated_at")
            }
        )

    st.dataframe(pd.DataFrame(table_data), use_container_width=True)

    with st.expander("管理岗位状态与备注"):
        job_options = {
            f"{job.get('id')}｜{job.get('job_name')}｜{job.get('company') or '未填写公司'}": job.get("id")
            for job in jobs
        }

        selected_label = st.selectbox("选择一个岗位", list(job_options.keys()))
        selected_job_id = job_options[selected_label]
        job = get_job_by_id(selected_job_id)

        if job:
            st.markdown(f"**岗位名称：** {job.get('job_name')}")
            st.markdown(f"**公司：** {job.get('company') or '未填写'}")

            new_status = st.selectbox(
                "更新状态",
                STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(job.get("status")) if job.get("status") in STATUS_OPTIONS else 0
            )

            new_note = st.text_area("备注", value=job.get("note") or "", height=100)

            c1, c2 = st.columns(2)

            with c1:
                if st.button("保存状态与备注", use_container_width=True):
                    update_job_status(job["id"], new_status)
                    update_job_note(job["id"], new_note)
                    st.success("状态与备注已保存。")

            with c2:
                if st.button("删除该岗位", use_container_width=True):
                    delete_job(job["id"])
                    st.warning("岗位已删除。请刷新页面。")

            with st.expander("查看岗位 JD"):
                st.write(job.get("jd_text", ""))

    return jobs


def render_analysis_section(jobs):
    st.markdown("## ③ 选择岗位进行 AI 分析")

    if not st.session_state.resume_text:
        st.warning("请先在上方上传简历。")
        return

    if not jobs:
        st.warning("请先添加岗位到岗位池。")
        return

    job_options = {
        f"{job.get('id')}｜{job.get('job_name')}｜{job.get('company') or '未填写公司'}": job.get("id")
        for job in jobs
    }

    selected_labels = st.multiselect(
        "选择一个或多个岗位进行分析",
        list(job_options.keys())
    )

    selected_job_ids = [
        job_options[label]
        for label in selected_labels
    ]

    c1, c2 = st.columns(2)

    with c1:
        analyze_single = st.button("分析选中的单个岗位", type="primary", use_container_width=True)

    with c2:
        analyze_multi = st.button("对比分析多个岗位", use_container_width=True)

    if analyze_single:
        if len(selected_job_ids) != 1:
            st.warning("单岗位分析请选择 1 个岗位。")
        else:
            job = get_job_by_id(selected_job_ids[0])
            if job:
                with st.spinner(f"正在分析岗位：{job.get('job_name')}"):
                    result = analyze_job_and_save(st.session_state.resume_text, job)

                st.session_state.single_result = {
                    "job": job,
                    "result": result
                }
                st.session_state.multi_results = []
                st.success("分析完成，结果已保存。")

    if analyze_multi:
        if len(selected_job_ids) < 2:
            st.warning("多岗位对比请至少选择 2 个岗位。")
        else:
            compare_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            for idx, job_id in enumerate(selected_job_ids, start=1):
                job = get_job_by_id(job_id)

                if not job:
                    continue

                status_text.info(f"正在分析第 {idx}/{len(selected_job_ids)} 个岗位：{job.get('job_name')}")

                try:
                    result = analyze_job_and_save(st.session_state.resume_text, job)

                    if "raw_result" in result:
                        score = 0
                        level = "格式异常"
                        summary = "模型返回了非标准 JSON。"
                    else:
                        score = get_score(result.get("match_score", 0))
                        level = get_match_level(score)
                        summary = result.get("summary", "暂无总结")

                    compare_results.append(
                        {
                            "job_id": job.get("id"),
                            "job_name": job.get("job_name"),
                            "company": job.get("company"),
                            "score": score,
                            "level": level,
                            "summary": summary,
                            "result": result
                        }
                    )

                except Exception as e:
                    compare_results.append(
                        {
                            "job_id": job.get("id"),
                            "job_name": job.get("job_name"),
                            "company": job.get("company"),
                            "score": 0,
                            "level": "分析失败",
                            "summary": str(e),
                            "result": {}
                        }
                    )

                progress_bar.progress(idx / len(selected_job_ids))

            status_text.success("多岗位对比分析完成")
            st.session_state.multi_results = compare_results
            st.session_state.single_result = None


def render_result_section():
    st.markdown("## ④ 分析结果与下一步行动")

    if st.session_state.single_result:
        job = st.session_state.single_result["job"]
        result = st.session_state.single_result["result"]

        st.markdown(f"### 当前分析岗位：{job.get('job_name')}｜{job.get('company') or '未填写公司'}")
        render_single_result(result, job_id=job.get("id"))

    elif st.session_state.multi_results:
        sorted_results = sorted(
            st.session_state.multi_results,
            key=lambda x: x.get("score", 0),
            reverse=True
        )

        st.markdown("### 多岗位匹配度对比结果")

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
                    "公司": item.get("company"),
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

        st.markdown("### 各岗位详细分析")

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

                new_status = st.selectbox(
                    f"更新「{item.get('job_name')}」状态",
                    STATUS_OPTIONS,
                    key=f"multi_status_{item.get('job_id')}"
                )

                if st.button(
                    f"保存「{item.get('job_name')}」状态",
                    key=f"multi_save_status_{item.get('job_id')}",
                    use_container_width=True
                ):
                    update_job_status(item.get("job_id"), new_status)
                    st.success("状态已保存。")

    else:
        st.info("请选择岗位并开始分析。分析结果会显示在这里。")


def render_dashboard_section():
    st.markdown("## ⑤ 求职进度概览")

    stats = get_dashboard_stats()

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("岗位总数", stats.get("total_jobs", 0))
    c2.metric("已投递/推进中", stats.get("applied_count", 0))
    c3.metric("面试中", stats.get("interview_count", 0))
    c4.metric("Offer", stats.get("offer_count", 0))
    c5.metric("平均匹配度", stats.get("avg_score", 0))

    jobs = get_all_jobs()

    if not jobs:
        st.info("暂无岗位记录。")
        return

    table_data = []

    for job in jobs:
        table_data.append(
            {
                "ID": job.get("id"),
                "岗位名称": job.get("job_name"),
                "公司": job.get("company"),
                "城市": job.get("city"),
                "状态": job.get("status"),
                "匹配度": job.get("match_score"),
                "匹配等级": job.get("match_level"),
                "来源": job.get("source"),
                "更新时间": job.get("updated_at")
            }
        )

    df = pd.DataFrame(table_data)

    with st.expander("查看岗位进度表"):
        st.dataframe(df, use_container_width=True)

        csv_data = df.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            label="📥 导出求职岗位清单 CSV",
            data=csv_data,
            file_name="job_applications.csv",
            mime="text/csv",
            use_container_width=True
        )


def render_history_section():
    st.markdown("## ⑥ AI 分析历史")

    history = get_analysis_history()

    if not history:
        st.info("暂无分析历史。")
        return

    table_data = []

    for item in history[:20]:
        table_data.append(
            {
                "ID": item.get("id"),
                "岗位名称": item.get("job_name"),
                "公司": item.get("company"),
                "匹配度": item.get("match_score"),
                "匹配等级": item.get("match_level"),
                "分析时间": item.get("created_at"),
                "总体结论": item.get("summary")
            }
        )

    with st.expander("查看最近 20 条分析历史"):
        st.dataframe(pd.DataFrame(table_data), use_container_width=True)


st.title("🎯 JobMatch AI：AI求职工作台")

st.markdown(
    """
    这是一个面向 **AI 应用开发实习求职** 的一页式求职工作台。

    你可以在同一个页面完成：
    - 上传简历
    - 添加岗位
    - 选择岗位分析
    - 查看匹配结果
    - 更新投递状态
    - 下载分析报告
    - 查看求职进度
    """
)

st.divider()


with st.sidebar:
    st.header("当前状态")

    stats = get_dashboard_stats()

    st.metric("岗位总数", stats.get("total_jobs", 0))
    st.metric("平均匹配度", stats.get("avg_score", 0))
    st.metric("面试中 / Offer", f"{stats.get('interview_count', 0)} / {stats.get('offer_count', 0)}")

    st.divider()

    st.markdown(
        """
        **当前版本：v4-workbench**

        产品逻辑：
        1. 上传简历  
        2. 添加岗位  
        3. 选择岗位分析  
        4. 保存结果与状态  
        5. 查看求职进度  
        """
    )

    st.warning("请勿上传包含敏感隐私信息的简历到公开部署环境。")


render_resume_section()

st.divider()

jobs = render_job_pool_section()

st.divider()

render_analysis_section(jobs)

st.divider()

render_result_section()

st.divider()

render_dashboard_section()

st.divider()

render_history_section()

st.divider()

st.markdown(
    """
    ### 项目说明

    本项目是一个 AI 应用开发方向的求职作品，主要展示：
    - PDF 简历解析能力
    - 大语言模型 API 调用能力
    - Prompt Engineering 能力
    - Streamlit 一页式工作台开发能力
    - SQLite 数据持久化能力
    - 岗位信息 CRUD 能力
    - 求职状态管理能力
    - AI 分析历史保存能力
    - Markdown / CSV 报告导出能力
    - 面向真实求职场景的 AI 产品设计能力
    """
)