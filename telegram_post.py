import os
import requests
from dotenv import load_dotenv


# ======================================================
# LOAD ENVIRONMENT VARIABLES
# ======================================================

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# ======================================================
# POST TO TELEGRAM
# ======================================================

def post_to_telegram(
    title,
    url,
    image=None
):

    # ------------------------------------------
    # Validate Telegram configuration
    # ------------------------------------------

    if not BOT_TOKEN:

        raise ValueError(
            "TELEGRAM_BOT_TOKEN is missing"
        )

    if not CHAT_ID:

        raise ValueError(
            "TELEGRAM_CHAT_ID is missing"
        )

    # ------------------------------------------
    # Validate Blogger URL
    # ------------------------------------------

    if not url:

        raise ValueError(
            "Blogger post URL is missing"
        )

    # ------------------------------------------
    # Telegram Message
    # ------------------------------------------

    message = f"""📢 New Job Alert

{title}

🔗 Apply Here:
{url}
"""

    # ==================================================
    # IF IMAGE EXISTS → SEND IMAGE + MESSAGE
    # ==================================================

    if image:

        endpoint = (
            f"https://api.telegram.org/bot"
            f"{BOT_TOKEN}/sendPhoto"
        )

        data = {

            "chat_id": CHAT_ID,

            "photo": image,

            "caption": message

        }

    # ==================================================
    # IF NO IMAGE → SEND TEXT + URL
    # ==================================================

    else:

        endpoint = (
            f"https://api.telegram.org/bot"
            f"{BOT_TOKEN}/sendMessage"
        )

        data = {

            "chat_id": CHAT_ID,

            "text": message

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

        print()
        print(
            "✅ Posted to Telegram"
        )

        print(
            "Blogger URL:",
            url
        )

        if image:

            print(
                "Telegram Image:",
                image
            )

        return True

    # ------------------------------------------
    # Error
    # ------------------------------------------

    else:

        print()
        print(
            "❌ Telegram Error"
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
