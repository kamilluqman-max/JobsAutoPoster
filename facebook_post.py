import os
import requests

PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")


def post_to_facebook(title, url):
    message = f"""📢 New Job Alert

{title}

Apply Here:
{url}
"""

    endpoint = f"https://graph.facebook.com/v25.0/{PAGE_ID}/feed"

    data = {
        "message": message,
        "access_token": ACCESS_TOKEN
    }

    response = requests.post(endpoint, data=data)

    if response.status_code == 200:
        print("✅ Posted to Facebook")
    else:
        print("❌ Facebook Error")
        print(response.text)