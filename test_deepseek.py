import os
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

response = client.chat.completions.create(
    model=os.getenv("OPENAI_MODEL", "deepseek-chat"),
    messages=[
        {"role": "system", "content": "你是一个中文助手。"},
        {"role": "user", "content": "请用一句话介绍你自己。"}
    ],
    temperature=0.4
)

print(response.choices[0].message.content)