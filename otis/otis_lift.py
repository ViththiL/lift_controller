import os
import sys
import time
# import logging
from twisted.python import log
from twisted.python.logfile import DailyLogFile
from os import environ
from os.path import join
from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from klein import run, route
import json
from jsonschema import validate, ValidationError
import socketio
from socketio.exceptions import ConnectionError

from utility import requests_schema, mode_schema, get_access_token, door_schema, fire_alarm_schema, \
    FireAlarmUpdater
from config_parser import GROUP_ID, MACHINE_ID, DECK, SIDE, TYPE, TOKEN_EXPIRE_TIME, MAPPING_DATA, GROUND_FLOOR_ID, \
    TOP_FLOOR_ID, INSTALLATION_ID, PORT, LOG_FILE, RECONNECT_AND_RETRY, GROUP_STATUS_WAIT_TIME

# SESTO_FOLDER = join(environ.get("HOME"), ".sesto")
log_dir = os.path.expanduser(LOG_FILE)
log_file = log.startLogging(DailyLogFile.fromFullPath(log_dir))


version = "1.0.2"

lift_status = {
    "lift_car_id": 100,
    "current_floor": 1000,
    "direction": "stationary",
    "current_mode": "passenger",
    "door_state": "close"
}

active_floor_requests = {
    "desired_floor": -1,
    "amr_in_lift": False
}

car_status = {
    "door_state": "close",
    "mode": "NOR"
}

previous_status = {
    "car_mode": "NOR"
}
group_state = False
send_car_command = False
previous_mode = None
ehs_mode = False
hall_call_status = False
retry_on_ehs = False
car_call_status = False
car_command_response = False
maintenance_ehs_mode = False
fire_alarm_status = False
fake_fire_alarm_status = False

# create a SocketIO client instance
sio = socketio.Client()
headers = {
    'Authorization': get_access_token()[0],
    'InstallationId': INSTALLATION_ID
}

url = "https://asia.ems.otis.com?groupIds=1"
for data in MAPPING_DATA:
    if data["machine_id"] == MACHINE_ID:
        lift_status["lift_car_id"] = data["lift_id"]

# TOKEN_EXPIRE_TIME use only for first time token expire
expiration_time = TOKEN_EXPIRE_TIME + time.time()
reconnect_counter = 0
hall_call_timer = 0
car_call_timer = 0
group_status_counter = 0


def do_schedule():
    try:
        global reconnect_counter, send_car_command, ehs_mode, hall_call_status, hall_call_timer, retry_on_ehs, \
            car_call_status, car_call_timer, car_command_response, version
        reconnect_counter += 1
        log.msg(f"Status scheduler is running with lift_id {lift_status['lift_car_id']} version {version} connection state {sio.connected}...")
        log.msg(f"The lift status is {lift_status}. The active floor requests is {active_floor_requests['desired_floor']}")
        if sio.connected:  # if connected
            sio.emit('sendCarStatus', {"groupId": GROUP_ID, "machineId": MACHINE_ID})
            monitor_car_mode()
            if active_floor_requests["desired_floor"] == lift_status["current_floor"] and \
                    car_status["door_state"] == "open":
                if car_status["mode"] == "EHS" and not active_floor_requests["amr_in_lift"]:
                    ehs_mode = True
                elif active_floor_requests["amr_in_lift"] and not send_car_command:
                    sendCarCommand(state=True)

            if reconnect_counter % 3600 == 0 and lift_status["current_mode"] == "passenger":
                regenerate_token()

            if active_floor_requests["desired_floor"] == lift_status["current_floor"]:
                retry_on_ehs = False
            if car_status["mode"] == "EHS" and not retry_on_ehs:
                hall_call_status = False
                hall_call_timer = 0
            if hall_call_status and lift_status["current_mode"] == "amr":
                hall_call_timer += 1
                if hall_call_timer >= RECONNECT_AND_RETRY:
                    log.msg("The carStatus mode is not changed to EHS within the retry time. Reconnected and retry sendHallCall.")
                    regenerate_token()
                    desired_floor = int(active_floor_requests["desired_floor"]) - 1
                    sendHallCall(desired_floor, floor_direction="DOWN")
                    hall_call_timer = 0

            if active_floor_requests['amr_in_lift'] and car_call_status and active_floor_requests["desired_floor"] != -1:
                car_call_timer += 1
                if car_call_timer >= RECONNECT_AND_RETRY:
                    log.msg("CarCall response not received within the retry time. Reconnected and retry sendCarCall...")
                    regenerate_token()
                    desired_floor = int(active_floor_requests["desired_floor"]) - 1
                    sendCarCall(desired_floor)
                    car_call_timer = 0

            # turn off ATT mode, The logic use to change EHS mode to NOR mode
            if car_command_response and car_status["mode"] == "ATT":
                sendCarCommand(state=False)
                car_command_response = False

        else:
            log.msg("Socket is not connected. Reconnecting...")
            regenerate_token()
    except Exception as e:
        log.err(f"An error occurred: {e}")


