import streamlit as st
import streamlit.components.v1 as components

# 设置页面为宽屏模式
st.set_page_config(layout="wide", page_title="2024级焊接专业完整课程逻辑图")

st.title("2024级材料成型及控制工程（焊接方向）完整课程逻辑导图")
st.caption("依据辽宁石油化工大学2024版人才培养方案绘制 [cite: 1, 6, 11]")

# 完整 Mermaid 脚本：包含 8 个学期及全部核心节点
mermaid_code = """
graph LR
    %% 第一学年：基础与工具
    subgraph S1 [第1学期 - 11门]
        C1_1[大学外语1★]
        C1_2[高等数学D1★]
        C1_3[数据科学与智能技术概论]
        C1_4[工程制图与CAD II★]
        C1_9[思想道德与法治★]
        C1_11[形势与政策1]
    end

    subgraph S2 [第2学期 - 13门]
        C2_2[高等数学D2★]
        C2_3[大学物理F1★]
        C2_5[Python语言程序设计★]
        C2_6[普通化学]
        C2_7[二维材料成型计算机绘图]
        C2_11[中国近现代史纲要]
        C2_13[形势与政策2]
    end

    %% 第二学年：学科转接
    subgraph S3 [第3学期 - 14门]
        C3_2[线性代数B★]
        C3_3[大学物理F2★]
        C3_5[材料物理化学★]
        C3_6[工程力学B2★]
        C3_9[三维材料成型计算机绘图]
        C3_11[工程训练B]
        C3_14[形势与政策3]
    end

    subgraph S4 [第4学期 - 15门]
        C4_2[概率论与数理统计B★]
        C4_5[电工与电子技术C★]
        C4_7[材料科学基础★]
        C4_8[热流体★]
        C4_13[马克思主义基本原理★]
        C4_15[形势与政策4]
    end

    %% 第三学年：专业核心
    subgraph S5 [第5学期 - 12门]
        C5_3[材料成型智能控制基础★]
        C5_4[材料成型方法及工艺★]
        C5_5[工程材料及热处理★]
        C5_8[工程材料冷加工基础★]
        C5_9[机械设计基础★]
        C5_12[认识实习★]
        C5_13[习近平新时代思想概论]
    end

    subgraph S6 [第6学期 - 12门]
        C6_4[焊接方法及工艺★]
        C6_5[焊接质量检验与评价★]
        C6_7[焊接冶金与金属焊接性★]
        C6_8[焊接结构★]
        C6_9[焊接结构课程设计★]
        C6_10[焊接原理及工艺实验★]
        C6_14[大学生就业指导]
    end

    %% 第四学年：工程出口
    subgraph S7 [第7学期 - 10门]
        C7_3[焊接工艺课程设计★]
        C7_6[工业机器人★]
        C7_11[生产实习★]
        C7_2[增材制造技术]
        C7_4[绿色智能焊接新技术]
        C7_5[绿色智能交叉焊接综合实验]
    end

    subgraph S8 [第8学期 - 2门]
        C8_1[毕业设计★终极产出]
    end

    %% 核心逻辑关系连线 (根据培养方案逻辑流还原)
    C1_2 --> C2_2 --> C3_2 --> C4_2 --> C5_1
    C1_4 --> C2_7 --> C3_9 --> C5_9
    C2_3 --> C3_3 --> C4_5 --> C5_3
    C2_6 --> C3_5 --> C4_7 --> C5_5
    C4_7 --> C6_7
    C3_6 --> C5_9 --> C6_8
    C5_4 --> C6_4 --> C7_3
    C5_3 --> C6_4
    C6_8 --> C6_9 --> C8_1
    C5_12 --> C7_11 --> C8_1
    C6_4 & C6_7 & C6_8 --> C7_3 --> C8_1
    C7_6 --> C8_1

    %% 样式美化
    style C8_1 fill:#f96,stroke:#333,stroke-width:4px
    style C4_7 fill:#bbf,stroke:#333
    style C6_4 fill:#bbf,stroke:#333
    style C6_8 fill:#bbf,stroke:#333
"""

# 定义渲染函数，修复了之前导致报错的 f-string 语法
def render_mermaid(code):
    components.html(
        f"""
        <div class="mermaid">
            {code}
        </div>
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ 
                startOnLoad: true,
                theme: 'neutral',
                flowchart: {{ 
                    useMaxWidth: false, 
                    htmlLabels: true,
                    curve: 'basis' 
                }}
            }});
        </script>
        """,
        height=1200, 
        scrolling=True
    )

render_mermaid(mermaid_code)