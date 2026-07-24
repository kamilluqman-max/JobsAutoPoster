from facebook_post import post_to_facebook
from telegram_post import post_to_telegram

import time
import requests
import hashlib
import os
import re
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

BASE_URL = "https://www.pakistanjobsbank.com/"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# GitHub Actions controls the 30-minute schedule.
# This scraper runs only once per GitHub Actions execution.

POSTS_PER_RUN = 1

REQUEST_TIMEOUT = 10


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
# DOWNLOAD ALL BLOG POSTS
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

            m = re.search(
                r'<!--SOURCE:(.*?)-->',
                content
            )

            if m:

                urls.add(
                    m.group(1).strip()
                )

        token = response.get(
            "nextPageToken"
        )

        if not token:

            break

    return titles, urls


# ======================================================
# PAGE VALIDATION
# ======================================================

def is_valid_job_page(text):

    text = text.lower()

    keywords = [

        "how to apply",
        "vacancies",
        "eligibility",
        "qualification",
        "last date",
        "official advertisement"

    ]

    return any(
        k in text
        for k in keywords
    )


# ======================================================
# FILTER NON JOB POSTS
# ======================================================

def is_real_job(
    title,
    content
):

    title = title.lower()

    blacklist = [

        "result",
        "answer key",
        "merit list",
        "roll number",
        "syllabus",
        "interview schedule",
        "test date",
        "guess paper"

    ]

    if any(
        word in title
        for word in blacklist
    ):

        return False

    if len(content) < 600:

        return False

    return True


# ======================================================
# LABEL EXTRACTION
# ======================================================

def extract_labels_from_page(
    soup,
    title,
    url
):

    labels = set()

    # ---------- Breadcrumb ----------

    for a in soup.select(
        "ul.breadcrumb a"
    ):

        txt = a.get_text(
            strip=True
        )

        if txt:

            labels.add(
                txt
            )

    # ---------- URL ----------

    url_lower = url.lower()

    mappings = {

        "bank": "Bank Jobs",

        "police": "Police Jobs",

        "army": "Army Jobs",

        "navy": "Navy Jobs",

        "airforce": "PAF Jobs",

        "medical": "Medical Jobs",

        "hospital": "Medical Jobs",

        "education": "Education Jobs",

        "university": "Education Jobs",

        "ngo": "NGO Jobs",

        "embassy": "Embassy Jobs",

        "government": "Government Jobs"

    }

    for key, value in mappings.items():

        if key in url_lower:

            labels.add(
                value
            )

    # ---------- Title ----------

    title_lower = title.lower()

    for key, value in mappings.items():

        if key in title_lower:

            labels.add(
                value
            )

    # ---------- Cleanup ----------

    bad = {

        "home",

        "jobs",

        "latest",

        "pakistan",

        "read more",

        "apply",

        "advertisement"

    }

    cleaned = []

    for item in labels:

        item = item.strip()

        if len(item) < 3:

            continue

        if item.lower() in bad:

            continue

        cleaned.append(
            item
        )

    if not cleaned:

        cleaned.append(
            "Government Jobs"
        )

    return list(
        dict.fromkeys(
            cleaned
        )
    )


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

    if "air force" in t or "paf" in t:

        return "PAF Jobs"

    if "medical" in t or "hospital" in t:

        return "Medical Jobs"

    if "education" in t or "university" in t:

        return "Education Jobs"

    if "teacher" in t or "school" in t:

        return "Education Jobs"

    if "ngo" in t:

        return "NGO Jobs"

    if "embassy" in t:

        return "Embassy Jobs"

    return "Government Jobs"


# ======================================================
# SCRAPER
# ======================================================

