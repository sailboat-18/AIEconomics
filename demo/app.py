import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred
from datetime import datetime
from google import genai  # Google GenAI SDK

# =====================================================================
# 🌟 【API Key 快速填入區】請保持空白，改至網頁側邊欄或 Secrets 輸入以策安全！
# =====================================================================
HARDCODED_FRED_KEY = "" 
HARDCODED_GEMINI_KEY = ""
# =====================================================================


# 頁面基本配置
st.set_page_config(page_title="總體經濟與金融即時儀表板", layout="wide")
st.title("🌐 全球總體經濟與金融指標即時儀表板")

# 側邊欄：設定與金鑰讀取邏輯
st.sidebar.header("⚙️ 設定與金鑰")

# 1. 取得 FRED Key
if HARDCODED_FRED_KEY:
    fred_key = HARDCODED_FRED_KEY
    st.sidebar.success("已讀取程式碼中設定的 FRED Key！")
elif "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
    st.sidebar.success("已自動讀取 Secrets 中的 FRED Key！")
else:
    fred_key = st.sidebar.text_input("請輸入 FRED API Key:", type="password")

# 2. 取得 Gemini Key
if HARDCODED_GEMINI_KEY:
    gemini_key = HARDCODED_GEMINI_KEY
    st.sidebar.success("已讀取程式碼中設定的 Gemini Key！")
elif "GEMINI_API_KEY" in st.secrets:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    st.sidebar.success("已自動讀取 Secrets 中的 Gemini Key！")
else:
    gemini_key = st.sidebar.text_input("請輸入 Gemini API Key:", type="password")

if st.sidebar.button("手動刷新數據"):
    st.cache_data.clear()
    st.sidebar.success("快取已清除，正在重新載入...")

# 1. 抓取 FRED 數據
@st.cache_data(ttl=3600)
def get_fred_data(api_key):
    fred = Fred(api_key=api_key)
    data = {
        "CPI 物價指數": fred.get_series("CPIAUCSL"),
        "10年期美債殖利率": fred.get_series("DGS10"),
        "2年期美債殖利率": fred.get_series("DGS2"),
        "美國失業率": fred.get_series("UNRATE"),
        "聯邦基金利率": fred.get_series("FEDFUNDS"),
        "日本10年期公債殖利率": fred.get_series("IRLTLT01JPM156N")
    }
    df = pd.DataFrame(data).ffill().tail(365)
    df["美債殖利率利差 (10Y-2Y)"] = df["10年期美債殖利率"] - df["2年期美債殖利率"]
    return df

# 2. 抓取 Market 數據
@st.cache_data(ttl=600)
def get_market_data():
    tickers = {
        "S&P 500": "^GSPC",
        "台灣加權指數": "^TWII",
        "布蘭特原油": "BZ=F",
        "美元/台幣匯率": "TWD=X",
        "黃金現貨": "GC=F"
    }
    df = yf.download(list(tickers.values()), period="1y")
    
    if isinstance(df.columns, pd.MultiIndex):
        df = df["Close"]
    else:
        df = df[["Close"]]
        
    if "Close" in df:
        df = df["Close"]
        
    inverse_tickers = {v: k for k, v in tickers.items()}
    df = df.rename(columns=inverse_tickers)
    return df

