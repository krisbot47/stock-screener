import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import json
import os
from datetime import datetime
import pytz

# ==========================================
# 🔒 PAROOLIKAITSE
# ==========================================
SALAJANE_PAROOL = "kauple2024"  # MUUDA PAROOLI VAJADUSEL!

if "parool_sisestatud" not in st.session_state:
    st.session_state.parool_sisestatud = False

if not st.session_state.parool_sisestatud:
    st.title("🔒 Ligipääs piiratud")
    st.write("Sisesta parool, et näha aktsiate analüüse ja hallata portfelli.")
    st.info("💡 **Juhend:**\n1. Sisesta parool\n2. Sisesta oma nimi\n3. Lisa oma aktsiad\n4. Vaata täiustatud signaale")
    
    parool = st.text_input("Parool:", type="password")
    
    if st.button("Logi sisse", use_container_width=True):
        if parool == SALAJANE_PAROOL:
            st.session_state.parool_sisestatud = True
            st.rerun()
        else:
            st.error("❌ Vale parool!")
    st.stop()

# ==========================================
# 🌐 PEALEHKITUS JA TURU KELL
# ==========================================
st.set_page_config(page_title="Pro Trading Terminal", layout="wide")
st.title("📈 Aktsiad | Krüpto | Forex | Terminal")

def get_market_status():
    now_utc = datetime.now(pytz.UTC)
    ny = pytz.timezone('America/New_York')
    london = pytz.timezone('Europe/London')
    tokyo = pytz.timezone('Asia/Tokyo')
    sydney = pytz.timezone('Australia/Sydney')
    
    markets = []
    for tz_name, name, open_h, close_h, label in [
        (ny, "🇺🇸 USA (NY)", 9, 30, 16, 0, "ET", "9:30-16:00"),
        (london, "🇬 London", 8, 0, 16, 30, "GMT", "8:00-16:30"),
        (tokyo, "🇯 Tokyo", 9, 0, 15, 0, "JST", "9:00-15:00"),
        (sydney, "🇦 Sydney", 10, 0, 16, 0, "AEST", "10:00-16:00")
    ]:
        now = now_utc.astimezone(tz_name)
        o = now.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
        c = now.replace(hour=close_h, minute=close_m, second=0, microsecond=0)
        is_open = o <= now <= c and now.weekday() < 5
        markets.append({"name": name, "timezone": tz_label, "local_time": now.strftime("%H:%M"), "is_open": is_open, "hours": hours})
    return markets

# ==========================================
# 📦 ANDMEKOGUD
# ==========================================
STOCKS = ["SOFI", "PLUG", "NNDM", "SNDL", "OGI", "BBIG", "PROG", "GEVO", "CLSK", "RIOT", 
          "MARA", "HUT", "BITF", "ARBK", "WULF", "CIFR", "IREN", "MSTR", "COIN", "HOOD"]
GLOBAL_STOCKS = ["SAP.DE", "ASML.AS", "NESN.SW", "NOVO-B.CO", "SIE.DE", "MC.PA", "BP.L", "SHEL.L",
                 "7203.T", "9984.T", "005930.KS", "BABA", "JD", "NIO", "SHOP.TO", "RY.TO", "CNQ.TO", "BHP.AX", "CBA.AX"]
CRYPTOS = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "DOGE-USD", 
           "DOT-USD", "MATIC-USD", "LTC-USD", "AVAX-USD", "LINK-USD", "UNI-USD"]
FOREX = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X", 
         "NZDUSD=X", "EURGBP=X", "EURJPY=X", "GBPJPY=X"]

