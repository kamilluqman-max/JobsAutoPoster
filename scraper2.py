import schedule
import time
import requests
import hashlib
import os

from bs4 import BeautifulSoup

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# ---------------- SETTINGS ----------------

def extract_labels_from_page(soup, title, url):
    labels = set()

    # -------------------------------
    # 1. Breadcrumb extraction (BEST)
    # -------------------------------
    breadcrumb = soup.select("ul.breadcrumb li a")

    for b in breadcrumb:
        text = b.get_text(strip=True)
        if text and len(text) > 2:
            labels.add(text)

    # -------------------------------
    # 2. Category / tag links
    # -------------------------------
    for a in soup.find_all("a"):
        text = a.get_text(strip=True)

        if "job" in text.lower():
            labels.add(text)

    # -------------------------------
    # 3. URL fallback detection
    # -------------------------------
    url_lower = url.lower()

    if "bank" in url_lower:
        labels.add("Bank Jobs")

    if "army" in url_lower:
        labels.add("Army Jobs")

    if "medical" in url_lower:
        labels.add("Medical Jobs")

    if "government" in url_lower:
        labels.add("Government Jobs")

    # -------------------------------
    # Clean noise labels
    # -------------------------------
    bad = {
        "home",
        "jobs",
        "latest",
        "pakistan",
        "read more",
        "apply"
    }

    final_labels = []
    for l in labels:
        if l.lower() not in bad and len(l) > 2:
            final_labels.append(l)

    return list(dict.fromkeys(final_labels))[:6]

SCOPES = ["https://www.googleapis.com/auth/blogger"]

BLOG_ID = "7936247778963054240"

BASE_URL = "https://www.pakistanjobsbank.com/"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# ------------------------------------------


# ---------------- AUTH ----------------

def get_service():
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "client_secret.json",
                SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("blogger", "v3", credentials=creds)

# ---------------- DUPLICATE CHECK ----------------

def get_existing_titles(service):

    titles = set()

    try:
        posts = service.posts().list(
            blogId=BLOG_ID,
            maxResults=100
        ).execute()

        for post in posts.get("items", []):
            titles.add(
                post["title"].strip().lower()
            )

    except Exception as e:
        print("Blogger check error:", e)

    return titles

# ---------------- VALIDATION ----------------

def is_valid_job_page(text):
    text = text.lower()

    keywords = [
        "apply online",
        "vacancies",
        "how to apply",
        "eligibility",
        "qualification"
    ]

    return any(k in text for k in keywords)


def is_real_job(title, content):
    title = title.lower()

    blacklist = [
        "result",
        "answer key",
        "merit list",
        "roll number",
        "admit card",
        "test date",
        "syllabus",
        "interview schedule"
    ]

    if any(word in title for word in blacklist):
        return False

    if len(content) < 500:
        return False

    return True


# ---------------- SCRAPER ----------------

