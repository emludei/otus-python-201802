#!/usr/bin/env python3

import mimetypes
import multiprocessing
import logging
import socket
import select
import time
import re
import os
import codecs

from argparse import ArgumentParser
from collections import defaultdict
from http import HTTPStatus
from urllib import parse as urlparse


CPU_CORES = multiprocessing.cpu_count()
DEFAULT_DOCUMENT_ROOT = "document_root"
MAX_CLIENTS_IN_QUEUE = 400
SOCKET_TIMEOUT = 1
CHUNK_SIZE = 4096
MAX_REQUEST_SIZE = 8 * 1024 * 1024

HTTP_HEAD_SEPORATOR_RN = b'\r\n\r\n'
HTTP_HEAD_SEPORATOR_NN = b'\n\n\n\n'
HTTP_VERSION = "HTTP/1.1"
HTTP_START_LINE_PARTS = 3
HTTP_START_LINE_REGEXP = re.compile(
    r"(?P<method>[A-Z]{3,7}) (?P<uri>/.+) HTTP/1.[0,1]"
)

INDEX_FILE = "index.html"

SERVER = "Some server 1.0"


ALLOWED_CONTENT_TYPES = (
    "text/plain",
    "text/html",
    "text/css",
    "image/png",
    "image/jpeg",
    "image/gif",
    "application/javascript",
    "application/x-shockwave-flash"
)

ALLOWED_METHODS = ("GET", "HEAD")


LOGGER_FORMAT = "[%(asctime)s] %(levelname).1s %(message)s"
LOGGER_DATE_FORMAT = "%Y.%m.%d %H:%M:%S"


def get_server_socket(address):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    server.setsockopt(socket.SOL_SOCKET, socket.TCP_NODELAY, 1)
    server.bind(address)
    server.listen(MAX_CLIENTS_IN_QUEUE)
    server.setblocking(0)
    return server


def get_response(code, body=b"", content_type=None,
                 content_length=None):
    headers = {}
    start_string = "{0} {1} {2}".format(
        HTTP_VERSION,
        code.value,
        code.phrase
    )

    headers["Server"] = SERVER
    headers["Date"] = time.strftime(
        "%a, %d %b %Y %H:%M:%S GMT",
        time.gmtime()
    )

    if code.value == HTTPStatus.OK.value:
        headers["Content-Type"] = content_type or "text/htm"
        headers["Content-Length"] = content_length or "0"
    else:
        headers["Content-Type"] = "text/html"
        headers["Content-Length"] = "0"

    headers["Connection"] = "close"

    headers_string = "\r\n".join(
        "{0}: {1}".format(header, value) for header, value in headers.items()
    )

    response = "{0}\r\n{1}{2}".format(
        start_string,
        headers_string,
        HTTP_HEAD_SEPORATOR_RN.decode("utf-8"),
    ).encode("utf-8")
    return response + body


