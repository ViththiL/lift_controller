import json
import os

__all__ = ['config_data']


def extract_config():
    file_dir = os.path.dirname(os.path.realpath('__file__'))
    with open(os.path.join(file_dir, "config.json"), 'r') as f:
        data = json.load(f)
    return data


config_data = extract_config()
