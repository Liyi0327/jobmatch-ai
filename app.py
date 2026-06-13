import re
from difflib import SequenceMatcher
from textwrap import dedent

import pandas as pd
import streamlit as st

from resume_parser import extract_text_from_resume
from llm_client import analyze_resume_jd, extract_job_from_jd

from db import (
    init_db,
    init_resume_db,
    init_interview_db,
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
    search_jobs,
    add_interview_record,
    get_interviews_by_job,
    get_latest_interview_by_job,
    get_all_interviews,
    delete_interview_record,
    clear_demo_data
)


# =========================
# 基础配置
# =========================

st.set_page_config(
    page_title="JobMatch AI",
    page_icon="🎯",
    layout="wide"
)

init_db()
init_resume_db()
init_interview_db()


STATUS_OPTIONS = [
    "待分析",
    "待投递",
    "已投递",
    "笔试",
    "面试",
    "已拒绝",
    "Offer"
]


DEFAULT_STATE = {
    "resume_id": None,
    "resume_text": "",
    "resume_file_name": "",
    "resume_char_count": 0,
    "resume_uploader_version": 0,
    "last_uploaded_resume_key": "",
    "show_resume_history": False,
    "current_job_id": None,
    "current_job_name": "",
    "single_result": None,
    "multi_results": [],
    "pending_import_job": None,
    "duplicate_candidates": [],
    "last_imported_job_id": None,
    "last_imported_job_name": "",
    "import_feedback": "",
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================
# 简历同步
# =========================

def sync_active_resume_from_db():
    """
    页面刷新时，从数据库同步当前使用简历。
    """
    if st.session_state.resume_text:
        return

    active_resume = get_active_resume()

    if active_resume:
        st.session_state.resume_id = active_resume.get("id")
        st.session_state.resume_text = active_resume.get("resume_text", "")
        st.session_state.resume_file_name = active_resume.get("file_name", "")
        st.session_state.resume_char_count = active_resume.get("char_count", 0)


def set_resume_to_session(resume: dict):
    """
    将选中的历史简历设置到当前会话。
    """
    st.session_state.resume_id = resume.get("id")
    st.session_state.resume_text = resume.get("resume_text", "")
    st.session_state.resume_file_name = resume.get("file_name", "")
    st.session_state.resume_char_count = resume.get("char_count", 0)
    st.session_state.resume_uploader_version += 1
    st.session_state.last_uploaded_resume_key = ""


def clear_current_resume_from_session():
    """
    清空当前会话中的简历。
    """
    st.session_state.resume_id = None
    st.session_state.resume_text = ""
    st.session_state.resume_file_name = ""
    st.session_state.resume_char_count = 0
    st.session_state.resume_uploader_version += 1
    st.session_state.last_uploaded_resume_key = ""


# =========================
# 通用工具
# =========================

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

def build_demo_resume_text():
    return """
李明
AI 应用开发实习生｜示例简历

教育背景：
某某大学｜计算机科学与技术｜本科
主修课程：机器学习、深度学习、自然语言处理、数据库系统、Python 程序设计

技能能力：
- 熟悉 Python 编程，能够使用 Streamlit、FastAPI 构建基础 Web 应用
- 了解大模型 API 调用流程，熟悉 Prompt 设计和结构化输出
- 了解 RAG 基本流程，包括文档解析、向量检索、问答生成
- 熟悉 PyTorch 基础，理解神经网络训练流程
- 熟悉 SQLite、Pandas 等常用数据处理工具

项目经历：
JobMatch AI｜AI 求职岗位匹配系统
- 使用 Streamlit 构建求职工作台，实现简历上传、岗位 JD 解析、岗位匹配分析和求职进度管理
- 调用大模型 API 生成岗位匹配度、简历优化建议和模拟面试问题
- 使用 SQLite 存储简历、岗位、分析记录和求职状态
- 支持岗位库、求职看板、投递流程管理等功能

RAG 智能问答 Demo
- 实现文档上传、文本切分、向量检索和答案生成流程
- 使用 Prompt 模板约束回答格式，提升问答稳定性

求职方向：
AI 应用开发实习生、大模型应用开发实习生、RAG 应用开发实习生
"""


def build_demo_analysis_result(score, summary, position_keywords):
    return {
        "match_score": score,
        "summary": summary,
        "position_keywords": position_keywords,
        "resume_keywords": [
            "Python",
            "Streamlit",
            "SQLite",
            "大模型 API",
            "Prompt 设计",
            "RAG",
            "PyTorch"
        ],
        "strengths": [
            "具备 Python 应用开发基础，能够完成从页面到数据存储的完整功能闭环。",
            "有大模型 API 调用和 Prompt 设计经验，适合 AI 应用开发类岗位。",
            "项目中包含简历解析、岗位匹配、结构化分析和求职流程管理，业务场景完整。"
        ],
        "weaknesses": [
            "工程部署经验仍需加强，可以补充 FastAPI、Docker 或云部署相关实践。",
            "如果目标岗位偏算法，需要进一步加强深度学习模型训练和评估经验。",
            "RAG 项目可以继续补充向量数据库、召回评估和多轮问答能力。"
        ],
        "resume_suggestions": [
            {
                "target": "项目经历",
                "suggestion": "突出项目的完整业务闭环，而不仅是调用大模型。",
                "resume_expression": "独立完成 AI 求职岗位匹配系统，覆盖简历解析、JD 结构化提取、岗位匹配分析、简历优化建议生成和求职进度管理。"
            },
            {
                "target": "技术栈",
                "suggestion": "将 Streamlit、SQLite、大模型 API、Prompt 设计等关键词集中呈现。",
                "resume_expression": "熟悉 Python、Streamlit、SQLite 和大模型 API 调用，能够构建轻量级 AI 应用原型。"
            }
        ],
        "project_suggestion": {
            "name": "RAG 岗位知识库问答系统",
            "reason": "该项目可以进一步增强候选人在大模型应用开发方向的匹配度。",
            "features": [
                "岗位 JD 文档上传与解析",
                "岗位知识库构建",
                "向量检索",
                "基于大模型的问答生成"
            ],
            "tech_stack": [
                "Python",
                "Streamlit",
                "Embedding",
                "Vector DB",
                "LLM API"
            ],
            "resume_expression": "构建 RAG 岗位知识库问答系统，实现文档解析、向量检索和基于大模型的答案生成。"
        },
        "interview_questions": [
            {
                "type": "项目问题",
                "question": "你这个 JobMatch AI 项目中，岗位 JD 是如何被结构化解析的？"
            },
            {
                "type": "技术问题",
                "question": "你如何保证大模型返回的是稳定的 JSON 格式？"
            },
            {
                "type": "产品问题",
                "question": "这个系统相比普通简历优化工具，核心差异在哪里？"
            }
        ],
        "self_intro_advice": "建议围绕“数学与编程基础 + AI 应用项目 + 求职场景理解”展开，突出你能把大模型能力落到具体应用场景中。"
    }


def load_demo_data():
    """
    一键加载作品集演示数据。
    使用虚拟简历、虚拟岗位和虚拟分析结果，不包含任何真实个人信息。
    """
    clear_demo_data()

    demo_resume_text = build_demo_resume_text()

    resume_id = add_resume(
        file_name="[演示] 李明_AI应用开发实习_示例简历.docx",
        file_type="docx",
        resume_text=demo_resume_text,
        set_active=True
    )

    st.session_state.resume_id = resume_id
    st.session_state.resume_text = demo_resume_text
    st.session_state.resume_file_name = "[演示] 李明_AI应用开发实习_示例简历.docx"
    st.session_state.resume_char_count = len(demo_resume_text)
    st.session_state.resume_uploader_version += 1
    st.session_state.last_uploaded_resume_key = ""

    demo_jobs = [
        {
            "job_name": "[演示] AI应用开发实习生",
            "company": "云舟科技",
            "city": "杭州",
            "status": "待投递",
            "score": 82,
            "level": "较高",
            "summary": "候选人与岗位整体匹配度较高，具备 Python、Streamlit、大模型 API 调用和完整 AI 应用项目经验，适合优先投递。",
            "keywords": ["Python", "Streamlit", "LLM API", "Prompt", "AI 应用开发"],
            "jd_text": """
岗位名称：AI应用开发实习生
公司名称：云舟科技
城市：杭州

岗位职责：
- 参与 AI 应用原型开发
- 调用大模型 API 完成文本分析、问答和内容生成
- 使用 Streamlit 或 FastAPI 搭建内部工具
- 协助优化 Prompt 和结构化输出效果

岗位要求：
- 熟悉 Python
- 了解大模型 API 调用
- 有 AI 应用项目经验
- 了解基本数据库使用
"""
        },
        {
            "job_name": "[演示] RAG应用开发实习生",
            "company": "星河智能",
            "city": "上海",
            "status": "已投递",
            "score": 76,
            "level": "中等",
            "summary": "候选人具备 RAG 基础理解和大模型应用经验，但向量数据库和检索评估经验还可以进一步补充。",
            "keywords": ["RAG", "Embedding", "向量检索", "Python", "LLM"],
            "jd_text": """
岗位名称：RAG应用开发实习生
公司名称：星河智能
城市：上海

岗位职责：
- 参与企业知识库问答系统开发
- 负责文档解析、文本切分、向量检索和答案生成
- 优化 Prompt，提高问答准确率

岗位要求：
- 熟悉 Python
- 了解 RAG 基本流程
- 了解 Embedding 和向量数据库
- 有大模型应用项目经验
"""
        },
        {
            "job_name": "[演示] 大模型产品实习生",
            "company": "青禾AI",
            "city": "北京",
            "status": "面试",
            "score": 71,
            "level": "中等",
            "summary": "候选人具备 AI 应用项目经验和一定产品理解，但需要进一步加强产品分析、用户需求拆解和指标设计表达。",
            "keywords": ["大模型产品", "需求分析", "AI 工具", "Prompt", "用户场景"],
            "jd_text": """
岗位名称：大模型产品实习生
公司名称：青禾AI
城市：北京

岗位职责：
- 参与大模型产品需求分析
- 协助设计 AI 工具功能流程
- 整理用户反馈并推动产品优化
- 与研发协作完成 AI 功能落地

岗位要求：
- 理解大模型应用场景
- 有 AI 工具或产品项目经验
- 具备较好的沟通和文档能力
"""
        }
    ]

    first_job_id = None
    first_job_name = ""

    for index, demo_job in enumerate(demo_jobs):
        job_id = add_job(
            job_name=demo_job["job_name"],
            company=demo_job["company"],
            city=demo_job["city"],
            source="演示数据",
            job_url="",
            jd_text=demo_job["jd_text"],
            status=demo_job["status"],
            note="[DEMO_DATA] 作品集演示岗位"
        )

        update_job_match_result(
            job_id=job_id,
            match_score=demo_job["score"],
            match_level=demo_job["level"]
        )

        demo_result = build_demo_analysis_result(
            score=demo_job["score"],
            summary=demo_job["summary"],
            position_keywords=demo_job["keywords"]
        )

        save_analysis_result(
            job_id=job_id,
            job_name=demo_job["job_name"],
            company=demo_job["company"],
            match_score=demo_job["score"],
            match_level=demo_job["level"],
            summary=demo_job["summary"],
            result=demo_result
        )

        if index == 0:
            first_job_id = job_id
            first_job_name = demo_job["job_name"]

    st.session_state.current_job_id = first_job_id
    st.session_state.current_job_name = first_job_name
    st.session_state.single_result = None
    st.session_state.multi_results = []
    st.session_state.import_feedback = "演示数据已加载。现在可以在工作台、岗位库和求职看板中查看完整演示效果。"


def reset_demo_data_in_app():
    """
    清空演示数据，并重置当前页面状态。
    """
    clear_demo_data()

    st.session_state.resume_id = None
    st.session_state.resume_text = ""
    st.session_state.resume_file_name = ""
    st.session_state.resume_char_count = 0
    st.session_state.resume_uploader_version += 1
    st.session_state.last_uploaded_resume_key = ""

    st.session_state.current_job_id = None
    st.session_state.current_job_name = ""
    st.session_state.single_result = None
    st.session_state.multi_results = []

    st.session_state.import_feedback = "演示数据已清空。"

def render_demo_tools():
    with st.expander("演示模式", expanded=False):
        st.caption("用于作品集展示。加载虚拟简历、虚拟岗位和虚拟分析结果，不包含真实个人信息。")

        if st.button("加载演示数据", use_container_width=True):
            load_demo_data()
            st.rerun()

        if st.button("清空演示数据", use_container_width=True):
            reset_demo_data_in_app()
            st.rerun()


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
    """
    检查岗位池中是否已有疑似重复岗位。
    """
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


def parse_jd_to_payload(raw_jd: str):
    """
    使用大模型解析 JD，并转换为岗位入库 payload。
    """
    parsed = extract_job_from_jd(raw_jd)

    if "raw_result" in parsed:
        return None, parsed

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
        "note": note.strip(),
        "priority": priority,
        "priority_reason": priority_reason,
    }

    return payload, parsed


