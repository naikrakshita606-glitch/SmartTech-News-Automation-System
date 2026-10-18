"""Read and validate settings from the environment."""

import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv


load_dotenv()


def _read_integer(name, default, minimum, maximum):
    """Read an integer environment variable and check its allowed range."""
    value = os.getenv(name, str(default))

    try:
        number = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a whole number.") from error

    if not minimum <= number <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")

    return number


MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017").strip()
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "tech_news").strip()

if not MONGODB_URI:
    raise ValueError("MONGODB_URI cannot be empty.")

if not MONGODB_DATABASE:
    raise ValueError("MONGODB_DATABASE cannot be empty.")

NEWS_API_URL = os.getenv(
    "NEWS_API_URL",
    "https://gnews.io/api/v4/search",
).strip()
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "").strip()
NEWS_REQUEST_TIMEOUT_SECONDS = _read_integer(
    "NEWS_REQUEST_TIMEOUT_SECONDS",
    default=15,
    minimum=1,
    maximum=120,
)

NEWS_SCHEDULE_HOUR = _read_integer(
    "NEWS_SCHEDULE_HOUR",
    default=6,
    minimum=0,
    maximum=23,
)
NEWS_SCHEDULE_MINUTE = _read_integer(
    "NEWS_SCHEDULE_MINUTE",
    default=0,
    minimum=0,
    maximum=59,
)
NEWS_SCHEDULE_TIMEZONE = os.getenv("NEWS_SCHEDULE_TIMEZONE", "UTC").strip()

if not NEWS_SCHEDULE_TIMEZONE:
    raise ValueError("NEWS_SCHEDULE_TIMEZONE cannot be empty.")

try:
    ZoneInfo(NEWS_SCHEDULE_TIMEZONE)
except ZoneInfoNotFoundError as error:
    raise ValueError(
        "NEWS_SCHEDULE_TIMEZONE must be a valid timezone name, such as UTC."
    ) from error

APP_HOST = os.getenv("APP_HOST", "127.0.0.1").strip()
APP_PORT = _read_integer(
    "APP_PORT",
    default=5000,
    minimum=1,
    maximum=65535,
)
