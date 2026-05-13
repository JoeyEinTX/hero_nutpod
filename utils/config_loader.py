"""Load Phase 1 config.yaml as a plain dict."""
import yaml


def load_config(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)
