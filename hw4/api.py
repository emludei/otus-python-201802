#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import datetime
import logging
import hashlib
import uuid

from optparse import OptionParser
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import OrderedDict

from redis import Redis

from scoring import get_interests, get_score
from store import Store


SALT = "Otus"
ADMIN_LOGIN = "admin"
ADMIN_SALT = "42"
ADMIN_SCORE = 42.0
OK = 200
BAD_REQUEST = 400
FORBIDDEN = 403
NOT_FOUND = 404
INVALID_REQUEST = 422
INTERNAL_ERROR = 500
ERRORS = {
    BAD_REQUEST: "Bad Request",
    FORBIDDEN: "Forbidden",
    NOT_FOUND: "Not Found",
    INVALID_REQUEST: "Invalid Request",
    INTERNAL_ERROR: "Internal Server Error",
}
UNKNOWN = 0
MALE = 1
FEMALE = 2
GENDERS = {
    UNKNOWN: "unknown",
    MALE: "male",
    FEMALE: "female",
}
EMPTY_VALUES = ('', [], (), {})
AT_SIGN = "@"
EMAIL_PARTS = 2
PHONE_LENGTH = 11
PHONE_FIRST_NUMBER = "7"
DATE_FORMAT = "%d.%m.%Y"
BIRTH_DAY_MAX_YEARS = 70
REDIS_CONFIG = {
    "HOST": "127.0.0.1",
    "PORT": 6379,
    "DB": 0,
    "CONNECT_TIMEOUT": 1,
    "RESPONSE_TIMEOUT": 1,
}
STORE_MAX_RETRIES = 5


class ValidationError(Exception):
    def __init__(self, message, code="invalid", params=None):
        super().__init__(message, code, params)

        if isinstance(message, list):
            self.error_list = []
            for message in message:
                if not isinstance(message, ValidationError):
                    message = ValidationError(message)
                self.error_list.extend(message.error_list)
        else:
            self.message = message
            self.code = code
            self.params = params
            self.error_list = [self]

    def __iter__(self):
        for error in self.error_list:
            yield error.message

    def __str__(self):
        return repr(list(self))

    def __repr__(self):
        return "ValidationError({0})".format(self)


def validate_integer(value):
    if not isinstance(value, int):
        raise ValidationError("This field must be digit.")


def validate_string(value):
    if not isinstance(value, str):
        raise ValidationError("This field must be string")


def validate_dict(value):
    if not isinstance(value, dict):
        raise ValidationError("This field must be dict")


def validate_phone(value):
    if not isinstance(value, (str, int)):
        raise ValidationError("This field must be string or digit.")

    phone = str(value)
    if not phone.isdigit() or len(phone) != PHONE_LENGTH:
        message = "This field must consist of {0} digits.".format(PHONE_LENGTH)
        raise ValidationError(message)
    if phone[0] != PHONE_FIRST_NUMBER:
        message = "First digit of phone must be {0}".format(PHONE_FIRST_NUMBER)
        raise ValidationError(message)


def validate_email(value):
    validate_string(value)

    if AT_SIGN not in value:
        message = "This filed must contains {0}.".format(AT_SIGN)
        raise ValidationError(message)

    parts = list(part for part in value.split(AT_SIGN) if part)
    if len(parts) != EMAIL_PARTS:
        message = "Invalid email, must consist of two parts " \
                  "separated by {0}.".format(AT_SIGN)
        raise ValidationError(message)


def validate_date(value):
    validate_string(value)

    try:
        get_date_from_string(value)
    except ValueError:
        message = "Invalid format of date, supported " \
                  "format is <{0}>.".format(DATE_FORMAT)
        raise ValidationError(message)


def validate_birthday(value):
    validate_date(value)

    date = get_date_from_string(value)
    current_date = datetime.datetime.utcnow().date()
    year_diff = current_date.year - date.year
    if (current_date.month, current_date.day) < (date.month, date.day):
        year_diff -= 1

    if year_diff > BIRTH_DAY_MAX_YEARS:
        message = "Max years old is {0}.".format(BIRTH_DAY_MAX_YEARS)
        raise ValidationError(message)


def validate_gender(value):
    validate_integer(value)
    if value not in GENDERS:
        message = "Invalid type of gender, available values are {0}".format(
            ", ".join(map(str, GENDERS.keys()))
        )
        raise ValidationError(message)


def validate_int_array(value):
    error_message = "This field must be array of integers."
    if not isinstance(value, (list, tuple)):
        raise ValidationError(error_message)

    for item in value:
        try:
            validate_integer(item)
        except ValidationError:
            raise ValidationError(error_message)


def get_date_from_string(string_date):
    return datetime.datetime.strptime(string_date, DATE_FORMAT)


