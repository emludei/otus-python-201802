import json
import random
import unittest
import datetime
import hashlib

import api

from collections import defaultdict, OrderedDict


def cases(cases):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for case in cases:
                new_args = args + (case,)
                func(*new_args, **kwargs)
        return wrapper
    return decorator


class RedisConnectionPoolMock:
    def __init__(self, get_errors_count=0, set_errors_count=0,
                 get_timeout_err=False, set_timeout_err=False):
        self.get_errors_count = get_errors_count
        self.get_timeout_err = get_timeout_err
        self.set_errors_count = set_errors_count
        self.set_timeout_err = set_timeout_err

        self.get_counter = 0
        self.set_counter = 0
        self.storage = {}

    def get(self, key):
        if self.get_counter >= self.get_errors_count:
            return self.storage.get(key)

        self.get_counter += 1

        if self.get_timeout_err:
            raise TimeoutError("Test timeout exception")

        err_class = random.choice([
            ConnectionError,
            BrokenPipeError,
            ConnectionAbortedError,
            ConnectionRefusedError,
            ConnectionResetError
        ])
        raise err_class("Test connection exception")

    def set(self, key, value, ex=None):
        if self.set_counter >= self.set_errors_count:
            value_str = str(value)
            self.storage[key] = value_str.encode("utf-8")
            return

        self.set_counter += 1

        if self.set_timeout_err:
            raise TimeoutError("Test timeout exception")

        err_class = random.choice([
            ConnectionError,
            BrokenPipeError,
            ConnectionAbortedError,
            ConnectionRefusedError,
            ConnectionResetError
        ])
        raise err_class("Test connection exception")

    def reset(self):
        self.get_counter = 0
        self.set_counter = 0
        self.storage = {}


