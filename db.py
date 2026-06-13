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