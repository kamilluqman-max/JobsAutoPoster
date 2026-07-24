from facebook_post import post_to_facebook
from telegram_post import post_to_telegram

import csv
import requests
import hashlib
import os
import re
import random
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# ======================================================
# CONFIGURATION
# ======================================================

SCOPES = [
    "https://www.googleapis.com/auth/blogger"
]

BLOG_ID = "8970771897067197122"

# ONLY THIS PAGE IS SCRAPED
JOBS_URL = "https://bebee.com/pk/jobs"

BASE_URL = "https://bebee.com/"

# SEO KEYWORDS CSV
SEO_KEYWORDS_FILE = "seo_keywords.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,"
        "image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9"
}

REQUEST_TIMEOUT = 15

# ======================================================
# ONLY ONE NEW JOB PER COMPLETE GITHUB RUN
# ======================================================

POSTS_PER_RUN = 1


# ======================================================
# BLOGGER AUTH
# ======================================================

def get_service():

    creds = None

    if os.path.exists("token.json"):

        creds = Credentials.from_authorized_user_file(
            "token.json",
            SCOPES
        )

    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:

            creds.refresh(
                Request()
            )

        else:

            flow = InstalledAppFlow.from_client_secrets_file(
                "client_secret.json",
                SCOPES
            )

            creds = flow.run_local_server(
                port=0
            )

        with open(
            "token.json",
            "w"
        ) as token:

            token.write(
                creds.to_json()
            )

    return build(
        "blogger",
        "v3",
        credentials=creds
    )


# ======================================================
# GET EXISTING BLOGGER POSTS
# ======================================================

def get_existing_posts(service):

    titles = set()

    urls = set()

    token = None

    while True:

        response = service.posts().list(
            blogId=BLOG_ID,
            maxResults=500,
            pageToken=token
        ).execute()

        for post in response.get(
            "items",
            []
        ):

            title = post.get(
                "title",
                ""
            ).strip().lower()

            if title:

                titles.add(
                    title
                )

            content = post.get(
                "content",
                ""
            )

            match = re.search(
                r'<!--SOURCE:(.*?)-->',
                content
            )

            if match:

                urls.add(
                    match.group(
                        1
                    ).strip()
                )

        token = response.get(
            "nextPageToken"
        )

        if not token:

            break

    return titles, urls


# ======================================================
# JOB TYPE
# ======================================================

def get_job_type(title):

    t = title.lower()

    if "bank" in t:

        return "Bank Jobs"

    if "police" in t or "traffic" in t:

        return "Police Jobs"

    if "army" in t:

        return "Army Jobs"

    if "navy" in t:

        return "Navy Jobs"

    if (
        "air force" in t
        or "airforce" in t
        or "paf" in t
    ):

        return "PAF Jobs"

    if (
        "medical" in t
        or "hospital" in t
        or "doctor" in t
        or "nurse" in t
        or "health" in t
    ):

        return "Medical Jobs"

    if (
        "education" in t
        or "university" in t
        or "teacher" in t
        or "school" in t
    ):

        return "Education Jobs"

    if "ngo" in t:

        return "NGO Jobs"

    if "embassy" in t:

        return "Embassy Jobs"

    if (
        "government" in t
        or "govt" in t
    ):

        return "Government Jobs"

    return "Private Jobs"


# ======================================================
# LABEL EXTRACTION
# ======================================================

def extract_labels(
    title,
    url,
    soup
):

    labels = set()

    mappings = {

        "bank": "Bank Jobs",

        "banking": "Bank Jobs",

        "police": "Police Jobs",

        "traffic": "Police Jobs",

        "army": "Army Jobs",

        "navy": "Navy Jobs",

        "air force": "PAF Jobs",

        "airforce": "PAF Jobs",

        "paf": "PAF Jobs",

        "medical": "Medical Jobs",

        "hospital": "Medical Jobs",

        "doctor": "Medical Jobs",

        "nurse": "Medical Jobs",

        "health": "Medical Jobs",

        "education": "Education Jobs",

        "university": "Education Jobs",

        "school": "Education Jobs",

        "teacher": "Education Jobs",

        "ngo": "NGO Jobs",

        "embassy": "Embassy Jobs",

        "government": "Government Jobs",

        "govt": "Government Jobs"

    }

    text = (

        title
        + " "
        + url
        + " "
        + soup.get_text(
            " ",
            strip=True
        )

    ).lower()

    for key, value in mappings.items():

        if key in text:

            labels.add(
                value
            )

    if not labels:

        labels.add(
            "Private Jobs"
        )

    return list(
        dict.fromkeys(
            labels
        )
    )


