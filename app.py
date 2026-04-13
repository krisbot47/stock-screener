import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import json
import os
from datetime import datetime
import pytz

st.set_page_config(page_title="Pro Trading Terminal", layout="wide")
st.title("📈 Aktsiad | Krüpto | Forex | Terminal")

# --- TURUAVA KELL ---
def get_market_status():
    """Tagastab turude staatuse"""
    now_utc = datetime.now(pytz.UTC)
    
    ny = pytz.timezone('America/New_York')
    london = pytz.timezone('Europe/London')
    tokyo = pytz.timezone('Asia/Tokyo')
    sydney = pytz.timezone('Australia/Sydney')
    
    markets = []
    
    # USA
    ny_now = now_utc.astimezone(ny)
    ny_open = ny_now.replace(hour=9, minute=30, second=0, microsecond=0)
    ny_close = ny_now.replace(hour=16, minute=0, second=0, microsecond=0)
    ny_is_open = ny_open <= ny_now <= ny_close and ny_now.weekday() < 5
    markets.append({
        "name": "🇺🇸 USA (NY)",
        "timezone": "ET",
        "local_time": ny_now.strftime("%H:%M"),
        "is_open": ny_is_open,
        "hours": "9:30-16:00"
    })
    
    # London
    lon_now = now_utc.astimezone(london)
    lon_open = lon_now.replace(hour=8, minute=0, second=0, microsecond=0)
    lon_close = lon_now.replace(hour=16, minute=30, second=0, microsecond=0)
    lon_is_open = lon_open <= lon_now <= lon_close and lon_now.weekday() < 5
    markets.append({
        "name": "🇬🇧 London",
        "timezone": "GMT",
        "local_time": lon_now.strftime("%H:%M"),
        "is_open": lon_is_open,
        "hours": "8:00-16:30"
    })
    
    # Tokyo
    tok_now = now_utc.astimezone(tokyo)
    tok_morning_open = tok_now.replace(hour=9, minute=0, second=0, microsecond=0)
    tok_morning_close = tok_now.replace(hour=11, minute=30, second=0, microsecond=0)
    tok_afternoon_open = tok_now.replace(hour=12, minute=30, second=0, microsecond=0)
    tok_afternoon_close = tok_now.replace(hour=15, minute=0, second=0, microsecond=0)
    tok_is_open = ((tok_morning_open <= tok_now <= tok_morning_close) or 
                   (tok_afternoon_open <= tok_now <= tok_afternoon_close)) and tok_now.weekday() < 5
    markets.append({
        "name": "🇯🇵 Tokyo",
        "timezone": "JST",
        "local_time": tok_now.strftime("%H:%M"),
        "is_open": tok_is_open,
        "hours": "9:00-15:00"
    })
    
    # Sydney
    syd_now = now_utc.astimezone(sydney)
    syd_open = syd_now.replace(hour=10, minute=0, second=0, microsecond=0)
    syd_close = syd_now.replace(hour=16, minute=0, second=0, microsecond=0)
    syd_is_open = syd_open <= syd_now <= syd_close and syd_now.weekday() < 5
    markets.append({
        "name": "🇦🇺 Sydney",
        "timezone": "AEST",
        "local_time": syd_now.strftime("%H:%M"),
        "is_open": syd_is_open,
        "hours": "10:00-16:00"
    })
    
    next_market = None
    for m in markets:
        if not m["is_open"]:
            next_market = m
            break
    
    return markets, next_market

# --- ANDMEKOGUD ---
STOCKS = ["SOFI", "PLUG", "NNDM", "SNDL", "OGI", "BBIG", "PROG", "GEVO", "CLSK", "RIOT", 
          "MARA", "HUT", "BITF", "ARBK", "WULF", "CIFR", "IREN", "MSTR", "COIN", "HOOD"]

GLOBAL_STOCKS = [
    "SAP.DE", "ASML.AS", "NESN.SW", "NOVO-B.CO", "SIE.DE", "MC.PA", "BP.L", "SHEL.L",
    "7203.T", "9984.T", "005930.KS", "BABA", "JD", "NIO", "SHOP.TO", "RY.TO", "CNQ.TO",
    "BHP.AX", "CBA.AX"
]

