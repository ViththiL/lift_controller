import json
import time
import requests

from jsonschema import validate, ValidationError
from klein import route
from twisted.python import log

from lift_state import lift_car
from utility import requests_schema, mode_schema, door_schema, get_auth_token, emergency_alarm_schema

import constant

# Read configuration values from config.json
with open('config.json', 'r') as config_file:
    config_data = json.load(config_file)

automatic_door = config_data['automatic_door']
total_floor = config_data['total_floor']
server_ip = config_data['server_ip']
homing_floor = config_data['homing_floor']


@route('/lifts/statuses', methods=['GET'])
def get_lift(request):
    request.setResponseCode(200)
    log.msg(f"Lift statuses retrieved: {lift_car}")
    return json.dumps([lift_car])


def retry_fire_alarm(data, headers, delay=1):
    url = f"http://{server_ip}/public/emergency"
    while True:
        response = requests.put(url, headers=headers, json=data)
        if 200 <= response.status_code < 300:
            log.msg("The Emergency fire_alarm API call returned a successful response")
            return True
        elif response.status_code == 406:
            lift_car["current_mode"] = "passenger"
            log.msg(f"Lift Status: {lift_car}, Version: V1.0.1")
            log.msg(f"API call failed with status code 406. Retrying after {delay} seconds...")
            time.sleep(delay)
        else:
            log.msg(f"API call failed with status code: {response.status_code}")
            log.msg(f"Response content: {response.text}")
            return False


@route('/fire_alarm', methods=['PUT'])
def update_emergency_mode(request):
    headers = {
        'Authorization': "Bearer " + get_auth_token(),
        'Content-Type': "application/json"
    }

    data = json.loads(request.content.read())
    log.msg(f"Lift fire alarm active status: {data}")

    try:
        validate(instance=data, schema=emergency_alarm_schema)
    except ValidationError as e:
        error_msg = e.schema.get("error_msg", e.message)
        request.setResponseCode(400)
        log.msg(f"Error during Emergency Alarm Schema Validation: {error_msg}")
        return error_msg

    url = f"http://{server_ip}/public/emergency"

    response = requests.put(url, headers=headers, json=data)

    if 200 <= response.status_code < 300:
        log.msg("The Emergency fire_alarm API call returned a successful response")
    elif response.status_code == 406:
        log.msg("The status code was 406, so the retry process has started.")
        if retry_fire_alarm(data, headers):
            log.msg("Fire alarm successfully updated after retries.")
        else:
            request.setResponseCode(500)
            log.msg("Failed to update fire alarm after retries.")
            return "Failed to update fire alarm after retries."
    else:
        log.msg(f"API call failed with status code: {response.status_code}")
        log.msg(f"Response content: {response.text}")

    if data["active_status"]:
        lift_car["current_mode"] = "emergency"
        constant.desired_floor = homing_floor
        constant.last_floor_change_time = time.time()  # Reset the time to enforce delay
        request.setResponseCode(204)
        log.msg("Fire alarm has been activated.")

    else:
        lift_car["current_mode"] = "passenger"
        lift_car["door_state"] = "close"
        constant.desired_floor = None
        request.setResponseCode(204)
        log.msg("The fire alarm has been deactivated.")

    return "{}"


@route('/lifts/modes', methods=['PUT'])
def update_mode(request):
    data = json.loads(request.content.read())
    log.msg(f"lifts/modes PUT API called with : {data}")

    try:
        validate(instance=data, schema=mode_schema)
    except ValidationError as e:
        error_msg = e.schema.get("error_msg", e.message)
        request.setResponseCode(400)
        log.msg("Mode Schema Validation Error: ", error_msg)
        return error_msg

    if lift_car["lift_car_id"] == data.get("lift_car_id"):
        if lift_car["current_mode"] == "emergency":
            request.setResponseCode(501)
            log.msg("Fire alarm has been activated, and the mode can't be changed.")
            return "Fire alarm has been activated, and the mode cannot be changed."

        else:
            lift_car['current_mode'] = data.get("mode")
            request.setResponseCode(204)
            log.msg("Successfully changed mode response is: ", data)
            return "{}"
    else:
        request.setResponseCode(400)
        log.msg("Invalid lift_car_id value")
        return "Invalid lift_car_id value"