# ==========================================
# 🧠 UUENDATUD SCREENER LOOGIIKA
# ==========================================
@st.cache_data(ttl=300)
def analyze_asset(symbol, period_sel):
    try:
        asset = yf.Ticker(symbol)
        hist = asset.history(period=period_sel)
        if hist.empty or len(hist) < 30: return None, None
            
        current_price = hist['Close'].iloc[-1]
        if pd.isna(current_price) or current_price <= 0: return None, None
            
        # Põhinäitajad
        sma50 = hist['Close'].rolling(50).mean().iloc[-1] if len(hist) >= 50 else current_price
        sma200 = hist['Close'].rolling(200).mean().iloc[-1] if len(hist) >= 200 else current_price
        
        # RSI
        delta = hist['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        with np.errstate(divide='ignore', invalid='ignore'):
            rs = gain / loss
            rsi = float(100 - (100 / (1 + rs)).iloc[-1])
        if np.isnan(rsi) or np.isinf(rsi): rsi = 50.0

        # MACD
        exp12 = hist['Close'].ewm(span=12).mean()
        exp26 = hist['Close'].ewm(span=26).mean()
        macd = exp12 - exp26
        macd_signal = macd.ewm(span=9).mean()

        # ATR & Volatiilsus
        tr = pd.concat([hist['High']-hist['Low'], abs(hist['High']-hist['Close'].shift()), abs(hist['Low']-hist['Close'].shift())], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().iloc[-1])
        if np.isnan(atr) or np.isinf(atr) or atr == 0: atr = current_price * 0.01
        vol_pct = (atr / current_price) * 100

        # Volume Analüüs
        avg_vol = hist['Volume'].rolling(20).mean().iloc[-1]
        curr_vol = hist['Volume'].iloc[-1]
        vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1.0

        # ADX (Trendi tugevus)
        plus_dm = hist['High'].diff()
        minus_dm = -hist['Low'].diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        plus_di = 100 * (plus_dm.rolling(14).mean() / tr.rolling(14).mean())
        minus_di = 100 * (minus_dm.rolling(14).mean() / tr.rolling(14).mean())
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = float(dx.rolling(14).mean().iloc[-1])
        if np.isnan(adx): adx = 25.0

        # Bollinger Bands
        bb_sma = hist['Close'].rolling(20).mean()
        bb_std = hist['Close'].rolling(20).std()
        bb_upper = bb_sma + (bb_std * 2)
        bb_lower = bb_sma - (bb_std * 2)
        bb_pos = (current_price - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1]) if (bb_upper.iloc[-1] != bb_lower.iloc[-1]) else 0.5

        #  FILTRID (Kvaliteedikontroll)
        if current_price < 1.0: return None, None  # Liiga odav
        if vol_ratio < 0.4: return None, None      # Liiga vähe mahtu
        if adx < 18: return None, None             # Turg on "surnud" / konsolideerub

        # 📊 KAALUTUD SKOORIMINE
        score = 0.0
        # Trend (40%)
        if current_price > sma50 > sma200: score += 2.0 * 0.4
        elif current_price < sma50 < sma200: score -= 2.0 * 0.4
        elif sma50 > sma200: score += 0.5 * 0.4
        else: score -= 0.5 * 0.4
        # Momentum/RSI (20%)
        if rsi < 30: score += 1.5 * 0.2
        elif rsi > 70: score -= 1.5 * 0.2
        # MACD (15%)
        if len(macd) > 0 and len(macd_signal) > 0:
            if macd.iloc[-1] > macd_signal.iloc[-1]: score += 1.0 * 0.15
            else: score -= 1.0 * 0.15
        # Volume (15%)
        if vol_ratio > 1.5: score += 1.0 * 0.15
        elif vol_ratio < 0.8: score -= 0.5 * 0.15
        # ADX (10%)
        if adx > 25: score += 1.0 * 0.10
        elif adx < 20: score -= 0.5 * 0.10

        direction = "LONG" if score >= 1.2 else ("SHORT" if score <= -1.2 else "NEUTRAL")
        confidence = float(np.clip(50 + score * 12, 25, 92))

        # 🎯 DÜNAAMILINE RISKI JUHTIMINE
        if vol_pct > 4.0: sl_mult, tp_mult = 2.5, 4.0
        elif vol_pct < 1.5: sl_mult, tp_mult = 1.5, 2.5
        else: sl_mult, tp_mult = 2.0, 3.0

        if direction == "LONG":
            stop_loss = current_price - (sl_mult * atr)
            take_profit = current_price + (tp_mult * atr)
        elif direction == "SHORT":
            stop_loss = current_price + (sl_mult * atr)
            take_profit = current_price - (tp_mult * atr)
        else:
            stop_loss = current_price * 0.98
            take_profit = current_price * 1.02

        stop_loss = max(stop_loss, current_price * 0.5)
        take_profit = max(take_profit, current_price * 1.01)

        risk = abs(current_price - stop_loss)
        reward = abs(take_profit - current_price)
        rr_ratio = reward / risk if risk > 0.001 else 1.0
        risk_pct = (risk / current_price) * 100

        change_1d = float(((current_price / hist['Close'].iloc[-2]) - 1) * 100) if len(hist) > 1 else 0.0
        change_1w = float(((current_price / hist['Close'].iloc[-5]) - 1) * 100) if len(hist) > 5 else 0.0

        signal_emoji = "🟢 LONG" if direction == "LONG" else "🔴 SHORT" if direction == "SHORT" else "⚪ NEUTRAL"
        
        vol_tag = f"Vol:{vol_ratio:.1f}x" if vol_ratio > 1.2 else ""
        if direction == "LONG":
            analysis = f"✅ Tõusutrend. RSI:{rsi:.0f} ADX:{adx:.0f} {vol_tag}. Stop:{stop_loss:.4f} TP:{take_profit:.4f}"
        elif direction == "SHORT":
            analysis = f"🔻 Langustrend. RSI:{rsi:.0f} ADX:{adx:.0f} {vol_tag}. Stop:{stop_loss:.4f} TP:{take_profit:.4f}"
        else:
            analysis = f"⏸️ Oota. RSI:{rsi:.0f} ADX:{adx:.0f}. Turg konsolideerub."

        tier = "⭐⭐⭐⭐⭐" if score >= 1.8 and confidence >= 70 else "⭐⭐⭐⭐" if score >= 1.2 else "⭐⭐⭐"
        tier_label = "🔥 TUGEV SIGNAAL" if tier == "⭐⭐⭐⭐⭐" else "✅ HEA VÕIMALUS"
        risk_level = "🟢 MADAL" if risk_pct < 1.5 else "🔴 KÕRGE" if risk_pct > 4.0 else "🟡 KESKMINE"
        timing = "✅ SISSE KOHE" if (direction == "LONG" and rsi < 45) or (direction == "SHORT" and rsi > 55) else "⏳ OOTA PULLBACK"
        timing_reason = "Momentum soosib" if timing == "✅ SISSE KOHE" else "Oota paremat hinda"

        return hist, {
            "Symbol": symbol, "Price": round(current_price, 5), "Direction": direction, "Signal": signal_emoji,
            "Confidence_%": round(confidence, 1), "Entry": round(current_price, 5),
            "Stop_Loss": round(stop_loss, 5), "Take_Profit": round(take_profit, 5),
            "Risk_%": round(risk_pct, 2), "Reward_%": round((reward/current_price)*100, 2),
            "Risk_Reward": round(rr_ratio, 2), "Change_1d_%": round(change_1d, 2), "Change_1w_%": round(change_1w, 2),
            "RSI": round(rsi, 1), "ATR": round(atr, 6), "Score": round(score, 2),
            "SMA_50": round(sma50, 5), "SMA_200": round(sma200, 5), "Analysis": analysis,
            "Tier": tier, "Tier_Label": tier_label, "Risk_Level": risk_level, 
            "Timing": timing, "Timing_Reason": timing_reason,
            "ADX": round(adx, 1), "Vol_Ratio": round(vol_ratio, 2), "BB_Pos": round(bb_pos, 2)
        }
    except Exception:
        return None, None

