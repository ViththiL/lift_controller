import json
import requests

from twisted.python import log

with open('config.json', 'r') as config_file:
    config_data = json.load(config_file)

server_ip = config_data['server_ip']
user_name = config_data['server_user_name']
password = config_data['server_password']


def get_auth_token():
    token_url = f"http://{server_ip}/public/auth"

    auth_data = {
        "user_name": user_name,
        "password": password
    }

    auth_response = requests.post(token_url, json=auth_data)

    auth_response_data = auth_response.json()
    token = auth_response_data["access_token"]
    log.msg("Successfully received access token from server")
    return token


requests_schema = {
    "type": "object",
    "required": ["seq_id", "lift_car_id", "desired_floor", "amr_in_lift"],
    "properties": {
        "seq_id": {"type": "number"},
        "lift_car_id": {"type": "number", },
        "desired_floor": {"type": "number"},
        "amr_in_lift": {"type": "boolean"}
    },
}

mode_schema = {
    "type": "object",
    "required": ["lift_car_id", "mode"],
    "properties": {
        "lift_car_id": {"type": "number"},
        "mode": {"type": "string", },
    },
}


door_schema = {
    "type": "object",
    "required": ["lift_car_id", "door_state"],
    "properties": {
        "lift_car_id": {"type": "number"},
        "door_state": {"type": "string", },
    },
}


emergency_alarm_schema = {
    "type": "object",
    "required": ["active_status", "time_stamp"],
    "properties": {
        "active_status": {"type": "boolean"},
        "time_stamp": {"type": "string", },
    },
}
