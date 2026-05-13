"""Configure the single 'nutflix' logger writing to logs/nutflix.log."""
import logging


def setup_logging(logs_dir):
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("nutflix")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler = logging.FileHandler(logs_dir / "nutflix.log")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