# ======================================================
# LOAD SEO KEYWORDS
# ======================================================

def load_seo_keywords():

    keywords = []

    if not os.path.exists(
        SEO_KEYWORDS_FILE
    ):

        print(
            "⚠️ seo_keywords.csv not found."
        )

        return keywords

    try:

        with open(
            SEO_KEYWORDS_FILE,
            "r",
            encoding="utf-8-sig"
        ) as file:

            reader = csv.DictReader(
                file
            )

            for row in reader:

                keyword = ""

                category = ""

                if row.get(
                    "keyword"
                ):

                    keyword = row.get(
                        "keyword"
                    ).strip()

                elif row.get(
                    "keywords"
                ):

                    keyword = row.get(
                        "keywords"
                    ).strip()

                if row.get(
                    "category"
                ):

                    category = row.get(
                        "category"
                    ).strip()

                if keyword:

                    keywords.append({

                        "keyword":
                            keyword,

                        "category":
                            category

                    })

        print(
            f"Loaded {len(keywords)} SEO keywords."
        )

    except Exception as e:

        print(
            "⚠️ Failed to load seo_keywords.csv:",
            e
        )

    return keywords


# ======================================================
# SELECT SEO KEYWORDS
# ======================================================

def select_seo_keywords(
    job,
    max_keywords=3
):

    all_keywords = load_seo_keywords()

    if not all_keywords:

        return [

            "latest jobs in Pakistan",

            "Pakistan jobs",

            "online jobs in Pakistan"

        ]

    title = job.get(
        "title",
        ""
    ).lower()

    job_type = job.get(
        "job_type",
        ""
    ).lower()

    labels = " ".join(
        job.get(
            "labels",
            []
        )
    ).lower()

    combined_text = (

        title
        + " "
        + job_type
        + " "
        + labels

    )

    selected = []

    # ------------------------------------------
    # MATCH KEYWORDS
    # ------------------------------------------

    for item in all_keywords:

        keyword = item.get(
            "keyword",
            ""
        ).strip()

        if not keyword:

            continue

        if keyword.lower() in combined_text:

            if keyword not in selected:

                selected.append(
                    keyword
                )

        if len(
            selected
        ) >= max_keywords:

            break

    # ------------------------------------------
    # MATCH CATEGORY
    # ------------------------------------------

    if len(
        selected
    ) < max_keywords:

        for item in all_keywords:

            keyword = item.get(
                "keyword",
                ""
            ).strip()

            category = item.get(
                "category",
                ""
            ).strip().lower()

            if not keyword:

                continue

            if keyword in selected:

                continue

            if category == "general":

                selected.append(
                    keyword
                )

            elif category == "general jobs":

                selected.append(
                    keyword
                )

            elif (
                category == "government"
                and "government jobs" in job_type
            ):

                selected.append(
                    keyword
                )

            elif (
                category == "private"
                and "private jobs" in job_type
            ):

                selected.append(
                    keyword
                )

            elif (
                category == "bank"
                and "bank jobs" in job_type
            ):

                selected.append(
                    keyword
                )

            elif (
                category == "police"
                and "police jobs" in job_type
            ):

                selected.append(
                    keyword
                )

            elif (
                category == "army"
                and "army jobs" in job_type
            ):

                selected.append(
                    keyword
                )

            elif (
                category == "navy"
                and "navy jobs" in job_type
            ):

                selected.append(
                    keyword
                )

            elif (
                category == "paf"
                and "paf jobs" in job_type
            ):

                selected.append(
                    keyword
                )

            elif (
                category == "medical"
                and "medical jobs" in job_type
            ):

                selected.append(
                    keyword
                )

            elif (
                category == "education"
                and "education jobs" in job_type
            ):

                selected.append(
                    keyword
                )

            elif (
                category == "ngo"
                and "ngo jobs" in job_type
            ):

                selected.append(
                    keyword
                )

            if len(
                selected
            ) >= max_keywords:

                break

    # ------------------------------------------
    # FINAL FALLBACK
    # ------------------------------------------

    if len(
        selected
    ) < max_keywords:

        for item in all_keywords:

            keyword = item.get(
                "keyword",
                ""
            ).strip()

            if not keyword:

                continue

            if keyword in selected:

                continue

            selected.append(
                keyword
            )

            if len(
                selected
            ) >= max_keywords:

                break

    if not selected:

        selected = [

            "latest jobs in Pakistan",

            "Pakistan jobs",

            "online jobs in Pakistan"

        ]

    selected = selected[
        :max_keywords
    ]

    print()

    print(
        "SEO KEYWORDS:"
    )

    for keyword in selected:

        print(
            "🔑",
            keyword
        )

    return selected


