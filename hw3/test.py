import unittest
import datetime
import hashlib

import api

from collections import defaultdict, OrderedDict


class BaseHandlerTest(unittest.TestCase):
    def setUp(self):
        self.context = {}
        self.headers = {}
        self.store = None

    def get_response(self, request):
        data = {"body": request, "headers": self.headers}
        return api.method_handler(data, self.context, self.store)


class TestSuite(BaseHandlerTest):
    def test_empty_request(self):
        _, code = self.get_response({})
        self.assertEqual(api.INVALID_REQUEST, code)


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


class TestClientInterestsHandler(BaseHandlerTest):
    def test_admin_correct(self):
        key = datetime.datetime.now().strftime("%Y%m%d%H") + api.ADMIN_SALT
        digest = hashlib.sha512(key.encode("utf-8")).hexdigest()
        request = {
            "account": "horns&hoofs", "login": "admin",
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
            "account": "horns&hoofs", "login": "admin",
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
            "account": "horns&hoofs", "login": "admin",
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
            "account": "horns&hoofs", "login": "admin",
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
            "account": "horns&hoofs", "login": "admin",
            "method": "clients_interests",
            "token": digest,
            "arguments": {"client_ids": [], "date": "20.05.2017"}
        }

        response, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code)
        self.assertTrue("This field must be non empty" in response)


