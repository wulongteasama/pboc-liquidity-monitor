# generate_report.py (V9 - Selenium 终极版)

import requests
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# --- 1. 数据抓取模块 ---

def setup_selenium_driver():
    """配置并启动一个用于GitHub Actions的无头Chrome浏览器"""
    chrome_options = Options()
    chrome_options.add_argument("--headless") # 无头模式
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36")
    
    # 在GitHub Actions环境中，驱动程序通常是自动管理的
    # 我们直接初始化WebDriver
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def fetch_pbc_omo_history_selenium(pages=3):
    """使用Selenium驱动真实浏览器，从央行官网抓取OMO数据"""
    print("开始从央行官网抓取OMO数据 (Selenium模式)...")
    base_url = "http://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/"
    all_operations = []
    driver = setup_selenium_driver()

    try:
        for i in range(pages):
            url = f"{base_url}index{i+1}.html" if i > 0 else f"{base_url}index.html"
            print(f"正在处理列表页: {url}")
            driver.get(url)
            time.sleep(3) # 等待页面JavaScript加载

            # 使用CSS选择器找到公告列表的每一行
            rows = driver.find_elements(By.CSS_SELECTOR, 'div#r_con_con table tr')
            if not rows:
                print(f"  - 第 {i+1} 页未找到公告列表。")
                break

            for row in rows:
                try:
                    title_element = row.find_element(By.CSS_SELECTOR, 'td:nth-child(1) a')
                    date_element = row.find_element(By.CSS_SELECTOR, 'td:nth-child(2)')
                    
                    title = title_element.text
                    date_str = date_element.text

                    if "公开市场业务交易公告" in title:
                        injection_match = re.search(r'(\d+)\s*亿元', title)
                        maturity_match = re.search(r'有(\d+)\s*亿元.*到期', title)
                        
                        injection = int(injection_match.group(1)) if injection_match else 0
                        maturity = int(maturity_match.group(1)) if maturity_match else 0
                        
                        if "不开展" in title:
                            injection = 0

                        net_injection = injection - maturity
                        
                        all_operations.append({
                            "date": pd.to_datetime(date_str),
                            "net_injection": net_injection
                        })
                except Exception:
                    continue # 忽略表头或格式不正确的行
    finally:
        driver.quit() # 确保浏览器进程被关闭

    if not all_operations:
        print("未能从央行官网抓取到任何公开市场操作记录。")
        return pd.DataFrame()

    df = pd.DataFrame(all_operations).drop_duplicates(subset=['date']).set_index('date').sort_index()
    print(f"成功抓取 {len(df)} 条公开市场操作记录。")
    return df

def fetch_dr007_from_sina(days=90):
    """由于所有API都可能被云IP屏蔽，我们回归到最简单的新浪财经API作为DR007的来源"""
    print("开始从新浪财经数据接口抓取 DR007 历史利率数据...")
    url = f"https://money.finance.sina.com.cn/mac/api/jsonp.php/SINAREMOTECALLCALLBACK/MacPage_Service.get_p_l_shibor?yy=2024&type=DR007&num={days+30}"
    headers = {'Referer': 'https://finance.sina.com.cn/'}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        text = response.text
        start = text.find('[')
        end = text.rfind(']')
        if start == -1 or end == -1:
            raise ValueError(f"Response text does not contain valid JSON array: {text[:200]}")
        json_str = text[start : end+1]
        data = pd.read_json(json_str)
        data['d'] = pd.to_datetime(data['d'])
        data = data.rename(columns={'d': 'date', 'v': 'dr007'}).set_index('date').sort_index()
        print(f"成功抓取 {len(data)} 条 DR007 记录。")
        return data
    except Exception as e:
        print(f"从新浪财经抓取 DR007 数据失败: {e}")
        return pd.DataFrame()

def generate_interactive_report(df):
    print("开始生成交互式HTML报告...")
    output_dir = "public"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "index.html")

    df = df.dropna()
    if df.empty:
        print("数据处理后为空，无法生成报告。")
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
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_html)
    print(f"报告生成成功！已保存到 {output_path}")

if __name__ == "__main__":
    import warnings
    warnings.simplefilter(action='ignore', category=FutureWarning)

    omo_df = fetch_pbc_omo_history_selenium(pages=5)
    dr007_df = fetch_dr007_from_sina(days=90)
    if not omo_df.empty and not dr007_df.empty:
        combined_df = dr007_df.join(omo_df).fillna({'net_injection': 0}).dropna(subset=['dr007'])
        generate_interactive_report(combined_df)
    else:
        print("因部分或全部数据抓取失败，无法生成报告。")
        generate_interactive_report(pd.DataFrame())
