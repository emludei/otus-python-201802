import os
import time
import logging
import ipaddress

from copy import deepcopy
from http import HTTPStatus

import requests
import ujson


IPINFO_API_URL_TEMPLATE = "https://ipinfo.io/{0}"
WEATHER_API_URL = "http://api.openweathermap.org/data/2.5/weather"

LOGGER_FORMAT = "[%(asctime)s] %(levelname).1s %(message)s"
LOGGER_DATE_FORMAT = "%Y.%m.%d %H:%M:%S"

CONFIG_FILE_PATH_ENVIRON = "IP2W_CONFIG_FILE_PATH"
DEFAULT_CONFIG_FILE_PATH = "/usr/local/etc/ip2w.json"
DEFAULT_CONFIG = {
    "LOGFILE": "/var/log/ip2w/error.log",
    "WEATHER_API_KEY": ""  # api key for openWeatherMap, set in config file
}

DEFAULT_HTTP_CLIENT_TIMEOUT = 1
DEFAULT_RETIES_COUNT = 3
DEFAULT_RETRY_TIMEOUT = 3


def retry(max_retries, retry_timeout):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for retry_number in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    return result
                except OSError:
                    if retry_number == max_retries - 1:
                        raise

                    time.sleep(retry_timeout)

        return wrapper

    return decorator


def is_ip(ip):
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return False

    return True


@retry(DEFAULT_RETIES_COUNT, DEFAULT_RETRY_TIMEOUT)
def get_ipinfo(ip):
    url = IPINFO_API_URL_TEMPLATE.format(ip)
    response = requests.get(url, timeout=DEFAULT_HTTP_CLIENT_TIMEOUT)
    response.raise_for_status()
    return ujson.loads(response.content)


@retry(DEFAULT_RETIES_COUNT, DEFAULT_RETRY_TIMEOUT)
def get_weather(lat, lon, api_key):
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric"
    }
    response = requests.get(
        WEATHER_API_URL,
        timeout=DEFAULT_HTTP_CLIENT_TIMEOUT,
        params=params
    )
    response.raise_for_status()
    return ujson.loads(response.content)


class Application:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    def __call__(self, environ, start_response):
        try:
            result = self.process_request(environ, start_response)
            return result
        except:
            self.logger.exception("Runtime error: ")
            raise

    def process_request(self, environ, start_response):
        uri = environ.get("REQUEST_URI", "")
        uri_parts = uri.split("/")
        if len(uri_parts) < 1:
            return self.send_response(
                HTTPStatus.BAD_REQUEST,
                {"error": "Invalid request."},
                start_response
            )

        ip = uri_parts[-1]
        if not is_ip(ip):
            return self.send_response(
                HTTPStatus.BAD_REQUEST,
                {"error": "Invalid ip."},
                start_response
            )

        try:
            ipinfo = get_ipinfo(ip)
        except ValueError as e:
            self.logger.error("Cant get ip info: ", e)
            return self.send_response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "Cant get ip info."},
                start_response
            )

        if "error" in ipinfo:
            self.logger.error("Got cant get info for ip {0}, "
                              "response {1}".format(ip, ipinfo.get("error")))
            return self.send_response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "Cant get info for ip."},
                start_response
            )
        if "bogon" in ipinfo:
            return self.send_response(
                HTTPStatus.BAD_REQUEST,
                {"error": "Invalid ip."},
                start_response
            )

        location = ipinfo.get("loc")
        if not location:
            log_message = "Invalid response from {0}, no location: ".format(
                IPINFO_API_URL_TEMPLATE
            )
            self.logger.error(log_message)
            return self.send_response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "Cant get weather info by location."},
                start_response
            )

        try:
            lat, lon = location.split(",")
        except ValueError:
            log_message = "Invalid response from {0}, " \
                          "cant get location: ".format(IPINFO_API_URL_TEMPLATE)
            self.logger.error(log_message)
            return self.send_response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "Cant get location of ip."},
                start_response
            )

        try:
            weather_api_key = self.config.get("WEATHER_API_KEY")
            weather = get_weather(lat, lon, weather_api_key)
        except (ValueError, OSError) as e:
            self.logger.error("Cant get weather info by location: ", e)
            return self.send_response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "Cant get weather info by location."},
                start_response
            )

        try:
            data = {
                "city": weather["name"],
                "temp": weather["main"]["temp"],
                "conditions": weather["weather"][0]["description"]
            }
        except LookupError:
            log_message = "Invalid weather json response: {0}".format(weather)
            self.logger.error(log_message)
            return self.send_response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "Invalid weather json response."},
                start_response
            )

        return self.send_response(HTTPStatus.OK, data, start_response)

    @staticmethod
    def get_headers(body):
        response_headers = [
            ('Content-Type', 'text/plain'),
            ('Content-Length', str(len(body)))
        ]

        return response_headers

    @staticmethod
    def get_status_string(status):
        status_string = "{0} {1}".format(status.value, status.name)
        return status_string

    def send_response(self, status, data, start_response):
        body = ujson.dumps(data).encode("utf-8")
        headers = self.get_headers(body)
        status = self.get_status_string(status)
        start_response(status, headers)
        return [body]


def parse_config(config_file_path):
    config = deepcopy(DEFAULT_CONFIG)

    if not os.path.exists(config_file_path):
        raise FileNotFoundError(
            "Config {0} does not exist".format(config_file_path)
        )

    with open(config_file_path, "r") as config_file:
        user_config = ujson.load(config_file)
        config.update(user_config)

    return config


def get_logger(config):
    log_file = config.get("LOGFILE", None)

    logging.basicConfig(
        format=LOGGER_FORMAT,
        datefmt=LOGGER_DATE_FORMAT,
        filename=log_file,
        level=logging.INFO
    )

    logger = logging.getLogger(__name__)
    return logger


def create_application():
    config_file_path = os.environ.get(
        CONFIG_FILE_PATH_ENVIRON,
        DEFAULT_CONFIG_FILE_PATH
    )

    config = parse_config(config_file_path)
    logger = get_logger(config)

    app = Application(config, logger)
    return app


application = create_application()
