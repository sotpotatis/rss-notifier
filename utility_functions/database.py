"""database.py
Interacts with the (very simple) database used within this project."""

import datetime
from typing import List, Optional
from faunadb.client import FaunaClient
from faunadb import query as q
import logging
from utility_functions.time_and_date import get_current_unix_timestamp
from faunadb.objects import Ref

logging.basicConfig(level=logging.DEBUG)


def faunadb_client_from_config(config: dict) -> FaunaClient:
    """Loads a FaunaDB client from a provided configuration file contents.

    :param config: The contents of the config.toml file.
    Must have "database/secret" key for this function to work."""
    return FaunaClient(secret=config["database"]["secret"])


class DatabaseClient:
    def __init__(self, faunadb_client: FaunaClient):
        """Initializes a database client.

        :param faunadb_client: A FaunaDB client that can be used for
        database operations"""
        self.faunadb_client = faunadb_client
        self.logger = logging.getLogger(__name__)

    def get_subscribed_emails(self) -> List[str]:
        """Gets a list of all the subscribed emails."""
        subscribers_data = self.faunadb_client.query(
            q.paginate(q.documents(q.collection("Subscriber")))
        )
        subscribers = []
        # Load all subscribers individually
        # This probably is not the most effective but it works!
        for subscriber in subscribers_data["data"]:
            subscribers.append(self.faunadb_client.query(q.get(subscriber)))
        self.logger.debug(
            f"Got FaunaDB subscribers: {len(subscribers)} subscribers loaded."
        )
        return subscribers

    def find_subscriber_by_email(self, email_address: str) -> Optional[List]:
        """Finds a subscriber based on their email address.
        Returns None if the subscriber could not be found."""
        response = self.faunadb_client.query(
            q.call(q.function("getUserByEmail"), email_address)
        )
        if response is not None:
            self.logger.info(f"Found requested subscriber: {response}")
            return [q.get(response), response]
        self.logger.info(f"Did not find requested email {email_address}.")
        return [None, None]

    def remove_email_from_database(self, subscriber: Ref) -> None:
        """Unsubscribes an email by removing it from the database.

        :param subscriber: The subscriber to be removed from the database.
        This can be found from find_subscriber_by_email"""
        # Ensure subscriber is in database
        self.faunadb_client.query(q.delete(subscriber))

    def add_email_to_database(
        self, email_address: str, subscribed_at: Optional[int] = None
    ) -> None:
        """Adds an email to the database, thus adding it as a subscriber.

        :param email_address: The email address to add to the database.

        :param subscribed_at: When the email joined the list. Defaults to the epoch time at runtime
        if not set."""
        if subscribed_at is None:
            subscribed_at = get_current_unix_timestamp()
        self.faunadb_client.query(
            q.create(
                q.collection("Subscriber"),
                {
                    "data": {
                        "email_address": email_address,
                        "last_notified_at": 0,
                        "subscribed_at": subscribed_at,
                    }
                },
            )
        )
        self.logger.info(f"Added subscriber {email_address} to database.")

    def set_email_last_notified_at(
        self, subscriber_reference: Ref, notification_time: Optional[int] = None
    ) -> None:
        """Sets what post an email has been last notified about.

        :param subscriber_reference: A database reference to the subscriber.

        :param notification_time: When the user was notified as an epoch unix timestamp
        """
        if notification_time is None:
            notification_time = get_current_unix_timestamp()
        self.faunadb_client.query(
            q.update(
                subscriber_reference, {"data": {"last_notified_at": notification_time}}
            )
        )
        self.logger.info(
            f"Set subscriber ID {subscriber_reference.id} to be notified at {notification_time}"
        )