class Field:
    validators = []

    def __init__(self, required=True, nullable=False):
        self.required = required
        self.nullable = nullable
        self.is_empty = False

    def validate(self, value):
        self.is_empty = False

        if value is None and self.required:
            message = "This field is required."
            raise ValidationError(message, "required")

        if value in EMPTY_VALUES and not self.nullable:
            message = "This field must be non empty."
            raise ValidationError(message, "nullable")

        if value is None or value in EMPTY_VALUES:
            self.is_empty = True
            return

        errors = []
        for validator in self.validators:
            try:
                validator(value)
            except ValidationError as e:
                errors.append(e)

        if errors:
            raise ValidationError(errors)


class DeclarativeFieldsMeta(type):
    def __new__(cls, name, bases, attrs):
        declared_fields = OrderedDict()
        for key, value in list(attrs.items()):
            if isinstance(value, Field):
                declared_fields[key] = value
                attrs.pop(key)
        new_class = super().__new__(cls, name, bases, attrs)

        # Collect fields from base classes.
        for base in reversed(new_class.__mro__):
            if hasattr(base, "declared_fields"):
                declared_fields.update(base.declared_fields)

        new_class.fields = declared_fields
        new_class.declared_fields = declared_fields
        return new_class

    @classmethod
    def __prepare__(mcs, name, bases, **kwargs):
        return OrderedDict()


class BaseRequestValidator:
    def __init__(self, request_data=None):
        if request_data is None:
            request_data = {}

        self.request_data = request_data
        self._errors = None

    def is_valid(self):
        return not self.errors

    @property
    def errors(self):
        if self._errors is None:
            self.validate()

        return self._errors

    def validate(self):
        self._errors = {}
        for name, field in self.fields.items():
            try:
                value = self.request_data.get(name)
                field.validate(value)
            except ValidationError as e:
                self.add_error(name, e)

    def add_error(self, name, e):
        if self._errors is None:
            self._errors = {}

        if name not in self._errors:
            self._errors[name] = []
        self._errors[name].extend(list(e))

    def repr_errors(self):
        field_errors = []
        for name, errors in self.errors.items():
            repr_for_field = "{0}: {1}".format(
                name,
                ", ".join((str(error) for error in errors)),
            )
            field_errors.append(repr_for_field)
        return "; ".join(field_errors)

    def non_empty_fields(self):
        non_empty_fields = [
            name for name, field in self.fields.items() if not field.is_empty
        ]
        return non_empty_fields

    def __getattr__(self, attr):
        if self.fields.get(attr) is None:
            raise KeyError(
                "Key '%s' not found in '%s'. Choices are: %s." % (
                    attr,
                    self.__class__.__name__,
                    ', '.join(sorted(f for f in self.fields)),
                )
            )

        return self.request_data.get(attr)


class RequestValidator(BaseRequestValidator, metaclass=DeclarativeFieldsMeta):
    pass


class CharField(Field):
    validators = [validate_string]


class ArgumentsField(Field):
    validators = [validate_dict]


class EmailField(Field):
    validators = [validate_email]


class PhoneField(Field):
    validators = [validate_phone]


class DateField(Field):
    validators = [validate_date]


class BirthDayField(Field):
    validators = [validate_birthday]


class GenderField(Field):
    validators = [validate_gender]


class ClientIDsField(Field):
    validators = [validate_int_array]


class ClientsInterestsRequest(RequestValidator):
    client_ids = ClientIDsField(required=True)
    date = DateField(required=False, nullable=True)


class OnlineScoreRequest(RequestValidator):
    first_name = CharField(required=False, nullable=True)
    last_name = CharField(required=False, nullable=True)
    email = EmailField(required=False, nullable=True)
    phone = PhoneField(required=False, nullable=True)
    birthday = BirthDayField(required=False, nullable=True)
    gender = GenderField(required=False, nullable=True)

    def validate(self):
        super().validate()

        pairs = (
            self.phone and self.email,
            self.first_name and self.last_name,
            self.gender and self.birthday
        )
        if any(pairs):
            return

        message = "One of pairs first_name-lastname, phone-email, " \
                  "gender-birthday must be with non empty values"
        self.add_error("request_data", ValidationError(message))


class MethodRequest(RequestValidator):
    account = CharField(required=False, nullable=True)
    login = CharField(required=True, nullable=True)
    token = CharField(required=True, nullable=True)
    arguments = ArgumentsField(required=True, nullable=True)
    method = CharField(required=True, nullable=False)

    @property
    def is_admin(self):
        return self.login == ADMIN_LOGIN


