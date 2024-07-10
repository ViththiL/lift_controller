import json
import time

from lift_state import lift_car
from twisted.python import log

import constant

# Read configuration values from config.json
with open('config.json', 'r') as config_file:
    config_data = json.load(config_file)

total_floor = config_data['total_floor']
floor_change_delay = config_data['floor_change_delay']
automatic_door_open_time = config_data['automatic_door_open_time']
automatic_door = config_data['automatic_door']
homing_floor = config_data['homing_floor']


def do_schedule():
    log.msg("Lift Status: ", lift_car, "Version: ", config_data['version'])

    current_time = time.time()
    elapsed_time = current_time - constant.last_floor_change_time

    if lift_car["current_mode"] == "emergency":
        if constant.last_floor_change_time == 0:
            constant.last_floor_change_time = current_time

        if elapsed_time >= floor_change_delay:
            constant.last_floor_change_time = current_time

            if lift_car['current_floor'] != homing_floor:
                lift_car['door_state'] = "close"
                constant.door_state = "close"

                if lift_car['current_floor'] > homing_floor:
                    lift_car['door_state'] = "close"
                    constant.door_state = "close"
                    lift_car['current_floor'] -= 1
                    lift_car['direction'] = "down"
                else:
                    lift_car['door_state'] = "close"
                    constant.door_state = "close"
                    lift_car['current_floor'] += 1
                    lift_car['direction'] = "up"

                log.msg("The lift moving in the " + lift_car['direction'] + " direction is ", lift_car)
            else:
                lift_car['door_state'] = "open"
                constant.door_state = "open"
                lift_car['direction'] = "stationary"
            return

    if elapsed_time >= floor_change_delay:
        if constant.desired_floor is not None and lift_car['current_floor'] != constant.desired_floor:
            if lift_car['current_floor'] > constant.desired_floor:
                lift_car['current_floor'] -= 1
                lift_car['direction'] = "down"
                log.msg("The current floor value for the lift moving in the down direction is ", lift_car)
            else:
                lift_car['current_floor'] += 1
                lift_car['direction'] = "up"
                log.msg("The current floor value for the lift moving in the up direction is ", lift_car)

            constant.door_state = "close"  # Close the door when moving to another floor
            constant.last_floor_change_time = current_time

        if automatic_door:
            if constant.desired_floor is not None and lift_car['current_floor'] == constant.desired_floor:
                constant.auto_time += 1
                if automatic_door_open_time > constant.auto_time:
                    lift_car['door_state'] = "open"
                    lift_car['direction'] = "stationary"
                else:
                    lift_car['door_state'] = "close"

        if constant.desired_floor == lift_car["current_floor"]:
            lift_car["direction"] = "stationary"