class Server:
    def __init__(self, host, port, logger, document_root):
        self.host = host
        self.port = port
        self.logger = logger
        self.document_root = document_root

        self.connections = {}
        self.requests = defaultdict(bytearray)
        self.responses = {}
        self.eventloop = None

    def start(self):
        try:
            server = get_server_socket((self.host, self.port))
            server_fileno = server.fileno()

            self.eventloop = select.epoll()
            self.eventloop.register(server_fileno, select.EPOLLIN)

            while True:
                events = self.eventloop.poll(1)

                for fileno, event in events:
                    if fileno == server_fileno:
                        self.init_connection(server)
                    elif event & select.EPOLLIN:
                        self.handle_request(fileno)
                    elif event & select.EPOLLOUT:
                        self.send_request(fileno)
        except KeyboardInterrupt:
            self.logger.info(
                "Got keyboard interrupt, exit: pid {0}".format(os.getpid())
            )
        except:
            logging.exception("Runtime error: ")
            raise
        finally:
            self.close()

    def close(self):
        for fileno, conn in list(self.connections.items()):
            self.eventloop.unregister(fileno)
            conn.close()
            self.connections.pop(fileno, None)
            self.requests.pop(fileno, None)
            self.responses.pop(fileno, None)

        if self.eventloop is not None:
            self.eventloop.close()

    def init_connection(self, server):
        client, address = server.accept()
        self.logger.info("Connected client - {0}:{1}".format(*address))
        client.setblocking(0)
        client_fileno = client.fileno()
        self.eventloop.register(client_fileno, select.EPOLLIN)
        self.connections[client_fileno] = client

    def handle_request(self, fileno):
        client_socket = self.connections[fileno]

        data = client_socket.recv(CHUNK_SIZE)
        if not data:
            logger.error("Connection reset by peer")
            self.eventloop.unregister(fileno)
            client_socket.close()
            self.connections.pop(fileno, None)
            self.requests.pop(fileno, None)
            self.responses.pop(fileno, None)
            return

        self.requests[fileno] += data

        if self.requests[fileno].find(HTTP_HEAD_SEPORATOR_RN) >= 0 or \
                self.requests[fileno].find(HTTP_HEAD_SEPORATOR_NN) >= 0:
            self.eventloop.modify(fileno, select.EPOLLOUT)
            self.process_request(fileno)

    def send_request(self, fileno):
        client_socket = self.connections[fileno]
        response = self.responses.get(fileno, b"")

        if not response:
            self.eventloop.unregister(fileno)
            client_socket.shutdown(socket.SHUT_WR)
            self.connections.pop(fileno, None)
            self.requests.pop(fileno, None)
            self.responses.pop(fileno, None)
            return

        written = client_socket.send(response)
        self.responses[fileno] = response[written:]

    def process_request(self, fileno):
        try:
            data = self.requests[fileno].decode("utf-8")
        except ValueError:
            response = get_response(HTTPStatus.BAD_REQUEST)
            self.responses[fileno] = response
            return

        request_lines = data.split("\r\n")
        start_line_match = HTTP_START_LINE_REGEXP.fullmatch(request_lines[0])
        if start_line_match is None:
            response = get_response(HTTPStatus.BAD_REQUEST)
            self.responses[fileno] = response
            return

        start_line_group = start_line_match.groupdict()
        method = start_line_group.get("method", "").upper()
        if method not in ALLOWED_METHODS:
            response = get_response(HTTPStatus.METHOD_NOT_ALLOWED)
            self.responses[fileno] = response
            return

        parsed_uri = urlparse.urlparse(start_line_group.get("uri", ""))
        parsed_uri = urlparse.unquote(parsed_uri.path)
        parsed_uri = os.path.abspath(parsed_uri)

        use_index = False
        if os.path.isdir(parsed_uri) or "." not in os.path.basename(parsed_uri):
            use_index = True

        document_path = self.document_root + parsed_uri

        if use_index:
            document_path = os.path.join(document_path, INDEX_FILE)

        if not os.path.isfile(document_path):
            code = HTTPStatus.FORBIDDEN if use_index else HTTPStatus.NOT_FOUND
            response = get_response(code)
            self.responses[fileno] = response
            return

        content_type, _ = mimetypes.guess_type(document_path)
        if content_type not in ALLOWED_CONTENT_TYPES:
            response = get_response(HTTPStatus.METHOD_NOT_ALLOWED)
            self.responses[fileno] = response
            return

        try:
            size = os.path.getsize(document_path)
        except OSError:
            response = get_response(HTTPStatus.NOT_FOUND)
            self.responses[fileno] = response
            return

        if method == "HEAD":
            response = get_response(
                HTTPStatus.OK,
                content_type=content_type,
                content_length=str(size)
            )
            self.responses[fileno] = response
            return

        try:
            with codecs.open(document_path, "rb") as f:
                body = f.read()

        except ValueError:
            response = get_response(HTTPStatus.METHOD_NOT_ALLOWED)
            self.responses[fileno] = response
            return

        response = get_response(HTTPStatus.OK, body,
                                content_type, str(size))
        self.responses[fileno] = response


def get_logger(logfile):
    logging.basicConfig(
        format=LOGGER_FORMAT,
        datefmt=LOGGER_DATE_FORMAT,
        filename=logfile,
        level=logging.INFO
    )

    logger = logging.getLogger(__name__)
    return logger


def parse_arguments():
    parser = ArgumentParser()
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host for listening"
    )
    parser.add_argument(
        "--port", default=80, help="Port for listening", type=int
    )
    parser.add_argument("--log", default=None, help="Log file path")
    parser.add_argument(
        "-w", "--workers", default=CPU_CORES, help="Workers count", type=int
    )
    parser.add_argument(
        "-r", "--root", default=DEFAULT_DOCUMENT_ROOT, help="document_root")

    cmd_arguments = parser.parse_args()
    return cmd_arguments


def main(arguments, logger):
    workers = []
    servers = []
    try:
        for _ in range(arguments.workers):
            server = Server(
                arguments.host,
                arguments.port,
                logger,
                arguments.root
            )
            servers.append(server)
            worker = multiprocessing.Process(target=server.start)
            worker.start()
            workers.append(worker)

        for worker in workers:
            worker.join()

    except KeyboardInterrupt:
        logger.info(
            "Got keyboard interrupt, exit: pid {0}".format(os.getpid())
        )

    finally:
        for server in servers:
            server.close()

        for worker in workers:
            worker.terminate()
            logger.info("Terminate worker {0}".format(worker))


if __name__ == '__main__':
    arguments = parse_arguments()
    logger = get_logger(arguments.log)

    try:
        main(arguments, logger)
    except:
        logging.exception("Runtime error: ")
        raise
