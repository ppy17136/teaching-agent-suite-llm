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

# ============================================================
# 2. 核心路由：API Key 轮换与重试逻辑
# ============================================================

def call_llm_core(provider_name, api_key, prompt):
    """最底层的 API 调用，不做重试，只负责发请求"""
    config = PROVIDERS[provider_name]
    
    if "Gemini" in provider_name:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(config["model"])
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text)
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

def call_llm_with_retry_and_rotation(provider_name, user_api_key, prompt):
    all_keys = st.secrets.get("GEMINI_KEYS", [])
    
    # 场景 A: 非 Gemini 或用户手动输入了 Key
    if "Gemini" not in provider_name or user_api_key:
        target_key = user_api_key if user_api_key else st.secrets.get("GEMINI_API_KEY", "")
        return call_llm_core(provider_name, target_key, prompt)

    # 场景 B: Gemini 多 Key 自动轮换
    if not all_keys:
        raise Exception("未在 Secrets 中配置 GEMINI_KEYS 列表")

    if "api_key_index" not in st.session_state:
        st.session_state.api_key_index = 0

    last_exception = None
    
    # --- 关键修改点 1：每次调用该函数时，先主动跳到下一个 Key ---
    # 这样可以确保即便是成功的运行，下一次也会换 Key
    start_idx = st.session_state.api_key_index % len(all_keys)

    for i in range(len(all_keys)):
        # 计算当前尝试的索引
        current_attempt_idx = (start_idx + i) % len(all_keys)
        current_key = all_keys[current_attempt_idx]
        
        # 更新 session_state，确保 UI 显示的是当前正在尝试的那个
        st.session_state.api_key_index = current_attempt_idx
        
        try:
            st.write(f"正在尝试使用 Key #{current_attempt_idx + 1}...")
            result = call_llm_core(provider_name, current_key, prompt)
            
            # --- 关键修改点 2：成功运行后，将索引推到下一个，为下一次“全新运行”做准备 ---
            st.session_state.api_key_index = (current_attempt_idx + 1) % len(all_keys)
            return result
            
        except Exception as e:
            err_msg = str(e).lower()
            # 如果是配额问题，记录错误并继续循环（尝试下一个 key）
            if any(x in err_msg for x in ["429", "quota", "limit"]):
                st.warning(f"⚠️ Key #{current_attempt_idx + 1} 配额耗尽，自动尝试下一个...")
                continue 
            else:
                # 如果是其他错误（比如内容安全拦截），直接抛出不再重试
                raise e
    
    raise Exception(f"❌ 已尝试所有 {len(all_keys)} 个 Key，均无法完成请求。")
    
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

def parse_document_mega(user_api_key, pdf_bytes, provider_name):
    """带有动态状态反馈和自动轮换的解析函数"""
    with st.status(f"🚀 正在通过 {provider_name} 提取数据...", expanded=True) as status:
        try:
            st.write("🔍 正在读取 PDF 文本内容...")
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                all_text = "\n".join([p.extract_text() or "" for p in pdf.pages])
            st.write(f"✅ 已读取 {len(all_text)} 字符。")

            st.write("📑 正在发送 AI 抽取请求 (支持 Key 自动轮换)...")
            start_time = time.time()
            
            # --- 关键修改：调用带轮换重试的函数 ---
            full_prompt = f"{MEGA_PROMPT}\n\n原文：\n{all_text}"
            result = call_llm_with_retry_and_rotation(provider_name, user_api_key, full_prompt)
            
            duration = time.time() - start_time
            st.write(f"✨ 解析完成，总耗时 {duration:.1f} 秒。")
            status.update(label="✅ 提取成功！", state="complete", expanded=False)
            return result

        except Exception as e:
            status.update(label="❌ 提取失败", state="error", expanded=True)
            st.error(str(e))
            return None

# ============================================================
# 4. Streamlit UI
# ============================================================

def main():
    st.set_page_config(layout="wide", page_title="智能教学工作台")
    
    if "mega_data" not in st.session_state:
        st.session_state.mega_data = None

    with st.sidebar:
        st.title("🤖 模型配置")
        selected_provider = st.selectbox("选择模型供应商", list(PROVIDERS.keys()))
        
        # 允许手动输入 Key，如果不输入则走 Secrets 轮换逻辑
        user_input_key = st.text_input(f"输入 {selected_provider} API Key (留空则使用内置轮换)", type="password")
        
        if "Gemini" in selected_provider and not user_input_key:
            all_keys = st.secrets.get("GEMINI_KEYS", [])
            idx = st.session_state.get("api_key_index", 0) % len(all_keys) if all_keys else 0
            st.info(f"模式：多 Key 自动轮换 (就绪: {len(all_keys)}个)")
            st.caption(f"当前指针：第 {idx + 1} 个 Key")
        
        st.warning("如果遇到并发限制，系统会自动尝试列表中下一个 Key。")

    st.header("🧠 培养方案全量提取")
    file = st.file_uploader("上传 PDF", type="pdf")

    if file and st.button("🚀 执行一键全量抽取", type="primary"):
        # 调用函数
        result = parse_document_mega(user_input_key, file.getvalue(), selected_provider)
        if result:
            st.session_state.mega_data = result

    # 结果展示部分
    if st.session_state.mega_data:
        d = st.session_state.mega_data
        tab1, tab2, tab3, tab4 = st.tabs(["1-6 正文", "附表1: 计划表", "附表2: 学分统计", "附表4: 支撑矩阵"])
        # ... (展示代码保持不变) ...
        with tab1:
            sections = d.get("sections", {})
            if sections:
                sec_pick = st.selectbox("选择栏目", list(sections.keys()))
                st.text_area("内容", value=sections.get(sec_pick, ""), height=400)
        with tab2:
            st.dataframe(pd.DataFrame(d.get("table1", [])), use_container_width=True)
        with tab3:
            st.dataframe(pd.DataFrame(d.get("table2", [])), use_container_width=True)
        with tab4:
            st.dataframe(pd.DataFrame(d.get("table4", [])), use_container_width=True)

if __name__ == "__main__":
    main()