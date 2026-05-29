#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML 页面生成器

功能:
  1. 读取 data/ 目录下的 JSON 数据
  2. 生成主页面 index.html（按年份/区域/学校分类的表格）
  3. 生成研究生专区页面 grad.html
  4. 嵌入样式，生成统计信息和搜索过滤功能

运行:
  python update_html.py              # 生成所有页面
  python update_html.py --preview    # 生成后在浏览器中预览
"""

import os
import json
import argparse
import webbrowser
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

OUTPUT_DIR.mkdir(exist_ok=True)

# 区域排序（中心城区在前）
REGION_ORDER = [
    "高新区", "天府新区",
    "锦江区", "青羊区", "金牛区", "武侯区", "成华区",
    "龙泉驿区", "青白江区", "新都区", "温江区",
    "双流区", "郫都区", "新津区",
    "简阳市", "都江堰市", "彭州市", "邛崃市", "崇州市",
    "金堂县", "大邑县", "蒲江县",
    "未知区域",
]

# 状态徽章样式
STATUS_BADGES = {
    "进行中": '<span class="badge badge-active">进行中</span>',
    "即将开始": '<span class="badge badge-upcoming">即将开始</span>',
    "已截止": '<span class="badge badge-closed">已截止</span>',
    "请查看详情": '<span class="badge badge-info">请查看详情</span>',
}


def load_data(filename: str) -> dict:
    """加载JSON数据"""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        return {"jobs": [], "meta": {}}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def get_status_badge(status: str) -> str:
    """获取状态徽章HTML"""
    for key, badge in STATUS_BADGES.items():
        if key in status:
            return badge
    return f'<span class="badge badge-info">{status}</span>'


def sort_region_key(region: str) -> int:
    """区域排序键"""
    try:
        return REGION_ORDER.index(region)
    except ValueError:
        return len(REGION_ORDER)


def generate_header(active_page: str = "index") -> str:
    """生成页面头部导航"""
    nav_index = 'class="active"' if active_page == "index" else ""
    nav_grad = 'class="active"' if active_page == "grad" else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>成都小学数学教师招聘追踪系统</title>
    <style>
{load_css()}
    </style>
</head>
<body>
    <header class="header">
        <div class="container">
            <h1>📋 成都小学数学教师招聘追踪系统</h1>
            <p class="subtitle">覆盖成都市23个区县 · 自动更新 · 每两天同步</p>
            <p class="update-time">最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            <nav class="nav">
                <a href="index.html" {nav_index}>📊 全部招聘</a>
                <a href="grad.html" {nav_grad}>🎓 研究生专区</a>
                <a href="#stats">📈 数据统计</a>
                <a href="#upcoming">⏰ 即将开始</a>
            </nav>
        </div>
    </header>
    <main class="container">"""


def generate_footer() -> str:
    """生成页面底部"""
    return f"""    </main>
    <footer class="footer">
        <div class="container">
            <p>成都小学数学教师招聘追踪系统 · 自动更新于 {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            <p class="disclaimer">⚠️ 数据来源于公开渠道，仅供参考，请以官方公告为准。</p>
        </div>
    </footer>
    <script>
{load_js()}
    </script>
</body>
</html>"""


def load_css() -> str:
    """加载CSS样式"""
    css_path = OUTPUT_DIR / "style.css"
    if css_path.exists():
        return css_path.read_text(encoding="utf-8")
    return ""