def regenerate_token():
    new_access_token, expire_in = get_access_token()
    headers['Authorization'] = new_access_token
    log.msg('Updated access token successfully')
    global group_state
    global group_status_counter
    group_state = False
    sio.disconnect()
    time.sleep(1)
    log.msg(f"Connection state is {sio.connected} after the disconnection")
    sio.connect(
        url,
        headers=headers,
        socketio_path='/api/oid/v1',
        wait=True,
        transports=['websocket'],
        wait_timeout=1
    )
    while not group_state:
        if group_status_counter > GROUP_STATUS_WAIT_TIME * 10:
            log.msg("Extended group status waiting time")
            break
        group_status_counter += 1
        time.sleep(0.100)
        log.msg("Waiting for the group status after reconnection...")
    log.msg(f'Successfully reconnected and the state: {sio.connected}')
    group_status_counter = 0
    return expire_in


@sio.event
def connect():
    socket_id = sio.sid
    log.msg(f"Socket ID: {socket_id}")
    log.msg('Successfully connected to lift socket...')


@sio.event
def connect_error(data):
    log.msg(f"Error occurred while connecting the socket: {data}")
    if data == "Connection error":
        log.msg('Connection Error occurred. Attempting to reconnect...')
        regenerate_token()


@sio.event
def disconnect():
    log.msg("The socket connection has been disconnected")
    sio.disconnect()
    log.msg(f"Successfully disconnected. And connection state is {sio.connected}")


@sio.event
def carCall(data):
    global car_call_status
    log.msg(f'Received carCall: {data}')
    if data.get("carCallState") == "carCallAccepted":
        car_call_status = False


@sio.event
def groupStatus(data):
    log.msg(f'Received groupStatus: {data}')
    global group_state
    group_state = True


@sio.event
def carMode(data):
    log.msg(f'Received Mode: {data}')


@sio.event
def carStatus(data):
    log.msg(f'Received carStatus: {data}')
    position = data.get("position")
    if type(position) is int:
        lift_status["current_floor"] = position + 1
    else:
        lift_status["current_floor"] = 1000

    if data.get("direction") == "UP":
        lift_status["direction"] = "up"
    elif data.get("direction") == "DOWN":
        lift_status["direction"] = "down"
    elif data.get("direction") == "NONE" or not data.get("direction"):
        lift_status["direction"] = "stationary"
    else:
        lift_status["direction"] = "stationary"

    car_status["mode"] = data.get("mode")  # update car mode

    #  "CLOSED"   "CLOSING"   "OPENED"    "OPENING"

    if data.get('doorStatus') and SIDE == data['doorStatus'][0].get("side"):
        door_state = data['doorStatus'][0].get("state")
        if door_state == "OPENED":
            car_status["door_state"] = "open"
        elif door_state in ["CLOSED", "OPENING", "CLOSING"]:
            car_status["door_state"] = "close"
        else:
            car_status["door_state"] = "close"

    elif data.get('doorStatus') and SIDE == data['doorStatus'][1].get("side"):
        door_state = data['doorStatus'][1].get("state")
        if door_state == "OPENED":
            car_status["door_state"] = "open"
        elif door_state in ["CLOSED", "OPENING", "CLOSING"]:
            car_status["door_state"] = "close"
        else:
            car_status["door_state"] = "close"
    else:
        car_status["door_state"] = "close"

    # EFO EFS EQO are fire alarm related car modes
    global fire_alarm_status
    if data.get("mode") in ["EFO", "EFS", "EQO"]:
        if not fire_alarm_status:
            fire_alarm_status = True
            active_floor_requests["desired_floor"] = -1
            lift_status["current_mode"] = "emergency"
            d = fire_alarm_updater.update_fire_alarm(active_status=True)
            d.addBoth(lambda _: log.msg("Operation completed."))
    else:
        if fire_alarm_status:
            fire_alarm_status = False
            lift_status["current_mode"] = "passenger"
            d = fire_alarm_updater.update_fire_alarm(active_status=False)
            d.addBoth(lambda _: log.msg("Operation completed."))

    # The actual door status will be show. When the car status was ATT mode.
    if car_status["mode"] in ["EFO", "EFS", "EQO", "ATT"]:
        lift_status["door_state"] = car_status["door_state"]
    elif ehs_mode:
        lift_status["door_state"] = car_status["door_state"]
    elif fake_fire_alarm_status:
        lift_status["door_state"] = car_status["door_state"]
    else:
        lift_status["door_state"] = "close"