def save_imported_job(payload: dict) -> int:
    """
    保存 AI 导入后的岗位。
    """
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
    st.session_state.current_job_id = job_id
    st.session_state.current_job_name = payload.get("job_name", "")

    return job_id


# =========================
# 分析报告工具
# =========================

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


def render_single_result(result: dict, job_id=None, context_key="default"):
    if "raw_result" in result:
        st.warning("模型没有返回标准 JSON，以下展示原始分析结果：")
        st.markdown(result["raw_result"])
        return

    score = get_score(result.get("match_score", 0))
    level = get_match_level(score)

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("综合匹配度", f"{score}/100")

    with c2:
        st.metric("匹配等级", level)

    with c3:
        st.metric("当前简历", st.session_state.get("resume_file_name", "未选择"))

    st.progress(score)

    st.markdown("### 总体结论")
    st.info(result.get("summary", "暂无总结"))

    report_md = generate_markdown_report(result)

    safe_job_id = job_id if job_id is not None else "no_job"

    st.download_button(
        label="下载岗位匹配分析报告",
        data=report_md,
        file_name="JobMatch_AI_岗位匹配分析报告.md",
        mime="text/markdown",
        use_container_width=True,
        key=f"download_report_{context_key}_{safe_job_id}"
    )

    if job_id is not None:
        new_status = st.selectbox(
            "更新该岗位状态",
            STATUS_OPTIONS,
            key=f"single_status_{context_key}_{safe_job_id}"
        )

        if st.button(
            "保存岗位状态",
            use_container_width=True,
            key=f"save_status_{context_key}_{safe_job_id}"
        ):
            update_job_status(job_id, new_status)
            st.success("岗位状态已更新。")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "关键词",
            "优势",
            "短板",
            "简历建议",
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
        render_text_list(result.get("strengths", []))

    with tab3:
        render_text_list(result.get("weaknesses", []))

    with tab4:
        render_resume_suggestions(result.get("resume_suggestions", []))

        project = result.get("project_suggestion", {})
        if project:
            st.markdown("#### 推荐补充项目")
            st.markdown(f"**项目名称：** {project.get('name', '')}")
            st.markdown(f"**推荐原因：** {project.get('reason', '')}")
            st.info(project.get("resume_expression", ""))

    with tab5:
        render_interview_questions(result.get("interview_questions", []))
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