def load_js() -> str:
    """加载JS脚本"""
    return """
// 搜索过滤
function filterTable() {{
    const input = document.getElementById('searchInput');
    const filter = input.value.toUpperCase();
    const sections = document.querySelectorAll('.region-section');

    sections.forEach(section => {{
        const rows = section.querySelectorAll('tbody tr');
        let visible = 0;
        rows.forEach(row => {{
            const text = row.textContent.toUpperCase();
            if (text.indexOf(filter) > -1) {{
                row.style.display = '';
                visible++;
            }} else {{
                row.style.display = 'none';
            }}
        }});
        section.style.display = visible > 0 ? '' : 'none';
    }});
}}

// 年份切换
function switchYear(year) {{
    document.querySelectorAll('.year-tab').forEach(tab => {{
        tab.classList.remove('active');
        if (tab.dataset.year === year) tab.classList.add('active');
    }});
    document.querySelectorAll('.year-content').forEach(content => {{
        content.style.display = content.dataset.year === year ? '' : 'none';
    }});
}}

// 状态筛选
function filterStatus(status) {{
    const rows = document.querySelectorAll('tbody tr');
    rows.forEach(row => {{
        const badge = row.querySelector('.badge');
        if (!badge) return;
        if (status === 'all' || badge.textContent.includes(status)) {{
            row.style.display = '';
        }} else {{
            row.style.display = 'none';
        }}
    }});
    // 隐藏空的section
    document.querySelectorAll('.region-section').forEach(section => {{
        const visible = section.querySelectorAll('tbody tr[style=""]').length;
        section.style.display = visible > 0 ? '' : 'none';
    }});
}}
"""


def generate_index_page(jobs_by_year: dict) -> str:
    """生成主页面 HTML"""
    
    html = generate_header(active_page="index")
    
    # 搜索栏
    html += """
    <div class="toolbar">
        <input type="text" id="searchInput" onkeyup="filterTable()"
               placeholder="🔍 搜索学校名称、区域、岗位...">
        <div class="filter-buttons">
            <button class="filter-btn active" onclick="filterStatus('all')">全部</button>
            <button class="filter-btn" onclick="filterStatus('进行中')">🟢 进行中</button>
            <button class="filter-btn" onclick="filterStatus('即将开始')">🟡 即将开始</button>
            <button class="filter-btn" onclick="filterStatus('已截止')">🔴 已截止</button>
        </div>
    </div>
    """

    # 统计面板
    html += '<div class="stats-panel" id="stats">'
    html += '<h2>📈 数据统计</h2>'
    
    total_all = 0
    for year, jobs in sorted(jobs_by_year.items()):
        count = len(jobs)
        total_all += count
        active = sum(1 for j in jobs if "进行中" in j.get("status", ""))
        upcoming = sum(1 for j in jobs if "即将开始" in j.get("status", ""))
        closed = sum(1 for j in jobs if "已截止" in j.get("status", ""))
        
        html += f"""
        <div class="stat-card">
            <h3>{year}年</h3>
            <div class="stat-num">{count}</div>
            <div class="stat-detail">
                <span>🟢 进行中: {active}</span>
                <span>🟡 即将开始: {upcoming}</span>
                <span>🔴 已截止: {closed}</span>
            </div>
        </div>"""

    html += f'<div class="stat-card total"><h3>总计</h3><div class="stat-num">{total_all}</div></div>'
    html += '</div>'

    # 即将开始的招聘（高亮提醒）
    html += '<div class="upcoming-section" id="upcoming">'
    html += '<h2>⏰ 近期即将开始的招聘（重点关注）</h2>'
    html += '<div class="upcoming-list">'
    for year, jobs in sorted(jobs_by_year.items(), reverse=True):
        upcoming_jobs = [j for j in jobs if "即将开始" in j.get("status", "")]
        for job in upcoming_jobs[:10]:
            html += f"""
            <div class="upcoming-card">
                <span class="date-badge">{job.get('announcement_date', '')}</span>
                <strong>{job['school']}</strong>
                <span>{job['position']}</span>
                <span class="tag">{job['region']}</span>
                <span class="tag">{job.get('school_type', '')}</span>
            </div>"""
    html += '</div></div>'

    # 年份标签切换
    years = sorted(jobs_by_year.keys(), reverse=True)
    html += '<div class="year-tabs">'
    for i, year in enumerate(years):
        active = 'active' if i == 0 else ''
        html += f'<button class="year-tab {active}" data-year="{year}" onclick="switchYear(\'{year}\')">{year}年</button>'
    html += '</div>'

    # 按年份展示
    for year_idx, year in enumerate(years):
        jobs = jobs_by_year[year]
        display = '' if year_idx == 0 else 'style="display:none"'
        
        html += f'<div class="year-content" data-year="{year}" {display}>'
        html += f'<h2>{year}年 小学数学教师招聘信息</h2>'
        
        # 按区域分组
        region_jobs: dict[str, list] = {}
        for job in jobs:
            region = job.get("region", "未知区域")
            if region not in region_jobs:
                region_jobs[region] = []
            region_jobs[region].append(job)

        # 排序
        sorted_regions = sorted(region_jobs.keys(), key=sort_region_key)

        for region in sorted_regions:
            region_group = region_jobs[region]
            html += f"""
        <div class="region-section">
            <h3 class="region-title">📍 {region} ({len(region_group)}个岗位)</h3>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>学校名称</th>
                            <th>岗位</th>
                            <th>类型</th>
                            <th>人数</th>
                            <th>学历要求</th>
                            <th>发布日期</th>
                            <th>截止日期</th>
                            <th>考试日期</th>
                            <th>状态</th>
                            <th>来源</th>
                            <th>备注</th>
                        </tr>
                    </thead>
                    <tbody>"""

            for job in sorted(region_group, key=lambda j: j.get("announcement_date", ""), reverse=True):
                source_url = job.get("source_url", "")
                school_cell = f'<a href="{source_url}" target="_blank">{job["school"]}</a>' if source_url else job["school"]

                html += f"""
                        <tr>
                            <td>{school_cell}</td>
                            <td>{job.get('position', '')}</td>
                            <td>{job.get('school_type', '')}</td>
                            <td>{job.get('recruitment_count', '—')}</td>
                            <td>{job.get('requirement', '—')}</td>
                            <td>{job.get('announcement_date', '')}</td>
                            <td class="deadline">{job.get('deadline', '')}</td>
                            <td>{job.get('exam_date', '')}</td>
                            <td>{get_status_badge(job.get('status', ''))}</td>
                            <td>{job.get('source', '')}</td>
                            <td class="notes">{job.get('notes', '')}</td>
                        </tr>"""

            html += """
                    </tbody>
                </table>
            </div>
        </div>"""

        html += '</div>'  # year-content

    html += generate_footer()
    return html


