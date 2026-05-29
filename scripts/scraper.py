#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成都小学数学教师招聘信息爬虫脚本

功能:
  1. 从多个数据源抓取成都小学数学教师招聘信息
  2. 解析公告标题、链接、发布时间等关键字段
  3. 将新发现的岗位合并到 data/jobs_{year}.json
  4. 支持增量更新，避免重复数据

数据源:
  - 成都市人社局 (cdhrss.chengdu.gov.cn)
  - 成都人才网 (rc114.com)
  - 四川省人社厅 (rst.sc.gov.cn)
  - 智联招聘 (zhaopin.com)
  - 前程无忧 (51job.com)

运行方式:
  python scraper.py                    # 抓取所有源
  python scraper.py --source rc114     # 只抓取指定源
  python scraper.py --year 2026        # 只抓取指定年份
  python scraper.py --dry-run          # 试运行（不写入文件）

依赖:
  pip install requests beautifulsoup4 lxml
"""

import os
import sys
import json
import time
import hashlib
import logging
import argparse
import configparser
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("请先安装依赖: pip install requests beautifulsoup4 lxml")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
CONFIG_PATH = BASE_DIR / "config.ini"

# 确保目录存在
LOG_DIR.mkdir(exist_ok=True)

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "scraper.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("scraper")


def load_config() -> configparser.ConfigParser:
    """加载配置文件"""
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH, encoding="utf-8")
    return config


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def make_job_id(title: str, date_str: str, source: str) -> str:
    """生成唯一ID，用于去重"""
    raw = f"{title}|{date_str}|{source}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def load_existing_jobs(year: int) -> list[dict]:
    """加载已有数据"""
    filepath = DATA_DIR / f"jobs_{year}.json"
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("jobs", [])
    return []


def save_jobs(year: int, jobs: list[dict]):
    """保存数据到JSON文件"""
    filepath = DATA_DIR / f"jobs_{year}.json"
    existing_data = {}
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            existing_data = json.load(f)

    # 合并去重
    existing_ids = {j["id"] for j in existing_data.get("jobs", [])}
    new_count = 0
    for job in jobs:
        if job["id"] not in existing_ids:
            existing_data["jobs"].append(job)
            existing_ids.add(job["id"])
            new_count += 1

    existing_data["meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

    logger.info(f"保存 {year} 年数据: 新增 {new_count} 条, 总计 {len(existing_data['jobs'])} 条")


def detect_region(text: str, config: configparser.ConfigParser) -> str:
    """从文本中检测成都区县"""
    try:
        regions_str = config.get("regions", "regions")
        # 简单解析列表字符串
        import ast
        regions = ast.literal_eval(regions_str)
    except Exception:
        regions = [
            "锦江区", "青羊区", "金牛区", "武侯区", "成华区",
            "高新区", "天府新区", "龙泉驿区", "青白江区",
            "新都区", "温江区", "双流区", "郫都区", "新津区",
        ]

    for r in regions:
        if r in text:
            return r
    return "未知区域"


def detect_subject(text: str) -> bool:
    """判断是否为小学数学相关岗位"""
    keywords = ["数学", "小学数学", "数学教师", "数学老师"]
    return any(k in text for k in keywords)


# ---------------------------------------------------------------------------
# 数据源采集器
# ---------------------------------------------------------------------------

class BaseScraper:
    """爬虫基类

    针对中国政府网站的WAF绕过策略：
    - 使用完整的浏览器请求头（Accept/Language/Encoding等）
    - 保持Session以维护Cookie
    - 先访问首页建立会话，再访问子页面
    - 对gov.cn域名：HTTP 412表示WAF拦截，需更真实的浏览器模拟
    - 对rc114.com：ASP.NET WebForms，搜索可能需PostBack
    """

    # 模拟Chrome 125在Windows上的真实请求头
    BROWSER_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "DNT": "1",
    }

    def __init__(self, config: configparser.ConfigParser, timeout: int = 30):
        self.config = config
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.BROWSER_HEADERS)
        self.results: list[dict] = []

    def fetch(self, url: str, referer: str = None, **kwargs) -> requests.Response | None:
        """安全抓取，带重试和Referer"""
        headers = {}
        if referer:
            headers["Referer"] = referer

        for attempt in range(3):
            try:
                resp = self.session.get(
                    url, timeout=self.timeout, headers=headers, **kwargs
                )
                # 412 = WAF拦截，不重试（重试也没用）
                if resp.status_code == 412:
                    logger.warning(
                        f"HTTP 412 (WAF拦截): {url} — "
                        f"该网站使用了云防护，可能需要浏览器手动访问"
                    )
                    return None
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                logger.warning(f"请求失败 (尝试 {attempt+1}/3): {url} - {e}")
                time.sleep(5 * (attempt + 1))
        return None

    def fetch_gov_site(self, url: str) -> requests.Response | None:
        """专门用于.gov.cn网站的抓取：先访问首页建立会话"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        home = f"{parsed.scheme}://{parsed.netloc}/"

        # 先访问首页（不带Referer）
        logger.info(f"先访问首页建立会话: {home}")
        home_resp = self.fetch(home)
        if home_resp is None:
            logger.warning(f"首页不可达: {home}，可能被WAF拦截")
        else:
            logger.info(f"首页 OK ({home_resp.status_code})")

        # 再访问目标页面（带Referer）
        return self.fetch(url, referer=home)

    def parse(self, html: str) -> list[dict]:
        """解析HTML，子类实现"""
        raise NotImplementedError

    def run(self) -> list[dict]:
        """运行采集"""
        raise NotImplementedError


