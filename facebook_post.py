import os
import requests
from dotenv import load_dotenv


# ======================================================
# LOAD ENVIRONMENT VARIABLES
# ======================================================

load_dotenv()

PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")


# ======================================================
# POST TO FACEBOOK PAGE
# ======================================================

def post_to_facebook(
    title,
    url,
    image=None
):

    # ------------------------------------------
    # Validate Facebook configuration
    # ------------------------------------------

    if not PAGE_ID:

        raise ValueError(
            "FACEBOOK_PAGE_ID is missing from .env"
        )

    if not ACCESS_TOKEN:

        raise ValueError(
            "FACEBOOK_ACCESS_TOKEN is missing from .env"
        )

    # ------------------------------------------
    # Validate Blogger URL
    # ------------------------------------------

    if not url:

        raise ValueError(
            "Blogger post URL is missing"
        )

    # ------------------------------------------
    # Facebook Post Message
    # ------------------------------------------

    message = f"""📢 New Job Alert

{title}

🔗 Apply Here:
{url}
"""

    # ==================================================
    # IF IMAGE EXISTS → POST IMAGE + MESSAGE
    # ==================================================

    if image:

        endpoint = (
            f"https://graph.facebook.com/v25.0/"
            f"{PAGE_ID}/photos"
        )

        data = {

            "url": image,

            "caption": message,

            "access_token": ACCESS_TOKEN

        }

    # ==================================================
    # IF NO IMAGE → POST TEXT + URL
    # ==================================================

    else:

        endpoint = (
            f"https://graph.facebook.com/v25.0/"
            f"{PAGE_ID}/feed"
        )

        data = {

            "message": message,

            "access_token": ACCESS_TOKEN

        }

    # ------------------------------------------
    # Send Request
    # ------------------------------------------

    response = requests.post(
        endpoint,
        data=data,
        timeout=30
    )

    # ------------------------------------------
    # Success
    # ------------------------------------------

    if response.status_code == 200:

        result = response.json()

        facebook_post_id = result.get(
            "post_id"
        ) or result.get(
            "id"
        )

        print()
        print(
            "✅ Posted to Facebook"
        )

        print(
            "Facebook Post ID:",
            facebook_post_id
        )

        print(
            "Blogger URL:",
            url
        )

        if image:

            print(
                "Facebook Image:",
                image
            )

        return True

    # ------------------------------------------
    # Error
    # ------------------------------------------

    else:

        print()
        print(
            "❌ Facebook Error"
        )

        print(
            "Status Code:",
            response.status_code
        )

        print(
            "Response:",
            response.text
        )

        return False