CRYPTOS = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "DOGE-USD", 
           "DOT-USD", "MATIC-USD", "LTC-USD", "AVAX-USD", "LINK-USD", "UNI-USD"]

FOREX = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X", 
         "NZDUSD=X", "EURGBP=X", "EURJPY=X", "GBPJPY=X"]

# --- SCREENER LOOGIIKA ---
@st.cache_data(ttl=300)
def analyze_asset(symbol, period_sel):
    try:
        asset = yf.Ticker(symbol)
        hist = asset.history(period=period_sel)
        
        if hist.empty or len(hist) < 30:
            return None, None
            
        current_price = hist['Close'].iloc[-1]
        if pd.isna(current_price) or current_price <= 0:
            return None, None
            
        sma50 = hist['Close'].rolling(50).mean().iloc[-1] if len(hist) >= 50 else current_price
        sma200 = hist['Close'].rolling(200).mean().iloc[-1] if len(hist) >= 200 else current_price
        
        delta = hist['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        with np.errstate(divide='ignore', invalid='ignore'):
            rs = gain / loss
            rsi = float(100 - (100 / (1 + rs)).iloc[-1])
        if np.isnan(rsi) or np.isinf(rsi): rsi = 50.0

        exp12 = hist['Close'].ewm(span=12).mean()
        exp26 = hist['Close'].ewm(span=26).mean()
        macd = exp12 - exp26
        macd_signal = macd.ewm(span=9).mean()

        tr = pd.concat([hist['High']-hist['Low'], abs(hist['High']-hist['Close'].shift()), abs(hist['Low']-hist['Close'].shift())], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().iloc[-1])
        if np.isnan(atr) or np.isinf(atr): atr = current_price * 0.01

        score = 0.0
        if current_price > sma50 > sma200: score += 2.0
        elif current_price < sma50 < sma200: score -= 2.0
        elif sma50 > sma200: score += 0.5
        else: score -= 0.5

        if rsi < 30: score += 1.5
        elif rsi > 70: score -= 1.5

        if len(macd) > 0 and len(macd_signal) > 0:
            if macd.iloc[-1] > macd_signal.iloc[-1]: score += 1.0
            else: score -= 1.0

        direction = "LONG" if score >= 1.5 else ("SHORT" if score <= -1.5 else "NEUTRAL")
        confidence = float(np.clip(50 + score * 8, 20, 90))

        if direction == "LONG":
            stop_loss = current_price - (2.0 * atr)
            take_profit = current_price + (3.0 * atr)
        elif direction == "SHORT":
            stop_loss = current_price + (2.0 * atr)
            take_profit = current_price - (3.0 * atr)
        else:
            stop_loss = current_price * 0.99
            take_profit = current_price * 1.01

        risk = abs(current_price - stop_loss)
        reward = abs(take_profit - current_price)
        rr_ratio = reward / risk if risk > 0.001 else 1.0

        change_1d = float(((current_price / hist['Close'].iloc[-2]) - 1) * 100) if len(hist) > 1 else 0.0
        change_1w = float(((current_price / hist['Close'].iloc[-5]) - 1) * 100) if len(hist) > 5 else 0.0

        signal_emoji = "🟢 LONG" if direction == "LONG" else "🔴 SHORT" if direction == "SHORT" else "⚪ NEUTRAL"

        if direction == "LONG":
            analysis = f"✅ Tõusutrend. RSI {rsi:.1f}. Stop: {stop_loss:.5f}. Siht: {take_profit:.5f}"
        elif direction == "SHORT":
            analysis = f"🔻 Langustrend. RSI {rsi:.1f}. Stop: {stop_loss:.5f}. Siht: {take_profit:.5f}"
        else:
            analysis = f"⏸️ Konsolideerumine. SMA50: {sma50:.5f}, SMA200: {sma200:.5f}"

        tier = "⭐⭐⭐⭐⭐" if score >= 2.0 and confidence >= 65 else "⭐⭐⭐⭐" if score >= 1.5 else "⭐⭐⭐"
        tier_label = "🔥 PARIM VALIK" if tier == "⭐⭐⭐⭐⭐" else "✅ HEA VÕIMALUS"
        risk_pct = (risk/current_price*100)
        risk_level = "🟢 MADAL" if risk_pct < 1 else "🔴 KÕRGE" if risk_pct > 3 else "🟡 KESKMINE"
        timing = "✅ SISSE KOHE" if (direction == "LONG" and rsi < 40) or (direction == "SHORT" and rsi > 60) else "⏳ OOTA"
        timing_reason = "Hea sisemispunkt" if timing == "✅ SISSE KOHE" else "Oota paremat hinda"

        return hist, {
            "Symbol": symbol, "Price": round(current_price, 5), "Direction": direction, "Signal": signal_emoji,
            "Confidence_%": round(confidence, 1), "Entry": round(current_price, 5),
            "Stop_Loss": round(max(stop_loss, 0.0001), 5), "Take_Profit": round(take_profit, 5),
            "Risk_%": round(risk_pct, 2), "Reward_%": round((reward/current_price)*100, 2),
            "Risk_Reward": round(rr_ratio, 2), "Change_1d_%": round(change_1d, 2), "Change_1w_%": round(change_1w, 2),
            "RSI": round(rsi, 1), "ATR": round(atr, 6), "Score": round(score, 2),
            "SMA_50": round(sma50, 5), "SMA_200": round(sma200, 5), "Analysis": analysis,
            "Tier": tier, "Tier_Label": tier_label, "Risk_Level": risk_level, 
            "Timing": timing, "Timing_Reason": timing_reason
        }
    except Exception:
        return None, None

def get_asset_links(symbol):
    base_symbol = symbol.replace("-USD", "").replace("=X", "")
    if "=X" in symbol:
        links = {
            "TradingView": f"https://www.tradingview.com/symbols/FX-{base_symbol.replace('=X','')}/",
            "Investing.com": f"https://www.investing.com/currencies/{base_symbol.replace('=X','').lower()}",
        }
    elif "-USD" in symbol:
        links = {
            "Yahoo Finance": f"https://finance.yahoo.com/quote/{symbol}",
            "TradingView": f"https://www.tradingview.com/symbols/CRYPTO-{base_symbol}/",
            "CoinMarketCap": f"https://coinmarketcap.com/currencies/{base_symbol.lower().replace('-usd','')}/",
        }
    else:
        links = {
            "Yahoo Finance": f"https://finance.yahoo.com/quote/{symbol}",
            "TradingView": f"https://www.tradingview.com/symbols/NASDAQ-{symbol}/",
        }
    return links

# --- PORTFOLIO ---
PORTFOLIO_FILE = "portfolio.json"
def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f: return json.load(f)
    return []

def save_portfolio(data):
    with open(PORTFOLIO_FILE, "w") as f: json.dump(data, f, indent=4)

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()

# --- SIDEBAR ---
with st.sidebar:
    st.header("🌍 Turg")
    market_type = st.radio("Vali turg:", ["📊 Aktsiad", "₿ Krüpto", "💱 Forex"], index=0)
    period = st.selectbox("Ajaperiood", ["1mo", "3mo", "6mo", "1y"], index=2)
    
    st.divider()
    st.header("🌐 Turude staatus")
    markets, next_market = get_market_status()
    for m in markets:
        status = "🟢 AVATUD" if m["is_open"] else "🔴 SULETUD"
        st.text(f"{m['name']}: {status} ({m['local_time']})")
    
    show_global = st.checkbox("🌍 Kaasa globaalsed aktsiad", value=False)
    
    st.divider()
    st.header("🔎 Filtreerimine")
    max_price = st.number_input("Maks hind", min_value=0.1, max_value=10000.0, value=10.0)
    min_confidence = st.slider("Min tõenäosus (%)", 30, 85, 45, 5)
    only_strong = st.checkbox("Ainult tugevad (R:R > 1.5)", False)

# --- LIIDES ---
tab1, tab2 = st.tabs(["🔍 Screener", "💼 Portfell"])

with tab1:
    if market_type == "📊 Aktsiad":
        SYMBOLS = STOCKS + (GLOBAL_STOCKS if show_global else [])
        st.header("📊 Aktsiad" + (" + Globaalsed" if show_global else ""))
    elif market_type == "₿ Krüpto":
        SYMBOLS = CRYPTOS
        st.header("₿ Krüptovaluutad")
    else:
        SYMBOLS = FOREX
        st.header("💱 Forex Valuutapaarid")

    st.write(f"🔄 Skannin {len(SYMBOLS)} sümbolit...")
    results = []
    
    for sym in SYMBOLS:
        hist, data = analyze_asset(sym, period)
        if data is not None:
            if data["Price"] <= max_price and data["Confidence_%"] >= min_confidence:
                if (not only_strong) or (data["Risk_Reward"] >= 1.5):
                    results.append(data)

    if not results:
        st.warning("⚠️ Ühtegi setup'i ei leitud. Proovi muuta filtreid.")
    else:
        results = sorted(results, key=lambda x: x["Score"], reverse=True)
        df_results = pd.DataFrame(results)
        
        st.subheader(f"🏆 TOP 3")
        top3 = df_results.head(3)
        cols = st.columns(3)
        for i, (_, row) in enumerate(top3.iterrows()):
            with cols[i]:
                st.markdown(f"""
                ### {row['Tier']} {row['Symbol']}
                **{row['Tier_Label']}**  
                💰 Hind: **{row['Price']:.5f}**  
                📊 Signaal: **{row['Signal']}**  
                {row['Risk_Level']} Risk  
                ✅ **{row['Timing']}**
                """)
                if st.button(f"📊 Vaata {row['Symbol']}", key=f"top_{row['Symbol']}"):
                    st.session_state.selected_symbol = row['Symbol']
        
        st.divider()
        st.subheader(f"📋 Kõik ({len(results)})")
        view_option = st.radio("Kuidas vaadata?", ["📊 Tabel", "🎯 Ainult parimad", "🟢 Ainult LONG", "🔴 Ainult SHORT"], horizontal=True)
        
        if view_option == "📊 Tabel":
            st.dataframe(df_results, use_container_width=True)
        elif view_option == "🎯 Ainult parimad":
            st.dataframe(df_results[df_results["Tier"].isin(["⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"])], use_container_width=True)
        elif view_option == "🟢 Ainult LONG":
            st.dataframe(df_results[df_results["Direction"] == "LONG"], use_container_width=True)
        else:
            st.dataframe(df_results[df_results["Direction"] == "SHORT"], use_container_width=True)

        st.divider()
        
        default_symbol = st.session_state.get('selected_symbol', df_results.iloc[0]['Symbol'])
        if default_symbol not in df_results["Symbol"].values:
            default_symbol = df_results.iloc[0]['Symbol']
            
        selected = st.selectbox("🔍 Vali sümbol detailseks info", df_results["Symbol"], 
                               index=list(df_results["Symbol"]).index(default_symbol))
        
        row = df_results[df_results["Symbol"] == selected].iloc[0]

        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("💰 Hind", f"{row['Price']:.5f}")
        col2.metric("📊 Signaal", row["Signal"])
        col3.metric("🔮 Tõenäosus", f"{row['Confidence_%']}%")
        col4.metric("⭐ Reiting", row["Tier"].split().count("⭐"))
        col5.metric("⚖️ R:R", f"1:{row['Risk_Reward']}")
        col6.metric("📈 1d", f"{row['Change_1d_%']:+.2f}%")
        
        st.markdown("### 🎯 Kauplemissoovitus")
        c1, c2, c3 = st.columns(3)
        c1.info(f"**{row['Timing']}**\n\n_{row['Timing_Reason']}_")
        c2.success(f"**{row['Risk_Level']}**\n\nRisk: {row['Risk_%']}%")
        c3.warning(f"**{row['Tier_Label']}**\n\n{row['Tier']}")
        
        st.info(f"🤖 {row['Analysis']}")
        
        st.divider()
        st.subheader("📰 Uudised ja Lingid")
        
        try:
            asset = yf.Ticker(selected)
            news = asset.news
            if news and len(news) > 0:
                st.markdown("#### 📰 Viimased uudised")
                for item in news[:3]:
                    title = item.get('title', 'Pealkiri puudub')
                    link = item.get('link', '#')
                    with st.expander(f"📄 {title[:60]}..."):
                        if link and link != '#':
                            st.markdown(f"[🔗 Loe edasi]({link})")
            else:
                st.info("📭 Uudiseid ei leitud")
        except Exception:
            st.warning("⚠️ Uudiseid ei saanud laadida")

        st.markdown("#### 🔗 Kasulikud lingid")
        links = get_asset_links(selected)
        lcols = st.columns(3)
        for i, (name, url) in enumerate(links.items()):
            with lcols[i % 3]:
                st.markdown(f"[🔗 {name}]({url})")
        
        with st.expander("📊 Täpsemad näitajad"):
            c1, c2, c3, c4 = st.columns(4)
            c1.write(f"**SMA 50:** {row['SMA_50']:.5f}")
            c2.write(f"**SMA 200:** {row['SMA_200']:.5f}")
            c3.write(f"**RSI:** {row['RSI']}")
            c4.write(f"**ATR:** {row['ATR']:.6f}")
            st.divider()
            sc1, sc2, sc3 = st.columns(3)
            sc1.metric("📍 Sisenemine", f"{row['Entry']:.5f}")
            sc2.metric("🛑 Stop-Loss", f"{row['Stop_Loss']:.5f}")
            sc3.metric("🎯 Take-Profit", f"{row['Take_Profit']:.5f}")

with tab2:
    st.header("💼 Minu Portfell")
    with st.expander("➕ Lisa positsioon", expanded=True):
        with st.form("add_pos"):
            c1, c2, c3 = st.columns(3)
            with c1: sym = st.text_input("Sümbol", "").upper()
            with c2: b_price = st.number_input("Ostuhind", min_value=0.0001, step=0.0001, format="%.5f")
            with c3: qty = st.number_input("Kogus", min_value=0.000001, step=0.01)
            submitted = st.form_submit_button("✅ Lisa", use_container_width=True)
            
        if submitted and sym:
            st.session_state.portfolio.append({"Symbol": sym, "Buy_Price": b_price, "Qty": qty})
            save_portfolio(st.session_state.portfolio)
            st.success(f"✅ {sym} lisatud!")
            st.rerun()

    if st.session_state.portfolio:
        df_port = pd.DataFrame(st.session_state.portfolio)
        if st.button("🔄 Värskenda hinnad", type="primary"):
            with st.spinner("Laadin hindu..."):
                prices = {}
                for s in df_port["Symbol"].unique():
                    try: 
                        prices[s] = yf.Ticker(s).history(period="2d")["Close"].iloc[-1]
                    except: 
                        prices[s] = np.nan
                    
                df_port["Current_Price"] = df_port["Symbol"].map(prices)
                df_port["Cost_Basis"] = df_port["Buy_Price"] * df_port["Qty"]
                df_port["Current_Value"] = df_port["Current_Price"] * df_port["Qty"]
                df_port["PnL_$"] = df_port["Current_Value"] - df_port["Cost_Basis"]
                df_port["PnL_%"] = ((df_port["Current_Price"] / df_port["Buy_Price"]) - 1) * 100
                
                st.session_state.portfolio = df_port.to_dict("records")
                save_portfolio(st.session_state.portfolio)
                st.rerun()

        def color_pnl(val):
            if val > 0: return "color: #00ff88; font-weight: bold"
            elif val < 0: return "color: #ff4d4d; font-weight: bold"
            return ""

        st.subheader("📊 Positsioonid")
        st.dataframe(df_port.style.format({
            "Buy_Price": "{:.5f}", "Current_Price": "{:.5f}", 
            "Cost_Basis": "${:.2f}", "Current_Value": "${:.2f}", 
            "PnL_$": "${:.2f}", "PnL_%": "{:.2f}%"
        }).applymap(color_pnl, subset=['PnL_$', 'PnL_%']), use_container_width=True, hide_index=True)

        total = df_port["Current_Value"].sum()
        cost = df_port["Cost_Basis"].sum()
        pnl = total - cost
        pnl_pct = (pnl / cost * 100) if cost > 0 else 0
        
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Investeeritud", f"${cost:,.2f}")
        c2.metric("Hetke väärtus", f"${total:,.2f}")
        c3.metric("P&L", f"${pnl:,.2f} ({pnl_pct:.2f}%)")
        
        if st.button("🗑️ Tühjenda", type="secondary"):
            st.session_state.portfolio = []
            save_portfolio([])
            st.rerun()
    else:
        st.info("📝 Portfell on tühi")