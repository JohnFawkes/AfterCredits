import os, re, sys
from datetime import datetime, UTC

if sys.version_info[0] != 3 or sys.version_info[1] < 11:
    print("Version Error: Version: %s.%s.%s incompatible please use Python 3.11+" % (sys.version_info[0], sys.version_info[1], sys.version_info[2]))
    sys.exit(0)

try:
    import requests
    from git import Repo
    from lxml import html
    from kometautils import KometaArgs, KometaLogger, YAML
except (ModuleNotFoundError, ImportError):
    print("Requirements Error: Requirements are not installed")
    sys.exit(0)

options = [
    {"arg": "tr", "key": "trace",        "env": "TRACE",        "type": "bool", "default": False, "help": "Run with extra trace logs."},
    {"arg": "lr", "key": "log-requests", "env": "LOG_REQUESTS", "type": "bool", "default": False, "help": "Run with every request logged."}
]
script_name = "AfterCredits"
base_dir = os.path.dirname(os.path.abspath(__file__))
args = KometaArgs("Kometa-Team/AfterCredits", base_dir, options, use_nightly=False)
logger = KometaLogger(script_name, "aftercredits", os.path.join(base_dir, "logs"), is_trace=args["trace"], log_requests=args["log-requests"])
logger.screen_width = 160
logger.header(args, sub=True)
logger.separator("Validating Options", space=False, border=False)
logger.start()
logger.separator("Scraping AfterCredits", space=False, border=False)
api_url = "https://aftercredits.com/wp-json/wp/v2/posts"
page_num = 0
total_pages = 1
rows = []
data = YAML(path=os.path.join(base_dir, "aftercredits.yml"), start_empty=True)
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0",
    "Accept-Language": "en-US,en;q=0.5",
}

while page_num < total_pages:
    page_num += 1
    logger.info(f"Parsing Page {page_num}")
    response = requests.get(api_url, headers=headers, params={"categories": 7, "per_page": 100, "_embed": "wp:term", "page": page_num})
    total_pages = int(response.headers.get("X-WP-TotalPages", 1))
    posts = response.json()

    for post in posts:
        media_url = post["link"]
        try:
            logger.trace(f"Parsing Media: {media_url}")
            media_response = html.fromstring(post["content"]["rendered"])
            imdb_url = media_response.xpath("//a[contains(@href, 'imdb.com')]/@href")
            if not imdb_url:
                raise ValueError(f"Skipped {media_url}: IMDb URL not found")

            res = re.search(r".*/(tt\d*)/.*", imdb_url[0])
            imdb_id = res.group(1) if res else None
            if imdb_id is None:
                raise ValueError(f"Skipped {media_url}: IMDb ID not found")

            embedded_terms = post.get("_embedded", {}).get("wp:term", [])
            category_names = [t["name"] for t_list in embedded_terms for t in t_list if t.get("taxonomy") == "category"]
            tags = [t for t in category_names if t not in ["Now Showing", "Stingers"]]
            if "Games" in tags:
                raise ValueError(f"Skipped {media_url}: Video Game")

            kksr = media_response.xpath("//div[contains(@class, 'kksr-legend')]/text()")
            rating, votes = 0, 0
            if kksr:
                m = re.search(r"(\d+)/\d+ - \((\d+) votes?\)", kksr[0])
                if m:
                    rating, votes = int(m.group(1)), int(m.group(2))

            rows.append((imdb_id, rating, votes, ', '.join(tags), media_url))
            data[imdb_id] = YAML.inline({"rating": rating, "votes": votes, "tags": tags})
        except ValueError as e:
            logger.warning(e)


headers = ["IMDb ID", "Rating", "Votes", "Tags"]
widths = []
for i, header in enumerate(headers):
    if rows:
        _max = len(str(max(rows, key=lambda t: len(str(t[i])))[i]))
    else:
        _max = 0
    widths.append(_max if _max > len(header) else len(header))


data.yaml.width = 200
data.save()

if [item.a_path for item in Repo(path=".").index.diff(None) if item.a_path.endswith(".yml")]:

    with open("README.md", "r") as f:
        readme_data = f.readlines()

    readme_data[2] = f"Last generated at: {datetime.now(UTC).strftime('%B %d, %Y %I:%M %p')} UTC\n"

    with open("README.md", "w") as f:
        f.writelines(readme_data)

logger.separator("AfterCredits Report")
logger.info(f"{headers[0]:^{widths[0]}} | {headers[1]:^{widths[1]}} | {headers[2]:^{widths[2]}} | {headers[3]:<{widths[3]}}")
logger.separator(f"{'-' * (widths[0] + 1)}|{'-' * (widths[1] + 2)}|{'-' * (widths[2] + 2)}|{'-' * (widths[3] + 1)}", space=False, border=False, side_space=False, sep="-", left=True)
for imdb_id, rating, vote_count, tags, url in rows:
    logger.info(url)
    logger.info(f"{imdb_id:>{widths[0]}} | {rating:>{widths[1]}} | {vote_count:>{widths[2]}} | {tags:<{widths[3]}}")

logger.separator(f"{script_name} Finished\nTotal Runtime: {logger.runtime()}")
