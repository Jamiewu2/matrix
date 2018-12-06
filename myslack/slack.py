import hashlib
import hmac
import json
import os
import sys
import time
from enum import Enum

from slackclient import SlackClient


class ResponseType(Enum):
    """
    https://api.slack.com/docs/interactive-message-field-guide
    """
    IN_CHANNEL = "in_channel"
    EPHEMERAL = "ephemeral"


class Slack:
    def __init__(self, slack_oauth_token: str, slack_signing_secret: str):
        self.slack_client = SlackClient(slack_oauth_token)
        self.slack_signing_secret = slack_signing_secret

    def try_api_call(self, api_call_method, **kwargs):
        response = self.slack_client.api_call(api_call_method, **kwargs)
        if "error" in response:
            raise Exception("Error occurred during api call", response)
        return response

    def verify_signature(self, timestamp, signature, raw_body: bytes):
        """
        from https://github.com/slackapi/python-slack-events-api/blob/master/slackeventsapi/server.py
        :param timestamp:
        :param signature:
        :param raw_body: the raw post body. In flask this is request.get_data() before any other call to request
        :return:
        """
        if abs(int(time.time()) - int(timestamp)) > 60 * 5:
            # The request timestamp is more than five minutes from local time.
            # It could be a replay attack, so let's ignore it.
            return False

        # Verify the request signature of the request sent from Slack
        # Generate a new hash using the app's signing secret and request data

        # Compare the generated hash and incoming request signature
        # Python 2.7.6 doesn't support compare_digest
        # It's recommended to use Python 2.7.7+
        # noqa See https://docs.python.org/2/whatsnew/2.7.html#pep-466-network-security-enhancements-for-python-2-7
        if hasattr(hmac, "compare_digest"):
            req = str.encode('v0:' + str(timestamp) + ':') + raw_body
            request_hash = 'v0=' + hmac.new(
                str.encode(self.slack_signing_secret),
                req, hashlib.sha256
            ).hexdigest()

            # Compare byte strings for Python 2
            if sys.version_info[0] == 2:
                return hmac.compare_digest(bytes(request_hash), bytes(signature))
            else:
                return hmac.compare_digest(request_hash, signature)
        else:
            # So, we'll compare the signatures explicitly
            req = str.encode('v0:' + str(timestamp) + ':') + raw_body
            request_hash = 'v0=' + hmac.new(
                str.encode(self.slack_signing_secret),
                req, hashlib.sha256
            ).hexdigest()

            if len(request_hash) != len(signature):
                return False
            result = 0
            if isinstance(request_hash, bytes) and isinstance(signature, bytes):
                for x, y in zip(request_hash, signature):
                    result |= x ^ y
            else:
                for x, y in zip(request_hash, signature):
                    result |= ord(x) ^ ord(y)
            return result == 0

    @staticmethod
    def create() -> 'Slack':
        config_filename = "config.json"

        if not os.path.isfile(config_filename):
            print("Config file does not exist. Please create a config file named: `config.json`. See config.json.template")
            sys.exit(1)

        with open("config.json") as f:
            config_vals = json.load(f)
            slack_oauth_token = config_vals["SLACK_OAUTH_TOKEN"]
            slack_signing_secret = config_vals["SLACK_SIGNING_SECRET"]

        return Slack(slack_oauth_token, slack_signing_secret)