class TestStore(unittest.TestCase):
    def test_cache_get_return_value_after_reconnect(self):
        test_key = "test_key"
        test_value = "test_value"
        redis_connection_pool = RedisConnectionPoolMock(get_errors_count=4)
        redis_connection_pool.set(test_key, test_value)
        store = api.Store(redis_connection_pool, redis_connection_pool, 6)
        value = store.cache_get(test_key)
        self.assertEqual(value, test_value)
        self.assertEqual(redis_connection_pool.get_counter, 4)

    def test_cache_get_reconnect_timeout(self):
        test_key = "test_key"
        test_value = "test_value"
        redis_connection_pool = RedisConnectionPoolMock(
            get_errors_count=4,
            get_timeout_err=True
        )
        redis_connection_pool.set(test_key, test_value)
        store = api.Store(redis_connection_pool, redis_connection_pool, 6)
        value = store.cache_get(test_key)
        self.assertIsNone(value)
        self.assertEqual(redis_connection_pool.get_counter, 1)

    def test_cache_get_max_retries_limit_exceeded(self):
        test_key = "test_key"
        test_value = "test_value"
        redis_connection_pool = RedisConnectionPoolMock(get_errors_count=5)
        redis_connection_pool.set(test_key, test_value)
        store = api.Store(redis_connection_pool, redis_connection_pool, 3)
        value = store.cache_get(test_key)
        self.assertIsNone(value)
        self.assertEqual(redis_connection_pool.get_counter, 3)

    def test_cache_get_max_retries_limit_exceeded_timeout(self):
        test_key = "test_key"
        test_value = "test_value"
        redis_connection_pool = RedisConnectionPoolMock(
            get_errors_count=5,
            get_timeout_err=True
        )
        redis_connection_pool.set(test_key, test_value)
        store = api.Store(redis_connection_pool, redis_connection_pool, 3)
        value = store.cache_get(test_key)
        self.assertIsNone(value)
        self.assertEqual(redis_connection_pool.get_counter, 1)

    def test_cache_set_successfully(self):
        test_key = "test_key"
        test_value = "test_value"
        redis_connection_pool = RedisConnectionPoolMock(set_errors_count=4)
        store = api.Store(redis_connection_pool, redis_connection_pool, 5)
        store.cache_set(test_key, test_value, 60*60)
        value = store.cache_get(test_key)
        self.assertEqual(value, test_value)
        self.assertEqual(redis_connection_pool.set_counter, 4)

    def test_cache_set_timeout(self):
        test_key = "test_key"
        test_value = "test_value"
        redis_connection_pool = RedisConnectionPoolMock(
            set_errors_count=4,
            set_timeout_err=True
        )
        store = api.Store(redis_connection_pool, redis_connection_pool, 5)
        store.cache_set(test_key, test_value, 60*60)
        value = store.cache_get(test_key)
        self.assertIsNone(value)
        self.assertEqual(redis_connection_pool.set_counter, 1)

    def test_cache_set_unsuccessfully(self):
        test_key = "test_key"
        test_value = "test_value"
        redis_connection_pool = RedisConnectionPoolMock(set_errors_count=4)
        store = api.Store(redis_connection_pool, redis_connection_pool, 2)
        store.cache_set(test_key, test_value, 60*60)
        value = store.cache_get(test_key)
        self.assertIsNone(value)
        self.assertEqual(redis_connection_pool.set_counter, 2)

    def test_cache_set_max_retries_limit_exceeded_timeout(self):
        test_key = "test_key"
        test_value = "test_value"
        redis_connection_pool = RedisConnectionPoolMock(
            set_errors_count=4,
            set_timeout_err=True
        )
        store = api.Store(redis_connection_pool, redis_connection_pool, 2)
        store.cache_set(test_key, test_value, 60*60)
        value = store.cache_get(test_key)
        self.assertIsNone(value)
        self.assertEqual(redis_connection_pool.set_counter, 1)

    def test_get_return_value_after_reconnect(self):
        test_key = "test_key"
        test_value = "test_value"
        redis_connection_pool = RedisConnectionPoolMock(get_errors_count=4)
        redis_connection_pool.set(test_key, test_value)
        store = api.Store(redis_connection_pool, redis_connection_pool, 6)
        value = store.get(test_key)
        self.assertEqual(value, test_value)
        self.assertEqual(redis_connection_pool.get_counter, 4)

    def test_get_max_retries_limit_exceeded(self):
        test_key = "test_key"
        test_value = "test_value"
        redis_connection_pool = RedisConnectionPoolMock(get_errors_count=5)
        redis_connection_pool.set(test_key, test_value)
        store = api.Store(redis_connection_pool, redis_connection_pool, 3)

        with self.assertRaises(ConnectionError):
            store.get(test_key)

        self.assertEqual(redis_connection_pool.get_counter, 3)

    def test_get_return_value_after_reconnect_timeout(self):
        test_key = "test_key"
        test_value = "test_value"
        redis_connection_pool = RedisConnectionPoolMock(
            get_errors_count=4,
            get_timeout_err=True
        )
        redis_connection_pool.set(test_key, test_value)
        store = api.Store(redis_connection_pool, redis_connection_pool, 6)
        value = store.get(test_key)
        self.assertEqual(value, test_value)
        self.assertEqual(redis_connection_pool.get_counter, 4)

    def test_get_max_retries_limit_exceeded_timeout(self):
        test_key = "test_key"
        test_value = "test_value"
        redis_connection_pool = RedisConnectionPoolMock(
            get_errors_count=5,
            get_timeout_err=True
        )
        redis_connection_pool.set(test_key, test_value)
        store = api.Store(redis_connection_pool, redis_connection_pool, 3)

        with self.assertRaises(TimeoutError):
            store.get(test_key)

        self.assertEqual(redis_connection_pool.get_counter, 3)


class BaseHandlerTest(unittest.TestCase):
    def setUp(self):
        self.context = {}
        self.headers = {}
        self.redis_connection_pool = RedisConnectionPoolMock()
        self.store = api.Store(
            self.redis_connection_pool,
            self.redis_connection_pool,
            5
        )

    def get_response(self, request):
        data = {"body": request, "headers": self.headers}
        return api.method_handler(data, self.context, self.store)

    def set_correct_token(self, request):
        if request.get("login") == api.ADMIN_LOGIN:
            key = datetime.datetime.now().strftime("%Y%m%d%H") + api.ADMIN_SALT
            digest = hashlib.sha512(key.encode("utf-8")).hexdigest()
        else:
            key = "".join([
                request.get("account", ""),
                request.get("login", ""),
                api.SALT
            ])
            digest = hashlib.sha512(key.encode("utf-8")).hexdigest()

        request["token"] = digest


