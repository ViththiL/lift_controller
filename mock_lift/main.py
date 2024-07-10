import json
import os

from twisted.internet.task import LoopingCall
from klein import run
from twisted.python import log
from twisted.python.logfile import DailyLogFile

from scheduler import do_schedule
from lift_state import lift_car
from endpoints import get_lift, update_emergency_mode, update_mode, update_door, update_floor_requests

with open('config.json', 'r') as config_file:
    config_data = json.load(config_file)

port = config_data['port']
log_file_path = config_data['full_log_file_path']

# SESTO_FOLDER = join(environ.get("HOME"), ".sesto")
log_dir = os.path.expanduser(log_file_path)
log_file = log.startLogging(DailyLogFile.fromFullPath(log_dir))


if __name__ == '__main__':
    sch_status = LoopingCall(do_schedule)
    sch_status.start(1)
    run("0.0.0.0", port)
