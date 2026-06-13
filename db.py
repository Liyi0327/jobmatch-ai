import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


DB_PATH = Path("jobmatch.db")


def get_connection():
    """
    获取 SQLite 数据库连接。
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    初始化数据库表。
    包括：
    1. jobs：岗位库
    2. analysis_results：AI 分析历史
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name TEXT NOT NULL,
            company TEXT,
            city TEXT,
            source TEXT,
            job_url TEXT,
            jd_text TEXT NOT NULL,
            status TEXT DEFAULT '待分析',
            note TEXT,
            match_score INTEGER,
            match_level TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            job_name TEXT NOT NULL,
            company TEXT,
            match_score INTEGER,
            match_level TEXT,
            summary TEXT,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
        """
    )

    conn.commit()
    conn.close()


def init_resume_db():
    """
    初始化历史简历表。
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            file_type TEXT,
            resume_text TEXT NOT NULL,
            char_count INTEGER,
            is_active INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


def add_resume(
    file_name: str,
    file_type: str,
    resume_text: str,
    set_active: bool = True
) -> int:
    """
    新增一份历史简历。
    如果 set_active=True，则同时把它设为当前使用的简历。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    char_count = len(resume_text)

    conn = get_connection()
    cursor = conn.cursor()

    if set_active:
        cursor.execute(
            """
            UPDATE resumes
            SET is_active = 0
            """
        )

    cursor.execute(
        """
        INSERT INTO resumes (
            file_name, file_type, resume_text, char_count,
            is_active, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file_name,
            file_type,
            resume_text,
            char_count,
            1 if set_active else 0,
            now,
            now
        )
    )

    conn.commit()
    resume_id = cursor.lastrowid
    conn.close()

    return resume_id


def get_all_resumes() -> List[Dict]:
    """
    获取所有历史简历。
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM resumes
        ORDER BY updated_at DESC
        """
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_resume_by_id(resume_id: int) -> Optional[Dict]:
    """
    根据 ID 获取一份简历。
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM resumes
        WHERE id = ?
        """,
        (resume_id,)
    )

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return dict(row)


def get_active_resume() -> Optional[Dict]:
    """
    获取当前正在使用的简历。
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM resumes
        WHERE is_active = 1
        ORDER BY updated_at DESC
        LIMIT 1
        """
    )

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return dict(row)


def set_active_resume(resume_id: int):
    """
    设置某份历史简历为当前使用简历。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE resumes
        SET is_active = 0
        """
    )

    cursor.execute(
        """
        UPDATE resumes
        SET is_active = 1, updated_at = ?
        WHERE id = ?
        """,
        (now, resume_id)
    )

    conn.commit()
    conn.close()


def clear_active_resume():
    """
    取消当前使用的简历，但不删除历史记录。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE resumes
        SET is_active = 0, updated_at = ?
        WHERE is_active = 1
        """,
        (now,)
    )

    conn.commit()
    conn.close()


def delete_resume(resume_id: int):
    """
    删除一份历史简历。
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM resumes
        WHERE id = ?
        """,
        (resume_id,)
    )

    conn.commit()
    conn.close()


def add_job(
    job_name: str,
    jd_text: str,
    company: str = "",
    city: str = "",
    source: str = "",
    job_url: str = "",
    status: str = "待分析",
    note: str = ""
) -> int:
    """
    新增岗位，返回岗位 ID。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO jobs (
            job_name, company, city, source, job_url,
            jd_text, status, note, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_name,
            company,
            city,
            source,
            job_url,
            jd_text,
            status,
            note,
            now,
            now
        )
    )

    conn.commit()
    job_id = cursor.lastrowid
    conn.close()

    return job_id


def get_all_jobs() -> List[Dict]:
    """
    查询全部岗位。
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM jobs
        ORDER BY updated_at DESC
        """
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_job_by_id(job_id: int) -> Optional[Dict]:
    """
    根据 ID 查询单个岗位。
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM jobs
        WHERE id = ?
        """,
        (job_id,)
    )

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return dict(row)


def update_job_status(job_id: int, status: str):
    """
    更新岗位状态。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE jobs
        SET status = ?, updated_at = ?
        WHERE id = ?
        """,
        (status, now, job_id)
    )

    conn.commit()
    conn.close()


