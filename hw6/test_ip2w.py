import unittest
import requests
import time

from http import HTTPStatus

import ujson


class TestAPI(unittest.TestCase):
    url_template = "http://localhost/ip2w/{ip}"

    def test_invalid_ip(self):
        url = self.url_template.format(ip="127.0.0.9999")
        response = requests.get(url)

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST.value)
        self.assertEqual(response.content, b'{"error":"Invalid ip."}')

        time.sleep(.5)

    def test_bogon_ips(self):
        url = self.url_template.format(ip="127.0.0.1")
        response = requests.get(url)

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST.value)
        self.assertEqual(response.content, b'{"error":"Invalid ip."}')

        time.sleep(.5)

        url = self.url_template.format(ip="0.0.0.0")
        response = requests.get(url)

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST.value)
        self.assertEqual(response.content, b'{"error":"Invalid ip."}')

        time.sleep(.5)

        url = self.url_template.format(ip="10.0.0.0")
        response = requests.get(url)

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST.value)
        self.assertEqual(response.content, b'{"error":"Invalid ip."}')

        time.sleep(.5)

        url = self.url_template.format(ip="172.16.0.0")
        response = requests.get(url)

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST.value)
        self.assertEqual(response.content, b'{"error":"Invalid ip."}')

        time.sleep(.5)

        url = self.url_template.format(ip="192.168.0.0")
        response = requests.get(url)

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST.value)
        self.assertEqual(response.content, b'{"error":"Invalid ip."}')

        time.sleep(.5)

        url = self.url_template.format(ip="169.254.0.0")
        response = requests.get(url)

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST.value)
        self.assertEqual(response.content, b'{"error":"Invalid ip."}')

        time.sleep(.5)

    def test_correct_ips(self):
        url = self.url_template.format(ip="8.8.8.8")
        response = requests.get(url)

        json_response = ujson.loads(response.content)

        self.assertEqual(response.status_code, HTTPStatus.OK.value)
        self.assertEqual(
            set(json_response.keys()),
            {"city", "temp", "conditions"}
        )

        time.sleep(.5)

        url = self.url_template.format(ip="192.30.253.112")
        response = requests.get(url)

        json_response = ujson.loads(response.content)

        self.assertEqual(response.status_code, HTTPStatus.OK.value)
        self.assertEqual(
            set(json_response.keys()),
            {"city", "temp", "conditions"}
        )


if __name__ == "__main__":
    unittest.main()