# =========================
# 工作台：简历模块
# =========================

def render_resume_module():
    st.markdown("### 1. 我的简历")

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


# =========================
# 工作台：岗位模块
# =========================

def render_current_job_card():
    if st.session_state.current_job_id:
        job = get_job_by_id(st.session_state.current_job_id)

        if job:
            st.success(
                f"当前岗位：{job.get('job_name')} ｜ "
                f"{job.get('company') or '未填写公司'} ｜ "
                f"状态：{job.get('status')}"
            )
            return

    st.warning("当前未选择岗位。可以粘贴新 JD，或从岗位库中选择。")


def render_duplicate_resolution():
    if not st.session_state.pending_import_job:
        return

    st.warning("检测到疑似重复岗位，请选择处理方式。")

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
                "重复原因": item.get("reason")
            }
        )

    st.dataframe(pd.DataFrame(duplicate_table), use_container_width=True)

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
        if st.button("覆盖已有岗位", type="primary", use_container_width=True):
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

            st.session_state.current_job_id = selected_duplicate_id
            st.session_state.current_job_name = pending.get("job_name", "")
            st.session_state.last_imported_job_id = selected_duplicate_id
            st.session_state.last_imported_job_name = pending.get("job_name", "")
            st.session_state.pending_import_job = None
            st.session_state.duplicate_candidates = []
            st.session_state.import_feedback = f"已覆盖已有岗位：{pending.get('job_name')}"

            st.rerun()

    with c2:
        if st.button("仍然新增", use_container_width=True):
            job_id = save_imported_job(st.session_state.pending_import_job)

            st.session_state.pending_import_job = None
            st.session_state.duplicate_candidates = []
            st.session_state.import_feedback = f"已新增岗位，岗位 ID：{job_id}。"

            st.rerun()

    with c3:
        if st.button("放弃导入", use_container_width=True):
            st.session_state.pending_import_job = None
            st.session_state.duplicate_candidates = []
            st.session_state.import_feedback = "已放弃本次导入。"

            st.rerun()


