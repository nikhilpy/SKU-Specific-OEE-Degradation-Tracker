import os
import json
import urllib.request
import urllib.parse
from dotenv import load_dotenv

# Resolve .env from project root (two levels up from streamlit_app/)
_ENV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".env",
)
load_dotenv(_ENV_PATH)


def post_slack_alert(payload: dict) -> tuple[bool, str]:
    """
    Posts a mitigation alert to the configured Slack channel via the
    Slack Web API (chat.postMessage).

    Expected payload keys: Equipment_ID, Failure_Horizon, SKU_ID, OEM_Constraints

    All sensitive values (token, channel) are read from .env:
        SLACK_BOT_TOKEN  — Bot User OAuth Token (xoxb-...)
        SLACK_CHANNEL    — Target channel, e.g. #oee-production-alerts
    """
    token   = os.getenv("SLACK_BOT_TOKEN")
    channel = os.getenv("SLACK_CHANNEL", "#oee-production-alerts")

    if not token or token.startswith("xoxb-REPLACE"):
        return False, "Slack Bot Token is not configured. Please set SLACK_BOT_TOKEN in .env."

    message = (
        f"🚨 *URGENT*: SKU-{payload.get('SKU_ID')} runs are causing critical thermal stress "
        f"on {payload.get('Equipment_ID')}.\n"
        f"Predicted bearing failure in *{payload.get('Failure_Horizon')} hours*.\n"
        f"*OEM Limit*: {payload.get('OEM_Constraints')}.\n"
        f"*ACTION REQUIRED*: Reduce feed rate by 10% for all upcoming "
        f"{payload.get('SKU_ID')} batches."
    )

    try:
        data = urllib.parse.urlencode({
            "token":   token,
            "channel": channel,
            "text":    message,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://slack.com/api/chat.postMessage", data=data
        )
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read())
            if res.get("ok"):
                return True, f"Alert posted to {channel} successfully."
            else:
                return False, f"Slack API Error: {res.get('error')}"

    except Exception as e:
        return False, f"Exception while posting to Slack: {e}"