class CDHRSSScraper(BaseScraper):
    """
    成都市人社局 - 事业单位公开招聘
    采集公开招聘公告列表中的教育类/教师岗
    """

    NAME = "cdhrss"

    def run(self) -> list[dict]:
        logger.info("[cdhrss] 开始采集成都市人社局数据...")
        
        # 成都市人社局公开招聘页面
        # 注：实际URL应根据网站结构调整
        urls = [
            "https://cdhrss.chengdu.gov.cn/cdrsj/c109961/list.shtml",
        ]

        for url in urls:
            resp = self.fetch_gov_site(url)
            if not resp:
                logger.warning(
                    "[cdhrss] 无法访问成都市人社局。"
                    "该网站使用云WAF保护，本地浏览器可正常访问。"
                )
                continue
        
            soup = BeautifulSoup(resp.content, "lxml")
            
            # 尝试多种常见的列表项选择器
            selectors = [
                "ul.list-news li",
                "div.list-content li",
                "table.table-list tr",
                ".news-list li",
                "ul.list li",
            ]

            items = []
            for sel in selectors:
                items = soup.select(sel)
                if items:
                    break

            for item in items[:50]:  # 最多取50条
                try:
                    link = item.find("a")
                    if not link:
                        continue
                    
                    title = link.get("title", link.get_text(strip=True))
                    
                    # 只看教师招聘相关
                    if not ("教师" in title or "教育" in title or "学校" in title):
                        continue
                    if not detect_subject(title):
                        continue

                    href = link.get("href", "")
                    if href and not href.startswith("http"):
                        href = "https://cdhrss.chengdu.gov.cn" + href

                    # 尝试提取日期
                    date_span = item.find("span", class_="date") or item.find("td", class_="date")
                    date_str = date_span.get_text(strip=True) if date_span else ""

                    job = {
                        "id": make_job_id(title, date_str, self.NAME),
                        "year": datetime.now().year,
                        "region": detect_region(title, self.config),
                        "district": "",
                        "school": "",
                        "school_type": "",
                        "subject": "小学数学",
                        "position": title,
                        "recruitment_count": 0,
                        "requirement": "",
                        "announcement_date": date_str,
                        "deadline": "",
                        "source": "成都市人社局",
                        "source_url": href,
                        "status": "请查看详情",
                        "exam_date": "",
                        "notes": "",
                    }
                    self.results.append(job)
                except Exception as e:
                    logger.debug(f"解析条目失败: {e}")

        logger.info(f"[cdhrss] 采集完成，共 {len(self.results)} 条")
        return self.results