def generate_grad_page(grad_jobs: list[dict]) -> str:
    """生成研究生专区页面"""
    
    html = generate_header(active_page="grad")

    html += """
    <div class="grad-intro">
        <h2>🎓 研究生专区 — 面向成都大学教育学院</h2>
        <p>以下岗位对研究生学历有明确优先或硬性要求，适合成都大学教育学院硕士毕业生申请。</p>
        <p class="highlight-box">
            <strong>💡 特别提示：</strong> 成都大学附属小学（龙泉驿区）为成都大学直属附属学校，
            本校研究生有天然优势。地理位置紧邻校本部，方便兼顾学业与实习。
        </p>
    </div>
    
    <div class="toolbar">
        <input type="text" id="searchInput" onkeyup="filterTable()"
               placeholder="🔍 搜索学校、区域、标签...">
    </div>"""

    # 按状态分组
    active_jobs = [j for j in grad_jobs if "进行中" in j.get("status", "")]
    upcoming_jobs = [j for j in grad_jobs if "即将开始" in j.get("status", "")]

    if active_jobs:
        html += '<div class="grad-section"><h3>🟢 正在招聘</h3>'
        html += generate_grad_table(active_jobs)
        html += '</div>'

    if upcoming_jobs:
        html += '<div class="grad-section"><h3>🟡 即将开始</h3>'
        html += generate_grad_table(upcoming_jobs)
        html += '</div>'

    # 投递建议
    html += """
    <div class="advice-section">
        <h3>📝 研究生求职建议</h3>
        <div class="advice-cards">
            <div class="advice-card">
                <h4>🏫 公办学校优势</h4>
                <p>硕士学历入编后可跳过初级职称评审，直接认定中级职称。高新区、天府新区等新区对硕士有政策倾斜。</p>
            </div>
            <div class="advice-card">
                <h4>💼 民办学校机会</h4>
                <p>嘉祥、金苹果等高端民办薪资可达15-25K/月。硕士学历在面试和薪资谈判中竞争力显著更强。</p>
            </div>
            <div class="advice-card">
                <h4>📅 招聘周期</h4>
                <p>成都事业单位公开招聘分上下半年：上半年3-4月发布公告，下半年9-10月发布公告。各区县夏季（6-8月）有补招。</p>
            </div>
            <div class="advice-card">
                <h4>🔗 成都大学附属小学</h4>
                <p>成都大学附属小学位于龙泉驿区，是成都大学直属学校。本校教育学院研究生可通过导师推荐获得优先面试机会。</p>
            </div>
        </div>
    </div>"""

    html += generate_footer()
    return html


