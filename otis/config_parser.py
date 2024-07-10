import json


def extract_config():
    with open('config.json', 'r') as f:
        data = json.load(f)
    return data


extract_config()

EXTRACT_CONFIG = extract_config()


# DECK: Enum: "TOP", "BOTTOM".  The deck on which the car call is being placed
DECK = EXTRACT_CONFIG.get("DECK", "BOTTOM")
# GROUP_ID: The id of the elevator group that the machine is in
GROUP_ID = EXTRACT_CONFIG.get("group_id", 1)
# SIDE: Enum: "FRONT" "REAR". Indicates whether the front door of the elevator or the rear door of the elevator should
# open once the destination floor is reached.
SIDE = EXTRACT_CONFIG.get("SIDE", "FRONT")
# TYPE: Enum:- "STANDARD"   "WHEELCHAIR". String Indicates the type of car call that is being placed.
TYPE = EXTRACT_CONFIG.get("TYPE", "EHS")
# IThe id of the machine for which the car call is being placed
MACHINE_ID = EXTRACT_CONFIG.get("machine_id", 1)
TOKEN_EXPIRE_TIME = EXTRACT_CONFIG.get("token_expire_time", 7200)
MAPPING_DATA = EXTRACT_CONFIG.get("mapping_data", 1)
GROUND_FLOOR_ID = EXTRACT_CONFIG.get("ground_floor_id", 1)
TOP_FLOOR_ID = EXTRACT_CONFIG.get("top_floor_id", 11)
INSTALLATION_ID = EXTRACT_CONFIG.get("Installation_ID")
GRANT_TYPE = EXTRACT_CONFIG.get("grant_type")
CLIENT_ID = EXTRACT_CONFIG.get("client_id")
CLIENT_SECRET = EXTRACT_CONFIG.get("client_secret")
PORT = EXTRACT_CONFIG.get("port")
LOG_FILE = EXTRACT_CONFIG.get("full_log_file_path")
RECONNECT_AND_RETRY = EXTRACT_CONFIG.get("reconnect_and_retry", 10)
GROUP_STATUS_WAIT_TIME = EXTRACT_CONFIG.get("group_status_wait_time", 120)
SERVER_IP = EXTRACT_CONFIG.get("server_ip")
USERNAME = EXTRACT_CONFIG.get("username")
PASSWORD = EXTRACT_CONFIG.get("password")
