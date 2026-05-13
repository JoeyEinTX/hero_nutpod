"""Configure the single 'nutflix' logger.

Writes to logs/nutflix.log and also mirrors to stderr so that
`python3 service.py` in the foreground shows live output. Idempotent:
calling setup_logging() twice does not duplicate handlers.
"""
import logging
import sys


def setup_logging(logs_dir):
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("nutflix")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(logs_dir / "nutflix.log")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger
