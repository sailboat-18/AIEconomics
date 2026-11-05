import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred
from datetime import datetime

# 頁面基本配置
st.set_page_config(page_title="總體經濟與金融即時儀表板", layout="wide")
st.title("🌐 全球總體經濟與金融指標即時儀表板")

# 側邊欄：輸入 API Key 與刷新控制
st.sidebar.header("⚙️ 設定與金鑰")

# 優先使用 Streamlit Secrets，若無則讓學生在側邊欄輸入
if "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
    st.sidebar.success("已自動讀取 Secrets 中的 API Key！")
else:
    fred_key = st.sidebar.text_input("請輸入你的 FRED API Key:", type="password")

if st.sidebar.button("手動刷新數據"):
    st.cache_data.clear()
    st.sidebar.success("快取已清除，正在重新載入...")

# 1. 抓取 FRED 數據 (新增 2 年期美債 DGS2，並計算利差)
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
    
    # 計算 10 年期減去 2 年期美債殖利率利差
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

        # 🚨 檢查最新美債利差是否倒掛 (< 0) 並顯示警示燈號
        latest_spread = macro_df["美債殖利率利差 (10Y-2Y)"].dropna().iloc[-1]
        if latest_spread < 0:
            st.error(f"🚨 **【殖利率倒掛警示】** 當前 10 年期與 2 年期美債殖利率利差為 **{latest_spread:.2f}%**（小於 0）。歷史經驗顯示，倒掛通常是經濟衰退的重要領先指標，請留意市場風險！")
        else:
            st.success(f"✅ **【殖利率正常】** 當前 10 年期與 2 年期美債殖利率利差為 **{latest_spread:.2f}%**（正常正斜率）。")

        # 第一區塊：核心 KPI 卡片 (改為 6 個欄位)
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
            
            # 如果選擇的是利差，可以額外畫一條 0 軸參考線讓圖表更直覺
            if macro_choice == "美債殖利率利差 (10Y-2Y)":
                fig2.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="倒掛分界線 (0%)")
                
            st.plotly_chart(fig2, use_container_width=True)

        # 附加功能：允許下載數據
        with st.expander("📥 檢視與下載原始數據"):
            st.write("金融市場數據 (yfinance)")
            st.dataframe(market_df.tail(10))
            st.write("總體經濟數據 (FRED)")
            st.dataframe(macro_df.tail(10))

    except Exception as e:
        st.error(f"數據讀取失敗，請確認 FRED API Key 是否正確或網路連線是否正常。錯誤訊息: {e}")
else:
    st.info("👈 請在左側輸入您的 FRED API Key 以開啟儀表板。")
