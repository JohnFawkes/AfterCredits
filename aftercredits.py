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
url = "https://aftercredits.com/category/stingers/"
page_num = 0
rows = []
data = YAML(path=os.path.join(base_dir, "aftercredits.yml"), start_empty=True)
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0",
    "Accept-Language": "en-US,en;q=0.5",
}

response = html.fromstring(requests.get(url, headers=headers).content)
last_page = response.xpath("//a[@class='last']/@href")
total_pages = int(re.search(r"/page/(\d+)/", last_page[0]).group(1)) if last_page else 1
logger.info(f"Total Pages: {total_pages}")

while page_num < total_pages:
    page_num += 1
    if page_num > 1:
        url = f"https://aftercredits.com/category/stingers/page/{page_num}/"
        response = html.fromstring(requests.get(url, headers=headers).content)
    logger.info(f"Parsing Page {page_num}: {url}")

    for media_url in response.xpath("//h3[contains(@class, 'entry-title')]/a/@href"):
        try:
            logger.trace(f"Parsing Media: {media_url}")
            media_response = html.fromstring(requests.get(media_url, headers=headers).content)
            imdb_url = media_response.xpath("//a[text()='IMDb']/@href")
            if not imdb_url:
                raise ValueError(f"Skipped {media_url}: IMDb URL not found")

            res = re.search(r".*/(tt\d*)/.*", imdb_url[0])
            imdb_id = res.group(1) if res else None
            if imdb_id is None:
                raise ValueError(f"Skipped {media_url}: IMDb ID not found")

            tags = [str(t) for t in media_response.xpath("//li[@class='entry-category']/a/text()") if str(t) not in ["Now Showing", "Stingers"]]
            if "Games" in tags:
                raise ValueError(f"Skipped {media_url}: Video Game")
            rating_data = media_response.xpath("//span[@class='post-ratings']/strong/text()")
            rating = int(rating_data[0]) if rating_data else 0
            votes = int(rating_data[1]) if rating_data else 0

            rows.append((imdb_id, rating, votes, ', '.join(tags), media_url))
            data[imdb_id] = YAML.inline({"rating": rating, "votes": votes, "tags": tags})
        except ValueError as e:
            logger.warning(e)


headers = ["IMDb ID", "Rating", "Votes", "Tags"]
widths = []
for i, header in enumerate(headers):
    _max = len(str(max(rows, key=lambda t: len(str(t[i])))[i]))
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