class RC114Scraper(BaseScraper):
    """
    成都人才网 - 搜索教师岗位

    已知限制：
    - job.rc114.com 使用 ASP.NET WebForms，搜索通过 PostBack 而非 GET 参数
    - 直接 GET JobSearchCate.aspx?key=xxx 参数被忽略，返回默认结果
    - 可在本地浏览器中手动搜索后将 URL 或结果粘贴到数据文件中
    """

    NAME = "rc114"

    def run(self) -> list[dict]:
        logger.info("[rc114] 开始采集成都人才网数据...")
        logger.info(
            "[rc114] 注意: 该网站搜索基于 ASP.NET PostBack，"
            "GET 参数可能被忽略。将在默认搜索结果中筛选教师相关岗位。"
        )

        import re
        import urllib.parse

        # job.rc114.com 已验证可访问（HTTP 200）
        base_url = "https://job.rc114.com/JobSearchCate.aspx"

        for kw in ["小学数学教师", "数学教师", "小学教师"]:
            search_url = f"{base_url}?key={urllib.parse.quote(kw)}"

            resp = self.fetch(search_url, referer="https://job.rc114.com/")
            if not resp:
                continue

            # rc114 的搜索结果以文本行形式呈现（非结构化HTML列表）
            # 格式: "职位名 公司名 学历 区域 薪资 日期"
            text = resp.text
            soup = BeautifulSoup(resp.content, "lxml")
            full_text = soup.get_text()
            lines = [l.strip() for l in full_text.split("\n") if l.strip()]

            for line in lines:
                if "教师" not in line and "数学" not in line:
                    continue
                # 排除页面导航文本
                if any(skip in line for skip in [
                    "搜索", "关键词", "筛选", "职位类别", "工作地点",
                    "学历要求", "工作经验", "月薪范围", "地铁沿线"
                ]):
                    continue

                match = re.match(
                    r"(.+?)\s+(.+?)\s+(不要求|初中|高中|职高|中专|技校|大专|本科|硕士|博士)\s+"
                    r"(.+?)\s+(\S+元|\S+元/月|当面告知)\s+(\d{4}/\d{1,2}/\d{1,2})",
                    line
                )
                if match:
                    pos, company, edu, loc, salary, date_str = match.groups()
                    job = {
                        "id": make_job_id(pos, date_str, self.NAME),
                        "year": datetime.now().year,
                        "region": detect_region(loc, self.config),
                        "district": loc,
                        "school": company,
                        "school_type": "",
                        "subject": "小学数学",
                        "position": pos,
                        "recruitment_count": 0,
                        "requirement": edu,
                        "announcement_date": date_str,
                        "deadline": "",
                        "source": "成都人才网 (job.rc114.com)",
                        "source_url": resp.url,
                        "status": "进行中",
                        "exam_date": "",
                        "notes": f"薪资: {salary}",
                    }
                    self.results.append(job)
                    logger.info(f"[rc114] 发现: {pos} @ {company}")

            time.sleep(3)

        logger.info(f"[rc114] 采集完成，共 {len(self.results)} 条")
        return self.results


