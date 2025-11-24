import streamlit as st
import pandas as pd
import os
import json
from PIL import Image

# ==========================================
# 1. 网页基础设置
# ==========================================
st.set_page_config(page_title="我的选品工作台", layout="wide")

# --- 自定义样式 (为了更像你的软件) ---
st.markdown("""
<style>
    .sku-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 15px;
        border: 1px solid #e0e0e0;
    }
    .highlight-text {
        color: #ff4b4b;
        font-weight: bold;
    }
    .profit-bar {
        background-color: #d1e7dd;
        color: #0f5132;
        padding: 10px;
        border-radius: 5px;
        margin-top: 10px;
        font-size: 14px;
    }
    .comp-bar {
        background-color: #fff3cd;
        color: #664d03;
        padding: 8px;
        border-radius: 5px;
        margin-top: 5px;
        font-size: 13px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 核心功能函数
# ==========================================

@st.cache_data
def load_data():
    if not os.path.exists('product_database_master.csv'):
        return None
    df = pd.read_csv('product_database_master.csv')
    df = df.fillna(0) # 填充空值为0
    return df

df = load_data()

def fix_image_path(raw_path):
    path_str = str(raw_path)
    clean_path = path_str.replace("\\", "/")
    if "db_images" in clean_path:
        parts = clean_path.split("db_images")
        return "db_images" + parts[-1]
    return clean_path

# ==========================================
# 3. 界面布局逻辑
# ==========================================

if df is None:
    st.error("❌ 找不到数据文件，请检查 product_database_master.csv")
else:
    # --- 侧边栏：全局参数 (还原图3左侧) ---
    with st.sidebar:
        st.header("⚙️ 全局参数")
        
        # 模拟你的软件参数
        exchange_rate = st.number_input("全居汇率", value=5.4428, step=0.0001, format="%.4f")
        shipping_channel = st.selectbox("空运渠道", ["空运普货 (Legion)", "海运小包", "敏感货专线"])
        domestic_shipping = st.number_input("国内运费", value=0.0, step=1.0)
        ad_ratio_global = st.number_input("默认广告占比 (%)", value=0.0, step=1.0)
        
        st.info("💡 提示：网页版修改参数仅用于临时计算，刷新后会重置。")
        
        st.divider()
        page = st.radio("切换视图:", ["📄 商品详情与定价 (工作台)", "🏠 商品画廊 (主页)"])

    # 列名映射 (方便后续调用)
    col_map = {
        'img': '图片路径',
        'name': '商品',
        'price': '真实售价',
        'cost': '进货价',
        'weight': '重量',
        'size': '包装尺寸(cm)',
        'sku_json': 'SKU配置',
        'desc': '文案'
    }

    # ==========================================
    # 📄 核心页面：商品详情与定价 (还原图2和图3)
    # ==========================================
    if page == "📄 商品详情与定价 (工作台)":
        
        # 1. 顶部选择商品
        product_names = df[col_map['name']].unique().tolist()
        col_sel_1, col_sel_2 = st.columns([3, 1])
        with col_sel_1:
            selected_product_name = st.selectbox("当前选品:", product_names)
        
        # 获取当前商品数据
        p_data = df[df[col_map['name']] == selected_product_name].iloc[0]
        
        st.markdown("---")

        # 2. 主区域：还原图3布局 (左图，右参数)
        col_main_img, col_main_info = st.columns([1, 1.5])

        with col_main_img:
            st.subheader("🖼️ 商品主图")
            final_path = fix_image_path(p_data[col_map['img']])
            if os.path.exists(final_path):
                st.image(final_path, use_container_width=True)
            else:
                st.warning("图片未找到")

        with col_main_info:
            st.subheader("📝 信息与定价")
            
            # 第一行：汇率 (只读显示，读取侧边栏)
            c1, c2 = st.columns(2)
            c1.number_input("计算汇率", value=exchange_rate, disabled=True)
            
            # 第二行：单件实重 & 进货价
            c3, c4 = st.columns(2)
            weight = c3.number_input("单件实重 (kg)", value=float(p_data.get(col_map['weight'], 0.0)))
            cost_rmb = c4.number_input("单件进货价 (RMB)", value=float(p_data.get(col_map['cost'], 0.0)))

            # 第三行：目标利润率
            c5, c6 = st.columns(2)
            target_margin = c5.number_input("目标利润率 (%)", value=15.0)
            
            # 第四行：包装尺寸 (尝试解析 0.0x0.0x0.0)
            st.caption("📦 包装尺寸 (cm)")
            size_str = str(p_data.get(col_map['size'], "0x0x0"))
            try:
                # 简单的分割逻辑，如果格式不对就默认0
                dims = size_str.lower().split('x') if 'x' in size_str else [0,0,0]
                if len(dims) != 3: dims = [0,0,0]
            except:
                dims = [0,0,0]
                
            cc1, cc2, cc3 = st.columns(3)
            l = cc1.text_input("长", value=dims[0])
            w = cc2.text_input("宽", value=dims[1])
            h = cc3.text_input("高", value=dims[2])

        # 3. 文案部分
        st.subheader("📄 文案内容")
        with st.expander("查看/复制文案", expanded=False):
            st.text_area("文案", value=str(p_data.get(col_map['desc'], "无文案")), height=100)

        st.markdown("---")

        # 4. SKU 变体定价 (核心难点！还原图2)
        st.subheader("🛍️ SKU 变体定价")
        
        # 解析 JSON
        sku_json_str = str(p_data.get(col_map['sku_json'], "[]"))
        try:
            sku_list = json.loads(sku_json_str)
        except:
            sku_list = []
            st.error("⚠️ 该商品 SKU 数据格式有误，无法解析。")

        if not sku_list:
            st.info("此商品没有配置多 SKU 变体信息。")
        else:
            # 遍历每一个 SKU 生成卡片
            for i, sku in enumerate(sku_list):
                # 容器框
                with st.container(border=True):
                    # --- 标题栏 ---
                    st.markdown(f"**SKU #{i+1}：{sku.get('name', '未命名变体')}**")
                    
                    # --- 第一行输入：数量 | 总进货 ---
                    r1c1, r1c2, r1c3 = st.columns([1, 2, 2])
                    qty = r1c1.number_input(f"数量 (Qty)", value=int(sku.get('qty', 1)), key=f"qty_{i}")
                    
                    # 自动计算总进货 = 单价 * 数量
                    total_cost_calc = cost_rmb * qty
                    r1c2.number_input(f"总进货 (¥)", value=total_cost_calc, disabled=True, key=f"cost_{i}")
                    
                    # --- 第二行输入：利润% | 手动定价 | 竞品价 ---
                    r2c1, r2c2, r2c3 = st.columns([1.5, 1.5, 1.5])
                    margin_sku = r2c1.number_input(f"利润%", value=15.0, key=f"margin_{i}")
                    
                    # 读取预设价格 (如果有)
                    default_price = float(sku.get('fixed_price', 0.0))
                    manual_price = r2c2.number_input(f"手动定价 (SGD)", value=default_price if default_price > 0 else 20.0, key=f"price_{i}")
                    
                    comp_price = float(sku.get('comp_price', 0.0))
                    r2c3.number_input(f"竞品价 (SGD)", value=comp_price, disabled=True, key=f"comp_{i}")

                    # --- 实时计算逻辑 (模拟) ---
                    # 这是一个简单的估算，为了让界面动起来
                    # 真实运费计算太复杂，这里简化：(进货/汇率 + 5块钱运费) * 利润系数
                    estimated_cost_sgd = (total_cost_calc / exchange_rate) + (weight * qty * 5) # 假设5块运费
                    net_profit = (manual_price * 0.88) - estimated_cost_sgd # 假设扣点12%
                    real_margin = (net_profit / manual_price * 100) if manual_price > 0 else 0
                    
                    # --- 状态条 (还原绿色条) ---
                    st.markdown(f"""
                    <div class="profit-bar">
                        🔥 <b>建议:</b> s{estimated_cost_sgd*1.3:.2f} | 
                        🟢 <b>实际:</b> s{manual_price:.2f} | 
                        💰 <b>净赚:</b> ¥{net_profit * exchange_rate:.1f} | 
                        📈 <b>利润率:</b> {real_margin:.1f}%
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # --- 竞争力条 (还原黄色条) ---
                    diff = comp_price - manual_price
                    diff_text = f"比竞品 便宜 s{diff:.2f}" if diff > 0 else f"比竞品 贵 s{abs(diff):.2f}"
                    st.markdown(f"""
                    <div class="comp-bar">
                        ⚡ 竞争力: {diff_text}
                    </div>
                    """, unsafe_allow_html=True)

    # ==========================================
    # 🏠 附赠：商品画廊模式 (保留原来的功能)
    # ==========================================
    elif page == "🏠 商品画廊 (主页)":
        st.title("🛒 商品选品主页")
        search_term = st.text_input("🔍 搜索...", "")
        if search_term:
            filtered_df = df[df[col_map['name']].astype(str).str.contains(search_term, case=False, na=False)]
        else:
            filtered_df = df
            
        cols = st.columns(4) # 4列更紧凑
        for index, row in filtered_df.iterrows():
            with cols[index % 4]:
                with st.container(border=True):
                    final_path = fix_image_path(row[col_map['img']])
                    if os.path.exists(final_path):
                        st.image(final_path, use_container_width=True)
                    st.caption(row[col_map['name']])
                    st.markdown(f"**¥{row[col_map['cost']]}**")