def check_auth(request):
    if request.login == ADMIN_LOGIN:
        key = datetime.datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT
        digest = hashlib.sha512(key.encode("utf-8")).hexdigest()
    else:
        key = request.account + request.login + SALT
        digest = hashlib.sha512(key.encode("utf-8")).hexdigest()
    if digest == request.token:
        return True
    return False


def online_score_handler(method_request, context, store):
    online_score_request = OnlineScoreRequest(method_request.arguments)
    if not online_score_request.is_valid():
        return online_score_request.repr_errors(), INVALID_REQUEST

    context["has"] = online_score_request.non_empty_fields()

    if method_request.is_admin:
        return {"score": ADMIN_SCORE}, OK

    birthday = online_score_request.birthday
    if isinstance(birthday, str):
        birthday = get_date_from_string(birthday)

    score = get_score(
        store,
        online_score_request.phone,
        online_score_request.email,
        birthday,
        online_score_request.gender,
        online_score_request.first_name,
        online_score_request.last_name
    )
    return {"score": score}, OK


def clients_interests_handler(method_request, context, store):
    clients_interests_request = ClientsInterestsRequest(
        method_request.arguments
    )
    if not clients_interests_request.is_valid():
        return clients_interests_request.repr_errors(), INVALID_REQUEST

    client_ids = clients_interests_request.client_ids
    context["nclients"] = len(client_ids)
    response = {
        str(_id): get_interests(store, _id) for _id in client_ids
    }
    return response, OK


def method_handler(request, ctx, store):
    router = {
        "online_score": online_score_handler,
        "clients_interests": clients_interests_handler
    }

    body = request.get("body", None)
    if not body:
        return ERRORS[INVALID_REQUEST], INVALID_REQUEST

    method_request = MethodRequest(body)
    if not method_request.is_valid():
        return method_request.repr_errors(), INVALID_REQUEST

    if not check_auth(method_request):
        return ERRORS[FORBIDDEN], FORBIDDEN

    handler = router.get(method_request.method)
    if handler is None:
        return ERRORS[BAD_REQUEST], BAD_REQUEST

    return handler(method_request, ctx, store)


def get_redis_connection_pool(config):
    host = config.get("HOST")
    port = config.get("PORT")
    db = config.get("DB", 0)
    connect_timeout = config.get("CONNECT_TIMEOUT")
    response_timeout = config.get("RESPONSE_TIMEOUT")

    if host is None or port is None:
        raise ValueError("Invalid redis config")

    connection_pool = Redis(
        host=host,
        port=port,
        db=db,
        socket_connect_timeout=connect_timeout,
        socket_timeout=response_timeout,
    )
    return connection_pool


class MainHTTPHandler(BaseHTTPRequestHandler):
    router = {
        "method": method_handler
    }
    redis_conn_pool = get_redis_connection_pool(REDIS_CONFIG)
    store = Store(redis_conn_pool, redis_conn_pool, STORE_MAX_RETRIES)

    def get_request_id(self, headers):
        return headers.get("HTTP_X_REQUEST_ID", uuid.uuid4().hex)

    def do_POST(self):
        response, code = {}, OK
        context = {"request_id": self.get_request_id(self.headers)}
        request = None
        try:
            content_length = int(self.headers.get("Content-Length"))
            data_string = self.rfile.read(content_length).decode("utf-8")
            request = json.loads(data_string)
        except (TypeError, ValueError):
            code = BAD_REQUEST

        if request:
            path = self.path.strip("/")
            logging.info(
                "%s: %s %s" % (self.path, data_string, context["request_id"])
            )
            if path in self.router:
                try:
                    response, code = self.router[path](
                        {"body": request, "headers": self.headers},
                        context,
                        self.store
                    )
                except Exception as e:
                    logging.exception("Unexpected error: %s" % e)
                    code = INTERNAL_ERROR
            else:
                code = NOT_FOUND

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if code not in ERRORS:
            r = {"response": response, "code": code}
        else:
            r = {
                "error": response or ERRORS.get(code, "Unknown Error"),
                "code": code
            }
        context.update(r)
        logging.info(context)
        self.wfile.write(json.dumps(r).encode("utf-8"))
        return


if __name__ == "__main__":
    op = OptionParser()
    op.add_option("-p", "--port", action="store", type=int, default=8080)
    op.add_option("-l", "--log", action="store", default=None)
    (opts, args) = op.parse_args()
    logging.basicConfig(
        filename=opts.log,
        level=logging.INFO,
        format="[%(asctime)s] %(levelname).1s %(message)s",
        datefmt="%Y.%m.%d %H:%M:%S"
    )
    server = HTTPServer(("localhost", opts.port), MainHTTPHandler)
    logging.info("Starting server at %s" % opts.port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

    server.server_close()