class TestSuite(BaseHandlerTest):
    def test_empty_request(self):
        _, code = self.get_response({})
        self.assertEqual(api.INVALID_REQUEST, code)

    @cases([
        {"account": "horns&hoofs", "login": "h&f", "method": "online_score",
         "token": "", "arguments": {}},
        {"account": "horns&hoofs", "login": "h&f", "method": "online_score",
         "token": "badtoken", "arguments": {}},
        {"account": "horns&hoofs", "login": "h&f",
         "method": "clients_interests", "token": "", "arguments": {}},
        {"account": "horns&hoofs", "login": "h&f",
         "method": "clients_interests", "token": "badtoken", "arguments": {}},
        {"account": "horns&hoofs", "login": "admin", "method": "online_score",
         "token": "", "arguments": {}},
        {"account": "horns&hoofs", "login": "admin", "method": "online_score",
         "token": "badtoken", "arguments": {}},
        {"account": "horns&hoofs", "login": "admin",
         "method": "clients_interests", "token": "", "arguments": {}},
        {"account": "horns&hoofs", "login": "admin",
         "method": "clients_interests", "token": "badtoken", "arguments": {}},
    ])
    def test_forbidden_auth(self, request):
        _, code = self.get_response(request)
        self.assertEqual(api.FORBIDDEN, code)


class TestOnlineScoreHandler(BaseHandlerTest):
    def test_correct_all_fields(self):
        request = {
            "account": "horns&hoofs",
            "login": "h&f",
            "method": "online_score",
            "token": "55cc9ce545bcd144300fe9efc28e65d415b923ebb6be1e19d2750a2c"
                     "03e80dd209a27954dca045e5bb12418e7d89b6d718a9e35af34e14e1"
                     "d5bcd5a08f21fc95",
            "arguments": {
                "phone": "79175002040",
                "email": "john@gmail.com",
                "first_name": "John",
                "last_name": "Smith",
                "birthday": "01.01.1990",
                "gender": 1
            }
        }

        response, code = self.get_response(request)
        self.assertEqual(api.OK, code)
        self.assertEqual(
            set(self.context.get("has")),
            {"phone", "email", "first_name", "last_name", "birthday", "gender"}
        )
        self.assertAlmostEqual(response.get("score"), 5.0)

    def test_correct_without_last_name(self):
        request = {
            "account": "horns&hoofs",
            "login": "h&f",
            "method": "online_score",
            "token": "55cc9ce545bcd144300fe9efc28e65d415b923ebb6be1e19d2750a2c"
                     "03e80dd209a27954dca045e5bb12418e7d89b6d718a9e35af34e14e1"
                     "d5bcd5a08f21fc95",
            "arguments": {
                "phone": "79175002040",
                "email": "john@gmail.com",
                "first_name": "John",
                "birthday": "01.01.1990",
                "gender": 1
            }
        }

        response, code = self.get_response(request)
        self.assertEqual(api.OK, code)
        self.assertEqual(
            set(self.context.get("has")),
            {"phone", "email", "first_name", "birthday", "gender"}
        )
        self.assertAlmostEqual(response.get("score"), 4.5)

    def test_correct_birthday_and_gender(self):
        request = {
            "account": "horns&hoofs",
            "login": "h&f",
            "method": "online_score",
            "token": "55cc9ce545bcd144300fe9efc28e65d415b923ebb6be1e19d2750a2c"
                     "03e80dd209a27954dca045e5bb12418e7d89b6d718a9e35af34e14e1"
                     "d5bcd5a08f21fc95",
            "arguments": {
                "birthday": "01.01.1990",
                "gender": 1
            }
        }

        response, code = self.get_response(request)
        self.assertEqual(api.OK, code)
        self.assertEqual(
            set(self.context.get("has")),
            {"birthday", "gender"}
        )
        self.assertAlmostEqual(response.get("score"), 1.5)

    def test_invalid_birthday(self):
        request = {
            "account": "horns&hoofs",
            "login": "h&f",
            "method": "online_score",
            "token": "55cc9ce545bcd144300fe9efc28e65d415b923ebb6be1e19d2750a2c"
                     "03e80dd209a27954dca045e5bb12418e7d89b6d718a9e35af34e14e1"
                     "d5bcd5a08f21fc95",
            "arguments": {
                "birthday": "01.99.1990",
                "gender": 1
            }
        }

        response, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code)

        self.assertTrue(
            "Invalid format of date" in response
        )

    def test_admin_correct_birthday_and_gender(self):
        key = datetime.datetime.now().strftime("%Y%m%d%H") + api.ADMIN_SALT
        digest = hashlib.sha512(key.encode("utf-8")).hexdigest()
        request = {
            "account": "horns&hoofs",
            "login": "admin",
            "method": "online_score",
            "token": digest,
            "arguments": {
                "birthday": "01.01.1990",
                "gender": 1
            }
        }

        response, code = self.get_response(request)
        self.assertEqual(api.OK, code)
        self.assertEqual(
            set(self.context.get("has")),
            {"birthday", "gender"}
        )
        self.assertEqual(response.get("score"), 42)

    @cases([
        {"phone": "79175002040", "email": "john@gmail.com", "score": 3.0},
        {"phone": 79175002040, "email": "john@gmail.com", "gender": api.FEMALE,
         "birthday": "01.01.2018", "score": 4.5},
        {"first_name": "John", "last_name": "Smith", "gender": api.FEMALE,
         "birthday": "01.01.2018", "score": 2.0},
        {"phone": "79175002040", "email": "john@gmail.com",
         "first_name": "John", "last_name": "Smith", "score": 3.5},
        {"gender": api.MALE, "birthday": "01.01.2018", "score": 1.5},
        {"first_name": "John", "last_name": "Smith", "score": 0.5},
        {"phone": 79175002040, "email": "john@gmail.com", "first_name": "John",
         "last_name": "Smith", "gender": api.MALE, "birthday": "01.01.2018",
         "score": 5.0},
    ])
    def test_correct_score(self, data):
        self.redis_connection_pool.reset()
        request = {
            "account": "horns&hoofs",
            "login": "h&f",
            "method": "online_score",
            "arguments": data
        }
        self.set_correct_token(request)

        response, code = self.get_response(request)
        got_score = response.get("score")
        want_score = data.pop("score")

        self.assertEqual(api.OK, code)
        self.assertEqual(set(self.context["has"]), set(data.keys()))
        self.assertAlmostEqual(got_score, want_score)