# ======================================================
# CREATE VARIED SEO PARAGRAPHS
# ======================================================

def create_seo_paragraphs(
    job,
    keywords
):

    if not keywords:

        keywords = [

            "latest jobs in Pakistan",

            "Pakistan jobs",

            "online jobs in Pakistan"

        ]

    while len(
        keywords
    ) < 3:

        keywords.append(
            keywords[0]
        )

    title = job.get(
        "title",
        "this job opportunity"
    ).strip()

    job_type = job.get(
        "job_type",
        "Private Jobs"
    ).strip()

    labels = job.get(
        "labels",
        []
    )

    if labels:

        category = labels[0]

    else:

        category = job_type

    paragraph1_templates = [

        f"""
<p>
Candidates searching for <b>{{keyword}}</b> can explore
this latest {category.lower()} opportunity. The position
listed as <b>{title}</b> may be suitable for eligible
applicants seeking new career opportunities in Pakistan.
Interested candidates should review the complete vacancy
details before applying.
</p>
""",

        f"""
<p>
Those looking for <b>{{keyword}}</b> may find this
<b>{title}</b> vacancy worth considering. This opportunity
falls under the {job_type.lower()} category and may provide
a suitable career option for candidates who meet the required
qualifications and eligibility conditions.
</p>
""",

        f"""
<p>
If you are exploring <b>{{keyword}}</b>, this newly listed
<b>{title}</b> position may be relevant to your job search.
Applicants are encouraged to check the official vacancy
information carefully and confirm that they meet all
requirements before submitting an application.
</p>
""",

        f"""
<p>
Job seekers interested in <b>{{keyword}}</b> can review the
latest opening for <b>{title}</b>. The vacancy is listed under
{category.lower()}, and eligible candidates should examine the
available job information, qualifications, and application
instructions before proceeding.
</p>
""",

        f"""
<p>
For candidates searching for <b>{{keyword}}</b>, the
<b>{title}</b> opportunity is another vacancy to consider.
Applicants who are interested in this {job_type.lower()}
position should read the official listing and verify the
eligibility criteria before applying.
</p>
"""

    ]

    paragraph2_templates = [

        f"""
<p>
Applicants interested in <b>{{keyword}}</b> should carefully
review the qualification requirements and other conditions
mentioned for <b>{title}</b>. Candidates who satisfy the
eligibility criteria can follow the employer's official
application procedure and submit the required information.
</p>
""",

        f"""
<p>
Those searching for <b>{{keyword}}</b> should check the
complete details of this vacancy, including qualifications,
experience requirements, and application instructions.
Before applying for <b>{title}</b>, candidates should ensure
that their profile matches the conditions specified by the
employer.
</p>
""",

        f"""
<p>
Candidates considering <b>{{keyword}}</b> are advised to
read all available information about <b>{title}</b>. Meeting
the required educational and professional criteria is
important, so applicants should confirm their eligibility
before starting the application process.
</p>
""",

        f"""
<p>
For anyone exploring <b>{{keyword}}</b>, it is important to
understand the requirements associated with <b>{title}</b>.
Eligible applicants should prepare the necessary documents
and carefully follow the instructions provided in the
official job advertisement.
</p>
""",

        f"""
<p>
People interested in <b>{{keyword}}</b> can learn more by
checking the vacancy details for <b>{title}</b>. Applicants
should pay attention to the eligibility requirements and
make sure all requested information is provided correctly
when applying.
</p>
"""

    ]

    paragraph3_templates = [

        f"""
<p>
Applicants searching for <b>{{keyword}}</b> and other career
opportunities in Pakistan should consider reviewing this
vacancy. Those interested in <b>{title}</b> should prepare
their documents in advance and complete the application
process according to the official instructions.
</p>
""",

        f"""
<p>
Job seekers exploring <b>{{keyword}}</b> can use this
opportunity to discover another potential career option.
Candidates interested in <b>{title}</b> should apply within
the announced timeline and make sure they follow every step
required by the employer.
</p>
""",

        f"""
<p>
Those looking for <b>{{keyword}}</b> may want to review this
opening and compare its requirements with their qualifications.
Eligible candidates interested in <b>{title}</b> should
complete the application process carefully and avoid waiting
until the last moment.
</p>
""",

        f"""
<p>
Candidates who regularly search for <b>{{keyword}}</b> can
keep this <b>{title}</b> vacancy in mind as part of their
current job search. Interested applicants should check the
official listing for the latest information and submit their
application through the specified method.
</p>
""",

        f"""
<p>
For those seeking <b>{{keyword}}</b>, this vacancy may offer
another opportunity to explore. Applicants interested in
<b>{title}</b> should verify the latest requirements, gather
their documents, and follow the official application process
before the closing date.
</p>
"""

    ]

    random.shuffle(
        paragraph1_templates
    )

    random.shuffle(
        paragraph2_templates
    )

    random.shuffle(
        paragraph3_templates
    )

    paragraph1 = paragraph1_templates[0].format(
        keyword=keywords[0]
    )

    paragraph2 = paragraph2_templates[0].format(
        keyword=keywords[1]
    )

    paragraph3 = paragraph3_templates[0].format(
        keyword=keywords[2]
    )

    print()

    print(
        "✅ Varied SEO paragraphs generated."
    )

    return (

        paragraph1
        + "\n"
        + paragraph2
        + "\n"
        + paragraph3

    )