@sio.event
def sessionData(data):
    log.msg(f"Received sessionData: {data}")


@sio.event
def carPosition(data):
    log.msg(f"Received carPosition: {data}")


@sio.event
def errors(data):
    try:
        log.msg(f"Received Error: {data}")
        desired_floor = active_floor_requests["desired_floor"]
        error_messages = ["HallCall Error (Zapped). Please restart journey.",
                          "CarCall Error (Zapped). Please restart journey."]

        if data in error_messages and desired_floor != -1:
            if desired_floor != lift_status["current_floor"]:
                desired_floor = desired_floor - 1
                log.msg("Resend the sendHallCall after encountering a zapped error")
                regenerate_token()
                sendHallCall(desired_floor=desired_floor, floor_direction="DOWN")

            elif desired_floor != lift_status["current_floor"]:
                desired_floor = desired_floor - 1
                log.msg("Resend the sendCarCall after encountering a zapped error")
                regenerate_token()
                sendCarCall(desired_floor=desired_floor)
    except KeyError as e:
        log.msg(f"KeyError occurred: {e}")
        # Handle the KeyError here, for example, you could set a default value for desired_floor or take appropriate action.
    except Exception as e:
        log.msg(f"An unexpected exception occurred: {e}")
        # Handle other unexpected exceptions here, if needed.


@sio.event
def carCommand(data):
    log.msg(f"Received CarCommand: {data}")


@sio.event
def destinationRequest(data):
    log.msg(f"Received destinationRequest: {data}")


@sio.event
def direction(data):
    log.msg(f"Received direction: {data}")


@sio.event
def doorStatus(data):
    log.msg(f"Received doorStatus: {data}")


@sio.event
def hallCall(data):
    log.msg(f"Received hallCall: {data}")


@sio.event
def loadChange(data):
    log.msg(f"Received loadChange: {data}")


@route('/lifts/statuses', methods=['GET'])
def get_status(request):
    log.msg(f"Statuses API called with. Lift status: {lift_status}")
    request.setResponseCode(200)
    return json.dumps([lift_status])


