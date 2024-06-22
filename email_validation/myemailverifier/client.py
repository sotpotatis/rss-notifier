"""client.py
API client for myemailverifier."""

import logging
from typing import Tuple
import requests
from http import HTTPStatus
from enum import Enum

API_BASE_URL = "https://client.myemailverifier.com/verifier/"


class MyEmailVerifierRequestError(Exception):
    pass


class EmailStatus(Enum):
    """Defines statuses returned by MyEmailVerifier for verification."""

    INVALID = "Invalid"
    CATCH_ALL = "Catch-all"
    VALID = "Valid"
    UNKNOWN = "Unknown"


class EmailValidationResult:
    def __init__(
        self,
        is_valid: bool,
        is_free: bool,
        is_disposable: bool,
        is_role_based: bool,
        is_greylisted: bool,
        diagnosis: str,
    ) -> None:
        """Initializes an EmailValidationResult, representing the result of email validation.

        :param is_valid: If the email is valid or not

        :param is_free: If the email is free or not

        :param is_disposable: If the email is disposable or not

        :param is_role_based:  If the email is role based or not

        :param is_greylisted: If the email is greylisted or not

        :param diagnosis: A diagnosis message, helpful for invalid emails
        """
        self.is_valid = is_valid
        self.is_free = is_free
        self.is_disposable = is_disposable
        self.is_role_based = is_role_based
        self.is_greylisted = is_greylisted
        self.diagnosis = diagnosis


class MyEmailVerifierAPIClient:
    def __init__(self, api_key: str) -> None:
        """Initializes an API client for MyEmailVerifier.

        :param api_key: The API key to use the service."""
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)

    def authenticated_request(self, method: str, url: str) -> Tuple[int, dict]:
        """Sends an authenticated request to MyEmailVerifiers API.

        :param method The method to call, e.g. POST.

        :param url: The URL to request, without the base URL and without the API key at the end.
        """
        request_url = API_BASE_URL + url.strip("/") + f"/{self.api_key}"
        self.logger.info(f"Requesting URL {request_url}...")
        response = requests.request(method=method, url=request_url)
        try:
            response_json = response.json()
        except requests.JSONDecodeError:
            raise MyEmailVerifierRequestError(
                f"Could not decode response JSON from MyEmailVerifier."
            )
        return response.status_code, response_json

    def _int_to_bool(self, int_input: int) -> bool:
        """MyEmailSend uses 1 and 0 instead of true and false. This function performs that conversion."""
        if int_input == 1:
            return True
        elif int_input == 0:
            return False
        else:
            raise ValueError(f"Can not convert int {int_input} to bool.")

    def check_email_valid(self, email_address: str) -> EmailValidationResult:
        """Checks if an email is valid or not.

        :param email_address: The email address to validate"""
        status_code, response_json = self.authenticated_request(
            method="GET", url=f"validate_single/{email_address}"
        )
        if status_code != HTTPStatus.OK:
            raise MyEmailVerifierRequestError(
                f"Request to MyEmailVerifier failed: got unknown status code: {status_code}."
            )
        email_status = response_json["Status"]
        self.logger.info(f"Email validation result was: {email_status}")

        return EmailValidationResult(
            is_valid=email_status != EmailStatus.INVALID.value
            and email_status != EmailStatus.UNKNOWN.value,
            is_disposable=self._int_to_bool(response_json["Disposable_Domain"]),
            is_role_based=self._int_to_bool(response_json["Role_Based"]),
            is_free=self._int_to_bool(response_json["Free_Domain"]),
            is_greylisted=self._int_to_bool(response_json["Greylisted"]),
            diagnosis=response_json["Diagnosis"],
        )


def myemailverifier_client_from_config(config: dict) -> MyEmailVerifierAPIClient:
    """Loads a MyEmailVerifier client from a provided configuration file contents.

    :param config: The contents of the config.toml file.
    Must have "email/mailersend" key with "token" and "plan" defined for this function to work.
    """
    myemailverifier_config = config["email"]["myemailverifier"]
    return MyEmailVerifierAPIClient(api_key=myemailverifier_config["api_key"])
