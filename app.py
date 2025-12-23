import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(layout="wide", page_title="材料成型及控制工程课程逻辑图")

st.title("2024级材料成型及控制工程（焊接方向）课程逻辑")
st.write("依据辽宁石油化工大学2024版人才培养方案绘制 [cite: 6, 11]")

# 定义 Mermaid 流程图代码
mermaid_code = """
graph TD
    %% 定义学期子图
    subgraph S1 [第一学年: 第1学期]
        C1_1[高等数学D1★]
        C1_2[工程制图与CAD II*]
        C1_3[数据科学与智能技术概论]
    end

    subgraph S2 [第一学年: 第2学期]
        C2_1[高等数学D2★]
        C2_2[大学物理F1★]
        C2_3[Python语言程序设计*]
        C2_4[普通化学]
    end

    subgraph S3 [第二学年: 第3学期]
        C3_1[线性代数B*]
        C3_2[大学物理F2★]
        C3_3[材料物理化学*]
        C3_4[工程力学B2★]
    end

    subgraph S4 [第二学年: 第4学期]
        C4_1[材料科学基础*]
        C4_2[电工与电子技术C*]
        C4_3[概率论与数理统计B*]
    end

    subgraph S5 [第三学年: 第5学期]
        C5_1[材料成型方法及工艺★]
        C5_2[机械设计基础*]
        C5_3[工程材料及热处理]
        C5_4[材料成型智能控制基础*]
    end

    subgraph S6 [第三学年: 第6学期]
        C6_1[焊接方法及工艺★]
        C6_2[焊接结构*]
        C6_3[焊接冶金与金属焊接性]
    end

    subgraph S7_8 [第四学年: 毕业出口]
        C7_1[焊接工艺课程设计]
        C7_2[工业机器人]
        C8_1[毕业设计]
    end

    %% 定义核心逻辑链条 (依赖关系)
    C1_1 --> C2_1 --> C3_1 --> C4_3
    C1_2 --> C3_3
    C2_2 --> C3_2 --> C4_2
    C2_4 --> C3_3 --> C4_1 --> C5_3
    C4_1 --> C6_3
    C3_4 --> C5_2 --> C6_2
    C5_1 --> C6_1
    C6_1 & C6_2 & C6_3 --> C7_1 --> C8_1
    C5_4 --> C7_2 --> C8_1

    %% 样式美化
    style C8_1 fill:#f96,stroke:#333,stroke-width:4px
    style C4_1 fill:#bbf,stroke:#333
    style C6_1 fill:#bbf,stroke:#333
"""

# 在 Streamlit 中渲染
def render_mermaid(code):
    components.html(
        f"""
        <pre class="mermaid">
            {code}
        </pre>
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ startOnLoad: true }});
        </script>
        """,
        height=800,
        scrolling=True
    )

render_mermaid(mermaid_code)