class TestValidators(unittest.TestCase):
    def test_validate_integer_invalid_values(self):
        with self.assertRaises(api.ValidationError):
            api.validate_integer("12")
        with self.assertRaises(api.ValidationError):
            api.validate_integer(3.5)
        with self.assertRaises(api.ValidationError):
            api.validate_integer("asd")
        with self.assertRaises(api.ValidationError):
            api.validate_integer({})
        with self.assertRaises(api.ValidationError):
            api.validate_integer(None)

    def test_validate_integer_correct_values(self):
        try:
            api.validate_integer(10)
            api.validate_integer(-10)
            api.validate_integer(0)
        except BaseException as e:
            message = "api.validate_digit(value) function " \
                      "raises {0}{1}".format(type(e).__name__, e)
            self.fail(message)

    def test_validate_string_invalid_values(self):
        with self.assertRaises(api.ValidationError):
            api.validate_string(123)
        with self.assertRaises(api.ValidationError):
            api.validate_string(None)
        with self.assertRaises(api.ValidationError):
            api.validate_string({})
        with self.assertRaises(api.ValidationError):
            api.validate_string(str)

    def test_validate_string_correct_values(self):
        try:
            api.validate_string("")
            api.validate_string("asd")
            api.validate_string("123")
        except BaseException as e:
            message = "api.validate_string(value) function " \
                      "raises {0}{1}".format(type(e).__name__, e)
            self.fail(message)

    def test_validate_dict_invalid_values(self):
        with self.assertRaises(api.ValidationError):
            api.validate_dict(123)
        with self.assertRaises(api.ValidationError):
            api.validate_dict(None)
        with self.assertRaises(api.ValidationError):
            api.validate_dict([])
        with self.assertRaises(api.ValidationError):
            api.validate_dict("")
        with self.assertRaises(api.ValidationError):
            api.validate_dict(tuple())
        with self.assertRaises(api.ValidationError):
            api.validate_dict(dict)

    def test_validate_dict_correct_values(self):
        try:
            api.validate_dict({})
            api.validate_dict({"a": 1})
            api.validate_dict(defaultdict(int))
            api.validate_dict(OrderedDict())
        except BaseException as e:
            message = "api.validate_dict(value) function " \
                      "raises {0}{1}".format(type(e).__name__, e)
            self.fail(message)

    def test_validate_phone_invalid_values(self):
        with self.assertRaises(api.ValidationError):
            api.validate_phone(123)
        with self.assertRaises(api.ValidationError):
            api.validate_phone(-71234567890)
        with self.assertRaises(api.ValidationError):
            api.validate_phone(-7123456789)
        with self.assertRaises(api.ValidationError):
            api.validate_phone(None)
        with self.assertRaises(api.ValidationError):
            api.validate_phone([])
        with self.assertRaises(api.ValidationError):
            api.validate_phone("12345678900")
        with self.assertRaises(api.ValidationError):
            api.validate_phone("-7123456789")
        with self.assertRaises(api.ValidationError):
            api.validate_phone("")
        with self.assertRaises(api.ValidationError):
            api.validate_phone(tuple())
        with self.assertRaises(api.ValidationError):
            api.validate_phone(dict)

    def test_validate_phone_correct_values(self):
        try:
            api.validate_phone(71234567890)
            api.validate_phone("71234567890")
        except BaseException as e:
            message = "api.validate_phone(value) function " \
                      "raises {0}{1}".format(type(e).__name__, e)
            self.fail(message)

    def test_validate_email_invalid_values(self):
        with self.assertRaises(api.ValidationError):
            api.validate_email(123)
        with self.assertRaises(api.ValidationError):
            api.validate_email("asd.com")
        with self.assertRaises(api.ValidationError):
            api.validate_email("asd@")
        with self.assertRaises(api.ValidationError):
            api.validate_email(None)
        with self.assertRaises(api.ValidationError):
            api.validate_email({})
        with self.assertRaises(api.ValidationError):
            api.validate_email("@")
        with self.assertRaises(api.ValidationError):
            api.validate_email(str)
        with self.assertRaises(api.ValidationError):
            api.validate_email("asd@")

    def test_validate_email_correct_values(self):
        try:
            api.validate_email("test@test.com")
            api.validate_email("test.test@test.test.com")
        except BaseException as e:
            message = "api.validate_email(value) function " \
                      "raises {0}{1}".format(type(e).__name__, e)
            self.fail(message)

    def test_validate_birthday_invalid_values(self):
        with self.assertRaises(api.ValidationError):
            api.validate_birthday(123)
        with self.assertRaises(api.ValidationError):
            api.validate_birthday("")
        with self.assertRaises(api.ValidationError):
            api.validate_birthday(None)
        with self.assertRaises(api.ValidationError):
            api.validate_birthday({})
        with self.assertRaises(api.ValidationError):
            api.validate_birthday("@")
        with self.assertRaises(api.ValidationError):
            api.validate_birthday("01-01-1999")
        with self.assertRaises(api.ValidationError):
            api.validate_birthday("01.01.1940")
        with self.assertRaises(api.ValidationError):
            api.validate_birthday("99.01.1999")
        with self.assertRaises(api.ValidationError):
            api.validate_birthday("01.99.1999")
        with self.assertRaises(api.ValidationError):
            api.validate_birthday("01.99.2999")

    def test_validate_birthday_correct_values(self):
        try:
            api.validate_birthday("01.01.1990")
            api.validate_birthday("23.11.2015")
        except BaseException as e:
            message = "api.validate_birthday(value) function " \
                      "raises {0}{1}".format(type(e).__name__, e)
            self.fail(message)

    def test_validate_gender_invalid_values(self):
        with self.assertRaises(api.ValidationError):
            api.validate_gender(123)
        with self.assertRaises(api.ValidationError):
            api.validate_gender(-1)
        with self.assertRaises(api.ValidationError):
            api.validate_gender(1.0)
        with self.assertRaises(api.ValidationError):
            api.validate_gender("")
        with self.assertRaises(api.ValidationError):
            api.validate_gender(None)
        with self.assertRaises(api.ValidationError):
            api.validate_gender({})

    def test_validate_gender_correct_values(self):
        try:
            api.validate_gender(0)
            api.validate_gender(1)
            api.validate_gender(2)
        except BaseException as e:
            message = "api.validate_gender(value) function " \
                      "raises {0}{1}".format(type(e).__name__, e)
            self.fail(message)

    def test_validate_int_array_invalid_values(self):
        with self.assertRaises(api.ValidationError):
            api.validate_int_array(123)
        with self.assertRaises(api.ValidationError):
            api.validate_int_array("")
        with self.assertRaises(api.ValidationError):
            api.validate_int_array(None)
        with self.assertRaises(api.ValidationError):
            api.validate_int_array({1: 1, 2: 2})
        with self.assertRaises(api.ValidationError):
            api.validate_int_array(["1", "2", "3"])
        with self.assertRaises(api.ValidationError):
            api.validate_int_array([1, 2, "3"])
        with self.assertRaises(api.ValidationError):
            api.validate_int_array([1, 2, [3, 4]])
        with self.assertRaises(api.ValidationError):
            api.validate_int_array({1, 2, 3, 4})

    def test_validate_int_array_correct_values(self):
        try:
            api.validate_int_array([1, 2, 3, 4])
            api.validate_int_array((1, 2, 3, 4))
        except BaseException as e:
            message = "api.validate_int_array(value) function " \
                      "raises {0}{1}".format(type(e).__name__, e)
            self.fail(message)

    def test_validate_date_invalid_values(self):
        with self.assertRaises(api.ValidationError):
            api.validate_date(123)
        with self.assertRaises(api.ValidationError):
            api.validate_date("")
        with self.assertRaises(api.ValidationError):
            api.validate_date(None)
        with self.assertRaises(api.ValidationError):
            api.validate_date({})
        with self.assertRaises(api.ValidationError):
            api.validate_date("01-01-1999")
        with self.assertRaises(api.ValidationError):
            api.validate_date("99.01.1999")
        with self.assertRaises(api.ValidationError):
            api.validate_date("01.99.1999")
        with self.assertRaises(api.ValidationError):
            api.validate_date("01.99.2999")

    def test_validate_date_correct_values(self):
        try:
            api.validate_date("01.01.1990")
            api.validate_date("23.11.2015")
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
