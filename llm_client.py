import os
import json
import re
from dotenv import load_dotenv
from openai import OpenAI
from prompt_templates import RESUME_JD_ANALYSIS_PROMPT


load_dotenv()


def get_client() -> OpenAI:
    """
    创建 DeepSeek / OpenAI 兼容客户端。
    """
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")

    if not api_key:
        raise ValueError("未检测到 OPENAI_API_KEY，请检查 .env 文件。")

    if not base_url:
        raise ValueError("未检测到 OPENAI_BASE_URL。使用 DeepSeek 时请设置为 https://api.deepseek.com")

    return OpenAI(
        api_key=api_key,
        base_url=base_url
    )


def extract_json_from_text(text: str) -> dict:
    """
    尽量从模型输出中解析 JSON。
    即使模型误加了 ```json，也能尽量处理。
    """
    if not text:
        return {"raw_result": ""}

    cleaned = text.strip()

    cleaned = cleaned.replace("```json", "")
    cleaned = cleaned.replace("```", "")
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        json_text = match.group(0)
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            pass

    return {
        "raw_result": text
    }


def analyze_resume_jd(resume_text: str, jd_text: str) -> dict:
    """
    调用 DeepSeek API，分析简历与岗位 JD 的匹配情况。
    返回结构化 dict。
    """
    client = get_client()

    model_name = os.getenv("OPENAI_MODEL", "deepseek-chat")

    prompt = (
        RESUME_JD_ANALYSIS_PROMPT
        .replace("{resume_text}", resume_text[:8000])
        .replace("{jd_text}", jd_text[:6000])
    )

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": "你是一名严谨、真实、具体的 AI 应用开发岗位求职辅导专家。你必须严格按照用户要求输出 JSON。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3
    )

    content = response.choices[0].message.content
    return extract_json_from_text(content)