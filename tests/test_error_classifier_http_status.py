from dataclasses import asdict

import pytest

from research_engine.error_classifier import ErrorClassifier
from research_engine.search_models import RetryPolicy


class ErrorShape(Exception):
    pass


def classify(error: Exception):
    return ErrorClassifier().classify(error, RetryPolicy())


@pytest.mark.parametrize(
    ("path", "status"),
    (
        ("status_code", 408),
        ("http_status", 429),
        ("status", 500),
        ("code", 502),
        ("response.status_code", 503),
        ("response.status", 504),
        ("response.code", 418),
    ),
)
def test_extracts_supported_integer_status_shapes(path, status):
    error = ErrorShape("safe")
    if path.startswith("response."):
        error.response = type("Response", (), {})()
        setattr(error.response, path.removeprefix("response."), status)
    else:
        setattr(error, path, status)

    decision = classify(error)

    assert decision.http_status == status
    assert decision.error.http_status == status
    assert decision.error.code == f"provider_http_{status}"


@pytest.mark.parametrize("status", ["429", "503", " 418 "])
def test_extracts_numeric_string_status(status):
    error = ErrorShape("safe")
    error.status_code = status
    assert classify(error).http_status == int(status)


@pytest.mark.parametrize(
    "path",
    (
        "status_code",
        "http_status",
        "status",
        "code",
        "response.status_code",
        "response.status",
        "response.code",
    ),
)
def test_invokes_supported_zero_argument_callable_status_accessors(path):
    error = ErrorShape("safe")
    owner = error
    name = path
    if path.startswith("response."):
        owner = type("Response", (), {})()
        error.response = owner
        name = path.removeprefix("response.")
    setattr(owner, name, lambda: "503")

    assert classify(error).http_status == 503


def test_raising_callable_accessor_is_ignored_without_propagating():
    error = ErrorShape("safe")

    def raises():
        raise RuntimeError("accessor failure")

    error.status_code = raises
    error.http_status = 429
    assert classify(error).http_status == 429


def test_callable_requiring_arguments_is_not_invoked():
    error = ErrorShape("safe")
    error.status_code = lambda required: 500
    error.http_status = 429
    assert classify(error).http_status == 429


@pytest.mark.parametrize(
    "invalid",
    (True, False, 429.0, 429.5, 99, -429, 600, "four twenty nine", "429.0", ""),
)
def test_invalid_status_values_are_ignored(invalid):
    error = ErrorShape("safe")
    error.status_code = invalid
    error.status = 418
    assert classify(error).http_status == 418


def test_first_valid_status_wins_across_full_precedence_order():
    error = ErrorShape("safe")
    error.status_code = "invalid"
    error.http_status = 418
    error.status = 429
    error.code = 500
    error.response = type(
        "Response", (), {"status_code": 502, "status": 503, "code": 504}
    )()
    assert classify(error).http_status == 418


def test_429_with_retry_after_through_response_object():
    error = ErrorShape("safe")
    error.response = type(
        "Response", (), {"status_code": 429, "headers": {"Retry-After": "2.5"}}
    )()
    decision = classify(error)
    assert decision.retryable is True
    assert decision.retry_after_seconds == 2.5


def test_503_with_retry_after_through_exception_attribute():
    error = ErrorShape("safe")
    error.http_status = 503
    error.retry_after = "3"
    decision = classify(error)
    assert decision.retryable is True
    assert decision.retry_after_seconds == 3


def test_unknown_valid_http_status_is_not_retryable():
    error = ErrorShape("safe")
    error.code = 418
    decision = classify(error)
    assert decision.retryable is False
    assert decision.error.code == "provider_http_418"


def test_non_http_error_codes_keep_retryability_semantics():
    assert classify(ConnectionError("safe")).error.code == "provider_transient_failure"
    assert classify(ErrorShape("safe")).error.code == "provider_execution_failed"


def test_provider_execution_error_serialization_includes_http_status():
    error = ErrorShape("safe")
    error.status_code = 503
    assert asdict(classify(error).error)["http_status"] == 503
