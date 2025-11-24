import streamlit as st
import pandas as pd
import os
from PIL import Image

# 1. 网页设置
st.set_page_config(page_title="我的选品库", layout="wide")

# --- 🛠️ 数据读取与清洗 ---
@st.cache_data
def load_data():
    if not os.path.exists('product_database_master.csv'):
        return None
    df = pd.read_csv('product_database_master.csv')
    # 【关键修复】把所有的空值填为 "0" 或 "-"，防止出现 nan
    df = df.fillna("-")
    return df

df = load_data()

# --- 🛠️ 路径修复逻辑 ---
def fix_image_path(raw_path):
    path_str = str(raw_path)
    clean_path = path_str.replace("\\", "/")
    if "db_images" in clean_path:
        parts = clean_path.split("db_images")
        return "db_images" + parts[-1]
    return clean_path

# ==========================================
# 🌟 界面逻辑
# ==========================================

if df is None:
    st.error("❌ 找不到数据文件")
else:
    # 你的列名配置
    img_col = '图片路径'
    name_col = '商品'
    price_col = '真实售价'
    desc_col = '文案'

    # --- 侧边栏 ---
    st.sidebar.title("🚀 导航")
    page = st.sidebar.radio("选择页面:", ["🏠 商品主页", "📄 商品详情页"])

    # ==========================================
    # 🏠 页面 1：商品主页
    # ==========================================
    if page == "🏠 商品主页":
        st.title("🛒 商品选品主页")
        
        # 搜索与计数
        col1, col2 = st.columns([3, 1])
        with col1:
            search_term = st.text_input("🔍 搜索商品名称...", "")
        
        if search_term:
            filtered_df = df[df[name_col].astype(str).str.contains(search_term, case=False, na=False)]
        else:
            filtered_df = df
            
        with col2:
            st.metric("商品总数", f"{len(filtered_df)}")

        st.divider()

        # 图片画廊
        cols = st.columns(3)
        for index, row in filtered_df.iterrows():
            with cols[index % 3]:
                # 卡片容器
                with st.container(border=True):
                    # 图片
                    final_path = fix_image_path(row[img_col])
                    if os.path.exists(final_path):
                        st.image(final_path, use_container_width=True)
                    else:
                        st.text("暂无图片")
                    
                    # 标题和价格
                    st.markdown(f"#### {row[name_col]}")
                    st.info(f"💰 售价: {row[price_col]}")

    # ==========================================
    # 📄 页面 2：商品详情页 (精装修版)
    # ==========================================
    elif page == "📄 商品详情页":
        st.title("📄 商品详细资料")
        
        # 选择器
        product_names = df[name_col].unique().tolist()
        selected_product_name = st.selectbox("👇 选择商品:", product_names)
        
        st.divider()
        
        # 获取数据
        product_data = df[df[name_col] == selected_product_name].iloc[0]
        
        col_left, col_right = st.columns([1, 1.2])
        
        # --- 左侧：大图 ---
        with col_left:
            final_path = fix_image_path(product_data[img_col])
            if os.path.exists(final_path):
                st.image(final_path, use_container_width=True)
            else:
                st.error("图片丢失")

        # --- 右侧：详细数据 ---
        with col_right:
            st.header(product_data[name_col])
            st.success(f"💰 **真实售价: {product_data[price_col]}**")
            
            # 1. 利润分析 (使用 Metric 组件，更好看)
            st.markdown("### 📊 利润分析")
            m1, m2, m3 = st.columns(3)
            # 使用 .get() 安全获取数据，防止报错
            m1.metric("海运利润", f"¥{product_data.get('海运利润(RMB)', '-')}")
            m2.metric("空运利润", f"¥{product_data.get('空运利润(RMB)', '-')}")
            m3.metric("利润模式", f"{product_data.get('利润模式', '-')}")
            
            # 2. 营销文案
            st.markdown("### 📝 营销文案")
            desc_content = product_data.get(desc_col, "暂无文案")
            st.text_area("点击右下角复制", desc_content, height=150)

            # 3. 规格参数 (改成表格显示，不再是代码)
            st.markdown("### ⚙️ 采购规格")
            
            # 构建一个漂亮的表格数据
            specs = {
                "参数项目": ["进货价", "重量", "包装尺寸", "采购链接", "SKU配置"],
                "详细内容": [
                    f"¥{product_data.get('进货价', '-')}",
                    str(product_data.get('重量', '-')),
                    str(product_data.get('包装尺寸(cm)', '-')),
                    str(product_data.get('采购链接', '-')),
                    str(product_data.get('SKU配置', '-'))
                ]
            }
            specs_df = pd.DataFrame(specs)
            # 隐藏索引，只显示表格
            st.table(specs_df)


