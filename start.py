import streamlit as st
import pandas as pd
import json
import os
import requests
import time
import glob
import base64
import re
from PIL import Image
from io import BytesIO

# === 依赖检查 ===
try:
    from rembg import remove, new_session
except ImportError:
    st.error("❌ 缺少库，请运行: pip install --upgrade rembg[cli] pillow requests streamlit")
    st.stop()

# === 全局设置 ===
MASTER_DB_FILE = "product_database_master.csv" 
DEFAULT_SAVE_PATH = os.path.join(os.path.expanduser("~"), "Desktop", "Product_Images")
DB_IMG_FOLDER = "db_images"
STRIPE_PCT = 0.034
STRIPE_FIX = 0.50

if not os.path.exists(DB_IMG_FOLDER): os.makedirs(DB_IMG_FOLDER)

# === 初始化 Session ===
if 'rembg_session' not in st.session_state: st.session_state.rembg_session = new_session("isnet-general-use")
if 'current_view' not in st.session_state: st.session_state.current_view = 'dashboard'
if 'editing_index' not in st.session_state: st.session_state.editing_index = None
if 'uploaded_files' not in st.session_state: st.session_state.uploaded_files = []
if 'active_img_data' not in st.session_state: st.session_state.active_img_data = None

# === 0. 数据核心 ===
def load_data():
    df = pd.DataFrame()
    if os.path.exists(MASTER_DB_FILE):
        try: df = pd.read_csv(MASTER_DB_FILE)
        except: pass
    elif glob.glob("product_database*.csv"):
        latest = max(glob.glob("product_database*.csv"), key=os.path.getmtime)
        try: df = pd.read_csv(latest)
        except: pass
    
    if not df.empty:
        df = df.fillna("")
        if "图片路径" in df.columns:
            df["图片路径"] = df["图片路径"].astype(str)
            
        cols_to_drop = ["删除", "Delete", "选择", "图片预览", "利润率"] 
        df = df.drop(columns=[c for c in cols_to_drop if c in df.columns], errors='ignore')
        
        cols_check = ["目标利润率", "文案", "图片路径", "包装尺寸(cm)", "采购链接", "Shopee竞品链接", "数量", "真实售价", "SKU配置", "备注", "竞品价(SGD)"]
        for col in cols_check:
            if col not in df.columns:
                if col == "数量": df[col] = 1
                elif col == "真实售价": df[col] = 0.0
                elif col == "竞品价(SGD)": df[col] = 0.0
                else: df[col] = ""
    return df

def save_data(df):
    cols_to_drop = ["删除", "Delete", "选择", "图片预览"]
    df_clean = df.drop(columns=[c for c in cols_to_drop if c in df.columns], errors='ignore')
    df_clean.to_csv(MASTER_DB_FILE, index=False, encoding='utf-8-sig')

def image_to_base64(image_path):
    if not image_path or not isinstance(image_path, str) or image_path == "nan": return None
    if image_path.startswith("http"): return image_path
    if os.path.exists(image_path):
        try:
            with open(image_path, "rb") as f:
                return f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
        except: return None
    return None

# === 1. 辅助函数 ===
def get_realtime_rate():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get("https://open.er-api.com/v6/latest/SGD", headers=headers, timeout=3)
        return float(resp.json()['rates']['CNY'])
    except: return 5.35

def clean_taobao_image_url(url):
    if not isinstance(url, str): return ""
    match = re.search(r'(.*?\.jpg|.*?\.png|.*?\.jpeg)', url, re.IGNORECASE)
    return match.group(1) if match else url

