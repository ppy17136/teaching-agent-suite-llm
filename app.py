import streamlit as st
import google.generativeai as genai
import json
import pandas as pd
import sqlite3
import graphviz
from typing import Dict, Any
import time  # <--- 添加这一行


# ==========================================
# 1. 调试工具：探测可用模型
# ==========================================
def debug_models(api_key):
    genai.configure(api_key=api_key)
    st.sidebar.write("### 🔍 正在探测可用模型...")
    try:
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        if not available_models:
            st.sidebar.error("❌ 该 Key 未检测到可用模型")
        else:
            st.sidebar.success("✅ 检测到可用模型，请参考下方列表：")
            for name in available_models:
                st.sidebar.code(name)
    except Exception as e:
        st.sidebar.error(f"探测出错：{str(e)}")

# ==========================================
# 2. 数据库与引擎
# ==========================================
def init_db():
    conn = sqlite3.connect("curriculum_system.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS training_plan 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  section_id TEXT, 
                  section_name TEXT, 
                  content_json TEXT, 
                  status TEXT,
                  update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    return conn

def extract_full_plan(api_key: str, pdf_file):
    genai.configure(api_key=api_key)
    # 注意：这里如果报错404，请根据侧边栏探测到的真实名称修改
    # 常用名称：'gemini-1.5-pro' 或 'gemini-1.5-flash' 或 'models/gemini-1.5-flash-latest'
    model = genai.GenerativeModel('models/gemini-2.0-flash')
    pdf_content = pdf_file.getvalue()
    
    # 将任务拆分为四个逻辑块，避免一次性输出过长导致 JSON 截断
    tasks = {
        "text_parts": "提取：一、培养目标；二、毕业要求；三、专业定位与特色；四、主干学科/核心课程；五、学制学位；六、毕业条件。",
        "appendix_1": "提取：七、专业教学计划表（附表1）。请务必保持所有课程的列信息完整。",
        "appendix_2_3": "提取：八、学分统计表（附表2）和 九、教学进程表（附表3）。",
        "appendix_4_5": "提取：十、课程设置对毕业要求支撑关系表（附表4）和 十一、逻辑导图（附表5）。导图请用 Graphviz DOT 格式。"
    }
    
    final_data = {}
    
    for task_name, task_desc in tasks.items():
        prompt = f"""
        你是一个数据专家。请阅读 PDF，仅执行以下任务：{task_desc}
        要求：
        1. 必须输出纯 JSON 格式。
        2. 不要包含任何 Markdown 标识（如 ```json）。
        3. 如果是表格，请转化为对象列表。
        """
        
        # 尝试重试机制
        for attempt in range(3):
            try:
                response = model.generate_content([prompt, {"mime_type": "application/pdf", "data": pdf_content}])
                # 预处理：去掉可能存在的 Markdown 标签
                clean_text = response.text.replace("```json", "").replace("```", "").strip()
                chunk_json = json.loads(clean_text)
                final_data.update(chunk_json) # 合并到总数据中
                break 
            except Exception as e:
                if attempt == 2: raise e
                time.sleep(5) # 避开频率限制
                
    return final_data

# ==========================================
# 3. 主程序 UI
# ==========================================
def main():
    # 页面配置放在 main 内部的第一行
    st.set_page_config(page_title="培养方案全要素数字化平台", layout="wide")
    
    st.sidebar.title("⚙️ 控制面板")
    
    # 获取 API Key
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
    else:
        api_key = st.sidebar.text_input("输入 Gemini API Key", type="password", help="请先输入 Key 以激活探测")    

    # 如果有 Key，立即执行探测逻辑并显示在侧边栏
    if api_key:
        debug_models(api_key)

    uploaded_file = st.sidebar.file_uploader("上传 2024 级培养方案 PDF", type=['pdf'])
    
    if "data" not in st.session_state:
        st.session_state.data = None

    if st.sidebar.button("🚀 开始全量识别", type="primary"):
        if not api_key or not uploaded_file:
            st.error("请确保已输入 API Key 并上传文件")
        else:
            with st.spinner("Gemini 正在深度解析 11 个模块..."):
                try:
                    result = extract_full_plan(api_key, uploaded_file)
                    st.session_state.data = result
                    st.success("识别成功！请在右侧标签页校对数据。")
                except Exception as e:
                    st.error(f"解析出错: {e}。如果报404，请查看侧边栏支持的模型名称并修改代码。")

    st.title("📖 培养方案全要素校对与管理平台")

    if st.session_state.data:
        d = st.session_state.data
        tabs = st.tabs(["1-3 目标/特色", "4-6 核心/毕业", "7 教学计划(附1)", "8-9 学分(附2-3)", "10 矩阵(附4)", "11 导图(附5)"])

        with tabs[0]:
            d['objectives'] = st.text_area("一、培养目标", d.get('objectives', ''), height=200)
            req_df = pd.DataFrame(d.get('requirements', []))
            st.write("二、毕业要求")
            d['requirements'] = st.data_editor(req_df, num_rows="dynamic", use_container_width=True).to_dict('records')
            d['positioning'] = st.text_area("三、专业定位与特色", d.get('positioning', ''), height=150)

        with tabs[1]:
            d['core_elements'] = st.text_area("四、主干学科/核心课程", d.get('core_elements', ''), height=200)
            d['degree'] = st.text_input("五、学制学位", d.get('degree', ''))
            d['graduation_conditions'] = st.text_area("六、毕业条件", d.get('graduation_conditions', ''), height=150)

        with tabs[2]:
            st.subheader("七、附表1：教学计划表")
            plan_df = pd.DataFrame(d.get('appendix_1_plan', []))
            d['appendix_1_plan'] = st.data_editor(plan_df, num_rows="dynamic", use_container_width=True).to_dict('records')

        with tabs[3]:
            c1, c2 = st.columns(2)
            with c1:
                st.write("八、学分统计")
                d['appendix_2_credits'] = st.data_editor(pd.DataFrame(d.get('appendix_2_credits', []))).to_dict('records')
            with c2:
                st.write("九、教学进程")
                d['appendix_3_process'] = st.data_editor(pd.DataFrame(d.get('appendix_3_process', []))).to_dict('records')

        with tabs[4]:
            st.subheader("十、附表4：支撑矩阵")
            matrix_df = pd.DataFrame(d.get('appendix_4_matrix', []))
            d['appendix_4_matrix'] = st.data_editor(matrix_df, num_rows="dynamic", use_container_width=True).to_dict('records')

        with tabs[5]:
            st.subheader("十一、附表5：逻辑导图")
            dot_code = st.text_area("Graphviz DOT 代码", d.get('appendix_5_logic', ''), height=200)
            if dot_code:
                try:
                    st.graphviz_chart(dot_code)
                    d['appendix_5_logic'] = dot_code
                except:
                    st.error("绘图代码语法错误")

        if st.button("💾 确认无误，保存到数据库", type="primary"):
            conn = init_db()
            for key, val in d.items():
                conn.execute("INSERT INTO training_plan (section_id, content_json, status) VALUES (?, ?, ?)",
                          (key, json.dumps(val, ensure_ascii=False), "Verified"))
            conn.commit()
            st.success("确权保存成功！")
    else:
        st.info("👈 请在侧边栏上传 PDF 并点击开始。")

if __name__ == "__main__":
    main()