class TestClientInterestsHandler(BaseHandlerTest):
    def test_admin_correct(self):
        key = datetime.datetime.now().strftime("%Y%m%d%H") + api.ADMIN_SALT
        digest = hashlib.sha512(key.encode("utf-8")).hexdigest()
        request = {
            "account": "horns&hoofs",
            "login": "admin",
            "method": "clients_interests",
            "token": digest,
            "arguments": {"client_ids": [1, 2, 3, 4], "date": "20.07.2017"}
        }

        _, code = self.get_response(request)
        self.assertEqual(api.OK, code)
        self.assertEqual(self.context.get("nclients"), 4)

    def test_admin_invalid_date_format(self):
        key = datetime.datetime.now().strftime("%Y%m%d%H") + api.ADMIN_SALT
        digest = hashlib.sha512(key.encode("utf-8")).hexdigest()
        request = {
            "account": "horns&hoofs",
            "login": "admin",
            "method": "clients_interests",
            "token": digest,
            "arguments": {"client_ids": [1, 2, 3, 4], "date": "20.99.2017"}
        }

        response, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code)
        self.assertTrue("Invalid format of date" in response)

    def test_admin_invalid_date_format_and_client_ids_type(self):
        key = datetime.datetime.now().strftime("%Y%m%d%H") + api.ADMIN_SALT
        digest = hashlib.sha512(key.encode("utf-8")).hexdigest()
        request = {
            "account": "horns&hoofs",
            "login": "admin",
            "method": "clients_interests",
            "token": digest,
            "arguments": {"client_ids": {1, 2, 3, 4}, "date": "20.99.2017"}
        }

        response, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code)
        self.assertTrue("This field must be array of integers" in response)
        self.assertTrue("Invalid format of date" in response)

    def test_admin_invalid_client_ids_type(self):
        key = datetime.datetime.now().strftime("%Y%m%d%H") + api.ADMIN_SALT
        digest = hashlib.sha512(key.encode("utf-8")).hexdigest()
        request = {
            "account": "horns&hoofs",
            "login": "admin",
            "method": "clients_interests",
            "token": digest,
            "arguments": {"client_ids": {1, 2, 3, 4}, "date": "20.05.2017"}
        }

        response, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code)
        self.assertTrue("This field must be array of integers" in response)
        self.assertFalse("Invalid format of date" in response)

    def test_admin_invalid_empty_client_ids(self):
        key = datetime.datetime.now().strftime("%Y%m%d%H") + api.ADMIN_SALT
        digest = hashlib.sha512(key.encode("utf-8")).hexdigest()
        request = {
            "account": "horns&hoofs",
            "login": "admin",
            "method": "clients_interests",
            "token": digest,
            "arguments": {"client_ids": [], "date": "20.05.2017"}
        }

        response, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code)
        self.assertTrue("This field must be non empty" in response)

    @cases([
        {"client_ids": [1, 2, 3, 4, 5], "date": "01.01.2018"},
        {"client_ids": [1]},
        {"client_ids": [1, 2, 3]},
    ])
    def test_correct_interests(self, data):
        request = {
            "account": "horns&hoofs",
            "login": "h&f",
            "method": "clients_interests",
            "arguments": data
        }
        test_interests_json = '["travel", "music", "pets", "tv"]'
        test_interests = json.loads('["travel", "music", "pets", "tv"]')
        self.set_correct_token(request)

        client_ids = data.get("client_ids", [])

        for client_id in client_ids:
            key = "i:{0}".format(client_id)
            self.redis_connection_pool.set(key, test_interests_json)

        response, code = self.get_response(request)
        self.assertEqual(api.OK, code)
        self.assertEqual(self.context.get("nclients"), len(client_ids))

        for client_id in client_ids:
            client_id_str = str(client_id)
            interests = response.get(client_id_str)
            self.assertEqual(interests, test_interests)