class ZhaopinScraper(BaseScraper):
    """智联招聘 - 成都小学数学教师"""

    NAME = "zhaopin"

    def run(self) -> list[dict]:
        logger.info("[zhaopin] 开始采集智联招聘数据...")
        
        # 智联招聘 API（示例，实际接口可能变化）
        api_url = "https://fe-api.zhaopin.com/c/i/sou"
        params = {
            "pageSize": 30,
            "cityId": "530",  # 成都
            "workExperience": "-1",
            "education": "-1",
            "companyType": "-1",
            "employmentType": "-1",
            "jobWelfareTag": "-1",
            "kw": "小学数学教师",
            "kt": 3,
        }

        resp = self.fetch(api_url, params=params)
        if not resp:
            return self.results

        try:
            data = resp.json()
            results = data.get("data", {}).get("results", [])
            
            for item in results:
                title = item.get("jobName", "")
                if not detect_subject(title):
                    continue
                
                company = item.get("company", {}).get("name", "")
                city = item.get("city", {}).get("display", "")
                date_str = item.get("updateDate", "")
                
                # 只保留成都的
                if "成都" not in city:
                    continue

                job = {
                    "id": make_job_id(title, date_str, self.NAME),
                    "year": datetime.now().year,
                    "region": detect_region(title + company, self.config),
                    "district": city,
                    "school": company,
                    "school_type": "",
                    "subject": "小学数学",
                    "position": title,
                    "recruitment_count": 0,
                    "requirement": "",
                    "announcement_date": date_str,
                    "deadline": "",
                    "source": "智联招聘",
                    "source_url": item.get("positionURL", ""),
                    "status": "进行中",
                    "exam_date": "",
                    "notes": "",
                }
                self.results.append(job)
        except Exception as e:
            logger.error(f"解析智联招聘数据失败: {e}")

        logger.info(f"[zhaopin] 采集完成，共 {len(self.results)} 条")
        return self.results


class Job51Scraper(BaseScraper):
    """前程无忧 - 成都小学数学教师"""

    NAME = "job51"

    def run(self) -> list[dict]:
        logger.info("[job51] 开始采集前程无忧数据...")
        
        search_url = (
            "https://search.51job.com/list/090200,000000,0000,00,9,99,"
            "%D0%A1%D1%A7%CA%FD%D1%A7%BD%CC%CA%A6,2,1.html"
        )

        resp = self.fetch(search_url)
        if not resp:
            return self.results

        soup = BeautifulSoup(resp.content, "lxml")
        items = soup.select("div.joblist-item") or soup.select("div.el")

        for item in items[:30]:
            try:
                title_el = item.select_one("a.job-title") or item.select_one("span.jname")
                if not title_el:
                    continue
                
                title = title_el.get_text(strip=True)
                if not detect_subject(title):
                    continue

                company_el = item.select_one("a.cname") or item.select_one("span.cname")
                company = company_el.get_text(strip=True) if company_el else ""

                date_el = item.select_one("span.date") or item.select_one("span.t4")
                date_str = date_el.get_text(strip=True) if date_el else ""

                href = title_el.get("href", "")

                job = {
                    "id": make_job_id(title, date_str, self.NAME),
                    "year": datetime.now().year,
                    "region": detect_region(title + company, self.config),
                    "district": "",
                    "school": company,
                    "school_type": "",
                    "subject": "小学数学",
                    "position": title,
                    "recruitment_count": 0,
                    "requirement": "",
                    "announcement_date": date_str,
                    "deadline": "",
                    "source": "前程无忧",
                    "source_url": href,
                    "status": "进行中",
                    "exam_date": "",
                    "notes": "",
                }
                self.results.append(job)
            except Exception as e:
                logger.debug(f"解析条目失败: {e}")

        logger.info(f"[job51] 采集完成，共 {len(self.results)} 条")
        return self.results