def upload_job_block():
    raw_jd = st.text_area(
        "粘贴完整岗位 JD",
        height=240,
        key="workbench_raw_jd",
        placeholder="从招聘网站复制完整岗位描述，粘贴到这里。"
    )

    if st.button("AI 解析并保存岗位", type="primary", use_container_width=True):
        if not raw_jd.strip():
            st.warning("请先粘贴岗位 JD。")
        else:
            with st.spinner("正在解析岗位 JD，并检查是否重复..."):
                try:
                    payload, parsed = parse_jd_to_payload(raw_jd)

                    if payload is None:
                        st.warning("模型没有返回标准 JSON，以下展示原始结果：")
                        st.markdown(parsed.get("raw_result", ""))
                    else:
                        duplicates = find_duplicate_jobs(
                            job_name=payload["job_name"],
                            company=payload["company"],
                            jd_text=payload["jd_text"]
                        )

                        if duplicates:
                            st.session_state.pending_import_job = payload
                            st.session_state.duplicate_candidates = duplicates
                            st.rerun()
                        else:
                            job_id = save_imported_job(payload)
                            st.session_state.import_feedback = (
                                f"已保存岗位：{payload.get('job_name')} ｜ "
                                f"投递优先级：{payload.get('priority', '')} ｜ "
                                f"岗位 ID：{job_id}"
                            )
                            st.rerun()

                except Exception as e:
                    st.error(f"岗位 JD 解析失败：{e}")


