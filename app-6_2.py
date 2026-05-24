import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import json
import os

# ==================================================
# Streamlit
# ==================================================
st.set_page_config(layout="wide")

# ==================================================
# 保存ファイル
# ==================================================
SAVE_FILE = "settings.json"

# ==================================================
# 足種
# ==================================================
INTERVAL_OPTIONS = {
    "1分足": "1m",
    "5分足": "5m",
    "15分足": "15m",
    "30分足": "30m",
    "1時間足": "1h",
    "1日足": "1d",
    "1週足": "1wk",
    "1ヶ月足": "1mo"
}

# ==================================================
# 初期設定
# ==================================================
DEFAULT_SETTINGS = {
    "symbols": ["6758.T", "7974.T", "9984.T"],
    "charts": [
        {"value": 5, "unit": "d", "interval": "1m"},
        {"value": 3, "unit": "m", "interval": "1h"},
        {"value": 1, "unit": "y", "interval": "1d"}
    ]
}

# ==================================================
# 設定ロード
# ==================================================
def load_settings():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_SETTINGS

# ==================================================
# 設定保存
# ==================================================
def save_settings(settings):
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

# ==================================================
# session_state
# ==================================================
if "settings" not in st.session_state:
    st.session_state.settings = load_settings()

settings = st.session_state.settings

# ==================================================
# 安全な Series 化
# ==================================================
def safe_series(data):
    if isinstance(data, pd.DataFrame):
        data = data.iloc[:, 0]
    if hasattr(data, "ndim") and data.ndim > 1:
        data = data[:, 0]
    if hasattr(data, "flatten"):
        data = data.flatten()
    data = pd.Series(data)
    data = pd.to_numeric(data, errors="coerce")
    data = data.dropna()
    return data.reset_index(drop=True)
# ==================================================
# JPX 銘柄一覧 CSV 読み込み
# ==================================================
JPX_CSV_URL = "https://raw.githubusercontent.com/YH-1960/jpx-list/refs/heads/main/data_j.csv"

@st.cache_data(ttl=86400)
def load_jpx_list():
    df = pd.read_csv(JPX_CSV_URL, encoding="utf-8")
    df["コード"] = df["コード"].astype(str).str.zfill(4)
    return df

def get_company_name_from_jpx(symbol):
    code = symbol.replace(".T", "")
    df = load_jpx_list()
    row = df[df["コード"] == code]
    if len(row) == 0:
        return ""
    return row.iloc[0]["銘柄名"]


# ==================================================
# yfinance 制限対応
# ==================================================
def get_allowed_period(value, unit, interval):
    if unit == "d":
        days = value
    elif unit == "w":
        days = value * 7
    elif unit == "m":
        days = value * 30
    elif unit == "y":
        days = value * 365
    else:
        days = value

    if interval == "1m" and days > 7:
        return "7d"
    if interval in ["5m", "15m", "30m"] and days > 60:
        return "60d"
    if interval == "1h" and days > 730:
        return "730d"

    if unit == "d":
        return f"{value}d"
    elif unit == "w":
        return f"{value}wk"
    elif unit == "m":
        return f"{value}mo"
    elif unit == "y":
        return f"{value}y"

    return "1y"

# ==================================================
# データ取得
# ==================================================
@st.cache_data(ttl=300)
def fetch_stock_data(symbol, period, interval):
    try:
        ticker = yf.Ticker(symbol)
        df = yf.download(
            symbol,
            period=period,
            interval=interval,
            auto_adjust=True,
            progress=False,
            threads=False,
            group_by="column"
        )

        if df.empty:
            return None

        for col_name in ["Open", "High", "Low", "Close", "Volume"]:
            if col_name in df.columns:
                data = df[col_name]
                if isinstance(data, pd.DataFrame):
                    data = data.iloc[:, 0]
                df[col_name] = pd.to_numeric(data, errors="coerce")

        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert("Asia/Tokyo")
        else:
            df.index = df.index.tz_convert("Asia/Tokyo")

        currency = "JPY"
        try:
            currency = ticker.fast_info.get("currency", "JPY")
        except Exception:
            pass

        return {"df": df, "currency": currency}

    except Exception as e:
        return {"error": str(e)}

# ==================================================
# チャート表示（最上部）
# ==================================================
symbols = settings["symbols"]

