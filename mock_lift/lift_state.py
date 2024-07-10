import json

with open('config.json', 'r') as config_file:
    config_data = json.load(config_file)

lift_car_id = config_data['lift_car_id']

lift_car = {
    "lift_car_id": lift_car_id,
    "current_floor": 1,
    "current_mode": "passenger",
    "door_state": "close",
    "direction": "stationary"
}
