from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.AppConfig import AppConfig


class MongoManager:

    client: AsyncIOMotorClient | None = None

    @classmethod
    def connect(cls) -> None:
        """Initializes the asynchronous MongoDB client connection pool."""
        if cls.client is None:
            cls.client = AsyncIOMotorClient(AppConfig.MONGO_URL)

    @classmethod
    def close(cls) -> None:
        """Closes the active MongoDB client connection pool."""
        if cls.client is not None:
            cls.client.close()
            cls.client = None

    @classmethod
    def getDatabase(cls) -> AsyncIOMotorDatabase:
        """Returns the configured MongoDB database instance for agent memory.

        Returns:
            AsyncIOMotorDatabase: Motor database handle.
        """
        if cls.client is None:
            cls.connect()
        return cls.client[AppConfig.MONGO_DB_NAME]