def select_job_block(location_key: str):
    jobs = get_all_jobs()

    if not jobs:
        st.info("暂无岗位。可以先粘贴一个 JD。")
        return

    job_options = {
        f"{job.get('id')}｜{job.get('job_name')}｜{job.get('company') or '未填写公司'}｜{job.get('status')}": job.get("id")
        for job in jobs
    }

    selected_label = st.selectbox(
        "选择已有岗位",
        list(job_options.keys()),
        key=f"{location_key}_select_job"
    )

    selected_job_id = job_options[selected_label]

    if st.button("设为当前岗位", use_container_width=True, key=f"{location_key}_set_job"):
        job = get_job_by_id(selected_job_id)

        if job:
            st.session_state.current_job_id = job.get("id")
            st.session_state.current_job_name = job.get("job_name")
            st.success("已设为当前岗位。")
            st.rerun()


# =========================
# 工作台
# =========================

def render_workbench():
    st.subheader("工作台")
    st.caption("在这里完成求职者最常用的完整流程：选择简历、上传岗位、选择岗位、开始分析、查看结果。")

    if st.session_state.import_feedback:
        st.success(st.session_state.import_feedback)
        st.session_state.import_feedback = ""

    render_resume_module()

    st.divider()

    st.markdown("### 2. 岗位")
    render_current_job_card()

    job_tab1, job_tab2 = st.tabs(["粘贴新岗位 JD", "选择已有岗位"])

    with job_tab1:
        upload_job_block()

    with job_tab2:
        select_job_block("workbench")

    render_duplicate_resolution()

    st.divider()

    st.markdown("### 3. 开始分析")

    c1, c2 = st.columns(2)

    with c1:
        if st.session_state.resume_text:
            st.success(f"简历已选择：{st.session_state.resume_file_name}")
        else:
            st.warning("未选择简历")

    with c2:
        current_job = get_job_by_id(st.session_state.current_job_id) if st.session_state.current_job_id else None

        if current_job:
            st.success(f"岗位已选择：{current_job.get('job_name')}")
        else:
            st.warning("未选择岗位")

    if st.button("开始分析当前简历与当前岗位", type="primary", use_container_width=True):
        if not st.session_state.resume_text:
            st.warning("请先上传或选择当前简历。")
        elif not st.session_state.current_job_id:
            st.warning("请先上传或选择当前岗位。")
        else:
            job = get_job_by_id(st.session_state.current_job_id)

            if job:
                with st.spinner("正在分析岗位匹配度..."):
                    result = analyze_job_and_save(st.session_state.resume_text, job)

                st.session_state.single_result = {
                    "job": job,
                    "result": result
                }
                st.session_state.multi_results = []

                st.success("分析完成。")

    st.divider()

    st.markdown("### 4. 分析结果")

    if st.session_state.single_result:
        job = st.session_state.single_result["job"]
        result = st.session_state.single_result["result"]

        st.markdown(f"**分析岗位：** {job.get('job_name')}｜{job.get('company') or '未填写公司'}")
        st.caption(f"当前使用简历：{st.session_state.get('resume_file_name', '')}")

        render_single_result(
            result,
            job_id=job.get("id"),
            context_key=f"workbench_{job.get('id')}"
        )
    else:
        st.info("完成分析后，结果会显示在这里。")


# =========================
# 岗位库
# =========================

