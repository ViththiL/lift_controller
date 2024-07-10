import json
import time
import unittest

from unittest.mock import MagicMock, patch
from klein import Klein

from endpoints import get_lift, update_emergency_mode, update_mode, update_door, update_floor_requests
from lift_state import lift_car
from scheduler import do_schedule
import constant

with open('config.json', 'r') as config_file:
    config_data = json.load(config_file)

automatic_door = config_data['automatic_door']


class TestLiftRoutes(unittest.TestCase):

    def setUp(self):
        self.app = Klein()
        self.app.route('/lifts/statuses', methods=['GET'])(get_lift)
        self.app.route('/lifts/modes', methods=['PUT'])(update_mode)
        self.app.route('/lifts/door', methods=['PUT'])(update_door)
        self.app.route('/lifts/floor_requests', methods=['POST'])(update_floor_requests)

    def test_get_lift(self):
        request = MagicMock()
        request.method = 'GET'
        request.path = '/lifts/statuses'
        response = get_lift(request)
        if automatic_door:
            expected_response = json.dumps([{
                "lift_car_id": 10,
                "current_floor": 1,
                "current_mode": "passenger",
                "door_state": "open",
                "direction": "stationary"
            }])
        else:
            expected_response = json.dumps([{
                "lift_car_id": 10,
                "current_floor": 1,
                "current_mode": "passenger",
                "door_state": "close",
                "direction": "stationary"
            }])
        self.assertEqual(response, expected_response)

    def test_update_fire_alarm(self):
        request = MagicMock()
        request.method = 'PUT'
        request.path = '/fire_alarm'
        request.content.read.return_value = '{"active_status": true, "time_stamp": "2023-10-17 08:45:43"}'
        response = update_emergency_mode(request)
        self.assertEqual(response, "{}")

    def test_update_mode(self):
        request = MagicMock()
        request.method = 'PUT'
        request.path = '/lifts/modes'
        request.content.read.return_value = '{"lift_car_id": 10, "mode": "amr"}'
        response = update_mode(request)
        self.assertEqual(response, "{}")

    def test_update_door_manual(self):
        request = MagicMock()
        request.method = 'PUT'
        request.path = '/lifts/doors'
        if not automatic_door:
            request.content.read.return_value = '{"lift_car_id": 10, "door_state": "close"}'
            response = update_door(request)
            self.assertEqual(response, "{}")
        else:
            request.content.read.return_value = '{"lift_car_id": 10, "door_state": "close"}'
            response = update_door(request)
            self.assertEqual(response, "Automatic door control is enabled")

    def test_update_floor_requests_amr(self):
        request = MagicMock()
        request.method = 'POST'
        request.path = '/lifts/floor_requests'
        request.content.read.return_value = '{"lift_car_id": 10, "desired_floor": 2, "seq_id": 1, "amr_in_lift": false}'

        # Set the mode to "amr" in the lift_car dictionary
        lift_car["lift_car_id"] = 10
        lift_car["current_mode"] = "amr"

        response = update_floor_requests(request)
        self.assertEqual(response, '{"seq_id": 1, "lift_car_id": 10, "desired_floor": 2, "status": "ack"}')

    @patch('scheduler.time')
    def test_do_schedule_moving_up(self, mock_time):
        lift_car["current_floor"] = 1
        lift_car["direction"] = "stationary"
        lift_car["door_state"] = "close"
        constant.desired_floor = 3

        mock_time.time.side_effect = [100, 102]

        do_schedule()

        requested_floor_up_floor = 2

        self.assertEqual(lift_car["current_floor"], requested_floor_up_floor)
        self.assertEqual(lift_car["direction"], "up")
        self.assertEqual(lift_car["door_state"], "close")

        time.sleep(2)

        mock_time.time.side_effect = [102, 104]

        if lift_car["current_floor"] == requested_floor_up_floor and automatic_door:
            lift_car["direction"] = "stationary"
            lift_car["door_state"] = "open"
            self.assertEqual(lift_car["direction"], "stationary")

        else:
            lift_car["direction"] = "stationary"

        time.sleep(2)

        constant.desired_floor = 1

        mock_time.time.side_effect = [102, 104]

        do_schedule()

        requested_down_floor = 1

        if lift_car["current_floor"] > requested_down_floor:
            lift_car["direction"] = "down"

            self.assertEqual(lift_car["current_floor"], requested_down_floor)
            self.assertEqual(lift_car["direction"], "down")
            self.assertEqual(lift_car["door_state"], "close")

        if automatic_door:
            self.assertEqual(lift_car["current_floor"], requested_down_floor)
            self.assertEqual(lift_car["direction"], "stationary")
            self.assertEqual(lift_car["door_state"], "open")
        else:
            self.assertEqual(lift_car["current_floor"], requested_down_floor)
            self.assertEqual(lift_car["direction"], "stationary")
            self.assertEqual(lift_car["door_state"], "close")

        floor = lift_car["current_floor"]
        direction = lift_car["direction"]
        door = lift_car["door_state"]

        mock_time.time.side_effect = [100, 105]

        do_schedule()

        self.assertEqual(lift_car["current_floor"], floor)
        self.assertEqual(lift_car["direction"], direction)
        self.assertEqual(lift_car["door_state"], door)

    @patch('scheduler.time')
    def test_do_schedule_door_open(self, mock_time):
        # Mock lift_car and desired_floor values
        lift_car["current_floor"] = 3  # This is the desired floor
        lift_car["direction"] = "up"
        lift_car["door_state"] = "close"
        constant.desired_floor = 3

        mock_time.time.side_effect = [100, 105]

        do_schedule()

        if automatic_door:
            self.assertEqual(lift_car["current_floor"], 3)
            self.assertEqual(lift_car["direction"], "stationary")
            self.assertEqual(lift_car["door_state"], "open")
        else:
            self.assertEqual(lift_car["current_floor"], 3)
            self.assertEqual(lift_car["direction"], "stationary")
            self.assertEqual(lift_car["door_state"], "close")


if __name__ == '__main__':
    unittest.main()
