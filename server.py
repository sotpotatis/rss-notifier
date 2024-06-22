"""server.py
Runs the frontend server where users can subscribe and unsubscribe
to emails."""

import threading
import warnings
from enum import Enum
from http import HTTPStatus
from werkzeug.exceptions import HTTPException
from flask import Flask, request, Response
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from utility_functions import server_requests_and_responses, database, config
from email_sending.mailersend.client import mailersend_client_from_config
from email_validation.myemailverifier.client import myemailverifier_client_from_config
import sender
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Initialize app
app = Flask(__name__)
# Read config
CONFIG = config.read_config()
SERVER_CONFIG = CONFIG["server"]


# Below feature can be used for host-specific endpoints.
# Currently only Deta is supported
class ServerHostingPlatforms(Enum):
    DETA = "deta"


SERVER_HOSTING_PLATFORM = SERVER_CONFIG.get("hosting_platform", "unknown").lower()
# Add CORS, and limits for requests
API_LIMITS_CONFIG = SERVER_CONFIG.get("api_limits", {})
CORS(app, resources={r"*": {"origins": SERVER_CONFIG.get("api_cors_origins", "*")}})
limiter = Limiter(
    key_func=get_remote_address, app=app, storage_uri="memory://", default_limits=None
)
database_client = database.DatabaseClient(database.faunadb_client_from_config(CONFIG))
# Create email client
email_client = mailersend_client_from_config(CONFIG)
email_verification_client = myemailverifier_client_from_config(CONFIG)
# Register routes
most_characters_regex = "[a-zA-Z0-9_.-]"  # I mean, this is not wrong :P
EMAIL_ADDRESS_JSON_SCHEMA = {
    "email_address": {"type": "string"},
    "required": ["email_address"],
}


@app.route("/")
@limiter.limit(API_LIMITS_CONFIG.get("index", None))
def index() -> Response:
    """Simple index page."""
    return server_requests_and_responses.generate_response(
        server_requests_and_responses.RequestStatus.SUCCESS,
        data=server_requests_and_responses.message(["Pong!", "Pong!"]),
    )


@app.route("/subscribe", methods=["POST"])
@limiter.limit(API_LIMITS_CONFIG.get("subscribe", "4 per minute;8 per hour"))
def add_subscription() -> Response:
    """Adds a subscriber."""
    logger.info("Got a request to add a subscription!")
    request_valid, validation_errors, error_response = (
        server_requests_and_responses.validate_passed_json(
            request, EMAIL_ADDRESS_JSON_SCHEMA
        )
    )
    if not request_valid:
        return error_response
    else:
        # Check if email is in database
        request_json = request.get_json()
        email_address = request_json["email_address"]
        previous_email_entry, previous_email_reference = (
            database_client.find_subscriber_by_email(email_address)
        )
        if previous_email_entry is not None:
            logger.info("Unique constraint failed. Returning error...")
            return server_requests_and_responses.generate_response(
                server_requests_and_responses.RequestStatus.ERROR,
                status_code=HTTPStatus.CONFLICT,
                data=server_requests_and_responses.message(
                    [
                        "The email address is already subscribed.",
                        "Emailaddressen är redan prenumererad.",
                    ]
                ),
            )
        # Validate email
        logger.info("Validating email...")
        email_validation_result = email_verification_client.check_email_valid(
            email_address
        )
        if not email_validation_result.is_valid:
            logger.info("Email is not valid. Returning error...")
            return server_requests_and_responses.generate_response(
                server_requests_and_responses.RequestStatus.ERROR,
                status_code=HTTPStatus.BAD_REQUEST,
                data=server_requests_and_responses.message(
                    [
                        f"The email address is not valid. Reason: {email_validation_result.diagnosis}",
                        f"Emailaddressen är inte giltig. Anledning: {email_validation_result.diagnosis}",
                    ]
                ),
            )
        logger.info("Email is valid!")
        logger.info("Adding user...")
        database_client.add_email_to_database(email_address)
        return server_requests_and_responses.generate_response(
            server_requests_and_responses.RequestStatus.SUCCESS,
            data=server_requests_and_responses.message(
                ["Email added successfully.", "Mejladressen har lagts till."]
            ),
        )


