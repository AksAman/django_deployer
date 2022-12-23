#!/usr/bin/python3
import logging
import os
from pathlib import Path


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import click
except ImportError:
    print("Please install click with pip3 install click")
    exit(1)


def load_env_from_line(line: str):
    line = line.strip()
    if not line or line.startswith("#"):
        return
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip()
    os.environ[key] = value


def load_dotenv_from_file(env_file_path: Path):
    with open(env_file_path, "r") as f:
        for line in f:
            load_env_from_line(line)


@click.command()
@click.option("--env-file", default=".env", help="Path to .env file")
def load_dotenv(env_file: str):
    """Load environment variables from .env file"""
    env_file_path = Path(env_file)
    if not env_file_path.exists():
        logger.info(f"No .env file found at {str(env_file_path)}")
        return
    try:
        load_dotenv_from_file(env_file_path=env_file_path)
        logger.info("Loaded environment variables from .env file")
    except Exception as e:
        logger.error(f"Failed to load environment variables from .env file: {e}")
        exit(1)


if __name__ == "__main__":
    load_dotenv()
