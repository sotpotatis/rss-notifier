"""client.py
Implements an API client for Mailersend."""

import logging, time
from http import HTTPStatus

import requests
from typing import Optional, List, Union
from bs4 import BeautifulSoup

BASE_URL = "https://api.mailersend.com/v1/"
NO_PLAN = "no_plan"
FREE_PLAN = "free_plan"
PREMIUM_PLAN = "premium_plan"
MAILERSEND_PLANS = {NO_PLAN, FREE_PLAN, PREMIUM_PLAN}


class MailerSendRequestError(Exception):
    pass


class Contact:
    """Represents an email recipient or sender"""

    def __init__(self, email: str, name: Optional[str] = None) -> None:
        """Intializes an email object.

        :param email: The email that the object is linked to

        :param name: The name that the object is linked to, if any"""
        self.email = email
        self.name = name

    def to_dict(self) -> dict:
        """Converts an Contact object to a dict. Perfect for JSON-serialization."""
        result = {"email": self.email}
        if self.name is not None:
            result["name"] = self.name
        return result


class Email:
    """Represents an email."""

    def __init__(
        self,
        from_email: Contact,
        to_emails: Union[Contact, List[Contact]],
        subject: str,
        html: str,
        text: str,
    ):
        """Initializes an email.

        :param from_email: The person who sends the email.

        :param to_emails: The person(s) who receives the email.

        :param subject: The email subject.

        :param html: The content of the email, as parseable HTML.

        :param text: The content of the email, as text.
        """
        self.from_email = from_email
        # Mailersend wants a list of emails as the to email
        if not isinstance(to_emails, list):
            to_emails = [to_emails]
        self.to_emails = to_emails
        self.subject = subject
        self.html = html
        self.text = text

    def to_dict(self) -> dict:
        """Convert the email to dict, completely compatible with
        Mailersends API!"""
        return {
            "from": self.from_email.to_dict(),
            "to": [to_email.to_dict() for to_email in self.to_emails],
            "subject": self.subject,
            "html": self.html,
            "text": self.text,
        }


class MailerSendAPIClient:
    def __init__(self, api_token: str, plan: str):
        """Initializes API client.

        :param api_token: Your API token.

        :param plan: The plan that your account is using.
        Needed to avoid rate-limiting."""
        self.api_token = api_token
        self.plan = plan
        self.logger = logging.getLogger(f"{__name__}.MailerSendAPIClient")

    def authenticated_request(self, method, url: str, json: Optional[dict] = None):
        """Authenticates a request with the set API token and sends it.

        :param method: The request method as a request object, i.e. for example request.GET

        :param url: The URL to send the request to. Not including the base URL, so for example a valid pass
        might be /<name_of_api_endpoint> and not https://api.mailersend.com/v1/<name_of_api_endpoint>

        :param json: The JSON data to send"""
        request_parameters = {
            "url": BASE_URL + url.strip("/"),
            "headers": {"Authorization": f"Bearer {self.api_token}"},
            "method": method,
        }
        if json is not None:
            request_parameters["json"] = json
        response = requests.request(**request_parameters)
        try:
            response_json = response.json()
        except requests.exceptions.JSONDecodeError:
            self.logger.warning(
                f"Response JSON not available for request to {request_parameters['url']}!"
            )
            response_json = None
        return response.status_code, response.headers, response_json

    def send_emails(self, emails: List[Email]):
        """Sends out one or more emails

        :param emails: A list of emails to send.
        """
        # Check how many emails that can be grouped together,
        # from limits mentioned in API docs. We also have
        # API requests per minute: 10
        max_grouped_together_emails = 5 if self.plan == NO_PLAN else 500
        requests_to_send = [[]]
        for email in emails:
            if len(requests_to_send[-1]) < max_grouped_together_emails:
                requests_to_send[-1].append(email.to_dict())
            else:  # Start new request if buffer is full
                requests_to_send[-1] = [email.to_dict()]
        # Send requests
        self.logger.info(
            f"Will send {len(requests_to_send)} requests, which means a total of {len(emails)} emails..."
        )
        time_until_next_request = 6
        i = 0
        retries = 0
        while i < (len(requests_to_send)):
            if retries >= 3:
                raise MailerSendRequestError(
                    "Retried the request more than 3 times - you probably need to check what's going on!"
                )
            request_to_send = requests_to_send[i]
            self.logger.info(f"Sending {len(requests_to_send)} emails...")
            self.logger.debug(f"Emails: {request_to_send}")
            response_status, response_headers, response_json = (
                self.authenticated_request(
                    method="POST", url="bulk-email", json=request_to_send
                )
            )
            self.logger.info("Request sent.")
            self.logger.debug(
                f"Response: Status {response_status} with JSON {response_json} and headers {response_headers}"
            )
            if response_status in [HTTPStatus.ACCEPTED, HTTPStatus.OK]:
                self.logger.info("Emails queued.")
                i += 1
                retries = 0
            elif response_status == HTTPStatus.TOO_MANY_REQUESTS:
                time_until_next_request = (
                    int(response_headers["Retry-After"])
                    if "Retry-After" in response_headers
                    else None
                )
                if time_until_next_request is None:
                    self.logger.warning(
                        "Rate limit wait time is not available, doing guesswork that 15 seconds is enough..."
                    )
                    time_until_next_request = 15
                self.logger.warning(
                    f"We got rate limited. Retrying after {time_until_next_request} seconds."
                )
                if time_until_next_request > 300:
                    raise MailerSendRequestError(
                        "We got rate limited and have to retry after more than 5 minutes. This will not be done automatically since it is a rather long period of time."
                    )
                retries += 1
            else:
                raise MailerSendRequestError(
                    f"Unknown status code: {response_status} when trying to send an email."
                )
            if i < len(requests_to_send) - 1:
                self.logger.info(
                    f"Waiting {time_until_next_request} until sending another email..."
                )
                time.sleep(time_until_next_request)

    def check_email_valid(self, email_address: str) -> bool:
        """Checks if an email is valid or not using Mailersends API.

        :param email_address: The email address to validate."""
        status_code, headers, response_json = self.authenticated_request(
            method="POST",
            url="email-verification/verify",
            json={"email": email_address},
        )
        if status_code != HTTPStatus.OK:
            raise MailerSendRequestError(
                f"Unknown status code: {status_code} when trying to validate an email."
            )
        elif "status" not in response_json:
            raise MailerSendRequestError(
                f'Missing expected "status" parameter in response JSON. Response was: {response_json}.'
            )
        return response_json["valid"]


def mailersend_client_from_config(config: dict) -> MailerSendAPIClient:
    """Loads a Mailersend client from a provided configuration file contents.

    :param config: The contents of the config.toml file.
    Must have "email/mailersend" key with "token" and "plan" defined for this function to work.
    """
    mailersend_config = config["email"]["mailersend"]
    mailersend_plan = mailersend_config["plan"].lower()
    if mailersend_plan not in MAILERSEND_PLANS:
        raise ValueError(
            f"Invalid Mailersend plan! Valid plans are: {mailersend_plan}."
        )
    return MailerSendAPIClient(
        plan=mailersend_plan, api_token=mailersend_config["api_token"]
    )