def render_interview_module(job):
    job_id = job.get("id")

    st.markdown("### 面试记录")

    st.caption("记录这个岗位的面试内容、反馈和结果，用于后续判断下一步应该做什么。")

    with st.expander("新增面试记录", expanded=False):
        c1, c2, c3 = st.columns(3)

        with c1:
            round_name = st.selectbox(
                "面试轮次",
                ["一面", "二面", "三面", "HR面", "终面", "其他"],
                key=f"interview_round_{job_id}"
            )

        with c2:
            interview_type = st.selectbox(
                "面试类型",
                ["技术面", "业务面", "HR面", "综合面", "其他"],
                key=f"interview_type_{job_id}"
            )

        with c3:
            result = st.selectbox(
                "面试结果",
                ["待反馈", "通过", "进入下一轮", "未通过", "Offer"],
                key=f"interview_result_{job_id}"
            )

        interview_time = st.text_input(
            "面试时间",
            placeholder="例如：2026-06-15 14:00",
            key=f"interview_time_{job_id}"
        )

        interview_content = st.text_area(
            "面试内容",
            placeholder="记录面试官问了什么，例如：自我介绍、项目细节、PyTorch、RAG、优化算法等。",
            height=120,
            key=f"interview_content_{job_id}"
        )

        feedback = st.text_area(
            "面试反馈 / 自我复盘",
            placeholder="记录面试官反馈，或者你自己的复盘：哪里答得好，哪里没有答好。",
            height=120,
            key=f"interview_feedback_{job_id}"
        )

        next_step = st.text_area(
            "下一步计划",
            placeholder="例如：准备二面、补充项目表达、复习深度学习基础、等待 HR 反馈。",
            height=100,
            key=f"interview_next_step_{job_id}"
        )

        note = st.text_area(
            "备注",
            placeholder="其他补充信息。",
            height=80,
            key=f"interview_note_{job_id}"
        )

        if st.button(
            "保存面试记录",
            type="primary",
            use_container_width=True,
            key=f"save_interview_{job_id}"
        ):
            add_interview_record(
                job_id=job_id,
                round_name=round_name,
                interview_time=interview_time,
                interview_type=interview_type,
                interview_content=interview_content,
                feedback=feedback,
                result=result,
                next_step=next_step,
                note=note
            )

            if result in ["待反馈", "通过", "进入下一轮"]:
                update_job_status(job_id, "面试")

            elif result == "Offer":
                update_job_status(job_id, "Offer")

            elif result == "未通过":
                update_job_status(job_id, "已拒绝")

            st.success("面试记录已保存。")
            st.rerun()

    interviews = get_interviews_by_job(job_id)

    if not interviews:
        st.info("暂无面试记录。")
        return

    st.markdown("#### 历史面试记录")

    for interview in interviews:
        interview_id = interview.get("id")

        with st.expander(
            f"{interview.get('round_name', '面试')}｜"
            f"{interview.get('interview_type', '')}｜"
            f"{interview.get('result', '')}｜"
            f"{interview.get('created_at', '')}"
        ):
            st.markdown(f"**面试时间：** {interview.get('interview_time') or '未填写'}")
            st.markdown(f"**面试类型：** {interview.get('interview_type') or '未填写'}")
            st.markdown(f"**面试结果：** {interview.get('result') or '未填写'}")

            st.markdown("**面试内容：**")
            st.write(interview.get("interview_content") or "未填写")

            st.markdown("**面试反馈 / 自我复盘：**")
            st.write(interview.get("feedback") or "未填写")

            st.markdown("**下一步计划：**")
            st.write(interview.get("next_step") or "未填写")

            st.markdown("**备注：**")
            st.write(interview.get("note") or "未填写")

            if st.button(
                "删除这条面试记录",
                key=f"delete_interview_{interview_id}",
                use_container_width=True
            ):
                delete_interview_record(interview_id)
                st.success("面试记录已删除。")
                st.rerun()


def render_job_library():
    st.subheader("岗位库")
    st.caption("所有在工作台上传或保存过的岗位都会出现在这里。")

    jobs = get_all_jobs()

    if not jobs:
        st.info("暂无岗位。请先在工作台粘贴 JD 并保存。")
        return

    c1, c2 = st.columns(2)

    with c1:
        keyword = st.text_input("搜索岗位", placeholder="搜索岗位、公司、城市或 JD 内容")

    with c2:
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

    st.markdown("### 岗位操作")

    job_options = {
        f"{job.get('id')}｜{job.get('job_name')}｜{job.get('company') or '未填写公司'}": job.get("id")
        for job in jobs
    }

    selected_label = st.selectbox("选择一个岗位", list(job_options.keys()))
    selected_job_id = job_options[selected_label]
    job = get_job_by_id(selected_job_id)

    if not job:
        return

    st.markdown(f"**岗位名称：** {job.get('job_name')}")
    st.markdown(f"**公司：** {job.get('company') or '未填写'}")

    new_status = st.selectbox(
        "更新状态",
        STATUS_OPTIONS,
        index=STATUS_OPTIONS.index(job.get("status")) if job.get("status") in STATUS_OPTIONS else 0
    )

    new_note = st.text_area("备注", value=job.get("note") or "", height=100)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        if st.button("设为当前岗位", use_container_width=True):
            st.session_state.current_job_id = job.get("id")
            st.session_state.current_job_name = job.get("job_name")
            st.success("已设为当前岗位。")

    with c2:
        if st.button("保存状态与备注", use_container_width=True):
            update_job_status(job["id"], new_status)
            update_job_note(job["id"], new_note)
            st.success("状态与备注已保存。")

    with c3:
        if st.button("分析该岗位", use_container_width=True):
            if not st.session_state.resume_text:
                st.warning("请先选择当前使用简历。")
            else:
                with st.spinner("正在分析岗位匹配度..."):
                    result = analyze_job_and_save(st.session_state.resume_text, job)

                st.session_state.single_result = {
                    "job": job,
                    "result": result
                }
                st.session_state.current_job_id = job.get("id")
                st.session_state.current_job_name = job.get("job_name")
                st.success("分析完成。请回到工作台查看结果。")

    with c4:
        if st.button("删除岗位", use_container_width=True):
            delete_job(job["id"])

            if st.session_state.current_job_id == job["id"]:
                st.session_state.current_job_id = None
                st.session_state.current_job_name = ""

            st.success("岗位已删除。")
            st.rerun()

    with st.expander("查看岗位 JD"):
        st.write(job.get("jd_text", ""))

    st.divider()
    render_interview_module(job)


