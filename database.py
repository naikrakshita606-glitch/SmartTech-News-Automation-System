"""Connect to MongoDB and prepare the project's collections."""

from pymongo import ASCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

import config


def connect_to_database() -> tuple[MongoClient, Database]:
    """Connect to MongoDB, check the connection, and create unique indexes."""
    client = MongoClient(
        config.MONGODB_URI,
        serverSelectionTimeoutMS=5000,
    )

    try:
        client.admin.command("ping")
        database = client[config.MONGODB_DATABASE]

        database.news.create_index(
            [("url", ASCENDING)],
            unique=True,
            name="unique_article_url",
        )
        database.daily_briefings.create_index(
            [("briefing_date", ASCENDING)],
            unique=True,
            name="unique_briefing_date",
        )

        return client, database
    except PyMongoError as error:
        client.close()
        raise ConnectionError(
            "Could not connect to MongoDB or create the required unique indexes."
        ) from error 
   