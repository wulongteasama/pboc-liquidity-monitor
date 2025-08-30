# generate_report.py (V12 - Datayes API Final Version)

import requests
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# --- 1. 数据抓取模块 ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'Referer': 'https://robo.datayes.com/',
    'Origin': 'https://robo.datayes.com',
    'Content-Type': 'application/json'
}

def fetch_omo_from_datayes(days=90):
    """从Datayes API获取央行公开市场操作数据"""
    print("开始从Datayes API抓取OMO数据...")
    url = "https://robo.datayes.com/v2/client/market/get_open_market_op"
    # API需要一个POST请求体，我们请求最近3个月(3M)的逆回购(RRP)数据
    payload = {"opType": "RRP", "period": "3M"}
    try:
        response = requests.post(url, headers=HEADERS, json=payload, timeout=20)
        response.raise_for_status()
        json_data = response.json()

        if json_data.get('code') != 0 or not isinstance(json_data.get('data'), list):
            print(f"  - Datayes OMO API返回错误或格式不正确: {json_data.get('message')}")
            return pd.DataFrame()

        data = json_data['data']
        if not data:
            print("  - Datayes OMO API返回了空的数据列表。")
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['opDate'])
        df['injection'] = pd.to_numeric(df['opRepoMoney'], errors='coerce').fillna(0)
        df['maturity'] = pd.to_numeric(df['opRepoDueMoney'], errors='coerce').fillna(0)
        df['net_injection'] = df['injection'] - df['maturity']
        
        final_df = df[['date', 'net_injection']].set_index('date').sort_index().tail(days)
        print(f"成功抓取 {len(final_df)} 天的公开市场操作记录。")
        return final_df
    except Exception as e:
        print(f"从Datayes抓取OMO数据失败: {e}")
        return pd.DataFrame()

def fetch_dr007_from_datayes(days=90):
    """从Datayes API获取DR007历史数据"""
    print("开始从Datayes API抓取 DR007 历史利率数据...")
    url = "https://robo.datayes.com/v2/client/market/get_interbank_rate"
    payload = {"rateType": "DR", "period": "3M"}
    try:
        response = requests.post(url, headers=HEADERS, json=payload, timeout=20)
        response.raise_for_status()
        json_data = response.json()

        if json_data.get('code') != 0 or not isinstance(json_data.get('data'), list):
            print(f"  - Datayes DR007 API返回错误或格式不正确: {json_data.get('message')}")
            return pd.DataFrame()

        data = json_data['data']
        if not data:
            print("  - Datayes DR007 API返回了空的数据列表。")
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['tradeDate'])
        df['dr007'] = pd.to_numeric(df['rateDR007'], errors='coerce')
        
        final_df = df[['date', 'dr007']].set_index('date').sort_index().tail(days)
        print(f"成功抓取 {len(final_df)} 条 DR007 记录。")
        return final_df
    except Exception as e:
        print(f"从Datayes抓取 DR007 数据失败: {e}")
        return pd.DataFrame()

def generate_interactive_report(df):
    print("开始生成交互式HTML报告...")
    output_dir = "public"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "index.html")

    if df.empty or df.dropna().empty:
        print("数据为空或处理失败，无法生成报告。")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("<html><body><h1>数据为空或处理失败，无法生成报告。</h1></body></html>")
        return

    latest_data = df.dropna().iloc[-1]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    colors = ['#EE6363' if x > 0 else '#90EE90' for x in df['net_injection']]
    fig.add_trace(go.Bar(x=df.index, y=df['net_injection'], name='净投放/回笼 (亿元)', marker_color=colors), secondary_y=False)
    fig.add_trace(go.Scatter(x=df.index, y=df['dr007'], name='DR007 利率 (%)', line=dict(color='#4682B4', width=2)), secondary_y=True)
    fig.update_layout(title_text=f"<b>中国央行流动性监测报告 (截至 {df.index[-1].strftime('%Y-%m-%d')})</b>", xaxis_title="日期", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), template="plotly_white")
    fig.update_yaxes(title_text="<b>资金投放/回笼 (亿元)</b>", secondary_y=False)
    fig.update_yaxes(title_text="<b>DR007 利率 (%)</b>", secondary_y=True)
    report_html = f"""
    <!DOCTYPE html>
    <html><head><meta charset="UTF-8"><title>央行流动性监测报告</title>
    <style> body {{ font-family: sans-serif; margin: 40px; }} .container {{ max-width: 1200px; margin: auto; }} .header {{ text-align: center; margin-bottom: 20px; }} .kpi-container {{ display: flex; justify-content: space-around; text-align: center; margin-bottom: 40px; }} .kpi-box {{ padding: 20px; border-radius: 8px; background-color: #f8f9fa; min-width: 200px; }} .kpi-value {{ font-size: 2.5em; font-weight: bold; }} .kpi-label {{ font-size: 1em; color: #6c757d; }} .positive {{ color: #dc3545; }} .negative {{ color: #28a745; }} </style></head>
    <body><div class="container"> <div class="header"><h1>央行流动性监测报告</h1><p>最后更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p></div> <div class="kpi-container"> <div class="kpi-box"><div class="kpi-value {'positive' if latest_data['net_injection'] > 0 else 'negative'}">{latest_data['net_injection']:+.0f}</div><div class="kpi-label">最新净投放 (亿元)</div></div> <div class="kpi-box"><div class="kpi-value">{latest_data['dr007']:.3f}%</div><div class="kpi-label">最新 DR007 利率</div></div> <div class="kpi-box"><div class="kpi-value {'positive' if df['net_injection'].tail(7).mean() > 0 else 'negative'}">{df['net_injection'].tail(7).mean():+.0f}</div><div class="kpi-label">近7日平均净投放 (亿元)</div></div> </div> {fig.to_html(full_html=False, include_plotlyjs='cdn')} </div></body></html>
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_html)
    print(f"报告生成成功！已保存到 {output_path}")

if __name__ == "__main__":
    omo_df = fetch_omo_from_datayes(days=90)
    dr007_df = fetch_dr007_from_datayes(days=90)
    if not omo_df.empty and not dr007_df.empty:
        combined_df = dr007_df.join(omo_df).fillna({'net_injection': 0}).dropna(subset=['dr007'])
        generate_interactive_report(combined_df)
    else:
        print("因部分或全部数据抓取失败，无法生成报告。")
        generate_interactive_report(pd.DataFrame())