def get_jobs():
    response = requests.get(BASE_URL, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")

    jobs = []

    for a in soup.find_all("a", href=True):

        title = a.get_text(strip=True)
        link = a["href"]

        if not title or not link:
            continue

        if len(title) < 25:
            continue

        # skip junk links
        if any(x in link for x in ["category", "tag", "page", "author", "contact"]):
            continue

        full_link = link if link.startswith("http") else BASE_URL + link

        job_id = hashlib.md5(full_link.encode()).hexdigest()

        # fetch job page
        try:
            page = requests.get(full_link, headers=HEADERS, timeout=8)
            page_soup = BeautifulSoup(page.text, "html.parser")

            labels = extract_labels_from_page(page_soup, title, full_link)

            if not is_valid_job_page(page.text):
                continue

            if not is_real_job(title, page.text):
                continue

            image_url = None
            img = page_soup.find("img")

            if img and img.get("src"):
                image_url = img["src"]

                if not image_url.startswith("http"):
                    image_url = BASE_URL + image_url

        except:
            continue

        jobs.append({
            "title": title,
            "link": full_link,
            "image": image_url,
            "id": job_id,
            "labels": labels
         })

    return jobs


# ---------------- RELATED POSTS ----------------

def get_related_posts(service, current_title):
    related = []

    try:
        posts = service.posts().list(
            blogId=BLOG_ID,
            maxResults=5
        ).execute()

        for post in posts.get("items", []):

            if post["title"] == current_title:
                continue

            related.append(
                f'<li><a href="{post["url"]}">{post["title"]}</a></li>'
            )

            if len(related) >= 3:
                break

    except:
        pass

    return "".join(related)


# ---------------- ARTICLE ----------------

def create_article(job, service):

    title = job["title"]
    organization = title.split(" Jobs")[0]

    image_html = ""

    if job.get("image"):
        image_html = f"""
        <img src="{job['image']}" style="width:100%;height:auto;margin-bottom:20px;">
        """

    related_jobs = get_related_posts(service, title)

    content = f"""
<h1>{title}</h1>

{image_html}

<h2>Quick Information</h2>

<table border="1" cellpadding="8" cellspacing="0" style="width:100%;">
<tr><td><b>Organization</b></td><td>{organization}</td></tr>
<tr><td><b>Job Type</b></td><td>Latest Jobs</td></tr>
<tr><td><b>Location</b></td><td>Pakistan</td></tr>
<tr><td><b>Application Method</b></td><td>According to Advertisement</td></tr>
</table>

<h2>Job Details</h2>
<p>{organization} has announced new job opportunities for eligible candidates. Read complete details before applying.</p>

<h2>How to Apply</h2>
<ol>
<li>Read advertisement carefully</li>
<li>Prepare documents</li>
<li>Apply before deadline</li>
</ol>

<p>
<a href="{job['link']}" target="_blank">
View Official Advertisement
</a>
</p>

<h2>Official Advertisement</h2>

<p style="text-align:center;">
<a href="{job['link']}" target="_blank"
style="background:#0066cc;color:white;padding:12px 20px;text-decoration:none;border-radius:5px;">
View Original Advertisement
</a>
</p>

<h2>Related Jobs</h2>
<ul>
{related_jobs}
</ul>

<h2>Final Words</h2>
<p>{organization} offers great career opportunities. Apply as soon as possible.</p>
"""

    return content


# ---------------- LABELS (CLEAN) ----------------

def get_labels(title):
    t = title.lower()

    labels = ["Government Jobs"]

    if "bank" in t:
        labels.append("Bank Jobs")

    elif "army" in t:
        labels.append("Army Jobs")

    elif "police" in t:
        labels.append("Police Jobs")

    elif "medical" in t or "hospital" in t:
        labels.append("Medical Jobs")

    elif "university" in t or "education" in t:
        labels.append("Education Jobs")

    elif "ngo" in t:
        labels.append("NGO Jobs")

    elif "embassy" in t:
        labels.append("Embassy Jobs")

    elif "paf" in t:
        labels.append("PAF Jobs")

    elif "navy" in t:
        labels.append("Navy Jobs")

    elif "university" in t or "education" in t:
        labels.append("Education Jobs")

    return list(dict.fromkeys(labels))[:5]


# ---------------- POST TO BLOGGER ----------------

def post_to_blogger(service, title, content, labels):

    post = {
        "title": title,
        "content": content,
        "labels": labels
    }

    service.posts().insert(
        blogId=BLOG_ID,
        body=post,
        isDraft=False
    ).execute()

    print("✅ Posted:", title)


# ---------------- MAIN ----------------

def main(service):

    jobs = get_jobs()

    existing_titles = get_existing_titles(service)

    count = 0

    for job in jobs:

        if count >= 5:
            break

        if job["title"].strip().lower() in existing_titles:
            print("Already exists:", job["title"])
            continue

        content = create_article(job, service)

        post_to_blogger(service, job["title"], content, job["labels"])

        count += 1

        print("Done:", job["title"])

        if count < 5:
            print("Waiting 10 seconds...")
            time.sleep(10)


def job(service):
    print("\n==============================")
    print("Checking for new jobs...")
    print("==============================")
    main(service)


if __name__ == "__main__":

    service = get_service()

    print("Jobs Auto Poster Started")
    print("Checking for new jobs...")

    job(service)

    schedule.every(30).minutes.do(job, service)

    while True:
        schedule.run_pending()
        time.sleep(30)