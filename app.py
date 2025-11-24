import streamlit as st
import pandas as pd
import os
from PIL import Image

# 1. 网页基础设置 (宽屏模式)
st.set_page_config(page_title="我的选品库", layout="wide")

# --- 🛠️ 核心函数：读取数据 ---
@st.cache_data
def load_data():
    if not os.path.exists('product_database_master.csv'):
        return None
    df = pd.read_csv('product_database_master.csv')
    return df

df = load_data()

# --- 🛠️ 核心函数：修复图片路径 (你的专属修复逻辑) ---
def fix_image_path(raw_path):
    path_str = str(raw_path)
    # 把反斜杠 \ 变成正斜杠 /
    clean_path = path_str.replace("\\", "/")
    # 去掉本地盘符，只保留 db_images 之后的部分
    if "db_images" in clean_path:
        parts = clean_path.split("db_images")
        return "db_images" + parts[-1]
    return clean_path

# ==========================================
# 🌟 界面布局开始
# ==========================================

if df is None:
    st.error("❌ 错误：找不到 product_database_master.csv 文件，请检查GitHub是否上传成功。")
else:
    # 你的表格列名 (根据刚才截图确认的)
    img_col = '图片路径'
    name_col = '商品'
    price_col = '真实售价'
    desc_col = '文案'  # 详情页显示的文案
    
    # --- ⬅️ 侧边栏：导航区 ---
    st.sidebar.title("🚀 导航栏")
    # 这里就是切换“主页”和“详情页”的开关
    page = st.sidebar.radio("去往:", ["🏠 商品主页 (画廊)", "📄 商品详情页"])

    # ==========================================
    # 🏠 页面 1：商品主页
    # ==========================================
    if page == "🏠 商品主页 (画廊)":
        st.title("🛒 商品选品主页")
        
        # 顶部搜索框
        col_search, col_count = st.columns([3, 1])
        with col_search:
            search_term = st.text_input("🔍 输入关键词搜索商品...", "")
        
        # 筛选逻辑
        if search_term:
            filtered_df = df[df[name_col].astype(str).str.contains(search_term, case=False, na=False)]
        else:
            filtered_df = df

        with col_count:
            st.metric("当前展示", f"{len(filtered_df)} 款")

        st.markdown("---")

        # 🖼️ 图片网格展示 (3列布局)
        cols = st.columns(3)
        for index, row in filtered_df.iterrows():
            col = cols[index % 3]
            with col:
                # 1. 处理路径
                final_path = fix_image_path(row[img_col])
                
                # 2. 显示卡片
                with st.container(border=True): # 给每个商品加个边框，更好看
                    if os.path.exists(final_path):
                        st.image(final_path, use_container_width=True)
                    else:
                        st.warning("图片缺失")
                    
                    st.subheader(str(row[name_col]))
                    
                    # 显示价格
                    if price_col in row:
                        st.info(f"💰 售价: {row[price_col]}")
                    
                    # 显示ID或其他小信息
                    if 'id' in row:
                        st.caption(f"ID: {row['id']}")

    # ==========================================
    # 📄 页面 2：商品详情页
    # ==========================================
    elif page == "📄 商品详情页":
        st.title("📄 商品详细资料卡")
        
        # 1. 选择商品 (下拉框)
        # 获取所有商品名字
        product_names = df[name_col].unique().tolist()
        selected_product_name = st.selectbox("👇 请选择一个商品查看详情：", product_names)
        
        st.markdown("---")
        
        # 2. 获取该商品的所有数据
        product_data = df[df[name_col] == selected_product_name].iloc[0]
        
        # 3. 详情页布局 (左图右文)
        col_left, col_right = st.columns([1, 1.2])
        
        with col_left:
            # 左侧：大图
            final_path = fix_image_path(product_data[img_col])
            if os.path.exists(final_path):
                st.image(final_path, caption=product_data[name_col], use_container_width=True)
            else:
                st.error("图片文件丢失")
                
        with col_right:
            # 右侧：详细信息
            st.header(product_data[name_col])
            
            # 价格高亮显示
            if price_col in df.columns:
                st.success(f"💰 **真实售价:** {product_data[price_col]}")
            
            # 利润信息 (根据截图里的列)
            st.markdown("### 📊 利润分析")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("海运利润", f"¥{product_data.get('海运利润(RMB)', '-')}")
            with c2:
                st.metric("空运利润", f"¥{product_data.get('空运利润(RMB)', '-')}")
            with c3:
                st.metric("利润模式", str(product_data.get('利润模式', '-')))
            
            # 文案部分
            st.markdown("### 📝 营销文案")
            if desc_col in df.columns and pd.notna(product_data[desc_col]):
                st.text_area("复制文案", product_data[desc_col], height=150)
            else:
                st.info("暂无文案信息")
                
            # 更多参数 (折叠面板)
            with st.expander("查看 采购/规格 参数"):
                st.json({
                    "进货价": str(product_data.get('进货价', '未知')),
                    "重量": str(product_data.get('重量', '未知')),
                    "包装尺寸": str(product_data.get('包装尺寸(cm)', '未知')),
                    "采购链接": str(product_data.get('采购链接', '无'))
                })