# ======================================================
# EXTRACT TITLE
# ======================================================

def extract_title(
    card
):

    for tag in [

        "h1",
        "h2",
        "h3",
        "h4"

    ]:

        element = card.find(
            tag
        )

        if element:

            title = element.get_text(
                " ",
                strip=True
            )

            if title:

                return title

    for element in card.select(

        "[class*='title'], "
        "[class*='job-name'], "
        "[class*='position']"

    ):

        title = element.get_text(
            " ",
            strip=True
        )

        if title:

            return title

    return ""


# ======================================================
# EXTRACT IMAGE
# ======================================================

def extract_image(
    card,
    page_url
):

    image = card.find(
        "img"
    )

    if image:

        src = (

            image.get(
                "src"
            )

            or image.get(
                "data-src"
            )

            or image.get(
                "data-lazy-src"
            )

        )

        if src:

            return urljoin(
                page_url,
                src
            )

    return None


# ======================================================
# TODAY JOB CHECK
# ======================================================

def is_today_job(
    card
):

    text = card.get_text(
        " ",
        strip=True
    ).lower()

    today_keywords = [

        "today",
        "just now",
        "hours ago",
        "hour ago",
        "minutes ago",
        "minute ago",
        "1 hour ago",
        "2 hours ago",
        "3 hours ago",
        "4 hours ago",
        "5 hours ago",
        "6 hours ago",
        "7 hours ago",
        "8 hours ago",
        "9 hours ago",
        "10 hours ago",
        "11 hours ago",
        "12 hours ago",
        "13 hours ago",
        "14 hours ago",
        "15 hours ago",
        "16 hours ago",
        "17 hours ago",
        "18 hours ago",
        "19 hours ago",
        "20 hours ago",
        "21 hours ago",
        "22 hours ago",
        "23 hours ago"

    ]

    for keyword in today_keywords:

        if keyword in text:

            return True

    return False


# ======================================================
# SCRAPE BEEBEE
# ======================================================