class SCPTAScraper(BaseScraper):
    """四川人事考试网 - 事业单位招聘"""

    NAME = "scpta"

    def run(self) -> list[dict]:
        logger.info("[scpta] 开始采集四川省人事考试网数据...")

        # 四川人事考试网 - 事业单位招聘栏目
        urls = [
            "http://www.scpta.gov.cn/category/sydw",
        ]

        for url in urls:
            resp = self.fetch(url)
            if not resp:
                continue

            soup = BeautifulSoup(resp.content, "lxml")
            items = soup.select("ul.list li") or soup.select("div.list ul li") or soup.select("tr")

            for item in items[:50]:
                try:
                    link = item.find("a")
                    if not link:
                        continue
                    
                    title = link.get("title", link.get_text(strip=True))
                    
                    # 只看成都 + 教师相关
                    if "成都" not in title:
                        continue
                    if not ("教师" in title or "教育" in title):
                        continue
                    if not detect_subject(title):
                        continue

                    href = link.get("href", "")

                    date_el = item.find("span") or item.find("td")
                    date_str = date_el.get_text(strip=True) if date_el else ""

                    job = {
                        "id": make_job_id(title, date_str, self.NAME),
                        "year": datetime.now().year,
                        "region": detect_region(title, self.config),
                        "district": "",
                        "school": "",
                        "school_type": "",
                        "subject": "小学数学",
                        "position": title,
                        "recruitment_count": 0,
                        "requirement": "",
                        "announcement_date": date_str,
                        "deadline": "",
                        "source": "四川人事考试网",
                        "source_url": href,
                        "status": "请查看详情",
                        "exam_date": "",
                        "notes": "",
                    }
                    self.results.append(job)
                except Exception as e:
                    logger.debug(f"解析条目失败: {e}")

        logger.info(f"[scpta] 采集完成，共 {len(self.results)} 条")
        return self.results


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

# 注册所有采集器
SCRAPERS = {
    "cdhrss": CDHRSSScraper,
    "rc114": RC114Scraper,
    "zhaopin": ZhaopinScraper,
    "job51": Job51Scraper,
    "scpta": SCPTAScraper,
}


def run_scrapers(
    config: configparser.ConfigParser,
    sources: list[str] | None = None,
    year: int | None = None,
    dry_run: bool = False,
):
    """运行爬虫"""
    
    if year is None:
        year = datetime.now().year

    # 确定要运行的采集器
    if sources:
        selected = {k: v for k, v in SCRAPERS.items() if k in sources}
    else:
        selected = SCRAPERS

    all_jobs = []
    
    for name, scraper_cls in selected.items():
        try:
            scraper = scraper_cls(config)
            jobs = scraper.run()
            all_jobs.extend(jobs)
            
            # 请求间隔
            time.sleep(int(config.get("crawl", "request_delay", fallback="3")))
        except Exception as e:
            logger.error(f"采集器 {name} 运行失败: {e}", exc_info=True)

    # 去重
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        if job["id"] not in seen:
            seen.add(job["id"])
            unique_jobs.append(job)

    logger.info(f"总计采集 {len(all_jobs)} 条，去重后 {len(unique_jobs)} 条")

    if dry_run:
        logger.info("[DRY RUN] 不会写入文件。以下是采集结果摘要:")
        for job in unique_jobs:
            logger.info(f"  - [{job['source']}] {job['position']} ({job['region']})")
    else:
        save_jobs(year, unique_jobs)
        logger.info("数据已保存。")

    return unique_jobs


def main():
    parser = argparse.ArgumentParser(description="成都小学数学教师招聘爬虫")
    parser.add_argument(
        "--source", nargs="+", choices=list(SCRAPERS.keys()) + ["all"],
        default=["all"], help="指定采集源 (默认: all)"
    )
    parser.add_argument(
        "--year", type=int, default=datetime.now().year,
        help="目标年份 (默认: 当前年份)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="试运行模式，不写入文件"
    )
    parser.add_argument(
        "--list-sources", action="store_true",
        help="列出所有可用的采集源"
    )

    args = parser.parse_args()

    if args.list_sources:
        print("可用的采集源:")
        for name, cls in SCRAPERS.items():
            print(f"  {name}: {cls.__doc__ or cls.__name__}")
        return

    config = load_config()

    sources = None if "all" in args.source else args.source
    run_scrapers(config, sources=sources, year=args.year, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