def get_jobs():

    print(
        "Loading homepage..."
    )

    try:

        response = requests.get(
            BASE_URL,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

    except Exception as e:

        print(
            "❌ Failed to load Pakistan Jobs Bank:"
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

        title = a.get_text(
            strip=True
        )

        href = a["href"]

        if len(title) < 20:

            continue

        if href.startswith(
            "http"
        ):

            link = href

        else:

            link = BASE_URL + href

        if link in seen:

            continue

        seen.add(
            link
        )

        try:

            page = requests.get(
                link,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT
            )

            page_soup = BeautifulSoup(
                page.text,
                "html.parser"
            )

            if not is_valid_job_page(
                page.text
            ):

                continue

            if not is_real_job(
                title,
                page.text
            ):

                continue

            # ---------- Extract Image ----------

            image = None

            og = page_soup.find(
                "meta",
                property="og:image"
            )

            if og:

                image = og.get(
                    "content"
                )

            if not image:

                img = page_soup.find(
                    "img"
                )

                if img:

                    image = img.get(
                        "src"
                    )

            if image and not image.startswith(
                "http"
            ):

                image = BASE_URL + image

            # ---------- Extract Labels ----------

            labels = extract_labels_from_page(
                page_soup,
                title,
                link
            )

            # ---------- Create Job ----------

            job = {

                "title": title,

                "link": link,

                "image": image,

                "labels": labels,

                "job_type": get_job_type(
                    title
                ),

                "id": hashlib.md5(
                    link.encode()
                ).hexdigest()

            }

            jobs.append(
                job
            )

            print(
                "Found:",
                title
            )

            print(
                "Image:",
                image
            )

        except Exception as e:

            print(
                "Skipped:",
                e
            )

    print(
        "Total Jobs:",
        len(jobs)
    )

    return jobs


# ======================================================
# ARTICLE GENERATOR
# ======================================================

def create_article(job):

    title = job["title"]

    organization = title.split(
        " Jobs"
    )[0]

    job_type = job["job_type"]

    image_html = ""

    if job.get(
        "image"
    ):

        image_html = f"""
<p style="text-align:center;">

<img src="{job['image']}"
style="max-width:100%;height:auto;">

</p>
"""

    content = f"""
<!--SOURCE:{job['link']}-->

<h1>{title}</h1>

{image_html}

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
{organization}
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
According to Official Advertisement
</td>

</tr>

</table>

<h2>Job Details</h2>

<p>

{organization} has announced the latest career opportunities
for eligible candidates across Pakistan. Applicants are advised
to read the official advertisement carefully before submitting
their applications.

</p>

<p>

Candidates possessing the required qualifications and experience
can apply before the closing date mentioned in the official
advertisement.

</p>

<h2>Eligibility Criteria</h2>

<ul>

<li>
Required qualification according to advertisement.
</li>

<li>
Relevant experience where applicable.
</li>

<li>
Age limit according to organization rules.
</li>

<li>
Both male and female candidates may apply where eligible.
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
Experience Certificates
</li>

<li>
Recent Passport Size Photographs
</li>

<li>
Updated CV
</li>

</ul>

<h2>How to Apply</h2>

<ol>

<li>
Read the complete advertisement carefully.
</li>

<li>
Prepare all required documents.
</li>

<li>
Submit the application before the deadline.
</li>

<li>
Incomplete applications may not be accepted.
</li>

</ol>

<h2>Official Advertisement</h2>

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

View Official Advertisement

</a>

</p>

<h2>Final Words</h2>

<p>

Interested candidates should apply as early as possible and
carefully follow all instructions mentioned in the official
advertisement. Late or incomplete applications may not be
entertained.

</p>

"""

    return content


# ======================================================
# BLOGGER POSTING + FACEBOOK + TELEGRAM
# ======================================================

def post_to_blogger(
    service,
    job
):

    content = create_article(
        job
    )

    post = {

        "title": job["title"],

        "content": content,

        "labels": job["labels"]

    }

    # ------------------------------------------
    # Publish to Blogger
    # ------------------------------------------

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
            "⚠️ Blogger did not return a post URL."
        )

        return False

    # ------------------------------------------
    # Facebook
    # ------------------------------------------

    print()

    print(
        "Posting to Facebook..."
    )

    try:

        facebook_success = post_to_facebook(
            job["title"],
            blogger_url,
            job.get("image")
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
            "⚠️ Blogger published successfully,"
            " but Facebook posting failed:"
        )

        print(
            e
        )

    # ------------------------------------------
    # Telegram
    # ------------------------------------------

    print()

    print(
        "Posting to Telegram..."
    )

    try:

        telegram_success = post_to_telegram(
            job["title"],
            blogger_url,
            job.get("image")
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
            "⚠️ Blogger published successfully,"
            " but Telegram posting failed:"
        )

        print(
            e
        )

    return True


# ======================================================
# MAIN
# ======================================================

def main(service):

    print(
        "\nLoading existing Blogger posts..."
    )

    existing_titles, existing_urls = get_existing_posts(
        service
    )

    print(
        f"Found {len(existing_titles)} existing posts."
    )

    jobs = get_jobs()

    if not jobs:

        print(
            "\nNo jobs found."
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

        # ------------------------------------------
        # Duplicate URL Check
        # ------------------------------------------

        if url in existing_urls:

            print(
                "⏩ Duplicate URL skipped"
            )

            print(
                job["title"]
            )

            continue

        # ------------------------------------------
        # Duplicate Title Check
        # ------------------------------------------

        if title in existing_titles:

            print(
                "⏩ Duplicate title skipped"
            )

            print(
                job["title"]
            )

            continue

        # ------------------------------------------
        # Publish ONE Job
        # ------------------------------------------

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

                print(
                    f"Posted {posted}/{POSTS_PER_RUN}"
                )

                print(
                    "\n===================================="
                )

                print(
                    "Posting window complete."
                )

                print(
                    "1 new job posted by scraper2."
                )

                print(
                    "===================================="
                )

                return True

        except Exception as e:

            print(
                "Posting failed:",
                e
            )

    # ------------------------------------------
    # Final Result
    # ------------------------------------------

    print(
        "\n===================================="
    )

    if posted == 0:

        print(
            "No new jobs posted by scraper2."
        )

    else:

        print(
            f"Finished. {posted} new job posted."
        )

    print(
        "===================================="
    )

    return posted > 0


# ======================================================
# START
# ======================================================

if __name__ == "__main__":

    service = get_service()

    print(
        "===================================="
    )

    print(
        "Pakistan Jobs Auto Poster"
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

        print(
            "✅ scraper2 posted a new job."
        )

        exit(0)

    else:

        print(
            "ℹ️ scraper2 did not post a new job."
        )

        exit(1)
