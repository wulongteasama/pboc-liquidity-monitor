# generate_report.py (V7.1 - Save to public folder)

import requests
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os # 导入os模块来创建文件夹

# --- 1. 数据抓取模块 (无变化) ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'Referer': 'https://data.eastmoney.com/',
    'Origin': 'https://data.eastmoney.com'
}
def fetch_omo_from_eastmoney_datacenter(days=90):
    print("开始从东方财富数据中心抓取OMO数据...")
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        'reportName': 'RPT_IMP_YANG行CAOZUO', 'columns': 'TRADE_DATE,OP_TOOL,OP_TERM,OP_R_TRADING,OP_R_WITHDRAWAL',
        'sortColumns': 'TRADE_DATE', 'sortTypes': '-1', 'pageSize': days, 'pageNumber': '1', 'source': 'WEB',
    }
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()['result']['data']
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['TRADE_DATE'])
        df['injection'] = pd.to_numeric(df['OP_R_TRADING'], errors='coerce').fillna(0)
        df['maturity'] = pd.to_numeric(df['OP_R_WITHDRAWAL'], errors='coerce').fillna(0)
        daily_summary = df.groupby('date').agg(total_injection=('injection', 'sum'), total_maturity=('maturity', 'sum')).reset_index()
        daily_summary['net_injection'] = daily_summary['total_injection'] - daily_summary['total_maturity']
        final_df = daily_summary[['date', 'net_injection']].set_index('date').sort_index()
        print(f"成功抓取 {len(final_df)} 天的公开市场操作记录。")
        return final_df
    except Exception as e:
        print(f"从东方财富数据中心抓取OMO数据失败: {e}")
        return pd.DataFrame()

def fetch_dr007_from_eastmoney_datacenter(days=90):
    print("开始从东方财富数据中心抓取 DR007 历史利率数据...")
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        'reportName': 'RPT_SHIBOR_DR', 'columns': 'REPORT_DATE,LATEST', 'filter': '(TYPE="DR007")',
        'sortColumns': 'REPORT_DATE', 'sortTypes': '-1', 'pageSize': days, 'pageNumber': '1', 'source': 'WEB',
    }
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()['result']['data']
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['REPORT_DATE'])
        df['dr007'] = pd.to_numeric(df['LATEST'], errors='coerce')
        final_df = df[['date', 'dr007']].set_index('date').sort_index()
        print(f"成功抓取 {len(final_df)} 条 DR007 记录。")
        return final_df
    except Exception as e:
        print(f"从东方财富数据中心抓取 DR007 数据失败: {e}")
        return pd.DataFrame()

def generate_interactive_report(df):
    print("开始生成交互式HTML报告...")
    df = df.dropna()
    if df.empty:
        print("数据处理后为空，无法生成报告。")
        # 【修改点1】: 定义输出文件夹和文件路径
        output_dir = "public"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "index.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("<html><body><h1>数据为空或处理失败，无法生成报告。</h1></body></html>")
        return

    latest_data = df.iloc[-1]
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
    # 【修改点2】: 将报告保存到 public 文件夹下，并重命名为 index.html
    output_dir = "public"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_html)
    print(f"报告生成成功！已保存到 {output_path}")

if __name__ == "__main__":
    omo_df = fetch_omo_from_eastmoney_datacenter(days=90)
    dr007_df = fetch_dr007_from_eastmoney_datacenter(days=90)
    if not omo_df.empty and not dr007_df.empty:
        combined_df = dr007_df.join(omo_df).fillna({'net_injection': 0}).dropna(subset=['dr007'])
        generate_interactive_report(combined_df)
    else:
        print("因部分或全部数据抓取失败，无法生成报告。")
