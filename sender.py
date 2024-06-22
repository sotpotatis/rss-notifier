"""sender.py
Watches a given RSS feed and sends emails if there are any updates available."""

import logging, requests
import os

import dateutil.parser
import pytz
from rss_parser import RSSParser
from utility_functions.database import DatabaseClient, faunadb_client_from_config
from utility_functions.config import read_config
from utility_functions.time_and_date import get_current_unix_timestamp
from email_sending.mailersend.client import (
    MailerSendAPIClient,
    mailersend_client_from_config,
    Email,
    Contact,
)
from email_sending.templating import fill_out_new_post_template, load_jinja_template

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
CONFIG = read_config()
RSS_FEED_CONFIG = CONFIG["rss_feed"]
DEFAULT_TIMEZONE_NAME = CONFIG["general"].get("default_timezone", "Europe/Stockholm")
DEFAULT_TIMEZONE = pytz.timezone(DEFAULT_TIMEZONE_NAME)
# Initialize database client
database_client = DatabaseClient(faunadb_client_from_config(CONFIG))
# ...email client as well
email_client = mailersend_client_from_config(CONFIG)
# ...load email config
EMAIL_CONFIG = CONFIG["email"]
EMAIL_TEMPLATES_PATH = os.path.join(os.getcwd(), EMAIL_CONFIG["templates_path"])
EMAIL_UNSUBSCRIBE_URL = EMAIL_CONFIG["unsubscribe_url"]
# Who is sending the email
FROM_CONTACT = Contact(
    email=EMAIL_CONFIG["from"]["email_address"], name=EMAIL_CONFIG["from"].get("name")
)
EMAIL_SUBJECT = EMAIL_CONFIG["subjects"]["new_entry"]
NEW_POST_EMAIL_TEMPLATE = load_jinja_template(EMAIL_TEMPLATES_PATH, "new_entry.jinja")


def run_main_code() -> None:
    """Runs the main code to retrieve the RSS field and process email notifications."""
    # Get RSS field
    logger.info("Retrieving RSS field...")
    try:
        rss_field_response = requests.get(
            RSS_FEED_CONFIG["source"],
            headers={
                "User-Agent": RSS_FEED_CONFIG.get("user_agent", "Python/RSSNotifier")
            },
        )
        rss_field_data = RSSParser.parse(rss_field_response.text)
    except Exception as e:
        logger.critical(
            f"An error occurred when trying to retrieve the RSS field: {e}",
            exc_info=True,
        )
        exit(1)
    # Parse the RSS field to group entries by ID
    items_to_notify_about = []
    for item in rss_field_data.channel.items:
        if item.guid is None or item.link is None or item.pub_date is None:
            logger.warning(
                f"Can not parse {item} because it is missing its link or GUID entry!"
            )
            continue
        else:
            items_to_notify_about.append(
                {
                    "published_at": dateutil.parser.parse(item.pub_date.content),
                    "title": item.title.content,
                    "link": item.link.content,
                    "description": (
                        None if item.description is None else item.description.content
                    ),
                }
            )
    # Sort items based on their publishing date
    items_to_notify_about.sort(
        key=lambda item: item["published_at"].timestamp(), reverse=True
    )  # Newest posts first
    subscribers = database_client.get_subscribed_emails()
    notifications = []
    subscribers_to_notify = []
    for subscriber in subscribers:
        subscription_date = subscriber["data"]["subscribed_at"]
        last_notified_at = subscriber["data"]["last_notified_at"]
        if subscriber in subscribers_to_notify:  # Only notify each subscriber once
            continue
        for item in items_to_notify_about:
            item_published_at_unix_timestamp = item["published_at"].timestamp()
            # FaunaDBd doesn't take None, hence the 0
            if (
                item_published_at_unix_timestamp > subscription_date
                and last_notified_at == 0
            ) or item_published_at_unix_timestamp > last_notified_at:
                logger.info("Found post to notify a subscriber about.")
                # Schedule notification email
                subscriber_email = subscriber["data"]["email_address"]
                email_html, email_text = fill_out_new_post_template(
                    NEW_POST_EMAIL_TEMPLATE,
                    email_address=subscriber_email,
                    unsubscribe_url=EMAIL_UNSUBSCRIBE_URL,
                    item_to_notify_about=item,
                )
                notifications.append(
                    Email(
                        from_email=FROM_CONTACT,
                        to_emails=Contact(email=subscriber_email),
                        subject=EMAIL_SUBJECT,
                        html=email_html,
                        text=email_text,
                    )
                )
                database_client.set_email_last_notified_at(
                    subscriber["ref"], get_current_unix_timestamp()
                )
                subscribers_to_notify.append(subscriber)
    logger.info(f"Processing {len(notifications)} notifications...")
    if len(notifications) > 0:
        email_client.send_emails(notifications)
        logger.info("Notifications processed.")
    else:
        logger.info("No notifications to send for now.")


if __name__ == "__main__":
    run_main_code()
