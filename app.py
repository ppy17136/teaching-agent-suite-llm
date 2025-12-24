import os
import io, json, time, re
import pandas as pd
import streamlit as st
import pdfplumber
import google.generativeai as genai
from typing import Dict, List, Any
from openai import OpenAI  # 用于适配 DeepSeek, Kimi, Yi, 智谱等

# ============================================================
# 1. 模型供应商配置
# ============================================================
PROVIDERS = {
    "Gemini (Google)": {"base_url": None, "model": "gemini-2.5-flash"},
    "DeepSeek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat"},
    "Kimi (Moonshot)": {"base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k"},
    "智谱 AI (GLM)": {"base_url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4"},
    "零一万物 (Yi)": {"base_url": "https://api.lingyiwanwu.com/v1", "model": "yi-34b-chat-0205"},
    "通义千问 (Qwen)": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    "豆包 (字节)": {"base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "doubao-pro-32k"}
}


# GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
# if not GEMINI_API_KEY:
    # st.error("未配置 QWEN_API_KEY（请在 Streamlit Cloud 的 Secrets 中设置）")
    # st.stop()
# ============================================================
# 0. API Key 轮换管理逻辑
# ============================================================
def get_next_api_key():
    """
    从 Secrets 中获取轮换的 API Key
    """
    # 优先从 Secrets 获取列表，如果没有则尝试获取单个 Key 作为备选
    all_keys = st.secrets.get("GEMINI_KEYS", [])
    
    if not all_keys:
        # 兼容你原来的单 Key 逻辑
        single_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
        return single_key

    # 使用 Streamlit 的 session_state 来记录当前该用哪一个（针对当前用户 session）
    # 如果想实现全局跨用户轮换，可以去掉这个 if 直接使用全局变量（但在 Cloud 环境下不稳定）
    if "api_key_index" not in st.session_state:
        st.session_state.api_key_index = 0
    
    # 获取当前索引对应的 Key
    selected_key = all_keys[st.session_state.api_key_index % len(all_keys)]
    
    # 索引自增，供下一次运行使用
    st.session_state.api_key_index += 1
    
    return selected_key


# ============================================================
# 2. 统一大模型调用路由
# ============================================================
def call_llm(provider_name, api_key, prompt):
    config = PROVIDERS[provider_name]
    
    # --- 场景 A: Gemini 专用 SDK ---
    if "Gemini" in provider_name:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(config["model"])
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text)
    
    # --- 场景 B: OpenAI 兼容格式 (DeepSeek, Kimi, GLM, etc.) ---
    else:
        client = OpenAI(api_key=api_key, base_url=config["base_url"])
        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": "你是一个只输出 JSON 的教务专家助手。"},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)


# ============================================================
# 1. 核心提示词定义：一次性指令
# ============================================================
MEGA_PROMPT = """
你是一个专业的高校教务专家。请深度阅读提供的的培养方案文本，并按照以下要求精确提取信息。

### 提取要求：
1. **分条列出**：对于“毕业要求”等包含多个子项的内容，必须保留原始编号（如 1.1, 1.2），并使用换行符或 Markdown 列表格式（* 或 1.）逐条列出，严禁合并成段落。
2. **完整性**：提取 1-6 项正文时，必须包含所有细分条款。例如“毕业条件”必须包含学分要求（如至少修满 174 学分）。
3. **表格精度**：
   - 附表 1：(教学计划表) 请提取所有课程，不要遗漏，确保包含“学位课”标记（√）。
   - 附表 2：(学分统计)必须清晰区分“焊接”和“无损检测”两个方向。
   - 附表 4：(支撑矩阵)提取课程对指标点的支撑强度（H/M/L）。
   
### 输出格式： 
必须严格输出一个 JSON 对象，结构如下：
{
  "sections": {
    "1培养目标": "...",
    "2毕业要求": "...",
    "3专业定位与特色": "...",
    "4主干学科/核心课程/实践环节": "...",
    "5标准学制与授予学位": "...",
    "6毕业条件": "..."
  },
  "table1": [{"课程体系": "...", "课程编码": "...", "课程名称": "...", "开课模式": "...", "考核方式": "...", "课内学分": "...", "课内总学时": "...", "课内讲课学时": "...", "课内实验学时": "...", "课内上机学时": "...", "课内实践学时": "...", "课外学分": "...", "课外学时": "...", "上课学期": "...", "专业方向": "...", "是否学位课": "...", "备注": "..."}],
  "table2": [{"专业方向": "...", "课程体系": "...", "开课模式": "...", "学期一学分分配": "...", "学期二学分分配": "...", "学期三学分分配": "...", "学期四学分分配": "...", "学期五学分分配": "...", "学期六学分分配": "...", "学期七学分分配": "...", "学期八学分分配": "...", "学分统计": "...", "学分比例": "..."}],
  "table4": [{"课程名称": "...", "指标点": "...", "强度": "..."}]
}

"""

