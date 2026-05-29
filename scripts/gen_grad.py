#!/usr/bin/env python3
"""独立生成 grad.html（研究生专区页面）"""
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

# 加载数据
with open(DATA_DIR / "grad_jobs.json", "r", encoding="utf-8") as f:
    data = json.load(f)
jobs = data.get("jobs", [])

# 读取CSS
css = (BASE_DIR / "output" / "style.css").read_text(encoding="utf-8")

# 状态徽章
BADGES = {
    "进行中": '<span class="badge badge-active">进行中</span>',
    "即将开始": '<span class="badge badge-upcoming">即将开始</span>',
    "已截止": '<span class="badge badge-closed">已截止</span>',
    "请查看详情": '<span class="badge badge-info">请查看详情</span>',
}

def badge(s):
    for k, v in BADGES.items():
        if k in s:
            return v
    return f'<span class="badge badge-info">{s}</span>'

def build_rows(jobs_list):
    rows = ""
    for job in jobs_list:
        tags = " ".join(
            f'<span class="tag">{t}</span>' for t in job.get("tags", [])
        )
        url = job.get("source_url", "")
        school = f'<a href="{url}" target="_blank">{job["school"]}</a>' if url else job["school"]
        rows += f"""<tr>
            <td>{school}</td>
            <td>{job.get("position", "")}</td>
            <td>{job["region"]}</td>
            <td>{job.get("school_type", "")}</td>
            <td class="salary">{job.get("salary_range", "面议")}</td>
            <td>{job.get("requirement", "")}</td>
            <td class="deadline">{job.get("deadline", "")}</td>
            <td>{badge(job.get("status", ""))}</td>
            <td class="notes">{job.get("grad_advantage", "")}</td>
            <td>{tags}</td>
        </tr>"""
    return rows

active_jobs = [j for j in jobs if "进行中" in j.get("status", "")]
upcoming_jobs = [j for j in jobs if "即将开始" in j.get("status", "")]

active_rows = build_rows(active_jobs)
upcoming_rows = build_rows(upcoming_jobs)

now = datetime.now().strftime("%Y-%m-%d %H:%M")

THEAD = """<tr>
    <th>学校</th><th>岗位</th><th>区域</th><th>类型</th>
    <th>薪资</th><th>学历要求</th><th>截止日期</th>
    <th>状态</th><th>研究生优势</th><th>标签</th>
</tr>"""

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>研究生专区 - 成都小学数学教师招聘</title>
<style>
{css}
</style>
</head>
<body>
<header class="header">
<div class="container">
<h1>📋 成都小学数学教师招聘追踪系统</h1>
<p class="subtitle">覆盖成都市23个区县 · 自动更新 · 每两天同步</p>
<p class="update-time">最后更新: {now}</p>
<nav class="nav">
<a href="index.html">📊 全部招聘</a>
<a href="grad.html" class="active">🎓 研究生专区</a>
</nav>
</div>
</header>
<main class="container">
<div class="grad-intro">
<h2>🎓 研究生专区 — 面向成都大学教育学院</h2>
<p>以下岗位对研究生学历有明确优先或硬性要求，适合成都大学教育学院硕士毕业生申请。</p>
<p class="highlight-box"><strong>💡 特别提示：</strong> 成都大学附属小学（龙泉驿区）为成都大学直属附属学校，本校研究生有天然优势。地理位置紧邻校本部，方便兼顾学业与实习。</p>
</div>
<div class="toolbar">
<input type="text" id="searchInput" onkeyup="filterTable()" placeholder="🔍 搜索学校、区域、标签...">
</div>
"""
if active_jobs:
    html += f"""<div class="grad-section"><h3>🟢 正在招聘</h3>
<div class="table-wrapper"><table><thead>{THEAD}</thead><tbody>{active_rows}</tbody></table></div></div>"""

if upcoming_jobs:
    html += f"""<div class="grad-section"><h3>🟡 即将开始</h3>
<div class="table-wrapper"><table><thead>{THEAD}</thead><tbody>{upcoming_rows}</tbody></table></div></div>"""

html += f"""<div class="advice-section"><h3>📝 研究生求职建议</h3>
<div class="advice-cards">
<div class="advice-card"><h4>🏫 公办学校优势</h4><p>硕士学历入编后可跳过初级职称评审，直接认定中级职称。高新区、天府新区等新区对硕士有政策倾斜。</p></div>
<div class="advice-card"><h4>💼 民办学校机会</h4><p>嘉祥、金苹果等高端民办薪资可达15-25K/月。硕士学历在面试和薪资谈判中竞争力显著更强。</p></div>
<div class="advice-card"><h4>📅 招聘周期</h4><p>成都事业单位公开招聘分上下半年：上半年3-4月发布公告，下半年9-10月发布公告。各区县夏季（6-8月）有补招。</p></div>
<div class="advice-card"><h4>🔗 成都大学附属小学</h4><p>成都大学附属小学位于龙泉驿区，是成都大学直属学校。本校教育学院研究生可通过导师推荐获得优先面试机会。</p></div>
</div></div>
</main>
<footer class="footer">
<div class="container">
<p>成都小学数学教师招聘追踪系统 · 自动更新于 {now}</p>
<p class="disclaimer">⚠️ 数据来源于公开渠道，仅供参考，请以官方公告为准。</p>
</div>
</footer>
<script>
function filterTable(){{
    const input = document.getElementById('searchInput');
    const filter = input.value.toUpperCase();
    const sections = document.querySelectorAll('.grad-section');
    sections.forEach(section => {{
        const rows = section.querySelectorAll('tbody tr');
        let visible = 0;
        rows.forEach(row => {{
            const text = row.textContent.toUpperCase();
            if(text.indexOf(filter) > -1) {{
                row.style.display = '';
                visible++;
            }} else {{
                row.style.display = 'none';
            }}
        }});
        section.style.display = visible > 0 ? '' : 'none';
    }});
}}
</script>
</body>
</html>"""

out_path = BASE_DIR / "output" / "grad.html"
out_path.write_text(html, encoding="utf-8")
print(f"✅ grad.html 已生成，包含 {len(jobs)} 个岗位")
print(f"   进行中: {len(active_jobs)} | 即将开始: {len(upcoming_jobs)}")