def get_jobs():

    print()

    print(
        "===================================="
    )

    print(
        "Loading BeBee Pakistan jobs..."
    )

    print(
        JOBS_URL
    )

    print(
        "===================================="
    )

    try:

        response = requests.get(

            JOBS_URL,

            headers=HEADERS,

            timeout=REQUEST_TIMEOUT

        )

        response.raise_for_status()

    except Exception as e:

        print()

        print(
            "❌ Failed to load BeBee:"
        )

        print(
            e
        )

        return []

    soup = BeautifulSoup(

        response.text,

        "html.parser"

    )

    jobs = []

    seen = set()

    for a in soup.find_all(

        "a",

        href=True

    ):

        href = a.get(
            "href",
            ""
        ).strip()

        if not href:

            continue

        link = urljoin(
            BASE_URL,
            href
        )

        parsed = urlparse(
            link
        )

        if parsed.netloc.lower() not in [

            "bebee.com",
            "www.bebee.com"

        ]:

            continue

        path = parsed.path.lower()

        if path in [

            "/",
            "/pk",
            "/pk/jobs",
            "/pk/jobs/"

        ]:

            continue

        if link in seen:

            continue

        seen.add(
            link
        )

        card = (

            a.find_parent(
                "article"
            )

            or a.find_parent(
                "li"
            )

            or a.find_parent(
                "div"
            )

        )

        if not card:

            continue

        title = extract_title(
            card
        )

        if not title:

            title = a.get_text(
                " ",
                strip=True
            )

        if not title:

            continue

        if len(
            title
        ) < 5:

            continue

        if not is_today_job(
            card
        ):

            continue

        image = extract_image(

            card,

            JOBS_URL

        )

        labels = extract_labels(

            title,

            link,

            card

        )

        job = {

            "title":
                title,

            "link":
                link,

            "image":
                image,

            "labels":
                labels,

            "job_type":
                get_job_type(
                    title
                ),

            "id":
                hashlib.md5(
                    link.encode()
                ).hexdigest()

        }

        jobs.append(
            job
        )

        print()

        print(
            "✅ TODAY JOB FOUND"
        )

        print(
            "Title:",
            title
        )

        print(
            "Labels:",
            labels
        )

        print(
            "Image:",
            image
        )

        print(
            "URL:",
            link
        )

    print()

    print(
        "===================================="
    )

    print(
        "Today's Jobs Found:",
        len(jobs)
    )

    print(
        "===================================="
    )

    return jobs


# ======================================================
# CREATE BLOGGER ARTICLE
# ======================================================

def create_article(
    job
):

    title = job[
        "title"
    ]

    job_type = job[
        "job_type"
    ]

    seo_keywords = select_seo_keywords(

        job,

        max_keywords=3

    )

    seo_paragraphs = create_seo_paragraphs(

        job,

        seo_keywords

    )

    image_html = ""

    if job.get(
        "image"
    ):

        image_html = f"""
<p style="text-align:center;">

<img src="{job['image']}"
alt="{title}"
style="max-width:100%;height:auto;">

</p>
"""

    content = f"""
<!--SOURCE:{job['link']}-->

<h1>{title}</h1>

{image_html}

<h2>Latest Job Opportunity</h2>

{seo_paragraphs}

<h2>Quick Information</h2>

<table border="1"
cellpadding="8"
cellspacing="0"
style="width:100%;border-collapse:collapse;">

<tr>

<td>
<b>Organization</b>
</td>

<td>
Employer
</td>

</tr>

<tr>

<td>
<b>Job Type</b>
</td>

<td>
{job_type}
</td>

</tr>

<tr>

<td>
<b>Location</b>
</td>

<td>
Pakistan
</td>

</tr>

<tr>

<td>
<b>Application Method</b>
</td>

<td>
According to Official Job Listing
</td>

</tr>

</table>

<h2>Job Details</h2>

<p>
{title} is a job opportunity listed for eligible candidates.
Applicants should carefully review the official job listing
and follow all application instructions before applying.
</p>

<h2>Eligibility Criteria</h2>

<ul>

<li>
Required qualification according to the official job listing.
</li>

<li>
Relevant experience where applicable.
</li>

<li>
Candidates must meet the requirements specified by the employer.
</li>

</ul>

<h2>Required Documents</h2>

<ul>

<li>
CNIC
</li>

<li>
Educational Certificates
</li>

<li>
Experience Certificates where applicable
</li>

<li>
Updated CV
</li>

<li>
Recent Photograph where required
</li>

</ul>

<h2>How to Apply</h2>

<ol>

<li>
Read the complete official job listing.
</li>

<li>
Prepare the required documents.
</li>

<li>
Follow the employer's application instructions.
</li>

<li>
Submit your application before the deadline.
</li>

</ol>

<h2>Official Job Listing</h2>

<p style="text-align:center;">

<a href="{job['link']}"
target="_blank"
style="
background:#0066cc;
color:#fff;
padding:12px 20px;
border-radius:5px;
text-decoration:none;
display:inline-block;
font-weight:bold;">

View Official Job Listing

</a>

</p>

<h2>Final Words</h2>

<p>

Interested candidates should apply as early as possible
and carefully follow all instructions mentioned in the
official job listing.

</p>
"""

    return content