class TestValidators(unittest.TestCase):
    @cases(["12", 3.5, "asd", {}, None, [], tuple(), set(), int])
    def test_validate_integer_invalid_values(self, value):
        with self.assertRaises(api.ValidationError):
            api.validate_integer(value)

    @cases([10, -10, 0, 1, -1])
    def test_validate_integer_correct_values(self, value):
        try:
            api.validate_integer(value)
        except BaseException as e:
            message = "api.validate_digit(value) function " \
                      "raises {0}{1}".format(type(e).__name__, e)
            self.fail(message)

    @cases([123, None, [], {}, set(), tuple(), str, 3.5])
    def test_validate_string_invalid_values(self, value):
        with self.assertRaises(api.ValidationError):
            api.validate_string(value)

    @cases(["", "123", "asd"])
    def test_validate_string_correct_values(self, value):
        try:
            api.validate_string(value)
        except BaseException as e:
            message = "api.validate_string(value) function " \
                      "raises {0}{1}".format(type(e).__name__, e)
            self.fail(message)

    @cases([123, None, {1, 2}, tuple(), dict, "", [], 3.4])
    def test_validate_dict_invalid_values(self, value):
        with self.assertRaises(api.ValidationError):
            api.validate_dict(value)

    @cases([{}, {"a": 1}, defaultdict(int), OrderedDict()])
    def test_validate_dict_correct_values(self, value):
        try:
            api.validate_dict(value)
        except BaseException as e:
            message = "api.validate_dict(value) function " \
                      "raises {0}{1}".format(type(e).__name__, e)
            self.fail(message)

    @cases([123, -71234567890, -7123456789, None, [], "12345678900",
            "-7123456789", "", tuple(), dict])
    def test_validate_phone_invalid_values(self, value):
        with self.assertRaises(api.ValidationError):
            api.validate_phone(value)

    @cases([71234567890, "71234567890"])
    def test_validate_phone_correct_values(self, value):
        try:
            api.validate_phone(value)
        except BaseException as e:
            message = "api.validate_phone(value) function " \
                      "raises {0}{1}".format(type(e).__name__, e)
            self.fail(message)

    @cases([123, "asd.com", "asd@", None, {}, "@", str, "asd@"])
    def test_validate_email_invalid_values(self, value):
        with self.assertRaises(api.ValidationError):
            api.validate_email(value)

    @cases(["test@test.com", "test.test@test.test.com"])
    def test_validate_email_correct_values(self, value):
        try:
            api.validate_email(value)
        except BaseException as e:
            message = "api.validate_email(value) function " \
                      "raises {0}{1}".format(type(e).__name__, e)
            self.fail(message)

    @cases([123, "", None, {}, "@", "01-01-1999", "01.01.1940", "99.01.1999",
            "01.99.1999", "01.99.2999"])
    def test_validate_birthday_invalid_values(self, value):
        with self.assertRaises(api.ValidationError):
            api.validate_birthday(value)

    @cases(["01.01.1990", "23.11.2015"])
    def test_validate_birthday_correct_values(self, value):
        try:
            api.validate_birthday(value)
        except BaseException as e:
            message = "api.validate_birthday(value) function " \
                      "raises {0}{1}".format(type(e).__name__, e)
            self.fail(message)

    @cases([123, -1, 1.0, "", None, {}, int, [], tuple(), set(), 3])
    def test_validate_gender_invalid_values(self, value):
        with self.assertRaises(api.ValidationError):
            api.validate_gender(value)

    @cases([0, 1, 2])
    def test_validate_gender_correct_values(self, value):
        try:
            api.validate_gender(value)
        except BaseException as e:
            message = "api.validate_gender(value) function " \
                      "raises {0}{1}".format(type(e).__name__, e)
            self.fail(message)

    @cases([123, "", None, {1: 1, 2: 2}, ["1", "2", "3"], [1, 2, "3"],
            [1, 2, [3, 4]], {1, 2, 3, 4}])
    def test_validate_int_array_invalid_values(self, value):
        with self.assertRaises(api.ValidationError):
            api.validate_int_array(value)

    @cases([[1, 2, 3, 4], (1, 2, 3, 4)])
    def test_validate_int_array_correct_values(self, value):
        try:
            api.validate_int_array(value)
        except BaseException as e:
            message = "api.validate_int_array(value) function " \
                      "raises {0}{1}".format(type(e).__name__, e)
            self.fail(message)

    @cases([123, "", None, {}, "01-01-1999", "99.01.1999", "01.99.1999",
            "01.99.2999"])
    def test_validate_date_invalid_values(self, value):
        with self.assertRaises(api.ValidationError):
            api.validate_date(value)

    @cases(["01.01.1990", "23.11.2015"])
    def test_validate_date_correct_values(self, value):
        try:
            api.validate_date(value)
        except BaseException as e:
            message = "api.validate_date(value) function " \
                      "raises {0}{1}".format(type(e).__name__, e)
            self.fail(message)