# =========================
# 求职看板
# =========================

def render_dashboard():
    st.subheader("求职看板")
    st.caption("只保留最关键的求职推进信息：流程走到哪一步、当前应该做什么。")

    jobs = get_all_jobs()

    if not jobs:
        st.info("暂无岗位数据。请先在工作台保存岗位。")
        return

    def get_status(job):
        return job.get("status") or "待分析"

    def get_score_text(job):
        score = job.get("match_score")
        if score is None:
            return "未分析"
        return f"{score} 分"

    def get_next_action(job):
        status = get_status(job)
        score = job.get("match_score")

        latest_interview = get_latest_interview_by_job(job.get("id"))

        if latest_interview:
            result = latest_interview.get("result") or "待反馈"
            feedback = latest_interview.get("feedback") or ""
            next_step = latest_interview.get("next_step") or ""

            if result == "待反馈":
                if feedback.strip():
                    return "已有面试复盘，建议整理重点问题，并准备 3～5 天后跟进反馈。"
                return "面试后暂无反馈，建议先补充面试内容和自我复盘，再准备跟进。"

            if result in ["通过", "进入下一轮"]:
                if next_step.strip():
                    return next_step
                return "面试已通过，建议准备下一轮面试材料和项目表达。"

            if result == "未通过":
                if feedback.strip():
                    return "根据面试反馈复盘问题，提炼简历和项目表达中的短板。"
                return "面试未通过，建议补充失败原因和面试反馈，用于后续复盘。"

            if result == "Offer":
                return "已拿到 Offer，建议比较薪资、城市、成长性、稳定性和入职时间。"

        if status == "待分析":
            return "先完成岗位匹配分析，判断这个岗位是否值得继续投递。"

        if status == "待投递":
            if isinstance(score, int) and score >= 75:
                return "优先修改简历并投递，这个岗位值得推进。"
            return "先根据分析结果补充简历关键词，再决定是否投递。"

        if status == "已投递":
            return "记录投递渠道，准备 3～5 天后跟进，同时准备岗位相关项目表达。"

        if status == "笔试":
            return "集中准备笔试内容，复习算法、深度学习基础和岗位关键词。"

        if status == "面试":
            return "补充面试内容、反馈和结果，这样系统才能给出更准确的下一步建议。"

        if status == "Offer":
            return "比较城市、薪资、成长性、稳定性和入职时间，准备做选择。"

        if status == "已拒绝":
            return "复盘失败原因，保留经验，不再作为当前重点。"

        return "继续跟进。"

    status_count = {status: 0 for status in STATUS_OPTIONS}

    for job in jobs:
        status = get_status(job)

        if status not in status_count:
            status_count[status] = 0

        status_count[status] += 1

    total_jobs = len(jobs)
    rejected_jobs = status_count.get("已拒绝", 0)
    valid_jobs = total_jobs - rejected_jobs
    waiting_jobs = status_count.get("待分析", 0) + status_count.get("待投递", 0)
    process_jobs_count = (
        status_count.get("已投递", 0)
        + status_count.get("笔试", 0)
        + status_count.get("面试", 0)
    )
    offer_count = status_count.get("Offer", 0)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("岗位总数", total_jobs)

    with c2:
        st.metric("有效跟进", valid_jobs)

    with c3:
        st.metric("待处理", waiting_jobs)

    with c4:
        st.metric("Offer", offer_count)

    st.divider()

    st.markdown("### 已进入投递流程的岗位")

    process_statuses = ["已投递", "笔试", "面试", "Offer"]

    in_process_jobs = [
        job for job in jobs
        if get_status(job) in process_statuses
    ]

    if not in_process_jobs:
        st.info("暂无进入投递流程的岗位。投递后，这里会显示岗位推进进度。")
    else:
        status_priority = {
            "面试": 4,
            "笔试": 3,
            "已投递": 2,
            "Offer": 1
        }

        in_process_jobs = sorted(
            in_process_jobs,
            key=lambda job: status_priority.get(get_status(job), 0),
            reverse=True
        )

        for job in in_process_jobs[:8]:
            status = get_status(job)
            current_index = process_statuses.index(status)

            job_name = job.get("job_name") or "未命名岗位"
            company = job.get("company") or "未填写公司"
            city = job.get("city") or "未填写城市"

            st.markdown(f"#### {job_name}")
            st.caption(
                f"{company} ｜ {city} ｜ 当前状态：{status} ｜ 匹配度：{get_score_text(job)}"
            )

            flow_parts = []

            for index, stage in enumerate(process_statuses):
                if index < current_index:
                    flow_parts.append(f"✅ {stage}")
                elif index == current_index:
                    flow_parts.append(f"🔴 {stage}")
                else:
                    flow_parts.append(f"⚪ {stage}")

            st.markdown(" → ".join(flow_parts))

            progress_value = (current_index + 1) / len(process_statuses)
            st.progress(progress_value)

            st.info(f"下一步：{get_next_action(job)}")

            st.divider()

        if len(in_process_jobs) > 8:
            st.caption(
                f"还有 {len(in_process_jobs) - 8} 个已进入流程的岗位未展示，可在岗位库中查看完整列表。"
            )

    st.markdown("### 当前最该处理的岗位")

    pending_jobs = [
        job for job in jobs
        if get_status(job) in ["待分析", "待投递"]
    ]

    def pending_sort_key(job):
        status = get_status(job)
        score = job.get("match_score")

        status_weight = {
            "待投递": 2,
            "待分析": 1
        }.get(status, 0)

        score_value = score if isinstance(score, int) else 0

        return status_weight * 1000 + score_value

    pending_jobs = sorted(
        pending_jobs,
        key=pending_sort_key,
        reverse=True
    )

    if not pending_jobs:
        st.success("当前没有待分析或待投递的岗位。")
    else:
        for job in pending_jobs[:5]:
            job_name = job.get("job_name") or "未命名岗位"
            company = job.get("company") or "未填写公司"
            city = job.get("city") or "未填写城市"
            status = get_status(job)

            st.markdown(f"#### {job_name}")
            st.caption(
                f"{company} ｜ {city} ｜ 当前状态：{status} ｜ 匹配度：{get_score_text(job)}"
            )

            st.warning(f"建议：{get_next_action(job)}")

            st.divider()

        if len(pending_jobs) > 5:
            st.caption(
                f"还有 {len(pending_jobs) - 5} 个待处理岗位未展示，可在岗位库中查看完整列表。"
            )