def get_asset_links(symbol):
    base = symbol.replace("-USD", "").replace("=X", "")
    if "=X" in symbol:
        return {"TradingView": f"https://www.tradingview.com/symbols/FX-{base}/", "Investing.com": f"https://www.investing.com/currencies/{base.lower()}"}
    elif "-USD" in symbol:
        return {"Yahoo Finance": f"https://finance.yahoo.com/quote/{symbol}", "TradingView": f"https://www.tradingview.com/symbols/CRYPTO-{base}/", "CoinMarketCap": f"https://coinmarketcap.com/currencies/{base.lower().replace('-usd','')}/"}
    else:
        return {"Yahoo Finance": f"https://finance.yahoo.com/quote/{symbol}", "TradingView": f"https://www.tradingview.com/symbols/NASDAQ-{symbol}/"}

# ==========================================
# 🖥️ LIIDES
# ==========================================
with st.sidebar:
    st.header("🌍 Turg")
    market_type = st.radio("Vali turg:", ["📊 Aktsiad", "₿ Krüpto", "💱 Forex"], index=0)
    period = st.selectbox("Ajaperiood", ["1mo", "3mo", "6mo", "1y"], index=2)
    
    st.divider()
    st.header("🌐 Turude staatus")
    for m in get_market_status():
        st.text(f"{m['name']}: {'🟢 AVATUD' if m['is_open'] else '🔴 SULETUD'} ({m['local_time']})")
    
    show_global = st.checkbox("🌍 Kaasa globaalsed aktsiad", value=False)
    
    st.divider()
    st.header("🔎 Filtreerimine")
    max_price = st.number_input("Maks hind", min_value=0.1, max_value=10000.0, value=10.0)
    min_confidence = st.slider("Min tõenäosus (%)", 30, 85, 45, 5)
    only_strong = st.checkbox("Ainult tugevad (R:R > 1.5)", False)

