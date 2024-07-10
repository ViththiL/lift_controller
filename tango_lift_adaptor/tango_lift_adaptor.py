#!/usr/bin/env python
# encoding: utf-8
import json

from flask import Flask, request
import logging
from lift_adaptor_service import LiftAdaptorService
from config_parser import config_data

app = Flask(__name__)


@app.route('/lifts/statuses', methods=['GET'])
def get_lift_statuses():
    logging.info("Getting lift statuses")
    return lift_adaptor_service.fetch_lift_statuses()


@app.route('/lifts/modes', methods=['PUT'])
def put_lift_mode():
    logging.info("Putting lift modes")
    data = json.loads(request.data)
    logging.info(data)
    return lift_adaptor_service.set_lift_modes(data)


@app.route('/lifts/floor_requests', methods=['POST'])
def post_lift_floor_requests():
    logging.info("Posting floor requests")
    data = json.loads(request.data)
    logging.info(data)
    return lift_adaptor_service.set_floor(data)


if __name__ == "__main__":
    logging.getLogger()
    logging.basicConfig(format='%(asctime)s:  %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', filename='tango_lift_adaptor.log', level=logging.DEBUG)
    logging.info("Starting the Tango lift adaptor")
    lift_adaptor_service = LiftAdaptorService()
    # host_ip = config_data['host_ip']
    # port = config_data['port']
    app.run("0.0.0.0", 9000, debug=True)
    logging.info("Running on url: 0.0.0.0:9000")
    logging.info("Closing adaptor")