def update_job_note(job_id: int, note: str):
    """
    更新岗位备注。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE jobs
        SET note = ?, updated_at = ?
        WHERE id = ?
        """,
        (note, now, job_id)
    )

    conn.commit()
    conn.close()


def update_job_match_result(job_id: int, match_score: int, match_level: str):
    """
    把最新匹配度写回岗位库。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE jobs
        SET match_score = ?, match_level = ?, updated_at = ?
        WHERE id = ?
        """,
        (match_score, match_level, now, job_id)
    )

    conn.commit()
    conn.close()


def replace_job_info(
    job_id: int,
    job_name: str,
    company: str,
    city: str,
    source: str,
    job_url: str,
    jd_text: str,
    note: str
):
    """
    用新的岗位信息覆盖已有岗位。

    注意：
    1. 保留原来的投递状态 status；
    2. 因为 JD 内容可能变化，所以清空旧的匹配度和匹配等级；
    3. 不删除分析历史，只更新岗位本身。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE jobs
        SET
            job_name = ?,
            company = ?,
            city = ?,
            source = ?,
            job_url = ?,
            jd_text = ?,
            note = ?,
            match_score = NULL,
            match_level = NULL,
            updated_at = ?
        WHERE id = ?
        """,
        (
            job_name,
            company,
            city,
            source,
            job_url,
            jd_text,
            note,
            now,
            job_id
        )
    )

    conn.commit()
    conn.close()


def delete_job(job_id: int):
    """
    删除岗位，同时删除相关分析历史。
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM analysis_results
        WHERE job_id = ?
        """,
        (job_id,)
    )

    cursor.execute(
        """
        DELETE FROM jobs
        WHERE id = ?
        """,
        (job_id,)
    )

    conn.commit()
    conn.close()


def save_analysis_result(
    job_id: Optional[int],
    job_name: str,
    company: str,
    match_score: int,
    match_level: str,
    summary: str,
    result: Dict
) -> int:
    """
    保存 AI 分析结果。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO analysis_results (
            job_id, job_name, company, match_score,
            match_level, summary, result_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            job_name,
            company,
            match_score,
            match_level,
            summary,
            json.dumps(result, ensure_ascii=False),
            now
        )
    )

    conn.commit()
    analysis_id = cursor.lastrowid
    conn.close()

    return analysis_id


def get_analysis_history() -> List[Dict]:
    """
    获取所有分析历史。
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM analysis_results
        ORDER BY created_at DESC
        """
    )

    rows = cursor.fetchall()
    conn.close()

    history = []

    for row in rows:
        item = dict(row)
        try:
            item["result"] = json.loads(item.get("result_json", "{}"))
        except json.JSONDecodeError:
            item["result"] = {}
        history.append(item)

    return history


def get_dashboard_stats() -> Dict:
    """
    获取求职看板统计数据。
    """
    jobs = get_all_jobs()

    total_jobs = len(jobs)
    applied_count = sum(1 for job in jobs if job.get("status") in ["已投递", "笔试", "面试", "Offer"])
    interview_count = sum(1 for job in jobs if job.get("status") in ["面试", "Offer"])
    offer_count = sum(1 for job in jobs if job.get("status") == "Offer")

    scored_jobs = [
        job for job in jobs
        if job.get("match_score") is not None
    ]

    if scored_jobs:
        avg_score = round(
            sum(job.get("match_score", 0) for job in scored_jobs) / len(scored_jobs),
            1
        )
    else:
        avg_score = 0

    return {
        "total_jobs": total_jobs,
        "applied_count": applied_count,
        "interview_count": interview_count,
        "offer_count": offer_count,
        "avg_score": avg_score
    }


def search_jobs(keyword: str = "", status: str = "") -> List[Dict]:
    """
    根据关键词和状态筛选岗位。
    """
    jobs = get_all_jobs()

    if keyword:
        keyword = keyword.lower()
        jobs = [
            job for job in jobs
            if keyword in (job.get("job_name") or "").lower()
            or keyword in (job.get("company") or "").lower()
            or keyword in (job.get("city") or "").lower()
            or keyword in (job.get("jd_text") or "").lower()
        ]

    if status and status != "全部":
        jobs = [
            job for job in jobs
            if job.get("status") == status
        ]

    return jobs