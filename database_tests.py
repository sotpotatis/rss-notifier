from utility_functions.database import DatabaseClient, faunadb_client_from_config
from faunadb.client import FaunaClient
from utility_functions import config

CONFIG = config.read_config()
# Please don't actually use this when you are testing if you're not me (Albin/
# sotpotatis on GitHub and other platforms). Thank you very much
TEST_EMAIL = "albin@albins.website"
d = DatabaseClient(faunadb_client_from_config(CONFIG))
subscribers = d.get_subscribed_emails()
d.add_email_to_database(TEST_EMAIL)
# _, subscriber_reference = d.find_subscriber_by_email(TEST_EMAIL)
# d.set_email_last_notified_about(subscriber_reference, "ABC123")
# print(d.get_subscribed_emails())
