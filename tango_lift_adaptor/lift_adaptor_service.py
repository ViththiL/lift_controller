#!/usr/bin/env python
# encoding: utf-8
import json
import logging
import requests
from flask import jsonify
from config_parser import config_data
from utility import get_door_status

__all__ = ['LiftAdaptorService']


class LiftAdaptorService:
    def __init__(self):
        self.session = requests.Session()
        ip_address = config_data["host_ip"]+":"+config_data["port"]
        logging.info("IP Address of Tango lift is : {}".format(ip_address))
        self.statuses_url = "http://{}/smart_lift/lift_status".format(ip_address)
        self.requests_url = "http://{}/smart_lift/remote_operation".format(ip_address)
        self.timeout = 10
        self.lift_statuses = {}
        self.is_amr_mode = False
        self.lift_id = config_data["lifts"]["unique_lift_car_id"]
        self.lift_name = config_data["lifts"]["lift_name"]

    def fetch_lift_statuses(self):
        try:
            logging.info("Fetching status from Tango lift")
            response = self.session.get(self.statuses_url, timeout=self.timeout)
            logging.info("Response: status code: {}, json is: {}".format(response.status_code, response.json()))
            self.lift_statuses = response.json()
            logging.info("Response from lift controller : {}".format(self.lift_statuses))
            status_response = [{'lift_car_id': config_data["lifts"]["unique_lift_car_id"] if self.lift_statuses["lift_id"] == self.lift_name else 0,
                                "current_floor": config_data["floors"].get(self.lift_statuses.get("current_floor", 0), 0),
                                "direction": "stationary",
                                "current_mode": "amr" if self.is_amr_mode else "passenger",
                                "door_state": get_door_status(self.lift_statuses["door_state"])
                                }]
            logging.info("Response back to server is: {}".format(status_response))
            return jsonify(status_response)
        except Exception as e:
            raise e

    def set_lift_modes(self, mode_request):
        try:
            logging.info("Setting lift mode: mode_request = {}".format(mode_request))
            if mode_request["mode"] == "amr":
                self.is_amr_mode = True
                logging.info("Mode is set to AMR")
                return "", 204
            elif mode_request["mode"] == "passenger":
                self.is_amr_mode = False
                logging.info("Releasing the lift based on the lift statuses: {}".format(self.lift_statuses))
                request = {
                    "destination_floor": self.lift_statuses.get("current_floor", 0),
                    "lift_id": self.lift_name,
                    "request_type": 0
                }
                logging.info("Request being sent to Tango: {}".format(request))
                response = self.session.post(self.requests_url, json=request, timeout=self.timeout)
                logging.info("Response from release lift: {}".format(response.json()))
                if response.status_code == 200:
                    return "", 204
        except Exception as e:
            raise e

    def set_floor(self, floor_request):
        try:
            logging.info("Setting lift floor: floor_request = {}".format(floor_request))
            logging.info("is AMR mode : {}".format(self.is_amr_mode))
            floor_req_response = {}
            if self.is_amr_mode:
                request = {
                    "destination_floor": list(config_data["floors"].keys())[list(config_data["floors"].values()).index(floor_request.get("desired_floor", 0))],
                    "lift_id": self.lift_name,
                    "request_type": 1
                }
                logging.info("Request being sent to Tango: {}".format(request))
                response = self.session.post(self.requests_url, json=request, timeout=self.timeout)
                logging.info("Response from set floor request: {}".format(response.json()))
                if response.status_code == 200:
                    floor_req_response = {
                        "lift_car_id": floor_request.get("lift_car_id", 0),
                        "desired_floor": floor_request.get("desired_floor", 0),
                        "seq_id": floor_request.get("seq_id", 0),
                        "status": "ack",
                    }
                    logging.info("Response sending to sesto status server: {}".format(floor_req_response))
                    return jsonify(floor_req_response)
                else:
                    logging.info("No valid response from the lift")
            else:
                logging.info("Mode is not set to AMR")
                floor_req_response = {
                    "lift_car_id": floor_request.get("lift_id", 0),
                    "desired_floor": floor_request.get("desired_floor", 0),
                    "seq_id": floor_request.get("seq_id", 0),
                    "status": "failed",
                }
                logging.info("Response sending to sesto status server: {}".format(floor_req_response))
            return jsonify(floor_req_response)
        except Exception as e:
            raise e
