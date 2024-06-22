"""server_requests_and_responses.py
Functions to validate requests and send responses
for the server."""

import json
from enum import Enum
from typing import Optional, Tuple, List
from jsonschema import Draft7Validator
from flask import Response, jsonify, Request, make_response
from http import HTTPStatus


class RequestStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"


def message(messages: List[str], locales: Optional[List[str]] = None) -> dict:
    """Generates a message data to return with the request.
    Aka., returns a dict like {
    "message":
        {"en": "<Message in English>",
        "sv": "<Message in Swedish>",
        }
        etc.
    }

    :param messages: A list of messsages in the locales specified by the locales argument
    (if no locales are specified, the default will be English and Swedish (in that particular order)

    :param locales: A list of locales that the messages correspond to. The length should match with the
    messages argument and have the same ordering.
    (if no locales are specified, the default will be English and Swedish (in that particular order)

    :returns An object with localized message data: {"message": {"sv": "Hej!", "en": "Hello!"}} etc.
    """
    # Fill out default locales
    if locales is None:
        locales = ["en", "sv"]
    message_data = {}
    i = 0
    for i in range(len(messages)):
        message_data[locales[i]] = messages[i]
    return {"message": message_data}


def generate_response(
    status: RequestStatus,
    status_code: Optional[int] = None,
    data: Optional[dict] = None,
) -> Response:
    """Generates a response object with JSON status.

    :param status The status of the request. A RequestStatus entry,
    for example RequestStatus.SUCCESS

    :param status_code Optional status code.

    :param data Optional data (JSON) to include.
    """
    # Fill put defaults
    if data is None:
        data = {}
    if status_code is None:
        if status == RequestStatus.SUCCESS:
            status_code = HTTPStatus.OK
        else:
            status_code = HTTPStatus.BAD_REQUEST
    data["status"] = {"type": status.value, "status_code": status_code}
    return make_response(jsonify(data), status_code)


def validate_passed_json(
    request: Request, json_schema: Optional[dict] = None
) -> Tuple[bool, List, Optional[Response]]:
    """Validates a request with passed JSON.
    Checks if the JSON matches a JSON schema.

    :param request A request object from Flask.

    :param json_schema The associated JSON schema to validate, if any.
    If none is passed, the function checks that valid JSON has been passed.

    :returns A tuple in the format [<request valid>, <list of errors that occurred in validation>,
    <response that can be returned to indicate error if the request is not valid>]"""
    request_json = request.get_json()
    validation_errors = []
    if request_json is None:
        validation_errors = ["No JSON provided in request."]
    elif json_schema is not None:
        validator = Draft7Validator(schema=json_schema)
        # Sort the errors as suggested in the JSONSchema library docs
        validation_errors = sorted(
            validator.iter_errors(instance=request_json), key=lambda error: error.path
        )
    if (
        len(validation_errors) > 0
    ):  # Provide the errors and a response that can be used to indicate the error
        validation_errors_messages = [
            validation_error.message for validation_error in validation_errors
        ]
        validation_errors_messages_text = ",".join(validation_errors_messages)
        response_data = message(
            [
                f"The following validation error(s) occurred: {validation_errors_messages_text}",
                f"Datan du skickade har följande fel: {validation_errors_messages_text}",
            ]
        )
        response_data["validation_errors"] = validation_errors_messages
        return (
            False,
            validation_errors_messages,
            generate_response(
                RequestStatus.ERROR,
                status_code=HTTPStatus.BAD_REQUEST,
                data=response_data,
            ),
        )
    return (True, [], None)