# ======================================================
# BLOGGER + FACEBOOK + TELEGRAM
# ======================================================

def post_to_blogger(
    service,
    job
):

    content = create_article(
        job
    )

    post = {

        "title":
            job["title"],

        "content":
            content,

        "labels":
            job["labels"]

    }

    result = service.posts().insert(

        blogId=BLOG_ID,

        body=post,

        isDraft=False

    ).execute()

    blogger_url = result.get(
        "url"
    )

    print()

    print(
        "===================================="
    )

    print(
        "✅ Blogger Post Published"
    )

    print(
        "Title:",
        job["title"]
    )

    print(
        "Blogger URL:",
        blogger_url
    )

    print(
        "===================================="
    )

    if not blogger_url:

        print(
            "⚠️ Blogger did not return a URL."
        )

        return False

    # ==================================================
    # FACEBOOK
    # ==================================================

    try:

        facebook_success = post_to_facebook(

            job["title"],

            blogger_url,

            job.get(
                "image"
            )

        )

        if facebook_success:

            print(
                "✅ Facebook post created successfully"
            )

        else:

            print(
                "❌ Facebook posting failed"
            )

    except Exception as e:

        print(
            "⚠️ Facebook posting failed:",
            e
        )

    # ==================================================
    # TELEGRAM
    # ==================================================

    try:

        telegram_success = post_to_telegram(

            job["title"],

            blogger_url,

            job.get(
                "image"
            )

        )

        if telegram_success:

            print(
                "✅ Telegram post created successfully"
            )

        else:

            print(
                "❌ Telegram posting failed"
            )

    except Exception as e:

        print(
            "⚠️ Telegram posting failed:",
            e
        )

    return True


# ======================================================
# MAIN
# ======================================================

def main(
    service
):

    print()

    print(
        "Loading existing Blogger posts..."
    )

    existing_titles, existing_urls = get_existing_posts(

        service

    )

    print(
        f"Found {len(existing_titles)} existing posts."
    )

    jobs = get_jobs()

    if not jobs:

        print()

        print(
            "No today's jobs found."
        )

        return False

    posted = 0

    for job in jobs:

        if posted >= POSTS_PER_RUN:

            break

        title = job[
            "title"
        ].strip().lower()

        url = job[
            "link"
        ].strip()

        if url in existing_urls:

            print()

            print(
                "⏩ Duplicate URL skipped:"
            )

            print(
                job["title"]
            )

            continue

        if title in existing_titles:

            print()

            print(
                "⏩ Duplicate title skipped:"
            )

            print(
                job["title"]
            )

            continue

        try:

            success = post_to_blogger(

                service,

                job

            )

            if success:

                existing_titles.add(
                    title
                )

                existing_urls.add(
                    url
                )

                posted += 1

                print()

                print(
                    "===================================="
                )

                print(
                    "BeBee successfully posted 1 new job."
                )

                print(
                    "GitHub Actions will NOT run scraper2."
                )

                print(
                    "===================================="
                )

                return True

        except Exception as e:

            print()

            print(
                "❌ Posting failed:"
            )

            print(
                e
            )

    print()

    print(
        "===================================="
    )

    print(
        "No new job was posted by BeBee."
    )

    print(
        "GitHub Actions will now run scraper2.py."
    )

    print(
        "===================================="
    )

    return False


# ======================================================
# START
# ======================================================

if __name__ == "__main__":

    service = get_service()

    print()

    print(
        "===================================="
    )

    print(
        "BeBee Pakistan Jobs Auto Poster"
    )

    print(
        "30-Minute Posting Window"
    )

    print(
        "Maximum 1 New Job Per Run"
    )

    print(
        "===================================="
    )

    success = main(
        service
    )

    if success:

        exit(0)

    else:

        exit(1)
