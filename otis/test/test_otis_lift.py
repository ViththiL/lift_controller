# test_otis.py
import os
import sys
import unittest
from unittest.mock import patch, MagicMock, mock_open

# Adjust the path to include the 'otis' package directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from otis.otis_lift import active_floor_requests, carStatus, lift_status, car_status


class TestCarStatus(unittest.TestCase):

    # Fire alarm activated
    @patch('otis.otis_lift.update_fire_alarm')
    def test_fire_alarm_status_active_with_EFO_mode(self, mock_update_fire_alarm):
        data = {
            'machineId': '1',
            'load': {'BOTTOM': 'EMPTY'},
            'direction': 'NONE',
            'committedDirection': 'NONE',
            'position': 0,
            'doorStatus': [{'state': 'CLOSED', 'deck': 'BOTTOM', 'side': 'FRONT'},
                           {'state': 'CLOSED', 'deck': 'BOTTOM', 'side': 'REAR'}],
            'mode': 'EFO'
        }
        carStatus(data)
        self.assertEqual(lift_status["current_mode"], "emergency")
        self.assertEqual(lift_status["direction"], "stationary")
        self.assertEqual(lift_status["door_state"], car_status["door_state"])
        self.assertEqual(active_floor_requests["desired_floor"], -1)
        mock_update_fire_alarm.assert_called_once_with(active_status=True)

    # Fire alarm remains active in EFO mode
    @patch('otis.otis_lift.update_fire_alarm')
    def test_fire_alarm_status_remains_active_in_EFO_mode(self, mock_update_fire_alarm):
        data = {
            'machineId': '1',
            'load': {'BOTTOM': 'EMPTY'},
            'direction': 'NONE',
            'committedDirection': 'NONE',
            'position': 0,
            'doorStatus': [{'state': 'CLOSED', 'deck': 'BOTTOM', 'side': 'FRONT'},
                           {'state': 'CLOSED', 'deck': 'BOTTOM', 'side': 'REAR'}],
            'mode': 'EFO'
        }
        carStatus(data)
        self.assertEqual(lift_status["current_mode"], "emergency")
        self.assertEqual(lift_status["direction"], "stationary")
        self.assertEqual(lift_status["door_state"], car_status["door_state"])
        self.assertEqual(active_floor_requests["desired_floor"], -1)

    # Fire alarm deactivated
    @patch('otis.otis_lift.update_fire_alarm')
    def test_fire_alarm_status_deactivated_from_EFO_to_normal(self, mock_update_fire_alarm):
        data = {
            'machineId': '1',
            'load': {'BOTTOM': 'EMPTY'},
            'direction': 'DOWN',
            'committedDirection': 'DOWN',
            'position': 6,
            'committedPosition': 7,
            'doorStatus': [{'state': 'CLOSED', 'deck': 'BOTTOM', 'side': 'FRONT'},
                           {'state': 'CLOSED', 'deck': 'BOTTOM', 'side': 'REAR'}],
            'mode': 'NOR'
        }

        carStatus(data)
        self.assertEqual(lift_status["current_mode"], "passenger")
        self.assertEqual(lift_status["direction"], "down")
        self.assertEqual(lift_status["door_state"], car_status["door_state"])
        mock_update_fire_alarm.assert_called_once_with(active_status=False)

    # Normal operation without fire alarm
    @patch('otis.otis_lift.update_fire_alarm')
    def test_normal_operation_without_fire_alarm(self, mock_update_fire_alarm):
        data = {
            'machineId': '1',
            'load': {'BOTTOM': 'EMPTY'},
            'direction': 'DOWN',
            'committedDirection': 'DOWN',
            'position': 6,
            'committedPosition': 7,
            'doorStatus': [{'state': 'CLOSED', 'deck': 'BOTTOM', 'side': 'FRONT'},
                           {'state': 'CLOSED', 'deck': 'BOTTOM', 'side': 'REAR'}],
            'mode': 'NOR'
        }
        carStatus(data)
        self.assertEqual(lift_status["current_mode"], "passenger")
        self.assertEqual(lift_status["direction"], "down")
        self.assertEqual(lift_status["door_state"], car_status["door_state"])


if __name__ == '__main__':
    unittest.main()