@route('/lifts/floor_requests', methods=['POST'])
def lift_request(request):
    request_floor_args = json.loads(request.content.read())
    log.msg(f"Floor requests API called with : {request_floor_args}")
    try:
        validate(instance=request_floor_args, schema=requests_schema)
    except ValidationError as e:
        raise e.schema["error_msg"] if "error_msg" in e.schema else e.message
    desired_floor = request_floor_args["desired_floor"] - 1
    amr_in_lift = request_floor_args["amr_in_lift"]
    current_floor = lift_status["current_floor"]

    if request_floor_args["lift_car_id"] != lift_status["lift_car_id"]:
        request.setResponseCode(400)
        return "Invalid Parameter"

    if fire_alarm_status:
        log.msg(f"Fire alarm is activate in lift. Hence rejecting the floor request API call...")
        return "Lift is in Emergency Mode"

    if fake_fire_alarm_status:
        log.msg(f"Fake fire alarm is activate for testing. Hence rejecting the floor request API call...")
        return "Lift is in fake Emergency Mode"

    if active_floor_requests["desired_floor"] == request_floor_args["desired_floor"] and \
            active_floor_requests["amr_in_lift"] == request_floor_args["amr_in_lift"]:
        if time.time() - active_floor_requests["time"] < 10:  # Remove duplicate calls
            log.msg("The request has already been processed on this floor.")
            request.setResponseCode(201)
            response = json.dumps({
                "lift_car_id": lift_status.get('lift_car_id'),
                "seq_id": request_floor_args.get('seq_id'),
                "desired_floor": request_floor_args.get('desired_floor'),
                "status": "ack"
            })
            return response
        else:
            active_floor_requests["desired_floor"] = request_floor_args["desired_floor"]
            active_floor_requests["amr_in_lift"] = amr_in_lift
            active_floor_requests["time"] = time.time()

    active_floor_requests["desired_floor"] = request_floor_args["desired_floor"]
    active_floor_requests["amr_in_lift"] = amr_in_lift
    active_floor_requests["time"] = time.time()

    if int(desired_floor) - int(current_floor) > 0:
        floor_direction = "UP"
    elif int(desired_floor) - int(current_floor) < 0:
        floor_direction = "DOWN"
    else:
        floor_direction = "DOWN"

    if car_status["mode"] == "ATT" or active_floor_requests["amr_in_lift"]:
        sendCarCommand(state=False)

    global ehs_mode, car_command_response, maintenance_ehs_mode
    ehs_mode = False
    car_command_response = False
    if amr_in_lift:
        sendCarCall(desired_floor)
        maintenance_ehs_mode = False
    else:
        sendHallCall(desired_floor, floor_direction)
        maintenance_ehs_mode = True

    response = json.dumps({
        "lift_car_id": lift_status.get('lift_car_id'),
        "seq_id": request_floor_args.get('seq_id'),
        "desired_floor": request_floor_args.get('desired_floor'),
        "status": "ack"
    })
    request.setResponseCode(201)
    return response


@route('/lifts/modes', methods=['PUT'])
def lift_modes(request):
    global previous_mode, ehs_mode, hall_call_status, hall_call_timer, retry_on_ehs, car_call_status, car_call_timer,\
        car_command_response, maintenance_ehs_mode
    request_mode_args = json.loads(request.content.read())
    log.msg(f"Modes API called with : {request_mode_args}")
    try:
        validate(instance=request_mode_args, schema=mode_schema)
    except ValidationError as e:
        raise e.schema["error_msg"] if "error_msg" in e.schema else e.message

    if request_mode_args["lift_car_id"] != lift_status["lift_car_id"]:
        request.setResponseCode(400)
        return "Invalid Parameter"

    if fire_alarm_status:
        log.msg(f"Fire alarm is activate in lift. Hence rejecting the mode change API call...")
        return "Lift is in Emergency Mode"

    if fake_fire_alarm_status:
        log.msg(f"Fake fire alarm is activate for testing. Hence rejecting the mode change API call...")
        return "Lift is in fake Emergency Mode"

    if request_mode_args["mode"] == "passenger":
        if car_status["mode"] == "EHS":
            sendCarCommand(state=True)
            car_command_response = True
        maintenance_ehs_mode = False
        hall_call_status = False
        car_call_status = False
        ehs_mode = False
        retry_on_ehs = False
        hall_call_timer = 0
        car_call_timer = 0
        active_floor_requests["desired_floor"] = -1
        active_floor_requests["amr_in_lift"] = False
        sendCarCommand(state=False)

    elif request_mode_args["mode"] == "amr":
        if previous_mode != "amr":
            regenerate_token()

    lift_status["current_mode"] = request_mode_args.get("mode")
    previous_mode = request_mode_args.get("mode")
    request.setResponseCode(204)
    return {}


