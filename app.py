import streamlit as st
import google.generativeai as genai
import json
import pandas as pd
import sqlite3
import graphviz
from typing import Dict, Any

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
    model = genai.GenerativeModel('models/gemini-1.5-flash')
    
    prompt = """
    你是一个教育专家和数据分析师。请完整识别并抽取上传培养方案PDF中的所有内容。
    必须严格按照以下 11 个标题进行分类，并输出为 JSON 格式：

    【文字部分】
    1. "objectives": 抽取“一、培养目标”的完整文字。
    2. "requirements": 抽取“二、毕业要求”，包含指标点编号和具体描述。
    3. "positioning": 抽取“三、专业定位与特色”。
    4. "core_elements": 抽取“四、主干学科、专业核心课程和主要实践性教学环节”。
    5. "degree": 抽取“五、标准学制与授予学位”。
    6. "graduation_conditions": 抽取“六、毕业条件”。

    【表格部分 - 需转化为结构化列表】
    7. "appendix_1_plan": “七、专业教学计划表（附表1）”，包含课程代码、名称、学分、各学期学时等。
    8. "appendix_2_credits": “八、学分统计表（附表2）”，分类统计各模块学分。
    9. "appendix_3_process": “九、教学进程表（附表3）”。
    10. "appendix_4_matrix": “十、课程设置对毕业要求支撑关系表（附表4）”，提取课程对指标点的支撑强度（H/M/L）。

    【图形部分】
    11. "appendix_5_logic": “十一、课程设置逻辑思维导图(附表5)”，请根据图片逻辑，输出一套符合 Graphviz DOT 格式的绘图代码。

    要求：
    - 不要总结，要原文提取。表格务必保持行列对应的逻辑。
    - 只返回纯 JSON，不要包含 Markdown 标记。
    """
    
    pdf_content = pdf_file.getvalue()
    response = model.generate_content([
        prompt,
        {"mime_type": "application/pdf", "data": pdf_content}
    ])
    
    clean_json = response.text.strip().replace("```json", "").replace("```", "")
    return json.loads(clean_json)

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