for idx, chart in enumerate(settings["charts"]):
    value = chart["value"]
    unit = chart["unit"]
    interval = chart["interval"]

    period = get_allowed_period(value, unit, interval)
    # title = f"{value}{unit} ({interval})"

    cols = st.columns(len(symbols))

    for col, symbol in zip(cols, symbols):
        data = fetch_stock_data(symbol, period, interval)

        # タイトルを銘柄コード付きに変更
        title = (
          f"<b>{value}{unit} ({interval})</b>"
          f"　<span style='font-size:14px;color:gray;'>{symbol}</span>"
        )

        if data is None or "error" in data:
            col.error("データなし")
            continue

        df = data["df"]
        currency = data["currency"]

        # --- 銘柄名を取得 ---
        company_name = get_company_name_from_jpx(symbol)

        open_data = safe_series(df["Open"])
        high_data = safe_series(df["High"])
        low_data = safe_series(df["Low"])
        close_data = safe_series(df["Close"])

        # データ取得（直近2営業日）
        stock = yf.Ticker(symbol)
        hist = stock.history(period="2d")

        # 最新終値
        latest_close = hist["Close"].iloc[-1]

        # 前日終値
        prev_close = hist["Close"].iloc[-2]

        diff = latest_close - prev_close
        pct = diff / prev_close * 100 if prev_close != 0 else 0
        color = "red" if diff > 0 else "blue" if diff < 0 else "gray"

        # --- 1行目だけ銘柄コード + 銘柄名 + 株価を表示 ---
        if idx == 0:
            col.markdown(
                f"""
                <span style="font-size:20px;font-weight:bold;">{symbol} {company_name}</span><br>
                <span style="font-size:24px;font-weight:bold;">{latest_close:.2f} {currency}</span><br>
                <span style="color:{color};font-size:15px;">
                {diff:+.2f} ({pct:+.2f}%)
                </span>
                """,
                unsafe_allow_html=True
            )

        # チャート本体
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=open_data,
            high=high_data,
            low=low_data,
            close=close_data,
            increasing_line_color="red",
            decreasing_line_color="blue"
        ))

        fig.update_layout(
            # title=symbol,
            title=title,
            height=350,
            xaxis_rangeslider_visible=False,
            showlegend=False,
            margin=dict(l=10, r=10, t=40, b=10),
            title_font=dict(size=14)
        )

        # ここに追加！
        fig.update_layout(
           font=dict(size=16),
           title_font=dict(size=20)
        )

        fig.update_xaxes(tickfont=dict(size=14)) # X軸
        fig.update_yaxes(tickfont=dict(size=16)) # Y軸

        # col.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        col.plotly_chart(
           fig,
           use_container_width=True,
           config={
               "displayModeBar": False,
               "staticPlot": True
           }
           # key=f"chart_{idx}_{symbol}"
        )


# ==================================================
# 銘柄リスト & チャート設定（チャートの下で横並び）
# ==================================================
left_col, right_col,dunny_col = st.columns([0.7, 0.7,1.0])

# -----------------------------
# 左：銘柄リスト
# -----------------------------
with left_col:
    st.markdown("## 銘柄リスト")

    symbols = settings["symbols"]

    for i, sym in enumerate(symbols):
       company_name = get_company_name_from_jpx(sym)

       cols = st.columns([4, 0.5, 0.5, 0.8])

       # 銘柄コード + 銘柄名
       cols[0].markdown(
           f"<b>{sym}</b> <span style='color:gray;'>{company_name}</span>",
           unsafe_allow_html=True
       )

       # ↑ ボタン（上へ移動）
       if cols[1].button("↑", key=f"up_{i}"):
          if i > 0:
             symbols[i], symbols[i-1] = symbols[i-1], symbols[i]
             settings["symbols"] = symbols
             save_settings(settings)
             st.rerun()

       # ↓ ボタン（下へ移動）
       if cols[2].button("↓", key=f"down_{i}"):
          if i < len(symbols) - 1:
             symbols[i], symbols[i+1] = symbols[i+1], symbols[i]
             settings["symbols"] = symbols
             save_settings(settings)
             st.rerun()

       # 削除ボタン
       if cols[3].button("削除", key=f"del_{i}"):
           symbols.pop(i)
           settings["symbols"] = symbols
           save_settings(settings)
           st.rerun()

    new_symbol = st.text_input("銘柄を追加", "")
    if st.button("追加"):
        if new_symbol.strip():
            symbols.append(new_symbol.strip())
            settings["symbols"] = symbols
            save_settings(settings)   # ← 追加
            st.rerun()

# -----------------------------
# 右：チャート設定
# -----------------------------
with right_col:
    st.markdown("## チャート設定")

    period_units = ["d", "w", "m", "y"]

    for i in range(3):
        chart = settings["charts"][i]

        with st.expander(
            f"チャート {i+1}（{chart['value']}{chart['unit']} / {chart['interval']}）",
            expanded=False
        ):
            col1, col2, col3 = st.columns(3)

            with col1:
                value = st.number_input(
                    f"期間{i+1}",
                    min_value=1,
                    max_value=5000,
                    value=chart["value"],
                    key=f"value_{i}"
                )

            with col2:
                unit = st.selectbox(
                    f"単位{i+1}",
                    period_units,
                    index=period_units.index(chart["unit"]),
                    key=f"unit_{i}"
                )

            with col3:
                interval_label = st.selectbox(
                    f"足{i+1}",
                    list(INTERVAL_OPTIONS.keys()),
                    index=list(INTERVAL_OPTIONS.values()).index(chart["interval"]),
                    key=f"interval_{i}"
                )

            chart["value"] = value
            chart["unit"] = unit
            chart["interval"] = INTERVAL_OPTIONS[interval_label]

            # ★ ここに追加！
            save_settings(settings)

    if st.button("銘柄リスト、チャート設定を保存"):
        save_settings(settings)
        st.success("保存しました")