def generate_grad_table(jobs: list[dict]) -> str:
    """生成研究生专区表格"""
    html = """
    <div class="table-wrapper">
        <table>
            <thead>
                <tr>
                    <th>学校</th>
                    <th>岗位</th>
                    <th>区域</th>
                    <th>类型</th>
                    <th>薪资</th>
                    <th>学历要求</th>
                    <th>截止日期</th>
                    <th>状态</th>
                    <th>研究生优势</th>
                    <th>标签</th>
                </tr>
            </thead>
            <tbody>"""

    for job in jobs:
        tags_html = " ".join(
            f'<span class="tag">{t}</span>' for t in job.get("tags", [])
        )
        source_url = job.get("source_url", "")
        school_cell = f'<a href="{source_url}" target="_blank">{job["school"]}</a>' if source_url else job["school"]

        html += f"""
                <tr>
                    <td>{school_cell}</td>
                    <td>{job.get('position', '')}</td>
                    <td>{job['region']}</td>
                    <td>{job.get('school_type', '')}</td>
                    <td class="salary">{job.get('salary_range', '面议')}</td>
                    <td>{job.get('requirement', '')}</td>
                    <td class="deadline">{job.get('deadline', '')}</td>
                    <td>{get_status_badge(job.get('status', ''))}</td>
                    <td class="notes">{job.get('grad_advantage', '')}</td>
                    <td>{tags_html}</td>
                </tr>"""

    html += """
            </tbody>
        </table>
    </div>"""
    return html


def main():
    parser = argparse.ArgumentParser(description="HTML页面生成器")
    parser.add_argument("--preview", action="store_true", help="生成后在浏览器中预览")
    args = parser.parse_args()

    # 加载所有年份数据
    jobs_by_year: dict[str, list] = {}
    for f in sorted(DATA_DIR.glob("jobs_*.json")):
        year_str = f.stem.replace("jobs_", "")
        data = load_data(f.name)
        jobs_by_year[year_str] = data.get("jobs", [])

    # 加载研究生专区数据
    grad_data = load_data("grad_jobs.json")
    grad_jobs = grad_data.get("jobs", [])

    # 生成主页面
    index_html = generate_index_page(jobs_by_year)
    index_path = OUTPUT_DIR / "index.html"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"✅ 主页面已生成: {index_path}")

    # 生成研究生专区
    grad_html = generate_grad_page(grad_jobs)
    grad_path = OUTPUT_DIR / "grad.html"
    with open(grad_path, "w", encoding="utf-8") as f:
        f.write(grad_html)
    print(f"✅ 研究生专区已生成: {grad_path}")

    # 预览
    if args.preview:
        webbrowser.open(str(index_path))


if __name__ == "__main__":
    main()
