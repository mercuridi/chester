"""Main code for Chester"""
# first-party imports
import logging

# third-party imports
import dotenv

# global variables
DISCORD_API_VERSION = 10
DISCORD_API_ENDPOINT_BASE_URL = f"https://discord.com/api/v{DISCORD_API_VERSION}"
LOGGING_DESTINATION = "logs/chester.log"

if __name__ == "__main__":
    dotenv.load_dotenv()
    filehandler = logging.FileHandler(
        filename=LOGGING_DESTINATION,
        mode="w",
        encoding="utf8",
    )
    streamhandler = logging.StreamHandler()
    logging.basicConfig(
        handlers=[
            filehandler, streamhandler
        ],
        level=logging.DEBUG
    )
    logging.info("Hello Logging!")
