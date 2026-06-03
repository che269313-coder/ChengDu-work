# 成都小学数学教师招聘追踪系统

> 面向成都大学教育学院 · 自动追踪 · 每两天更新

## 项目简介

本系统自动追踪成都市23个区县的小学数学教师招聘信息，按年份、区域、学校分类整理为可搜索的HTML表格，并每两天自动更新一次。

**特色功能：**
- 📊 **全量招聘表格** — 2025/2026年所有成都小学数学教师岗位，按区县分组
- 🎓 **研究生专区** — 精选面向硕士的岗位，含成都大学附属小学等精准推荐
- ⏰ **即将开始高亮** — 6-9月招聘高峰期重点提醒
- 🔄 **自动更新** — 每两天自动爬取+更新HTML（Windows Task Scheduler）
- 🔍 **实时搜索过滤** — 按学校名、区域、状态一键筛选

## 项目结构

```
cdu_teacher_jobs/
├── README.md                    # 本文件
├── VERSION_HISTORY.md           # 版本管理文档
├── .gitignore                   # Git忽略规则
├── config.ini                   # 项目配置（数据源、关键词等）
│
├── data/                        # 数据目录（JSON格式）
│   ├── jobs_2025.json           # 2025年招聘数据
│   ├── jobs_2026.json           # 2026年招聘数据（持续更新）
│   └── grad_jobs.json           # 研究生专区数据
│
├── scripts/                     # 脚本目录
│   ├── scraper.py               # 多源爬虫（人社局/人才网/招聘平台）
│   ├── update_html.py           # HTML生成器（读取JSON生成页面）
│   └── install_scheduler.ps1    # Windows定时任务安装脚本
│
├── docs/                        # 输出目录（GitHub Pages /docs）
│   ├── index.html               # 主页面（全部招聘）
│   ├── grad.html                # 研究生专区页面
│   └── style.css                # 统一样式表
│
└── logs/                        # 日志目录
    └── scraper.log              # 爬虫运行日志
```

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 数据存储 | JSON | 纯文本，Git友好，易于手动编辑 |
| 爬虫 | Python + requests + BeautifulSoup | 多源并发采集，增量去重 |
| 页面生成 | Python (纯字符串拼接) | 零依赖，读取JSON直接生成静态HTML |
| 前端 | HTML5 + CSS3 + Vanilla JS | 搜索过滤、年份切换、状态筛选 |
| 定时调度 | Windows Task Scheduler (PowerShell) | 每两天自动执行 |

## 数据源

> **核心策略：优先第三方招聘平台。** 很多政府部门的招聘信息委托第三方（如教师人才网）发布，这些平台通常有更友好的API。

| 来源 | 状态 | 类型 | 说明 |
|------|:--:|------|------|
| 教师人才网 API | ✅ 可用 | RESTful JSON | `jiaoshi.com.cn/api/jobs?location=成都` |
| 成都市人社局 | ⚠️ 受限 | 事业单位公招 | 云WAF(412)，需浏览器手动访问 |
| 成都人才网 | ⚠️ 受限 | 综合招聘 | 首页可访问，搜索靠PostBack |
| 智联/前程无忧 | 📋 待接入 | 商业招聘 | 可能需JS渲染 |

### 验证码处理原则

遇到验证码时**不破解、不强解**：
1. 自动检测（`_detect_captcha`）→ 暂停60秒 → 跳过该源
2. 降低请求频率
3. 优先切换到第三方平台（见上方策略）

### 进阶：JS渲染页面抓取

对SPA或动态加载的网页，需要浏览器自动化：

```bash
pip install playwright && playwright install chromium   # 推荐
# 或: pip install selenium                              # 传统方案
# Cloudflare等专业WAF: docker run flaresolverr/flaresolverr
```

## 成都教师招聘周期

| 时间段 | 事件 | 关注重点 |
|--------|------|----------|
| 3-4月 | 上半年统一招聘公告发布 | 中心城区多，竞争激烈 |
| 5-6月 | 上半年笔试+面试 | 各区县单独补招开始 |
| **6-8月** | **夏季补招高峰期** | **主要机会窗口，务必关注** |
| 9-10月 | 下半年统一招聘公告发布 | 岗位数通常少于上半年 |
| 11-12月 | 下半年笔试+面试 | 补录机会 |

## 快速开始

### 1. 环境准备

```bash
# 安装Python依赖
pip install requests beautifulsoup4 lxml
```

### 2. 手动运行一次

```bash
# 运行爬虫（抓取最新数据）
python scripts/scraper.py

# 生成HTML页面
python scripts/update_html.py

# 用浏览器打开
start docs/index.html
```

### 3. 设置自动更新

以**管理员身份**打开PowerShell，执行：

```powershell
cd C:\Users\che26\Desktop\work\cdu_teacher_jobs
.\scripts\install_scheduler.ps1
```

> 这将在Windows Task Scheduler中创建任务 `CDU_TeacherJobs_Update`，每两天上午10:00自动运行。

### 4. 手动管理定时任务

```powershell
# 立即运行一次
schtasks /Run /TN "CDU_TeacherJobs_Update"

# 查看任务状态
schtasks /Query /TN "CDU_TeacherJobs_Update" /V

# 删除任务
schtasks /Delete /TN "CDU_TeacherJobs_Update" /F

# 查看最近日志
Get-Content logs\scheduler.log -Tail 20
```

## 手动添加招聘信息

如果发现爬虫漏掉了某个岗位，可以直接编辑JSON文件：

1. 打开 `data/jobs_2026.json`
2. 在 `"jobs"` 数组中添加新条目
3. 运行 `python scripts/update_html.py` 重新生成HTML

## 针对成都大学教育学院研究生

- **成都大学附属小学**（龙泉驿区）是成都大学直属学校，本校研究生具有天然优势
- 研究生学历在成都公办教师招聘中通常可以：
  - 跳过初级职称评审，直接认定中级
  - 在面试环节获得加分
  - 高新区、天府新区等新区有硕士专项政策

## 注意事项

⚠️ 数据来源为公开渠道，信息仅供参考。报名前请务必以官方公告为准，特别是截止日期和考试时间等关键信息。

## License

MIT