# =========================
# 主程序
# =========================

sync_active_resume_from_db()

st.title("🎯 JobMatch AI")
st.caption("面向 AI 应用开发实习求职的一站式岗位匹配与求职管理工作台。")

with st.sidebar:
    st.header("当前状态")

    stats = get_dashboard_stats()

    st.metric("岗位数", stats.get("total_jobs", 0))
    st.metric("推进中", stats.get("applied_count", 0))
    st.metric("面试 / Offer", f"{stats.get('interview_count', 0)} / {stats.get('offer_count', 0)}")

    st.divider()

    st.markdown("**当前版本：v7-interview-tracking**")

    if st.session_state.resume_text:
        st.info(f"当前简历：{st.session_state.get('resume_file_name', '')}")
    else:
        st.warning("当前未选择简历")

    if st.session_state.current_job_id:
        job = get_job_by_id(st.session_state.current_job_id)
        if job:
            st.info(f"当前岗位：{job.get('job_name')}")
    else:
        st.warning("当前未选择岗位")

    st.warning("请勿在公开部署环境上传包含敏感隐私信息的简历。")

    render_demo_tools()

tab_workbench, tab_jobs, tab_dashboard = st.tabs(
    [
        "工作台",
        "岗位库",
        "求职看板"
    ]
)

with tab_workbench:
    render_workbench()

with tab_jobs:
    render_job_library()

with tab_dashboard:
    render_dashboard()