# 頁面渲染邏輯
if fred_key:
    try:
        with st.spinner("正在從 FRED 與 Yahoo Finance 同步最新數據..."):
            macro_df = get_fred_data(fred_key)
            market_df = get_market_data()

        st.sidebar.info(f"數據最後載入時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 🚨 檢查最新美債利差是否倒掛 (< 0)
        latest_spread = macro_df["美債殖利率利差 (10Y-2Y)"].dropna().iloc[-1]
        if latest_spread < 0:
            st.error(f"🚨 **【殖利率倒掛警示】** 當前 10 年期與 2 年期美債殖利率利差為 **{latest_spread:.2f}%**（小於 0）。歷史經驗顯示，倒掛通常是經濟衰退的重要領先指標，請留意市場風險！")
        else:
            st.success(f"✅ **【殖利率正常】** 當前 10 年期與 2 年期美債殖利率利差為 **{latest_spread:.2f}%**（正常正斜率）。")

        # 第一區塊：核心 KPI 卡片
        st.subheader("📊 關鍵總體經濟指標 (FRED)")
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        latest_cpi = macro_df["CPI 物價指數"].dropna().iloc[-1]
        col1.metric("CPI 物價指數", f"{latest_cpi:.1f}")
        
        latest_rate = macro_df["10年期美債殖利率"].dropna().iloc[-1]
        rate_prev = macro_df["10年期美債殖利率"].dropna().iloc[-2]
        col2.metric("10年美債殖利率", f"{latest_rate:.2f}%", f"{latest_rate - rate_prev:+.2f}%")
        
        latest_2y = macro_df["2年期美債殖利率"].dropna().iloc[-1]
        rate_2y_prev = macro_df["2年期美債殖利率"].dropna().iloc[-2]
        col3.metric("2年美債殖利率", f"{latest_2y:.2f}%", f"{latest_2y - rate_2y_prev:+.2f}%")
        
        spread_prev = macro_df["美債殖利率利差 (10Y-2Y)"].dropna().iloc[-2]
        col4.metric("10Y-2Y 利差", f"{latest_spread:.2f}%", f"{latest_spread - spread_prev:+.2f}%", delta_color="normal" if latest_spread >= 0 else "inverse")
        
        latest_unemp = macro_df["美國失業率"].dropna().iloc[-1]
        col5.metric("美國失業率", f"{latest_unemp:.1f}%")
        
        latest_jp = macro_df["日本10年期公債殖利率"].dropna().iloc[-1]
        col6.metric("日本10年債殖利率", f"{latest_jp:.2f}%")

        # 第二區塊：互動式圖表
        st.write("---")
        st.subheader("📈 市場走勢與總體指標折線圖")
        
        tab1, tab2 = st.tabs(["金融市場走勢 (yfinance)", "總體經濟趨勢 (FRED)"])
        
        with tab1:
            market_choice = st.selectbox("選擇金融市場標的：", market_df.columns, key="market_select")
            fig1 = px.line(market_df, y=market_choice, title=f"{market_choice} 近一年走勢", labels={"value": "指數/價格", "Date": "日期"})
            st.plotly_chart(fig1, use_container_width=True)
            
        with tab2:
            macro_choice = st.selectbox("選擇總體經濟指標：", macro_df.columns, key="macro_select")
            fig2 = px.line(macro_df, y=macro_choice, title=f"{macro_choice} 近一年走勢", labels={"value": "數值", "Date": "日期"})
            if macro_choice == "美債殖利率利差 (10Y-2Y)":
                fig2.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="倒掛分界線 (0%)")
            st.plotly_chart(fig2, use_container_width=True)

        # 第三區塊：AI 總體經濟摘要生成器
        st.write("---")
        st.subheader("🤖 AI 智慧總經短評")
        
        if "ai_summary" not in st.session_state:
            st.session_state.ai_summary = ""

        if st.button("✨ 產生 AI 總體經濟摘要"):
            if not gemini_key:
                st.warning("請先在左側邊欄輸入您的 Gemini API Key！")
            else:
                try:
                    with st.spinner("Gemini 正在分析當前總體經濟數據並撰寫短評..."):
                        latest_fed_rate = macro_df["聯邦基金利率"].dropna().iloc[-1]
                        latest_unemployment = macro_df["美國失業率"].dropna().iloc[-1]
                        
                        prompt = f"""
                        你是一位專業的華爾街總體經濟分析師。請根據以下最新的美國經濟數據，撰寫一份約 200 字的專業總體經濟短評：
                        - CPI 物價指數: {latest_cpi:.1f}
                        - 聯邦基金利率: {latest_fed_rate:.2f}%
                        - 美國失業率: {latest_unemployment:.1f}%
                        - 10年期美債殖利率: {latest_rate:.2f}%
                        - 2年期美債殖利率: {latest_2y:.2f}%
                        - 10Y-2Y 美債殖利率利差: {latest_spread:.2f}% (小於0代表倒掛)

                        請分析目前的通膨、貨幣政策利率環境以及殖利率曲線狀況，並給出投資人應注意的潛在總經風險。語氣需專業、客觀。
                        """

                        # 使用更新後的 gemini-3.8-flash 模型[cite: 5]
                        client = genai.Client(api_key=gemini_key)
                        response = client.models.generate_content(
                            model='gemini-3.8-flash',
                            contents=prompt
                        )
                        st.session_state.ai_summary = response.text
                except Exception as e:
                    st.error(f"AI 生成失敗，請確認 Gemini API Key 是否正確。錯誤訊息: {e}")

        if st.session_state.ai_summary:
            st.info(st.session_state.ai_summary)

        # 附加功能：允許下載數據
        with st.expander("📥 檢視與下載原始數據"):
            st.write("金融市場數據 (yfinance)")
            st.dataframe(market_df.tail(10))
            st.write("總體經濟數據 (FRED)")
            st.dataframe(macro_df.tail(10))

    except Exception as e:
        st.error(f"數據讀取失敗，請確認 FRED API Key 是否正確或網路連線是否正常。錯誤訊息: {e}")
else:
    st.info("👈 請在左側邊欄輸入您的 FRED API Key 以開啟儀表板。")
