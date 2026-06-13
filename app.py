import re
from difflib import SequenceMatcher

import pandas as pd
import streamlit as st

from resume_parser import extract_text_from_resume
from llm_client import analyze_resume_jd, extract_job_from_jd

from db import (
    init_db,
    init_resume_db,
    add_resume,
    get_all_resumes,
    get_resume_by_id,
    get_active_resume,
    set_active_resume,
    clear_active_resume,
    delete_resume,
    add_job,
    get_all_jobs,
    get_job_by_id,
    update_job_status,
    update_job_note,
    update_job_match_result,
    replace_job_info,
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
init_resume_db()


STATUS_OPTIONS = [
    "待分析",
    "待投递",
    "已投递",
    "笔试",
    "面试",
    "已拒绝",
    "Offer"
]


if "resume_id" not in st.session_state:
    st.session_state.resume_id = None

if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""

if "resume_file_name" not in st.session_state:
    st.session_state.resume_file_name = ""

if "resume_char_count" not in st.session_state:
    st.session_state.resume_char_count = 0

if "resume_uploader_version" not in st.session_state:
    st.session_state.resume_uploader_version = 0

if "last_uploaded_resume_key" not in st.session_state:
    st.session_state.last_uploaded_resume_key = ""

if "show_resume_history" not in st.session_state:
    st.session_state.show_resume_history = False

if "single_result" not in st.session_state:
    st.session_state.single_result = None

if "multi_results" not in st.session_state:
    st.session_state.multi_results = []

if "pending_import_job" not in st.session_state:
    st.session_state.pending_import_job = None

if "duplicate_candidates" not in st.session_state:
    st.session_state.duplicate_candidates = []

if "last_imported_job_id" not in st.session_state:
    st.session_state.last_imported_job_id = None

if "last_imported_job_name" not in st.session_state:
    st.session_state.last_imported_job_name = ""

if "import_feedback" not in st.session_state:
    st.session_state.import_feedback = ""


def sync_active_resume_from_db():
    """
    页面刷新时，从数据库中同步当前正在使用的简历。
    """
    if st.session_state.resume_text:
        return

    active_resume = get_active_resume()

    if active_resume:
        st.session_state.resume_id = active_resume.get("id")
        st.session_state.resume_text = active_resume.get("resume_text", "")
        st.session_state.resume_file_name = active_resume.get("file_name", "")
        st.session_state.resume_char_count = active_resume.get("char_count", 0)


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


def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = text.lower()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[，。、“”‘’：:；;（）()\[\]【】/\\|_-]", "", text)
    return text


def similarity(a: str, b: str) -> float:
    a = normalize_text(a)
    b = normalize_text(b)

    if not a or not b:
        return 0.0

    return SequenceMatcher(None, a, b).ratio()


def find_duplicate_jobs(job_name: str, company: str, jd_text: str):
    jobs = get_all_jobs()
    duplicates = []

    new_job_name_norm = normalize_text(job_name)
    new_company_norm = normalize_text(company)
    new_jd_norm = normalize_text(jd_text)[:1500]

    for job in jobs:
        old_job_name = job.get("job_name") or ""
        old_company = job.get("company") or ""
        old_jd = job.get("jd_text") or ""

        old_job_name_norm = normalize_text(old_job_name)
        old_company_norm = normalize_text(old_company)
        old_jd_norm = normalize_text(old_jd)[:1500]

        exact_same_company_and_name = (
            new_company_norm
            and old_company_norm
            and new_company_norm == old_company_norm
            and new_job_name_norm == old_job_name_norm
        )

        same_company_name_similar = (
            new_company_norm
            and old_company_norm
            and new_company_norm == old_company_norm
            and similarity(job_name, old_job_name) >= 0.75
        )

        jd_highly_similar = (
            new_jd_norm
            and old_jd_norm
            and similarity(new_jd_norm, old_jd_norm) >= 0.85
        )

        if exact_same_company_and_name or same_company_name_similar or jd_highly_similar:
            duplicates.append(
                {
                    "id": job.get("id"),
                    "job_name": old_job_name,
                    "company": old_company,
                    "city": job.get("city"),
                    "status": job.get("status"),
                    "match_score": job.get("match_score"),
                    "updated_at": job.get("updated_at"),
                    "reason": (
                        "公司和岗位名相同"
                        if exact_same_company_and_name
                        else "公司相同且岗位名相似"
                        if same_company_name_similar
                        else "JD 内容高度相似"
                    )
                }
            )

    return duplicates


def build_cleaned_jd_from_parsed(parsed: dict) -> str:
    responsibilities = parsed.get("responsibilities", [])
    requirements = parsed.get("requirements", [])
    bonus_points = parsed.get("bonus_points", [])
    keywords = parsed.get("keywords", [])

    cleaned_jd_parts = []

    cleaned_jd_parts.append(f"岗位名称：{parsed.get('job_name', '')}")
    cleaned_jd_parts.append(f"公司名称：{parsed.get('company', '')}")
    cleaned_jd_parts.append(f"城市：{parsed.get('city', '')}")
    cleaned_jd_parts.append("")

    cleaned_jd_parts.append("岗位职责：")
    for item in responsibilities:
        cleaned_jd_parts.append(f"- {item}")

    cleaned_jd_parts.append("")
    cleaned_jd_parts.append("岗位要求：")
    for item in requirements:
        cleaned_jd_parts.append(f"- {item}")

    if bonus_points:
        cleaned_jd_parts.append("")
        cleaned_jd_parts.append("加分项：")
        for item in bonus_points:
            cleaned_jd_parts.append(f"- {item}")

    if keywords:
        cleaned_jd_parts.append("")
        cleaned_jd_parts.append("岗位关键词：")
        cleaned_jd_parts.append("、".join(keywords))

    return parsed.get("cleaned_jd") or "\n".join(cleaned_jd_parts)


def save_imported_job(payload: dict) -> int:
    job_id = add_job(
        job_name=payload.get("job_name", "").strip(),
        company=payload.get("company", "").strip(),
        city=payload.get("city", "").strip(),
        source=payload.get("source", "").strip(),
        job_url=payload.get("job_url", "").strip(),
        jd_text=payload.get("jd_text", "").strip(),
        status=payload.get("status", "待分析"),
        note=payload.get("note", "").strip()
    )

    st.session_state.last_imported_job_id = job_id
    st.session_state.last_imported_job_name = payload.get("job_name", "")

    return job_id


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

    st.caption("上传一份 PDF 或 Word 简历，后续所有岗位分析都会默认使用当前选中的简历。")

    uploaded_file = st.file_uploader(
        "上传简历文件",
        type=["pdf", "docx"],
        accept_multiple_files=False,
        key=f"main_resume_{st.session_state.resume_uploader_version}"
    )

    if uploaded_file is not None:
        upload_key = f"{uploaded_file.name}_{uploaded_file.size}_{st.session_state.resume_uploader_version}"

        if upload_key != st.session_state.last_uploaded_resume_key:
            try:
                resume_text = extract_text_from_resume(uploaded_file)

                if resume_text.strip():
                    file_name = uploaded_file.name
                    file_type = file_name.split(".")[-1].lower()

                    resume_id = add_resume(
                        file_name=file_name,
                        file_type=file_type,
                        resume_text=resume_text,
                        set_active=True
                    )

                    st.session_state.resume_id = resume_id
                    st.session_state.resume_text = resume_text
                    st.session_state.resume_file_name = file_name
                    st.session_state.resume_char_count = len(resume_text)
                    st.session_state.last_uploaded_resume_key = upload_key

                    st.success(f"当前简历：{file_name}，已解析并设为当前使用简历。")

                else:
                    st.error("没有从简历中解析出文本，请确认文件不是纯图片扫描版。")

            except Exception as e:
                st.error(f"简历解析失败：{e}")

    if st.session_state.resume_text:
        st.info(
            f"当前使用的简历：{st.session_state.get('resume_file_name', '')}。"
            f"后续岗位分析都会使用这份简历，解析文本约 "
            f"{st.session_state.get('resume_char_count', len(st.session_state.resume_text))} 字。"
        )

        c1, c2, c3 = st.columns([1, 1, 1])

        with c1:
            if st.button("历史简历", use_container_width=True):
                st.session_state.show_resume_history = not st.session_state.show_resume_history

        with c2:
            with st.expander("查看当前简历文本"):
                st.text_area(
                    "当前简历解析文本",
                    value=st.session_state.resume_text,
                    height=220
                )

        with c3:
            if st.button("移除当前简历", use_container_width=True):
                clear_active_resume()

                st.session_state.resume_id = None
                st.session_state.resume_text = ""
                st.session_state.resume_file_name = ""
                st.session_state.resume_char_count = 0
                st.session_state.resume_uploader_version += 1
                st.session_state.last_uploaded_resume_key = ""

                st.success("当前简历已移除，但历史记录仍然保留。")
                st.rerun()

    else:
        st.info("请先上传简历。上传成功后，后续分析无需重复上传。")

        if st.button("历史简历", use_container_width=True):
            st.session_state.show_resume_history = not st.session_state.show_resume_history

    if st.session_state.show_resume_history:
        st.markdown("### 历史简历")

        resumes = get_all_resumes()

        if not resumes:
            st.info("暂无历史简历。")
            return

        for resume in resumes:
            resume_id = resume.get("id")
            file_name = resume.get("file_name", "")
            file_type = resume.get("file_type", "")
            char_count = resume.get("char_count", 0)
            created_at = resume.get("created_at", "")
            is_active = resume.get("is_active") == 1

            row_col1, row_col2, row_col3 = st.columns([5, 1.2, 1.2])

            with row_col1:
                if is_active:
                    st.markdown(f"**{file_name}**  `当前使用`")
                else:
                    st.markdown(f"**{file_name}**")

                st.caption(f"{file_type}｜约 {char_count} 字｜上传时间：{created_at}")

            with row_col2:
                if is_active:
                    st.button(
                        "当前使用",
                        key=f"active_resume_{resume_id}",
                        disabled=True,
                        use_container_width=True
                    )
                else:
                    if st.button(
                        "设为当前",
                        key=f"set_resume_{resume_id}",
                        use_container_width=True
                    ):
                        selected_resume = get_resume_by_id(resume_id)

                        if selected_resume:
                            set_active_resume(resume_id)

                            st.session_state.resume_id = selected_resume.get("id")
                            st.session_state.resume_text = selected_resume.get("resume_text", "")
                            st.session_state.resume_file_name = selected_resume.get("file_name", "")
                            st.session_state.resume_char_count = selected_resume.get("char_count", 0)
                            st.session_state.resume_uploader_version += 1
                            st.session_state.last_uploaded_resume_key = ""

                            st.success("已设为当前使用简历。")
                            st.rerun()

            with row_col3:
                if st.button(
                    "删除",
                    key=f"delete_resume_{resume_id}",
                    use_container_width=True
                ):
                    is_current_resume = (
                        st.session_state.resume_id == resume_id
                    )

                    delete_resume(resume_id)

                    if is_current_resume:
                        st.session_state.resume_id = None
                        st.session_state.resume_text = ""
                        st.session_state.resume_file_name = ""
                        st.session_state.resume_char_count = 0
                        st.session_state.resume_uploader_version += 1
                        st.session_state.last_uploaded_resume_key = ""

                    st.success("历史简历已删除。")
                    st.rerun()

            with st.expander(f"查看解析文本：{file_name}"):
                st.text_area(
                    "历史简历解析文本",
                    value=resume.get("resume_text", ""),
                    height=180,
                    key=f"resume_text_{resume_id}"
                )

            st.divider()


def render_job_pool_section():
    st.markdown("## ② 我的岗位池")

    if st.session_state.import_feedback:
        st.success(st.session_state.import_feedback)
        st.session_state.import_feedback = ""

    with st.expander("🤖 AI 智能导入岗位 JD", expanded=True):
        st.markdown(
            """
            将从 BOSS、实习僧、公司官网等平台复制来的完整岗位 JD 粘贴到这里。
            系统会自动提取岗位名称、公司、城市、职责、要求、关键词，并判断投递优先级。

            点击按钮后：
            - 如果岗位池中没有重复岗位，系统会自动保存；
            - 如果检测到疑似重复岗位，系统会提示你选择处理方式。
            """
        )

        raw_jd = st.text_area(
            "粘贴完整岗位 JD",
            height=240,
            key="raw_jd_for_import",
            placeholder="请粘贴完整岗位描述，包括岗位名称、公司、职责、要求、加分项等。"
        )

        if st.button("🤖 AI 解析并保存岗位", type="primary", use_container_width=True):
            if not raw_jd.strip():
                st.warning("请先粘贴岗位 JD。")
            else:
                with st.spinner("正在解析岗位 JD，并检查是否重复，请稍等..."):
                    try:
                        parsed = extract_job_from_jd(raw_jd)

                        if "raw_result" in parsed:
                            st.warning("模型没有返回标准 JSON，以下展示原始结果：")
                            st.markdown(parsed["raw_result"])
                        else:
                            cleaned_jd = build_cleaned_jd_from_parsed(parsed)

                            keywords = parsed.get("keywords", [])
                            priority = parsed.get("priority", "")
                            priority_reason = parsed.get("priority_reason", "")
                            source_guess = parsed.get("source_guess", "")

                            note = f"""AI 导入结果：
投递优先级：{priority}
优先级理由：{priority_reason}
岗位关键词：{"、".join(keywords)}
"""

                            payload = {
                                "job_name": parsed.get("job_name", "").strip() or "未命名岗位",
                                "company": parsed.get("company", "").strip(),
                                "city": parsed.get("city", "").strip(),
                                "source": source_guess.strip(),
                                "job_url": "",
                                "jd_text": cleaned_jd.strip(),
                                "status": "待分析",
                                "note": note.strip()
                            }

                            duplicates = find_duplicate_jobs(
                                job_name=payload["job_name"],
                                company=payload["company"],
                                jd_text=payload["jd_text"]
                            )

                            if duplicates:
                                st.session_state.pending_import_job = payload
                                st.session_state.duplicate_candidates = duplicates
                                st.warning("检测到疑似重复岗位，暂未自动保存。请在下方选择处理方式。")
                            else:
                                job_id = save_imported_job(payload)
                                st.session_state.import_feedback = (
                                    f"岗位已自动保存到岗位池，岗位 ID：{job_id}。"
                                    f"AI 投递优先级判断：{priority}。{priority_reason}"
                                )
                                st.rerun()

                    except Exception as e:
                        st.error(f"岗位 JD 解析失败：{e}")

    if st.session_state.pending_import_job:
        st.warning("存在一个待确认的岗位导入结果。")

        st.markdown("### 疑似重复岗位")

        duplicates = st.session_state.duplicate_candidates

        duplicate_table = []

        for item in duplicates:
            duplicate_table.append(
                {
                    "ID": item.get("id"),
                    "岗位名称": item.get("job_name"),
                    "公司": item.get("company"),
                    "城市": item.get("city"),
                    "状态": item.get("status"),
                    "匹配度": item.get("match_score"),
                    "更新时间": item.get("updated_at"),
                    "重复原因": item.get("reason")
                }
            )

        st.dataframe(pd.DataFrame(duplicate_table), use_container_width=True)

        with st.expander("查看本次准备导入的岗位信息", expanded=True):
            pending = st.session_state.pending_import_job
            st.markdown(f"**岗位名称：** {pending.get('job_name')}")
            st.markdown(f"**公司：** {pending.get('company') or '未填写'}")
            st.markdown(f"**城市：** {pending.get('city') or '未填写'}")
            st.markdown("**备注：**")
            st.text(pending.get("note", ""))
            st.markdown("**整理后的 JD：**")
            st.text_area(
                "本次准备保存的 JD",
                value=pending.get("jd_text", ""),
                height=180
            )

        st.markdown("### 请选择处理方式")

        duplicate_options = {
            f"{item.get('id')}｜{item.get('job_name')}｜{item.get('company') or '未填写公司'}｜{item.get('reason')}": item.get("id")
            for item in duplicates
        }

        selected_duplicate_label = st.selectbox(
            "选择要覆盖 / 替换的已有岗位",
            list(duplicate_options.keys())
        )

        selected_duplicate_id = duplicate_options[selected_duplicate_label]

        c1, c2, c3 = st.columns(3)

        with c1:
            if st.button("覆盖选中的已有岗位", type="primary", use_container_width=True):
                pending = st.session_state.pending_import_job

                replace_job_info(
                    job_id=selected_duplicate_id,
                    job_name=pending.get("job_name", ""),
                    company=pending.get("company", ""),
                    city=pending.get("city", ""),
                    source=pending.get("source", ""),
                    job_url=pending.get("job_url", ""),
                    jd_text=pending.get("jd_text", ""),
                    note=pending.get("note", "")
                )

                st.session_state.last_imported_job_id = selected_duplicate_id
                st.session_state.last_imported_job_name = pending.get("job_name", "")

                st.session_state.pending_import_job = None
                st.session_state.duplicate_candidates = []
                st.session_state.import_feedback = f"已覆盖已有岗位，岗位 ID：{selected_duplicate_id}。旧匹配度已清空，可重新分析。"

                st.rerun()

        with c2:
            if st.button("仍然新增到岗位池", use_container_width=True):
                job_id = save_imported_job(st.session_state.pending_import_job)

                st.session_state.pending_import_job = None
                st.session_state.duplicate_candidates = []
                st.session_state.import_feedback = f"已仍然新增该岗位，岗位 ID：{job_id}。"

                st.rerun()

        with c3:
            if st.button("放弃本次导入", use_container_width=True):
                st.session_state.pending_import_job = None
                st.session_state.duplicate_candidates = []
                st.session_state.import_feedback = "已放弃本次导入。"

                st.rerun()

    if st.session_state.last_imported_job_id:
        st.success(
            f"最近保存岗位：{st.session_state.last_imported_job_name}，可在下方选择该岗位进行分析。"
        )

        if st.session_state.resume_text:
            if st.button("立即分析最近保存的岗位", use_container_width=True):
                job = get_job_by_id(st.session_state.last_imported_job_id)

                if job:
                    with st.spinner(f"正在分析岗位：{job.get('job_name')}"):
                        result = analyze_job_and_save(st.session_state.resume_text, job)

                    st.session_state.single_result = {
                        "job": job,
                        "result": result
                    }
                    st.session_state.multi_results = []
                    st.success("分析完成，结果已保存。")
        else:
            st.info("上传简历后，可以直接分析最近保存的岗位。")

    with st.expander("手动新增岗位到岗位池", expanded=False):
        with st.form("manual_add_job_form"):
            c1, c2 = st.columns(2)

            with c1:
                job_name = st.text_input("岗位名称 *")
                company = st.text_input("公司名称")
                city = st.text_input("城市")

            with c2:
                source = st.text_input("岗位来源", placeholder="例如：BOSS直聘 / 实习僧 / 公司官网")
                job_url = st.text_input("岗位链接")
                status = st.selectbox("当前状态", STATUS_OPTIONS, index=0)

            jd_text = st.text_area("岗位 JD *", height=240)
            note = st.text_area("备注", height=120)

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
        st.warning("请先在上方上传或选择当前使用的简历。")
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
        st.caption(f"当前使用简历：{st.session_state.get('resume_file_name', '')}")
        render_single_result(result, job_id=job.get("id"))

    elif st.session_state.multi_results:
        sorted_results = sorted(
            st.session_state.multi_results,
            key=lambda x: x.get("score", 0),
            reverse=True
        )

        st.markdown("### 多岗位匹配度对比结果")
        st.caption(f"当前使用简历：{st.session_state.get('resume_file_name', '')}")

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


sync_active_resume_from_db()


st.title("🎯 JobMatch AI：AI求职工作台")

st.markdown(
    """
    这是一个面向 **AI 应用开发实习求职** 的一页式求职工作台。

    你可以在同一个页面完成：
    - 上传和管理多份历史简历
    - 选择当前使用简历
    - AI 智能导入岗位 JD
    - 自动查重并保存岗位
    - 判断投递优先级
    - 选择岗位分析
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
        **当前版本：v5-jd-intake**

        产品逻辑：
        1. 管理历史简历  
        2. 选择当前简历  
        3. 粘贴 JD  
        4. AI 解析岗位  
        5. 自动查重保存  
        6. 选择岗位分析  
        7. 更新状态与导出报告  
        """
    )

    if st.session_state.resume_text:
        st.info(f"当前简历：{st.session_state.get('resume_file_name', '')}")
    else:
        st.warning("当前未选择简历")

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
    - PDF / Word 简历解析能力
    - 历史简历管理能力
    - 当前简历选择能力
    - 大语言模型 API 调用能力
    - Prompt Engineering 能力
    - Streamlit 一页式工作台开发能力
    - JD 智能导入与结构化抽取能力
    - 岗位自动查重能力
    - 投递优先级判断能力
    - SQLite 数据持久化能力
    - 岗位信息 CRUD 能力
    - 求职状态管理能力
    - AI 分析历史保存能力
    - Markdown / CSV 报告导出能力
    - 面向真实求职场景的 AI 产品设计能力
    """
)