from datetime import datetime
from twisted.internet import reactor, defer
from twisted.web.client import Agent, readBody, FileBodyProducer
from twisted.web.http_headers import Headers
from twisted.python import log
from twisted.web.iweb import IBodyProducer
from zope.interface import implementer
from twisted.internet.defer import succeed
import json

import requests
from config_parser import GRANT_TYPE, CLIENT_ID, CLIENT_SECRET, SERVER_IP, USERNAME, PASSWORD


def get_access_token():
    access_url = "https://ems.otis.com/auth/realms/ems/protocol/openid-connect/token"
    data = {
        "grant_type": GRANT_TYPE,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }

    response = requests.post(access_url, headers={"Content-Type": "application/x-www-form-urlencoded"}, data=data)
    access_token = response.json()["access_token"]
    expire_in = response.json()["expires_in"]
    print("Successfully received access token from lift")
    return access_token, expire_in


@implementer(IBodyProducer)
class BytesProducer:
    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class FireAlarmUpdater:

    def __init__(self):
        self.agent = Agent(reactor)
        self.retry_delay = 1

    def update_fire_alarm(self, active_status):
        d = self.generate_server_token()
        d.addCallback(self.make_update_request, active_status)
        d.addErrback(self.handle_error)
        return d

    def make_update_request(self, access_token, active_status):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        access_url = f"http://{SERVER_IP}/public/emergency"
        headers = Headers({"Authorization": [f"Bearer {access_token}".encode('utf-8')],
                           "Content-Type": ["application/json"]})
        data = json.dumps({"active_status": active_status, "timestamp": timestamp}).encode('utf-8')
        body = BytesProducer(data)

        d = self.agent.request(
            b'PUT',
            access_url.encode('utf-8'),
            headers,
            body
        )
        d.addCallback(self.handle_response, active_status, access_token)
        d.addErrback(self.handle_error, err="Failure on update fire alarm status.")
        return d

    def handle_response(self, response, active_status, access_token):
        log.msg("The response code for the update fire alarm status: ", response.code)
        if 200 <= response.code < 300:
            d = readBody(response)
            d.addCallback(lambda body: print("Request was successful:", json.loads(body)))
            log.msg(f"Fire alarm {'activated' if active_status else 'deactivated'}! Status has been successfully "
                    f"updated on the server.")
            return d
        elif response.code == 406 and not active_status:
            d = readBody(response)
            d.addCallback(lambda body: print("Retry for to clear fire alarm. The server response is:", json.loads(body)))
            reactor.callLater(self.retry_delay, self.make_update_request, access_token, active_status)
        else:
            d = readBody(response)
            d.addCallback(lambda body: print("Response content:", body.decode('utf-8')))
            return d

    def generate_server_token(self):
        log.msg("Inside the generate server token")
        url = f"http://{SERVER_IP}/public/auth"
        headers = Headers({b'Content-Type': [b'application/json']})
        data = json.dumps({"user_name": USERNAME, "password": PASSWORD}).encode('utf-8')
        body = BytesProducer(data)

        d = self.agent.request(
            b'POST',
            url.encode('utf-8'),
            headers,
            body
        )
        d.addCallback(self.handle_token_response)
        d.addErrback(self.handle_error, err="Failure on generate server token.")
        return d

    def handle_token_response(self, response):
        log.msg("The response code for the access token: ", response.code)
        if 200 <= response.code < 300:
            d = readBody(response)
            d.addCallback(lambda body: json.loads(body)["access_token"])
            log.msg("Successfully received fire alarm access token")
            return d
        else:
            d = readBody(response)
            d.addCallback(lambda body: defer.fail(Exception("Failed to get access token:", body.decode('utf-8'))))
            return d

    def handle_error(self, failure, err):
        log.msg("An error occurred:", err, "&&", failure.getErrorMessage())
        failure.printTraceback()
        return failure


requests_schema = {
    "type": "object",
    "required": ["seq_id", "lift_car_id", "desired_floor", "amr_in_lift"],
    "properties": {
        "seq_id": {"type": "number"},
        "lift_car_id": {"type": "number", },
        "desired_floor": {"type": "number"},
        "amr_in_lift": {"type": "boolean"}
    },
}

mode_schema = {
    "type": "object",
    "required": ["lift_car_id", "mode"],
    "properties": {
        "lift_car_id": {"type": "number"},
        "mode": {"type": "string", },
    },
}


door_schema = {
    "type": "object",
    "required": ["lift_car_id", "door_state"],
    "properties": {
        "lift_car_id": {"type": "number"},
        "door_state": {"type": "string", },
    },
}

fire_alarm_schema = {
    "type": "object",
    "required": ["lift_car_id", "activate"],
    "properties": {
        "lift_car_id": {"type": "number"},
        "activate": {"type": "boolean"},
    },
}