def extract_image_from_url(text_input):
    if not text_input or not isinstance(text_input, str): return None, "无效输入"
    match = re.search(r'https?://[^\s\u4e00-\u9fa5]+', text_input)
    raw_url = match.group(0) if match else text_input
    clean_url = clean_taobao_image_url(raw_url)
    if any(clean_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp', '.heic']):
        return clean_url, "直接链接"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'}
        resp = requests.get(clean_url, headers=headers, timeout=5, allow_redirects=True)
        soup = BeautifulSoup(resp.content, 'html.parser')
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"): 
            return clean_taobao_image_url(og_image["content"]), "抓取成功"
        return None, "未识别"
    except Exception as e: return None, str(e)

# === 2. 运费逻辑 (返回 费用 和 公式字符串) ===
def get_ship_cost_cny(weight, channel):
    w = weight
    cw = max(w, 1.0)
    
    price_table = {
        "空运普货 (Legion)": {"first": 40, "add": 23, "bulk": 21},
        "空运敏感 (Legion)": {"first": 55, "add": 31, "bulk": 29.5},
        "海运慢递 (ZTO)":    {"first": 30, "add": 10, "bulk": 10}
    }
    key = channel if channel in price_table else "海运慢递 (ZTO)"
    p = price_table[key]
    
    cost = 0
    formula = ""
    
    if w > 10:
        cost = w * p['bulk']
        formula = f"{w:.2f}kg × ¥{p['bulk']}"
    else:
        add_w = max(w - 1, 0)
        cost = p['first'] + add_w * p['add']
        formula = f"¥{p['first']}(首) + {add_w:.2f}kg × ¥{p['add']}"
        
    return cost, formula

# === 3. SKU 深度计算函数 (新版) ===
def calculate_sku_variant(unit_cost, domestic, unit_weight, qty, profit_pct, ad_pct, rate, air_channel, manual_price=None, comp_price=0.0):
    # 1. 基础数据
    total_goods_cny = unit_cost * qty
    total_weight = unit_weight * qty
    
    # 2. 运费计算 (空运 & 海运)
    ship_air_cny, ship_air_form = get_ship_cost_cny(total_weight, air_channel)
    ship_sea_cny, ship_sea_form = get_ship_cost_cny(total_weight, "海运慢递 (ZTO)")
    
    # 3. 空运硬成本
    hard_air_cny = total_goods_cny + domestic + ship_air_cny
    hard_air_sgd = hard_air_cny / rate
    
    # 4. 建议售价倒推 (基于空运)
    denom = 1 - STRIPE_PCT - ad_pct - profit_pct
    if denom <= 0.01:
        suggested_price = 0.0
    else:
        suggested_price = (hard_air_sgd + STRIPE_FIX) / denom
        
    # 5. 确定最终售价
    final_price = manual_price if (manual_price is not None and manual_price > 0) else suggested_price
    
    # 6. 费用核算 (基于最终售价)
    stripe_fee = final_price * STRIPE_PCT + STRIPE_FIX
    ad_fee = final_price * ad_pct
    total_fee = stripe_fee + ad_fee
    
    # 7. 空运利润
    profit_air_sgd = final_price - hard_air_sgd - total_fee
    profit_air_cny = profit_air_sgd * rate
    margin_air = (profit_air_sgd / final_price) if final_price > 0 else 0
    
    # 8. 海运利润 (假设售价相同)
    hard_sea_cny = total_goods_cny + domestic + ship_sea_cny
    hard_sea_sgd = hard_sea_cny / rate
    profit_sea_sgd = final_price - hard_sea_sgd - total_fee
    profit_sea_cny = profit_sea_sgd * rate
    margin_sea = (profit_sea_sgd / final_price) if final_price > 0 else 0
    
    # 9. 竞品对比
    comp_status = ""
    if comp_price > 0:
        diff = final_price - comp_price
        if diff > 0: comp_status = f"贵 S${diff:.2f}"
        else: comp_status = f"便宜 S${abs(diff):.2f}"
    
    return {
        "weight": total_weight,
        "final_price": final_price,
        "suggested_price": suggested_price,
        "comp_status": comp_status,
        "fees": {"stripe": stripe_fee, "ad": ad_fee},
        "air": {
            "ship_cny": ship_air_cny, "ship_form": ship_air_form,
            "hard_cny": hard_air_cny, "hard_sgd": hard_air_sgd,
            "profit_cny": profit_air_cny, "margin": margin_air
        },
        "sea": {
            "ship_cny": ship_sea_cny, "ship_form": ship_sea_form,
            "hard_cny": hard_sea_cny, "hard_sgd": hard_sea_sgd,
            "profit_cny": profit_sea_cny, "margin": margin_sea
        },
        "goods_cny": total_goods_cny
    }

# === 页面配置 ===
st.set_page_config(page_title="独立站工作站 v37.0", layout="wide")

# === 侧边栏 ===
with st.sidebar:
    st.header("⚙️ 全局参数")
    if 'rate' not in st.session_state: st.session_state.rate = get_realtime_rate()
    col_r1, col_r2 = st.columns([3,1])
    with col_r1: exchange_rate_global = st.number_input("全局汇率", value=st.session_state.rate, format="%.4f", key="global_rate")
    with col_r2: 
        if st.button("🔄"): st.session_state.rate = get_realtime_rate(); st.rerun()
    
    st.divider()
    air_ch = st.selectbox("空运渠道", ("空运普货 (Legion)", "空运敏感 (Legion)"))
    dom_ship = st.number_input("国内运费", value=0.0)
    global_ad = st.number_input("默认广告占比 (%)", 0.0, 100.0, 0.0, step=1.0)
    st.divider()
    st.info("v37.0: 详情页 SKU 增加海运计算与 Stripe 明细。")

# ============================================================
#  视图 1: 详情编辑页 (Detail View)
# ============================================================
if st.session_state.current_view == 'detail':
    df = load_data()
    if st.session_state.editing_index is not None and st.session_state.editing_index in df.index:
        row_idx = st.session_state.editing_index
        row = df.loc[row_idx]
        
        col_header_1, col_header_2 = st.columns([1, 6])
        with col_header_1:
            if st.button("⬅️ 返回列表"):
                st.session_state.update(current_view='dashboard')
                st.rerun()
        with col_header_2:
            st.title(f"🛠️ 编辑详情: {row['商品']}")
        
        st.markdown("---")
        col_left, col_right = st.columns([1, 1.6])
        
        with col_left:
            st.subheader("🖼️ 商品主图")
            current_img_path = str(row.get('图片路径', ''))
            if current_img_path and current_img_path != "nan" and os.path.exists(current_img_path):
                st.image(Image.open(current_img_path), use_column_width=True)
            else: st.info("暂无图片")
            
            with st.expander("更换主图"):
                new_img = st.file_uploader("上传新图片", type=['jpg','png','webp'])
                if new_img:
                    img_obj = Image.open(new_img)
                    new_path = f"{DB_IMG_FOLDER}/{row['商品']}_{int(time.time())}.png"
                    img_obj.save(new_path)
                    df.at[row_idx, '图片路径'] = new_path
                    save_data(df)
                    st.success("图片已更新")
                    st.rerun()
            
            st.divider()
            st.subheader("🔗 链接管理")
            new_sourcing_link = st.text_input("采购链接 (1688/淘宝)", value=str(row.get('采购链接', '')))
            new_shopee_link = st.text_input("Shopee 竞品链接", value=str(row.get('Shopee竞品链接', '')))

        with col_right:
            st.subheader("📝 信息与定价")
            col_rate, _ = st.columns([1, 2])
            with col_rate:
                current_page_rate = st.number_input("💱 计算汇率", value=exchange_rate_global, format="%.4f", step=0.01)

            def parse_pct(val): 
                try: return float(str(val).replace('%','')) 
                except: return 30.0
            
            old_dims = str(row.get('包装尺寸(cm)', '0x0x0')).split('x')
            if len(old_dims) != 3: old_dims = [0, 0, 0]
            l_val, w_val, h_val = [float(x) if str(x).replace('.','',1).isdigit() else 0.0 for x in old_dims]

            c1, c2 = st.columns(2)
            with c1:
                new_name = st.text_input("商品名称", value=str(row['商品']))
                new_cost = st.number_input("单件进货价 (RMB)", value=float(row['进货价']))
                
                st.caption("📦 包装尺寸 (cm)")
                col_l, col_w, col_h = st.columns(3)
                nl = col_l.number_input("长", value=l_val, step=1.0)
                nw = col_w.number_input("宽", value=w_val, step=1.0)
                nh = col_h.number_input("高", value=h_val, step=1.0)

            with c2:
                new_weight = st.number_input("单件实重 (kg)", value=float(row['重量']))
                old_profit = parse_pct(row.get('目标利润率', 30))
                old_ad = parse_pct(row.get('广告占比', 0))
                new_profit = st.number_input("目标利润率 (%)", value=old_profit, step=1.0) / 100
                new_ad = st.number_input("广告占比 (%)", value=old_ad, step=1.0) / 100
                new_comp = st.number_input("竞品参考价 (SGD)", value=float(row.get('竞品价(SGD)', 0)))
            
            st.markdown("#### 📄 文案内容")
            new_copy = st.text_area("文案", value=str(row.get('文案', '')), height=150)
            new_note = st.text_input("备注", value=str(row.get('备注', '')))
            
            # === SKU 管理 (核心更新) ===
            st.markdown("---")
            st.subheader("🛍️ SKU 变体定价")
            
            try: sku_list = json.loads(str(row.get('SKU配置', '[]')))
            except: sku_list = []
            if not sku_list:
                sku_list.append({"name": "1件装", "qty": 1, "cost": new_cost, "profit": new_profit, "fixed_price": 0.0, "comp_price": 0.0})

            updated_sku_list = []
            for i, sku in enumerate(sku_list):
                with st.container(border=True):
                    # 第一行：基础参数
                    c_s1, c_s2, c_s3 = st.columns([2, 1, 1.5])
                    with c_s1: s_name = st.text_input(f"SKU #{i+1}", value=sku.get("name", f"{sku.get('qty',1)}件装"), key=f"sn_{i}")
                    with c_s2: s_qty = st.number_input("数量", value=int(sku.get("qty",1)), min_value=1, key=f"sq_{i}")
                    with c_s3: s_cost = st.number_input("总进货(¥)", value=float(sku.get("cost", new_cost*s_qty)), key=f"sc_{i}")
                    
                    # 第二行：定价策略
                    c_s4, c_s5, c_s6 = st.columns([1.5, 1.5, 1.5])
                    with c_s4: s_profit = st.number_input("利润%", value=float(sku.get("profit", new_profit)*100), step=5.0, key=f"sp_{i}")/100
                    with c_s5: s_fixed = st.number_input("手动定价(SGD)", value=float(sku.get("fixed_price", 0.0)), key=f"sf_{i}")
                    with c_s6: s_comp = st.number_input("竞品价(SGD)", value=float(sku.get("comp_price", 0.0)), key=f"cp_{i}")
                    
                    # 计算
                    unit_c = s_cost / s_qty if s_qty > 0 else 0
                    res = calculate_sku_variant(unit_c, dom_ship, new_weight, s_qty, s_profit, new_ad, current_page_rate, air_ch, manual_price=s_fixed if s_fixed > 0 else None, comp_price=s_comp)
                    
                    if res:
                        # 结果栏
                        final_p = res['final_price']
                        st.info(f"💰 建议: S${res['suggested_price']:.2f} | 🟢 实际: S${final_p:.2f} | 🔥 净赚: ¥{res['air']['profit_cny']:.1f} | 📈 利润率: {res['air']['margin']*100:.1f}%")
                        
                        if res['comp_status']:
                            color = "red" if "贵" in res['comp_status'] else "green"
                            st.caption(f"竞争力: :{color}[比竞品 {res['comp_status']}]")

                        # 详细计算过程
                        with st.expander("🧮 查看该 SKU 成本明细 (含海运对比)"):
                            tab_air, tab_sea = st.tabs(["✈️ 空运明细", "🚢 海运明细"])
                            
                            with tab_air:
                                st.markdown(f"**1. 运费 (总重 {res['weight']:.2f}kg)**")
                                st.code(f"{res['air']['ship_form']} = ¥{res['air']['ship_cny']:.1f}")
                                
                                st.markdown("**2. 硬成本构成**")
                                st.write(f"货¥{res['goods_cny']:.0f} + 国内¥{dom_ship} + 国际¥{res['air']['ship_cny']:.1f} = ¥{res['air']['hard_cny']:.1f}")
                                st.write(f"折合: S${res['air']['hard_sgd']:.2f} (汇率 {current_page_rate})")
                                
                                st.markdown("**3. 费用扣除**")
                                st.write(f"Stripe: S${res['fees']['stripe']:.2f} ({(final_p*0.034+0.5):.2f})")
                                st.write(f"广告: S${res['fees']['ad']:.2f}")
                                
                                st.success(f"**4. 净利**: S${final_p} - 成本费用 = S${(res['air']['profit_cny']/current_page_rate):.2f} (¥{res['air']['profit_cny']:.1f})")

                            with tab_sea:
                                st.markdown(f"**1. 运费计算**")
                                st.code(f"{res['sea']['ship_form']} = ¥{res['sea']['ship_cny']:.1f}")
                                
                                st.markdown(f"**2. 利润对比 (按售价 S${final_p} 测算)**")
                                diff = res['sea']['profit_cny'] - res['air']['profit_cny']
                                st.info(f"海运净赚: ¥{res['sea']['profit_cny']:.1f} | 利润率: {res['sea']['margin']*100:.1f}%")
                                st.write(f"比空运多赚: ¥{diff:.1f}")
                    
                    updated_sku_list.append({
                        "name": s_name, "qty": s_qty, "cost": s_cost, 
                        "profit": s_profit, "fixed_price": s_fixed, "comp_price": s_comp
                    })

            col_add, col_del = st.columns(2)
            with col_add:
                if st.button("➕ 增加 SKU"):
                    updated_sku_list.append({"name": "新变体", "qty": 1, "cost": new_cost, "profit": new_profit, "fixed_price": 0.0, "comp_price": 0.0})
                    df.at[row_idx, 'SKU配置'] = json.dumps(updated_sku_list)
                    save_data(df); st.rerun()
            with col_del:
                if len(updated_sku_list) > 1:
                    if st.button("➖ 删除末尾"):
                        updated_sku_list.pop()
                        df.at[row_idx, 'SKU配置'] = json.dumps(updated_sku_list)
                        save_data(df); st.rerun()

            # 底部按钮
            st.markdown("---")
            b1, b2 = st.columns([1, 5])
            with b1:
                if st.button("🗑️ 删除商品"):
                    df = df.drop(row_idx)
                    save_data(df)
                    st.session_state.current_view = 'dashboard'
                    st.rerun()
            with b2:
                if st.button("💾 保存所有修改", type="primary", use_container_width=True):
                    if updated_sku_list:
                        first = updated_sku_list[0]
                        # 主表更新预览
                        f_res = calculate_sku_variant(first['cost']/first['qty'] if first['qty']>0 else 0, dom_ship, new_weight, first['qty'], first['profit'], new_ad, current_page_rate, air_ch, manual_price=first['fixed_price'], comp_price=first.get('comp_price', 0.0))
                        if f_res:
                            df.at[row_idx, '空运售价(SGD)'] = round(f_res['suggested_price'], 2)
                            df.at[row_idx, '真实售价'] = round(f_res['final_price'], 2)
                            df.at[row_idx, '硬成本(RMB)'] = round(f_res['air']['hard_cny'], 2)
                            df.at[row_idx, '竞品价(SGD)'] = first.get('comp_price', 0.0)

                    df.at[row_idx, '商品'] = new_name
                    df.at[row_idx, '重量'] = new_weight
                    df.at[row_idx, '进货价'] = new_cost
                    df.at[row_idx, '包装尺寸(cm)'] = f"{nl}x{nw}x{nh}"
                    df.at[row_idx, '目标利润率'] = f"{new_profit*100}%"
                    df.at[row_idx, '广告占比'] = f"{new_ad*100}%"
                    df.at[row_idx, '文案'] = new_copy
                    df.at[row_idx, '备注'] = new_note
                    df.at[row_idx, '采购链接'] = new_sourcing_link
                    df.at[row_idx, 'Shopee竞品链接'] = new_shopee_link
                    df.at[row_idx, 'SKU配置'] = json.dumps(updated_sku_list)
                    
                    save_data(df)
                    st.toast("保存成功！", icon="✅")
                    time.sleep(0.5)
                    st.session_state.current_view = 'dashboard'
                    st.rerun()
    else:
        st.error("商品未找到")
        if st.button("返回"): st.session_state.update(current_view='dashboard'); st.rerun()

# ============================================================
#  视图 2: 首页工作台 (Dashboard)
# ============================================================
else:
    st.title("🚀 独立站全能工作站")
    
    # 1. 录入区
    with st.container(border=True):
        st.subheader("➕ 新增商品")
        c_input, c_prev = st.columns([1.5, 1])
        
        with c_input:
            files = st.file_uploader("拖入图片 (批量)", type=['jpg','png','webp'], accept_multiple_files=True)
            if files:
                st.session_state.uploaded_files = files
                selected = st.selectbox("📸 选为主图:", [f.name for f in files])
                for f in files:
                    if f.name == selected:
                        st.session_state.active_img_data = Image.open(f)
                        break
        with c_prev:
            if st.session_state.active_img_data: st.image(st.session_state.active_img_data, width=150)

        c1, c2, c3 = st.columns(3)
        with c1: name = st.text_input("商品名称", placeholder="必填")
        with c3: cost = st.number_input("单件进货价 (RMB)", 0.0, 10000.0, 50.0)
        with c2: 
            weight = st.number_input("单件实重 (kg)", 0.01, 100.0, 0.5)
            qty_in = st.number_input("📦 初始数量", 1, 100, 1)
        
        c4, c5, c6 = st.columns(3)
        with c4: profit_in = st.number_input("目标利润率 (%)", 0.0, 100.0, 30.0, step=1.0) / 100
        with c5: ad_in = st.number_input("广告占比 (%)", 0.0, 100.0, global_ad, step=1.0) / 100
        with c6: comp_price = st.number_input("竞品参考价 (SGD)", 0.0, 1000.0, 0.0)
        
        real_price_in = st.number_input("🟢 真实卖价 (SGD, 0=自动)", 0.0, 1000.0, 0.0, step=0.5)

    # 2. 实时计算
    if cost > 0:
        # 首页仅展示单 SKU 预览
        res_pre = calculate_sku_variant(cost, dom_ship, weight, qty_in, profit_in, ad_in, exchange_rate_global, air_ch, manual_price=real_price_in if real_price_in > 0 else None, comp_price=comp_price)

        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"### ✈️ {air_ch}")
            st.metric("建议售价", f"S${res_pre['suggested_price']:.2f}")
            st.metric("当前售价", f"S${res_pre['final_price']:.2f}")
            st.caption(f"净赚: ¥{res_pre['air']['profit_cny']:.1f}")
            
            if res_pre['comp_status']:
                color = "red" if "贵" in res_pre['comp_status'] else "green"
                st.markdown(f":{color}[比竞品 {res_pre['comp_status']}]")
                
            with st.expander("📊 成本公式"):
                st.write(f"运费: {res_pre['air']['ship_form']} = ¥{res_pre['air']['ship_cny']:.1f}")
                st.info(f"硬成本: S${res_pre['air']['hard_sgd']:.2f}")

        with col2: 
            st.markdown("### 🚢 海运暴利模式")
            diff = res_pre['sea']['profit_cny'] - res_pre['air']['profit_cny']
            st.metric("海运净赚", f"¥{res_pre['sea']['profit_cny']:.1f}", delta=f"多赚 ¥{diff:.1f}")
            
            with st.expander("📊 成本公式"):
                st.write(f"运费: {res_pre['sea']['ship_form']} = ¥{res_pre['sea']['ship_cny']:.1f}")

        # 3. 批量抠图
        st.markdown("---")
        with st.expander("✂️ 批量抠图工具"):
            save_path = st.text_input("保存路径", value=DEFAULT_SAVE_PATH)
            if st.button("🔥 开始批量抠图"):
                files = st.session_state.uploaded_files
                if not files: st.warning("请上传")
                else:
                    if not os.path.exists(save_path): os.makedirs(save_path)
                    bar = st.progress(0)
                    for i, f in enumerate(files):
                        try:
                            f.seek(0); img = Image.open(f)
                            out = remove(img, session=st.session_state.rembg_session)
                            fname = f"{name if name else 'img'}_{i}_{int(time.time())}.png"
                            out.save(os.path.join(save_path, fname), "PNG")
                        except: pass
                        bar.progress((i+1)/len(files))
                    st.success("完成")

        # 4. 保存按钮
        st.markdown("---")
        if st.button("💾 保存并添加到库", type="primary"):
            if name and cost > 0 and res_pre:
                img_path = ""
                if st.session_state.active_img_data:
                    img_path = f"{DB_IMG_FOLDER}/{name}_{int(time.time())}.png"
                    st.session_state.active_img_data.save(img_path)
                
                df_curr = load_data()
                default_sku = [{"name": f"{qty_in}件装", "qty": qty_in, "cost": cost*qty_in, "profit": profit_in, "fixed_price": real_price_in, "comp_price": comp_price}]
                
                new_row = {
                    "图片路径": img_path, "商品": name, 
                    "重量": weight, "数量": qty_in, "包装尺寸(cm)": "",
                    "进货价": cost,
                    "目标利润率": f"{profit_in*100}%", "广告占比": f"{ad_in*100}%",
                    "空运售价(SGD)": round(res_pre['suggested_price'], 2), 
                    "真实售价": round(res_pre['final_price'], 2),
                    "硬成本(RMB)": round(res_pre['air']['hard_cny'], 2),
                    "竞品价(SGD)": comp_price, "文案": "", "备注": "", 
                    "采购链接": "", "Shopee竞品链接": "",
                    "SKU配置": json.dumps(default_sku),
                    "时间": time.strftime("%m-%d %H:%M")
                }
                df_new = pd.concat([pd.DataFrame([new_row]), df_curr], ignore_index=True)
                save_data(df_new)
                st.success("已添加！")
                st.rerun()

    # 5. 数据库列表
    st.markdown("---")
    st.subheader("📋 商品数据库")
    st.caption("💡 **单击表格中的任意一行**，进入详情编辑页。")

    df_hist = load_data()
    if not df_hist.empty:
        df_display = df_hist.copy()
        if "图片路径" in df_display.columns:
            df_display["主图"] = df_display["图片路径"].apply(image_to_base64)
            cols = ["主图", "商品", "数量", "重量", "进货价", "目标利润率", "空运售价(SGD)", "真实售价", "硬成本(RMB)", "竞品价(SGD)", "文案", "采购链接", "Shopee竞品链接"]
            valid_cols = [c for c in cols if c in df_display.columns]
            df_display = df_display[valid_cols]

        event = st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "主图": st.column_config.ImageColumn(width=60),
                "文案": st.column_config.TextColumn(width="small"),
                "采购链接": st.column_config.LinkColumn(display_text="采购"),
                "Shopee竞品链接": st.column_config.LinkColumn(display_text="Shopee"),
                "真实售价": st.column_config.NumberColumn(format="$%.2f"),
                "空运售价(SGD)": st.column_config.NumberColumn(label="建议售价", format="$%.2f")
            },
            on_select="rerun", selection_mode="single-row"
        )
        
        if len(event.selection.rows) > 0:
            st.session_state.editing_index = event.selection.rows[0]
            st.session_state.current_view = 'detail'
            st.rerun()
    else: st.info("暂无数据")