tab1, tab2 = st.tabs(["🔍 Screener", "💼 Portfell"])

with tab1:
    if market_type == "📊 Aktsiad":
        SYMBOLS = STOCKS + (GLOBAL_STOCKS if show_global else [])
        st.header("📊 Aktsiad" + (" + Globaalsed" if show_global else ""))
    elif market_type == "₿ Krüpto": SYMBOLS = CRYPTOS; st.header("₿ Krüptovaluutad")
    else: SYMBOLS = FOREX; st.header("💱 Forex Valuutapaarid")

    st.write(f"🔄 Skannin {len(SYMBOLS)} sümbolit (uuendatud algoritm)...")
    results = []
    for sym in SYMBOLS:
        hist, data = analyze_asset(sym, period)
        if data is not None:
            if data["Price"] <= max_price and data["Confidence_%"] >= min_confidence:
                if (not only_strong) or (data["Risk_Reward"] >= 1.5):
                    results.append(data)

    if not results:
        st.warning("⚠️ Ühtegi kvaliteetset setup'i ei leitud. Proovi muuta filtreid või perioodi.")
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
                {row['Risk_Level']} Risk | ADX: {row['ADX']}  
                ✅ **{row['Timing']}**
                """)
                if st.button(f"📊 Vaata {row['Symbol']}", key=f"top_{row['Symbol']}"):
                    st.session_state.selected_symbol = row['Symbol']
        
        st.divider()
        st.subheader(f"📋 Kõik ({len(results)})")
        view_option = st.radio("Kuidas vaadata?", ["📊 Tabel", "🎯 Ainult parimad", "🟢 Ainult LONG", "🔴 Ainult SHORT"], horizontal=True)
        
        if view_option == "📊 Tabel": st.dataframe(df_results, use_container_width=True)
        elif view_option == "🎯 Ainult parimad": st.dataframe(df_results[df_results["Tier"].isin(["⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"])], use_container_width=True)
        elif view_option == "🟢 Ainult LONG": st.dataframe(df_results[df_results["Direction"] == "LONG"], use_container_width=True)
        else: st.dataframe(df_results[df_results["Direction"] == "SHORT"], use_container_width=True)

        st.divider()
        default_symbol = st.session_state.get('selected_symbol', df_results.iloc[0]['Symbol'])
        if default_symbol not in df_results["Symbol"].values: default_symbol = df_results.iloc[0]['Symbol']
        selected = st.selectbox("🔍 Vali sümbol detailseks info", df_results["Symbol"], index=list(df_results["Symbol"]).index(default_symbol))
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
        st.subheader("🔗 Kasulikud lingid")
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(f"[📊 Yahoo Finance](https://finance.yahoo.com/quote/{selected})")
        with c2: st.markdown(f"[📈 TradingView](https://www.tradingview.com/symbols/{selected.replace('=X','').replace('-','')}/)")
        with c3: st.markdown(f"[💹 Investing.com](https://www.investing.com/equities/{selected.lower()})")
        with c4: st.markdown(f"[📰 MarketWatch](https://www.marketwatch.com/investing/stock/{selected.lower()})")
        
        with st.expander("📊 Täpsemad näitajad ja tasemed"):
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.write(f"**SMA 50:** {row['SMA_50']:.5f}")
            c2.write(f"**SMA 200:** {row['SMA_200']:.5f}")
            c3.write(f"**RSI:** {row['RSI']}")
            c4.write(f"**ADX:** {row['ADX']}")
            c5.write(f"**Vol Ratio:** {row['Vol_Ratio']}x")
            st.divider()
            sc1, sc2, sc3 = st.columns(3)
            sc1.metric("📍 Sisenemine", f"{row['Entry']:.5f}")
            sc2.metric("🛑 Stop-Loss", f"{row['Stop_Loss']:.5f}")
            sc3.metric("🎯 Take-Profit", f"{row['Take_Profit']:.5f}")

with tab2:
    st.header("💼 Minu Portfell")
    if "kasutaja_nimi" not in st.session_state or not st.session_state.kasutaja_nimi:
        st.warning("👋 Palun sisesta oma nimi, et eraldada sinu portfell teistest.")
        nimi = st.text_input("Sinu nimi (nt. Ema, Arno, Mina):", key="nimi_input")
        if st.button("✅ Kinnita nimi"):
            if nimi.strip():
                st.session_state.kasutaja_nimi = nimi.strip()
                st.session_state[f"portfolio_{nimi.strip()}"] = []
                st.rerun()
            else: st.error("Nimi ei tohi olla tühi!")
        st.stop()

    portfolio_key = f"portfolio_{st.session_state.kasutaja_nimi}"
    if portfolio_key not in st.session_state: st.session_state[portfolio_key] = []
    st.info(f"👤 Sisse logitud kui: **{st.session_state.kasutaja_nimi}**")

    with st.expander("➕ Lisa positsioon", expanded=True):
        with st.form("add_pos"):
            c1, c2, c3 = st.columns(3)
            with c1: sym = st.text_input("Sümbol", "").upper()
            with c2: b_price = st.number_input("Ostuhind ($)", min_value=0.0001, step=0.01)
            with c3: qty = st.number_input("Kogus", min_value=0.000001, step=0.01)
            submitted = st.form_submit_button("✅ Lisa", use_container_width=True)
        if submitted and sym:
            st.session_state[portfolio_key].append({"Symbol": sym, "Buy_Price": b_price, "Qty": qty})
            st.success(f"✅ {sym} lisatud!")
            st.rerun()

    if st.session_state[portfolio_key]:
        df_port = pd.DataFrame(st.session_state[portfolio_key])
        if st.button("🔄 Värskenda hinnad", type="primary"):
            with st.spinner("Laadin hindu..."):
                prices = {s: yf.Ticker(s).history(period="2d")["Close"].iloc[-1] for s in df_port["Symbol"].unique()}
                df_port["Current_Price"] = df_port["Symbol"].map(prices)
                df_port["Cost_Basis"] = df_port["Buy_Price"] * df_port["Qty"]
                df_port["Current_Value"] = df_port["Current_Price"] * df_port["Qty"]
                df_port["PnL_$"] = df_port["Current_Value"] - df_port["Cost_Basis"]
                df_port["PnL_%"] = ((df_port["Current_Price"] / df_port["Buy_Price"]) - 1) * 100
                st.session_state[portfolio_key] = df_port.to_dict("records")
                st.rerun()

        def color_pnl(val):
            return "color: #00ff88; font-weight: bold" if val > 0 else "color: #ff4d4d; font-weight: bold" if val < 0 else ""

        st.subheader("📊 Sinu positsioonid")
        st.dataframe(df_port.style.format({"Buy_Price": "{:.5f}", "Current_Price": "{:.5f}", "Cost_Basis": "${:.2f}", "Current_Value": "${:.2f}", "PnL_$": "${:.2f}", "PnL_%": "{:.2f}%"}).map(color_pnl, subset=['PnL_$', 'PnL_%']), use_container_width=True, hide_index=True)

        total = df_port["Current_Value"].sum()
        cost = df_port["Cost_Basis"].sum()
        pnl = total - cost
        pnl_pct = (pnl / cost * 100) if cost > 0 else 0
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Investeeritud", f"${cost:,.2f}")
        c2.metric("Hetke väärtus", f"${total:,.2f}")
        c3.metric("P&L", f"${pnl:,.2f} ({pnl_pct:.2f}%)")
        if st.button("🗑️ Tühjenda minu portfell", type="secondary"):
            st.session_state[portfolio_key] = []
            st.rerun()
    else:
        st.info("📝 Portfell on tühi. Lisa esimene positsioon ülal.")