@route('/lifts/doors', methods=['PUT'])
def update_door(request):
    data = json.loads(request.content.read())
    log.msg(f"lifts/doors PUT API called with : {data}")

    try:
        validate(instance=data, schema=door_schema)
    except ValidationError as e:
        error_msg = e.schema.get("error_msg", e.message)
        request.setResponseCode(400)
        log.msg("Door Schema Validation Error: ", error_msg)
        return error_msg

    if lift_car["lift_car_id"] == data.get("lift_car_id"):
        if lift_car["current_mode"] == "emergency":
            request.setResponseCode(501)
            log.msg("Fire alarm has been activated, and the door_state cannot be changed.")
            return "Fire alarm has been activated, and the door_state cannot be changed."

        if not automatic_door:
            if data.get("door_state") == "open":
                # Set the door to open
                lift_car['door_state'] = "open"
                # Indicate that manual door control is allowed
                request.setResponseCode(204)
                log.msg("Successfully changed response for not automatic door is: ", data)
                return "{}"
            elif data.get("door_state") == "close":
                # Set the door to close
                lift_car['door_state'] = "close"
                # Print an error message if door is manually closed before floor request
                log.msg("Error: Manual door closure without floor request")
                request.setResponseCode(204)
                log.msg("Successfully changed response for not automatic door is: ", data)
                return "{}"
            else:
                request.setResponseCode(400)
                log.msg("Invalid door state")
                return "Invalid door state"
        else:
            # If automatic_door is True, the door state is managed automatically
            request.setResponseCode(400)  # Indicate that manual door control is not allowed
            log.msg("Automatic door control is enabled")
            return "Automatic door control is enabled"
    else:
        request.setResponseCode(400)
        log.msg("Invalid lift_car_id value")
        return "Invalid lift_car_id value"


@route('/lifts/floor_requests', methods=['POST'])
def update_floor_requests(request):
    data = json.loads(request.content.read())
    log.msg(f"lifts/floor_requests POST API called with : {data}")

    try:
        validate(instance=data, schema=requests_schema)
    except ValidationError as e:
        error_msg = e.schema.get("error_msg", e.message)
        request.setResponseCode(400)
        log.msg("Floor Request Schema Validation Error: ", error_msg)
        return error_msg

    new_desired_floor = data.get("desired_floor")

    if lift_car["lift_car_id"] == data.get("lift_car_id"):
        if lift_car["current_mode"] == "emergency":
            request.setResponseCode(501)
            log.msg("Fire alarm has been activated, and the floor_request cannot be requested.")
            return "Fire alarm has been activated, and the floor_request cannot be requested."

        if lift_car["current_mode"] == "amr":
            if type(new_desired_floor) != int:
                request.setResponseCode(400)
                log.msg("Ensure desired_floor is an integer value.")
                return "Ensure desired_floor is an integer value."

            if new_desired_floor <= total_floor:
                if not automatic_door and lift_car['door_state'] == "open":
                    request.setResponseCode(400)
                    log.msg("Door is opened, need to close the door first")
                    return "Door is opened, need to close the door first"

                if new_desired_floor is not None and isinstance(new_desired_floor, int):
                    if automatic_door:
                        constant.auto_time = 0  # Reset auto_time to 0
                    constant.desired_floor = new_desired_floor
                    constant.last_floor_change_time = time.time()

                    # Set direction to stationary if desired_floor is same as current floor
                    if lift_car['current_floor'] == constant.desired_floor:
                        lift_car['direction'] = "stationary"
                    else:
                        if constant.desired_floor < lift_car['current_floor']:
                            lift_car['direction'] = "down"
                        else:
                            lift_car['direction'] = "up"

                    lift_car['door_state'] = "close"

                    request.setResponseCode(201)
                    log.msg("Successfully sent a floor requests: ", data)
                    return json.dumps({
                        "seq_id": data.get("seq_id"),
                        "lift_car_id": lift_car["lift_car_id"],
                        "desired_floor": constant.desired_floor,
                        "status": "ack"
                    })
                else:
                    request.setResponseCode(400)
                    log.msg("Invalid desired floor value")
                    return "Invalid desired floor value"
            else:
                request.setResponseCode(400)
                log.msg("The requested floor is above the total number of floors")
                return "The requested floor is above the total number of floors"
        else:
            request.setResponseCode(400)
            log.msg("Lift is not available for AMR")
            return "Lift is not available for AMR"
    else:
        request.setResponseCode(400)
        log.msg("Invalid lift_car_id value")
        return "Invalid lift_car_id value"