# ============================================================
# 2. 简化的解析引擎
# ============================================================
def parse_document_mega(api_key, pdf_bytes, provider_name):
    """
    带有动态状态反馈的解析函数
    """
    # 1. 使用 st.status 创建一个状态容器
    with st.status(f"🚀 正在通过 {provider_name} 提取数据...", expanded=True) as status:
        
        try:
            # 步骤 A: 读取 PDF
            st.write("🔍 正在读取 PDF 文本内容...")
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                all_text = "\n".join([p.extract_text() or "" for p in pdf.pages])
            st.write(f"✅ 已提取 {len(all_text)} 个字符。")

            # 步骤 B: 构建提示词
            st.write("📑 正在构建深度解析指令...")
            full_prompt = f"{MEGA_PROMPT}\n\n培养方案原文：\n{all_text}"
            
            # 步骤 C: 发送网络请求
            st.write(f"🤖 正在调用 {provider_name} 进行全量分析 (此步骤较慢，请稍候)...")
            
            # 记录开始时间以显示耗时（可选）
            start_time = time.time()
            
            # 执行 LLM 调用
            result = call_llm(provider_name, api_key, full_prompt)
            
            duration = time.time() - start_time
            st.write(f"✨ AI 解析完成，耗时 {duration:.1f} 秒。")

            # 步骤 D: 状态更新为完成
            status.update(label="✅ 提取任务全部完成！", state="complete", expanded=False)
            return result

        except Exception as e:
            # 捕获异常并更新状态
            status.update(label="❌ 提取过程中发生错误", state="error", expanded=True)
            st.error(f"详细错误信息: {str(e)}")
            return None


# ============================================================
# 3. Streamlit UI
# ============================================================
def main():
    st.set_page_config(layout="wide", page_title="多模型智能教学工作台")
    
    if "mega_data" not in st.session_state:
        st.session_state.mega_data = None

    with st.sidebar:
        st.title("🤖 模型配置")
        selected_provider = st.selectbox("选择模型供应商", list(PROVIDERS.keys()))
        
        # --- 修改这里 ---
        if "Gemini" in selected_provider:
            # 自动轮换获取 Key
            current_api_key = get_next_api_key()
            # 在侧边栏显示当前正在使用的 Key 编号（隐藏具体内容，保护隐私）
            all_keys = st.secrets.get("GEMINI_KEYS", [])
            key_info = f"轮换模式 (当前第 {(st.session_state.get('api_key_index', 1)-1) % len(all_keys) + 1} 个)" if all_keys else "单 Key 模式"
            st.caption(f"🔑 Gemini 状态: {key_info}")
        else:
            current_api_key = st.text_input(f"输入 {selected_provider} 的 API Key", type="password")
        
        # 如果手动输入了覆盖，则以手动为准（可选）
        api_key = current_api_key if current_api_key else ""

    st.header("🧠 培养方案全量提取 (多模型版)")
    file = st.file_uploader("上传 PDF 培养方案", type="pdf")

    if file and api_key and st.button("🚀 执行一键全量抽取", type="primary"):
        result = parse_document_mega(api_key, file.getvalue(), selected_provider)
        if result:
            st.session_state.mega_data = result
            st.success(f"抽取成功！来自模型: {selected_provider}")


    if st.session_state.mega_data:
        d = st.session_state.mega_data
        tab1, tab2, tab3, tab4 = st.tabs(["1-6 正文", "附表1: 计划表", "附表2: 学分统计", "附表4: 支撑矩阵"])
        
        with tab1:
            sections = d.get("sections", {})
            sec_pick = st.selectbox("选择栏目", list(sections.keys()))
            st.text_area("内容", value=sections.get(sec_pick, ""), height=400, key=f"ta_{sec_pick}")

        with tab2:
            st.dataframe(pd.DataFrame(d.get("table1", [])), use_container_width=True)

        with tab3:
            st.dataframe(pd.DataFrame(d.get("table2", [])), use_container_width=True)

        with tab4:
            st.dataframe(pd.DataFrame(d.get("table4", [])), use_container_width=True)

# ============================================================
# 修改后的 UI 部分逻辑
# ============================================================
def main():
    # ... 前面的代码 ...

    with st.sidebar:
        st.title("🤖 模型配置")
        selected_provider = st.selectbox("选择模型供应商", list(PROVIDERS.keys()))
        
        # --- 修改这里 ---
        if "Gemini" in selected_provider:
            # 自动轮换获取 Key
            current_api_key = get_next_api_key()
            # 在侧边栏显示当前正在使用的 Key 编号（隐藏具体内容，保护隐私）
            all_keys = st.secrets.get("GEMINI_KEYS", [])
            key_info = f"轮换模式 (当前第 {(st.session_state.get('api_key_index', 1)-1) % len(all_keys) + 1} 个)" if all_keys else "单 Key 模式"
            st.caption(f"🔑 Gemini 状态: {key_info}")
        else:
            current_api_key = st.text_input(f"输入 {selected_provider} 的 API Key", type="password")
        
        # 如果手动输入了覆盖，则以手动为准（可选）
        api_key = current_api_key if current_api_key else ""
        # ----------------




if __name__ == "__main__":
    main()