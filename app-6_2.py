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
# CSS（スマホ最適化）
# ==================================================
st.markdown("""

<style>

/* 銘柄行 */
.stock-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
    width: auto;
}

/* 左側 */
.stock-info {
    display: flex;
    align-items: center;
    overflow: hidden;
    white-space: nowrap;
    min-width: 0;
}

/* 銘柄名 */
.stock-name {
    color: gray;
    margin-left: 6px;
    font-size: 13px;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* ボタン */
.stock-buttons {
    display: flex;
    gap: 4px;
    flex-shrink: 0;
}

/* ボタン高さ */
button[kind="secondary"] {
    min-height: 32px !important;
    padding: 0px 8px !important;
}

/* ボタン横並び */
.stock-btn-row {
    display: flex;
    flex-direction: row;
    gap: 6px;
    align-items: center;
}
.stock-btn-row button {
    padding: 4px 8px;
    font-size: 13px;
}

/* Streamlit columns の余白削除 */
div[data-testid="column"] > div {
    margin: 0 !important;
    padding: 0 !important;
    width: auto;
    display: flex;
    justify-content: flex-start !important;
}

/* ★ columns を PC/スマホ共通で横並び固定 */
div[data-testid="column"] {
    display: flex !important;
    flex-direction: row !important;
    justify-content: flex-start !important;
    align-items: center !important;
    flex-wrap: nowrap !important;
    padding: 0 !important;
    margin: 0 !important;
}

/* ★ columns の親（stHorizontalBlock）も横並び固定 */
div[data-testid="stHorizontalBlock"] {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    justify-content: flex-start !important;
    align-items: center !important;
    width: auto !important;
    gap: 2px !important;
}

</style>



""", unsafe_allow_html=True)

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
        company_name = get_company_name_from_jpx(symbol)

        title = (
             f"<b>{value}{unit} ({interval})</b>"
             f"　<span style='font-size:14px;color:gray;'>{company_name}</span>"
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
left_col, right_col,dunny_col = st.columns([0.6, 0.6,1.0])
# -----------------------------
# 左：銘柄リスト（columns 不使用）
# -----------------------------
with left_col:
    st.markdown("## 銘柄リスト")
    symbols = settings["symbols"]

    st.markdown("""
    <style>
    .stock-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 0;
        # border-bottom: 1px solid #eee;
        border-bottom: none;   /* ← これに変更 */
    }
    .stock-left {
        display: flex;
        flex-direction: column;
        font-size: 15px;
    }
    .stock-buttons {
        display: flex;
        gap: 6px;
        align-items: center;
    }
    .stock-buttons > div > button {
        padding: 4px 8px;
        font-size: 13px;
    }

    #@media (max-width: 600px) {
    #    .stock-buttons > div > button {
    #        padding: 2px 4px !important;
    #        font-size: 11px !important;
    #        min-width: 32px !important;
    #    }
    #}

    </style>
    """, unsafe_allow_html=True)


    for i, sym in enumerate(symbols):
      company_name = get_company_name_from_jpx(sym)

      # 銘柄名
      st.markdown(
        f"""
        <div style="font-size:16px;font-weight:bold;margin-bottom:6px;">
            {sym}
            <span style="color:gray;font-weight:normal;">
                {company_name}
            </span>
        </div>
        """,
        unsafe_allow_html=True
      )

      # ボタン行
      # ★ 完全横並び（Streamlit columns）
      btn1, btn2, btn3, spacer = st.columns([0.4, 0.4, 0.6, 1])

      with btn1:
          up = st.button("↑", key=f"up_{i}")

      with btn2:
          down = st.button("↓", key=f"down_{i}")

      with btn3:
          delete = st.button("Del", key=f"del_{i}")



      if up:
        if i > 0:
            symbols[i], symbols[i-1] = symbols[i-1], symbols[i]
            save_settings(settings)
            st.rerun()

      if down:
        if i < len(symbols)-1:
            symbols[i], symbols[i+1] = symbols[i+1], symbols[i]
            save_settings(settings)
            st.rerun()

      if delete:
        symbols.pop(i)
        save_settings(settings)
        st.rerun()



   # ***************************************************
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