@app.route("/unsubscribe", methods=["POST"])
@limiter.limit(API_LIMITS_CONFIG.get("unsubscribe", ["10 per minute"]))
def unsubscribe() -> Response:
    """Unsubscribes a set email address from the list."""
    logger.info("Got a request to unsubscribe a user.")
    request_valid, validation_errors, error_response = (
        server_requests_and_responses.validate_passed_json(
            request, EMAIL_ADDRESS_JSON_SCHEMA
        )
    )
    if not request_valid:
        return error_response
    else:
        # Check if email is in database
        request_json = request.get_json()
        email_address = request_json["email_address"]
        subscriber, subscriber_reference = database_client.find_subscriber_by_email(
            email_address
        )
        if subscriber is None:
            logger.info("Error! User seems to not be subscribed.")
            return server_requests_and_responses.generate_response(
                server_requests_and_responses.RequestStatus.ERROR,
                status_code=HTTPStatus.BAD_REQUEST,
                data=server_requests_and_responses.message(
                    [
                        "It seems like the requested email address is not subscribed.",
                        "Det verkar inte som att den efterfrågade mejladressen är prenumererad.",
                    ]
                ),
            )
        logger.info("Sending unsubscribe request...")
        database_client.remove_email_from_database(subscriber_reference)
        logger.info("User was unsubscribed. Returning message...")
        return server_requests_and_responses.generate_response(
            server_requests_and_responses.RequestStatus.SUCCESS,
            data=server_requests_and_responses.message(
                [
                    "The email was successfully unsubscribed.",
                    "Mailaddressen har avprenumererats.",
                ]
            ),
        )


# For deta.dev hosting, we can trigger the sender by using Deta actions.
# Their action system sends a URL request at a set schedule.
if SERVER_HOSTING_PLATFORM == ServerHostingPlatforms.DETA.value:
    logger.info("Deta is used, adding Deta-specific URLS...")
    # You need to define the event name for starting the sender in the config
    START_SENDER_EVENT_NAME = SERVER_CONFIG.get("deta", {}).get(
        "start_sender_event_name", None
    )
    if START_SENDER_EVENT_NAME is None:
        warnings.warn(
            "You have not defined start_sender_event_name in your config. You can not use that Deta action."
        )
    else:

        @app.route("/__space/v0/actions", methods=["POST"])
        def space_actions() -> Response:
            """Handles a Space Action request from Deta Space"""
            request_json = request.get_json()
            logger.info(f"Got a request from Deta with JSON: {request_json}")
            if request_json["event"]["id"] == START_SENDER_EVENT_NAME:
                logger.info("Got request to start email sending. Starting task...")
                task = threading.Thread(target=sender.run_main_code)
                task.start()
                logger.info("Task started. Returning status...")
                return Response(status=HTTPStatus.CREATED)


# Add error handlers
@app.errorhandler(404)
def error_handler_404(exception) -> Response:
    """Error handler for 404 errors."""
    return server_requests_and_responses.generate_response(
        server_requests_and_responses.RequestStatus.ERROR,
        data=server_requests_and_responses.message(
            [
                "The requested URL could not be found. Please double-check the URL.",
                "Den efterfrågade URL:en kunde inte hittas. Vänligen dubbelkolla länken.",
            ]
        ),
    )


@app.errorhandler(Exception)
def error_handler_500(exception) -> Response:
    """Error handler for 500 errors."""
    if isinstance(exception, HTTPException):
        return exception
    logger.critical(f"Handling internal server error: exception: {exception}.")
    return server_requests_and_responses.generate_response(
        server_requests_and_responses.RequestStatus.ERROR,
        data=server_requests_and_responses.message(
            [
                "Internal server error, please try again later.",
                "Internt serverfel, vänligen försök igen senare.",
            ]
        ),
    )


@app.errorhandler(429)
def error_handler_429(exception) -> Response:
    """Error handler for 429 errors."""
    logger.critical(f"Handling rate limit error: {exception}.")
    return server_requests_and_responses.generate_response(
        server_requests_and_responses.RequestStatus.ERROR,
        data=server_requests_and_responses.message(
            [
                f"You have requested this service too many times, please try again later. {exception}",
                f"Du har efterfrågat denna tjänst för många gånger, försök igen senare. {exception}",
            ]
        ),
    )


if __name__ == "__main__":
    warnings.warn(
        "Do not use this server in a production environment, please use Gunicorn (or similar) instead!"
    )
    app.run(
        debug=SERVER_CONFIG.get("debug", False), port=SERVER_CONFIG.get("port", 5000)
    )