class TestClientsInterestRequest(unittest.TestCase):
    def test_correct_values(self):
        data = {
            "client_ids": [1, 2, 3, 4],
            "date": "01.01.1990"
        }
        request_validator = api.ClientsInterestsRequest(data)
        self.assertTrue(request_validator.is_valid())

    def test_invalid_string_client_id(self):
        data = {
            "client_ids": ["1", 2, 3, 4],
            "date": "01.01.1990"
        }
        request_validator = api.ClientsInterestsRequest(data)
        self.assertFalse(request_validator.is_valid())

    def test_invalid_date_month(self):
        data = {
            "client_ids": [1, 2, 3, 4],
            "date": "01.99.1990"
        }
        request_validator = api.ClientsInterestsRequest(data)
        self.assertFalse(request_validator.is_valid())

    def test_invalid_date_format(self):
        data = {
            "client_ids": [1, 2, 3, 4],
            "date": "01-01-1990"
        }
        request_validator = api.ClientsInterestsRequest(data)
        self.assertFalse(request_validator.is_valid())

    def test_correct_without_date(self):
        data = {
            "client_ids": [1, 2, 3, 4]
        }
        request_validator = api.ClientsInterestsRequest(data)
        self.assertTrue(request_validator.is_valid())

    def test_invalid_without_client_ids(self):
        data = {
            "date": "01.01.1990"
        }
        request_validator = api.ClientsInterestsRequest(data)
        self.assertFalse(request_validator.is_valid())

    def test_invalid_client_ids_type_set(self):
        data = {
            "client_ids": {1, 2, 3, 4},
            "date": "01.01.1990"
        }
        request_validator = api.ClientsInterestsRequest(data)
        self.assertFalse(request_validator.is_valid())

    def test_correct_client_ids_type_tuple(self):
        data = {
            "client_ids": (1, 2, 3, 4),
            "date": "01.01.1990"
        }
        request_validator = api.ClientsInterestsRequest(data)
        self.assertTrue(request_validator.is_valid())
        self.assertEqual(request_validator.client_ids, data.get("client_ids"))
        self.assertEqual(request_validator.date, data.get("date"))
        self.assertEqual(len(request_validator.client_ids), 4)
        self.assertEqual(
            request_validator.non_empty_fields(),
            ["client_ids", "date"]
        )