@route('/lifts/fire_alarm', methods=['PUT'])
def fire_alarm(request):
    # body = {"lift_car_id": 1, "activate": True}
    request_fire_alarm_args = json.loads(request.content.read())
    log.msg(f"Mock fire alarm activated with : {request_fire_alarm_args}")
    try:
        validate(instance=request_fire_alarm_args, schema=fire_alarm_schema)
    except ValidationError as e:
        raise e.schema["error_msg"] if "error_msg" in e.schema else e.message

    if request_fire_alarm_args["lift_car_id"] != lift_status["lift_car_id"]:
        request.setResponseCode(400)
        return "Invalid Parameter"

    global fake_fire_alarm_status
    if request_fire_alarm_args.get("activate", False):
        fake_fire_alarm_status = True
        active_floor_requests["desired_floor"] = -1
        lift_status["current_mode"] = "emergency"
        d = fire_alarm_updater.update_fire_alarm(active_status=True)
        d.addBoth(lambda _: print("Operation completed."))
    else:
        fake_fire_alarm_status = False
        lift_status["current_mode"] = "passenger"
        d = fire_alarm_updater.update_fire_alarm(active_status=False)
        d.addBoth(lambda _: print("Operation completed."))

    request.setResponseCode(204)
    return {}


@route('/lifts/doors', methods=['PUT'])
def lift_doors(request):
    request_door_args = json.loads(request.content.read())
    log.msg(f"lifts/doors PUT API called with : {request_door_args}")
    try:
        validate(instance=request_door_args, schema=door_schema)
    except ValidationError as e:
        raise e.schema["error_msg"] if "error_msg" in e.schema else e.message

    # if request_door_args["door_state"] == "open":
    #     sendCarCommand(state=True)
    # else:
    #     sendCarCommand(state=False)

    request.setResponseCode(204)
    return {}


def monitor_car_mode():
    global maintenance_ehs_mode
    pre_mode = previous_status["car_mode"]

    if pre_mode != car_status["mode"]:
        if pre_mode == "EHS" and maintenance_ehs_mode:
            log.msg(f"The previous car mode: {pre_mode} and the current car mode: {car_status['mode']}."
                    f"Trigger the sendHallCall to maintenance EHS mode")
            position = int(active_floor_requests["desired_floor"]) - 1
            sendHallCall(position, floor_direction="DOWN")
        previous_status["car_mode"] = car_status["mode"]


def sendCarCall(desired_floor):
    sio.emit('sendCarCall', {
        "carCallState": "carCallAccepted",
        "deck": DECK,
        "floor": desired_floor,
        "groupId": GROUP_ID,
        "machineId": MACHINE_ID,
        "side": SIDE,
        "type": "EXTENDED",
    })
    global car_call_status, car_call_timer
    car_call_status = True
    car_call_timer = 0
    request_floor = desired_floor + 1
    log.msg(f"Successfully sent sendCarCall to floor_id : {request_floor}")


def sendHallCall(desired_floor, floor_direction):
    sio.emit('sendHallCall', {
        "groupId": GROUP_ID,
        "direction": floor_direction,
        "side": SIDE,
        "floor": desired_floor,
        "type": "EHS",
    })
    global hall_call_status, hall_call_timer, retry_on_ehs
    if car_status["mode"] == "EHS":
        retry_on_ehs = True
    hall_call_status = True
    hall_call_timer = 0
    request_floor = desired_floor + 1
    log.msg(f"Successfully sent sendHallCall to floor_id : {request_floor}")


def sendCarCommand(state):
    if not state and car_status["mode"] != "ATT":
        pass
    else:
        sio.emit('sendCarCommand', {
            "groupId": GROUP_ID,
            "machineId": MACHINE_ID,
            "mode": "ATT",
            "state": state
        })
        log.msg(f"Successfully sent sendCarCommand to {'hold the door open' if state else 'release the door'}")
    global send_car_command
    if state:
        send_car_command = True
        active_floor_requests["desired_floor"] = -1
    else:
        send_car_command = False


if __name__ == '__main__':
    # Start the Socket.IO client
    sio.connect(
        url,
        headers=headers,
        socketio_path='/api/oid/v1',
        wait=True,
        transports=['websocket'],
        wait_timeout=1
    )
    fire_alarm_updater = FireAlarmUpdater()
    sch_status = LoopingCall(do_schedule)
    sch_status.start(1)
    run("0.0.0.0", PORT)
