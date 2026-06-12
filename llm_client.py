import os
from dotenv import load_dotenv
from openai import OpenAI
from prompt_templates import RESUME_JD_ANALYSIS_PROMPT


load_dotenv()


def get_client() -> OpenAI:
    """
    创建 OpenAI 客户端。

    默认读取：
    - OPENAI_API_KEY
    - OPENAI_BASE_URL，可选

    如果使用 OpenAI 官方 API，可以不设置 OPENAI_BASE_URL。
    如果使用 DeepSeek、通义千问等兼容接口，需要设置对应的 base_url。
    """
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")

    if not api_key:
        raise ValueError("未检测到 OPENAI_API_KEY，请在 .env 文件中配置。")

    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)

    return OpenAI(api_key=api_key)


def analyze_resume_jd(resume_text: str, jd_text: str) -> str:
    """
    调用大语言模型，分析简历与岗位 JD 的匹配情况。
    """
    client = get_client()

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    prompt = RESUME_JD_ANALYSIS_PROMPT.format(
        resume_text=resume_text[:8000],
        jd_text=jd_text[:6000]
    )

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": "你是一名严谨、真实、具体的 AI 应用开发岗位求职辅导专家。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.4
    )

    return response.choices[0].message.content