class TestOnlineScoreRequest(unittest.TestCase):
    def test_correct_all_fields(self):
        data = {
            "first_name": "John",
            "last_name": "Smith",
            "email": "john@gmail.com",
            "phone": "71234567890",
            "birthday": "06.01.1990",
            "gender": api.MALE
        }
        request_validator = api.OnlineScoreRequest(data)
        self.assertTrue(request_validator.is_valid())
        self.assertEqual(request_validator.first_name, data.get("first_name"))
        self.assertEqual(request_validator.last_name, data.get("last_name"))
        self.assertEqual(request_validator.email, data.get("email"))
        self.assertEqual(request_validator.phone, data.get("phone"))
        self.assertEqual(request_validator.birthday, data.get("birthday"))
        self.assertEqual(request_validator.gender, data.get("gender"))

    def test_correct_first_name_and_last_name(self):
        data = {
            "first_name": "John",
            "last_name": "Smith",
        }
        request_validator = api.OnlineScoreRequest(data)
        self.assertTrue(request_validator.is_valid())
        self.assertEqual(
            request_validator.non_empty_fields(),
            ["first_name", "last_name"]
        )

    def test_correct_email_and_phone(self):
        data = {
            "email": "john@gmail.com",
            "phone": "71234567890",
        }
        request_validator = api.OnlineScoreRequest(data)
        self.assertTrue(request_validator.is_valid())
        self.assertEqual(
            request_validator.non_empty_fields(),
            ["email", "phone"]
        )

    def test_correct_birthday_and_gender(self):
        data = {
            "birthday": "06.01.1990",
            "gender": api.MALE
        }
        request_validator = api.OnlineScoreRequest(data)
        self.assertTrue(request_validator.is_valid())
        self.assertEqual(
            request_validator.non_empty_fields(),
            ["birthday", "gender"]
        )

    def test_invalid_birthday(self):
        data = {
            "first_name": "John",
            "last_name": "Smith",
            "email": "john@gmail.com",
            "phone": "71234567890",
            "birthday": "06.01.1580",
            "gender": api.MALE
        }
        request_validator = api.OnlineScoreRequest(data)
        self.assertFalse(request_validator.is_valid())

    def test_invalid_email(self):
        data = {
            "first_name": "John",
            "last_name": "Smith",
            "email": "johngmail.com",
            "phone": "71234567890",
            "birthday": "06.01.1990",
            "gender": api.MALE
        }
        request_validator = api.OnlineScoreRequest(data)
        self.assertFalse(request_validator.is_valid())

    def test_invalid_field_pairs(self):
        data = {
            "first_name": "John",
            "phone": "71234567890",
            "gender": api.MALE
        }
        request_validator = api.OnlineScoreRequest(data)
        self.assertFalse(request_validator.is_valid())


class TestMethodRequest(unittest.TestCase):
    def test_correct_all_fields(self):
        data = {
            "account": "horns&hoofs",
            "login": "horns&hoofs",
            "token": "admin123",
            "arguments": {},
            "method": "some"
        }
        request_validator = api.MethodRequest(data)
        self.assertTrue(request_validator.is_valid())
        self.assertEqual(request_validator.account, data.get("account"))
        self.assertEqual(request_validator.login, data.get("login"))
        self.assertEqual(request_validator.token, data.get("token"))
        self.assertEqual(request_validator.arguments, data.get("arguments"))
        self.assertEqual(request_validator.method, data.get("method"))

    def test_correct_without_account(self):
        data = {
            "login": "horns&hoofs",
            "token": "admin123",
            "arguments": {},
            "method": "some"
        }
        request_validator = api.MethodRequest(data)
        self.assertTrue(request_validator.is_valid())
        self.assertEqual(
            request_validator.non_empty_fields(),
            ["login", "token", "method"]
        )

    def test_invalid_without_method(self):
        data = {
            "account": "horns&hoofs",
            "login": "horns&hoofs",
            "token": "admin123",
            "arguments": {},
        }
        request_validator = api.MethodRequest(data)
        self.assertFalse(request_validator.is_valid())

    def test_invalid_login(self):
        data = {
            "account": "horns&hoofs",
            "login": 123,
            "token": "admin123",
            "arguments": {},
            "method": "some"
        }
        request_validator = api.MethodRequest(data)
        self.assertFalse(request_validator.is_valid())

    def test_invalid_account(self):
        data = {
            "account": {"a": 12},
            "login": "horns&hoofs",
            "token": "admin123",
            "arguments": {},
            "method": "some"
        }
        request_validator = api.MethodRequest(data)
        self.assertFalse(request_validator.is_valid())


if __name__ == "__main__":
    unittest.main()
