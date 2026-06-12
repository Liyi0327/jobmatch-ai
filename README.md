# JobMatch AI：AI应用开发实习岗位匹配助手

## 1. 项目简介

JobMatch AI 是一个面向 AI 应用开发实习求职场景的智能分析工具。

用户可以上传自己的 PDF 简历，并粘贴目标岗位 JD。系统会自动解析简历内容，结合岗位要求生成岗位匹配分析、候选人优势、能力短板、简历优化建议和模拟面试问题，帮助求职者更高效地理解岗位要求并进行针对性准备。

本项目主要展示了从文档解析、大语言模型 API 调用、Prompt Engineering 到 Streamlit 前端展示的完整 AI 应用开发流程。

---

## 2. 项目背景

在实习求职过程中，求职者往往需要反复阅读岗位 JD、判断自身经历是否匹配、修改简历内容并准备面试问题。这个过程耗时较长，而且容易出现岗位理解不准确、简历表达不够针对性等问题。

因此，本项目设计了一个 AI 求职辅助工具，尝试使用大语言模型对“简历内容”和“岗位 JD”进行结构化分析，为求职者提供更加具体、可执行的求职建议。

---

## 3. 核心功能

### 3.1 PDF 简历解析

支持上传 PDF 格式简历，系统使用 PyMuPDF 自动提取简历文本内容。

### 3.2 岗位 JD 输入

用户可以粘贴目标岗位描述，包括岗位职责、岗位要求、加分项等信息。

### 3.3 岗位匹配分析

系统会根据简历内容和岗位 JD，自动分析：

* 岗位核心能力要求
* 候选人已有优势
* 综合岗位匹配度
* 当前能力短板
* 简历优化建议
* 可补充的小项目方向
* 模拟面试问题
* 面试表达建议

### 3.4 AI 分析结果展示

使用 Streamlit 搭建交互式 Web 页面，实现简历上传、岗位输入、结果生成和 Markdown 格式展示。

---

## 4. 技术栈

| 模块      | 技术                |
| ------- | ----------------- |
| 前端展示    | Streamlit         |
| PDF 解析  | PyMuPDF           |
| 大模型调用   | DeepSeek API      |
| API SDK | OpenAI Python SDK |
| 环境变量管理  | python-dotenv     |
| 开发语言    | Python            |

---

## 5. 项目结构

```text
jobmatch-ai/
├── app.py                    # Streamlit 前端入口
├── resume_parser.py          # PDF 简历解析模块
├── llm_client.py             # 大模型 API 调用模块
├── prompt_templates.py       # Prompt 模板
├── test_deepseek.py          # DeepSeek API 测试脚本
├── requirements.txt          # 项目依赖
├── .env                      # API Key 配置文件，不上传 GitHub
└── README.md                 # 项目说明文档
```

---

## 6. 运行方法

### 6.1 创建虚拟环境

```bash
conda create -n jobmatch-ai python=3.10
conda activate jobmatch-ai
```

### 6.2 安装依赖

```bash
pip install -r requirements.txt
```

如果没有使用 requirements.txt，也可以手动安装：

```bash
pip install streamlit pymupdf openai python-dotenv
```

### 6.3 配置 DeepSeek API

在项目根目录下创建 `.env` 文件：

```env
OPENAI_API_KEY=你的DeepSeek_API_Key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat
```

注意：`.env` 文件包含个人 API Key，不应上传到 GitHub。

### 6.4 测试 API 是否连接成功

```bash
python test_deepseek.py
```

如果终端输出一段中文回复，说明 API 已经连接成功。

### 6.5 启动项目

Windows PowerShell 推荐使用：

```powershell
& "D:\software\Anaconda\envs\jobmatch-ai\python.exe" -m streamlit run app.py
```

或者在已激活环境后运行：

```bash
python -m streamlit run app.py
```

启动成功后，在浏览器打开：

```text
http://localhost:8501
```

---

## 7. 使用流程

1. 打开项目页面；
2. 上传 PDF 格式简历；
3. 在右侧输入框中粘贴目标岗位 JD；
4. 点击“开始分析”按钮；
5. 查看系统生成的岗位匹配分析结果。

---

## 8. 示例岗位 JD

```text
岗位名称：AI应用开发实习生

岗位职责：
1. 参与大语言模型相关应用的开发与测试；
2. 负责 Prompt 设计、模型调用、结果评估与优化；
3. 参与 RAG、智能问答、文档解析等 AI 应用场景建设；
4. 使用 Python 完成数据处理、接口调用和原型系统开发；
5. 协助整理技术文档和项目汇报材料。

岗位要求：
1. 熟悉 Python 编程，有良好的代码习惯；
2. 了解机器学习、深度学习或大语言模型基础；
3. 了解 PyTorch、向量检索、RAG 或 Prompt Engineering 者优先；
4. 有 Streamlit、FastAPI、LangChain 等项目经验者优先；
5. 具备较强的学习能力、问题分析能力和文档整理能力。
```

---

## 9. 项目亮点

1. 面向真实求职场景，不是单纯的模型训练 Demo；
2. 完成了从 PDF 文档解析到大模型分析的完整 AI 应用链路；
3. 使用 Prompt Engineering 设计结构化输出模板，提高分析结果的可读性和稳定性；
4. 使用 Streamlit 快速搭建可交互页面，具备较好的演示效果；
5. 项目功能与 AI 应用开发实习岗位高度相关，可以作为求职作品展示。

---

## 10. 后续优化方向

后续可以继续扩展以下功能：

1. 增加岗位 JD 批量分析功能，比较多个岗位与简历的匹配程度；
2. 引入 RAG 知识库，加入 AI 应用开发常见面试题和岗位能力模型；
3. 使用 FAISS 或 Chroma 构建向量检索模块；
4. 增加匹配度评分卡、关键词标签、能力雷达图等可视化展示；
5. 支持 Word 简历解析；
6. 支持生成针对不同岗位的简历优化版本；
7. 部署到 Hugging Face Spaces、Streamlit Community Cloud 或云服务器。

---

## 11. 项目总结

本项目是一个面向 AI 应用开发实习求职场景的轻量级 AI 应用系统。通过该项目，我实践了 PDF 文档解析、大语言模型 API 调用、Prompt Engineering、环境变量配置和 Streamlit 页面开发等内容，进一步理解了 AI 应用开发中从需求场景到产品原型实现的完整流程。
