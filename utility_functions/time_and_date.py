"""time_and_date.py
Various helper functions related to time and date operations."""

import datetime
from math import floor


def get_current_unix_timestamp() -> int:
    """Gets the current unix time/epoch timestamp."""
    return floor(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())
