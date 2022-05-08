import datetime
import functools
import hashlib
import unittest

from pip._vendor.pyparsing import basestring

import api
from store import RedisStore


def cases(cases):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args):
            for c in cases:
                new_args = args + (c if isinstance(c, tuple) else (c,))
                f(*new_args)
        return wrapper
    return decorator


class MockCache:
    _has_connect = True

    def __init__(self):
        self._cache = {}

    def get(self, key):
        if not self._has_connect:
            raise ConnectionError('Can\'t connect to Store')
        return self._cache.get(key)

    def set(self, key, value, time=None):
        if not self._has_connect:
            raise ConnectionError('Can\'t connect to Store')
        self._cache.update({key: value})
        return self

    def disable_connection(self):
        self._has_connect = False
        return self


class TestSuite(unittest.TestCase):
    def setUp(self):
        self.context = {}
        self.headers = {}
        self.store = RedisStore(MockCache())

    def get_response(self, request):
        return api.method_handler({"body": request, "headers": self.headers}, self.context, self.store)

    def set_valid_auth(self, request):
        if request.get("login") == api.ADMIN_LOGIN:
            salt = datetime.datetime.now().strftime("%Y%m%d%H") + api.ADMIN_SALT
            request["token"] = hashlib.sha512(salt.encode('utf-8')).hexdigest()
        else:
            msg = request.get("account", "") + request.get("login", "") + api.SALT
            request["token"] = hashlib.sha512(msg.encode('utf-8')).hexdigest()

    def test_empty_request(self):
        _, code = self.get_response({})
        self.assertEqual(api.INVALID_REQUEST, code)

    @cases([
        {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "token": "", "arguments": {}},
        {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "token": "sdd", "arguments": {}},
        {"account": "horns&hoofs", "login": "admin", "method": "online_score", "token": "", "arguments": {}},
    ])
    def test_bad_auth(self, request):
        _, code = self.get_response(request)
        self.assertEqual(api.FORBIDDEN, code)

    @cases([
        {"account": "horns&hoofs", "login": "h&f", "method": "online_score"},
        {"account": "horns&hoofs", "login": "h&f", "arguments": {}},
        {"account": "horns&hoofs", "method": "online_score", "arguments": {}},
    ])
    def test_invalid_method_request(self, request):
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code)
        self.assertTrue(len(response))

    @cases([
        {},
        {"phone": "79175002040"},
        {"phone": "89175002040", "email": "stupnikov@otus.ru"},
        {"phone": "79175002040", "email": "stupnikovotus.ru"},
        {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": -1},
        {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": "1"},
        {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": 1, "birthday": "01.01.1890"},
        {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": 1, "birthday": "XXX"},
        {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": 1, "birthday": "01.01.2000", "first_name": 1},
        {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": 1, "birthday": "01.01.2000",
         "first_name": "s", "last_name": 2},
        {"phone": "79175002040", "birthday": "01.01.2000", "first_name": "s"},
        {"email": "stupnikov@otus.ru", "gender": 1, "last_name": 2},
    ])
    def test_invalid_score_request(self, arguments):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code, arguments)
        self.assertTrue(len(response))

    @cases([
        {"phone": "79175002040", "email": "stupnikov@otus.ru"},
        {"phone": 79175002040, "email": "stupnikov@otus.ru"},
        {"gender": 1, "birthday": "01.01.2000", "first_name": "a", "last_name": "b"},
        {"gender": 0, "birthday": "01.01.2000"},
        {"gender": 2, "birthday": "01.01.2000"},
        {"first_name": "a", "last_name": "b"},
        {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": 1, "birthday": "01.01.2000",
         "first_name": "a", "last_name": "b"},
    ])
    def test_ok_score_request(self, arguments):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "arguments": arguments}
        self.set_valid_auth(request)
        code, response = self.get_response(request)
        self.assertEqual(api.OK, code, arguments)
        score = response.get("score")
        self.assertTrue(isinstance(score, (int, float)) and score >= 0, arguments)
        self.assertEqual(sorted(self.context["has"]), sorted(arguments.keys()))


    @cases([
        {"client_ids": [1, 2, 3], "date": datetime.datetime.today().strftime("%d.%m.%Y")},
        {"client_ids": [1, 2], "date": "19.07.2017"},
        {"client_ids": [0]},
    ])
    def test_ok_interests_request(self, arguments):
        for cid in arguments['client_ids']:
            self.store.set('i:%s' % cid, '["cars", "pets"]')

        request = {"account": "horns&hoofs", "login": "h&f", "method": "clients_interests", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.OK, code, arguments)
        self.assertEqual(len(arguments["client_ids"]), len(response))
        self.assertTrue(all(v and isinstance(v, list) and all(isinstance(i, basestring) for i in v)
                            for v in response.values()))
        self.assertEqual(self.context.get("nclients"), len(arguments["client_ids"]))

    @cases([
        {},
        {"date": "20.07.2017"},
        {"client_ids": [], "date": "20.07.2017"},
        {"client_ids": {1: 2}, "date": "20.07.2017"},
        {"client_ids": ["1", "2"], "date": "20.07.2017"},
        {"client_ids": [1, 2], "date": "XXX"},
    ])
    def test_invalid_interests_request(self, arguments):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "clients_interests", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code, arguments)
        self.assertTrue(len(response))

    def test_competitive_requests(self):
        request = {"account": "horns&hoofs"}
        method_request = api.MethodRequest(request)
        another_request = {"account": "another-req"}
        another_method_request = api.MethodRequest(another_request)
        self.assertIsNot(method_request.account, another_method_request.account)


class FieldTests(unittest.TestCase):
    @cases(['abc', '111', '', '0'])
    def test_char_field_is_valid(self, args):
        field = api.CharField()
        self.assert_not_raises(ValueError, field.validate, args)

    @cases([11, 13.5, True])
    def test_char_field_invalid(self, args):
        field = api.CharField()
        with self.assertRaises(ValueError):
            field.validate(args)

    @cases(['test', [], {1, 'asd'}, True, False])
    def test_arguments_field_is_not_valid(self, args):
        field = api.ArgumentsField()
        with self.assertRaises(ValueError):
            field.validate(args)

    @cases(['user@yahoo.com', 'tester@aol.com'])
    def test_email_field_is_valid(self, args):
        field = api.EmailField()
        self.assert_not_raises(ValueError, field.validate, args)

    @cases(['rest', 111])
    def test_email_field_is_not_valid(self, args):
        field = api.EmailField()
        with self.assertRaises(ValueError):
            field.validate(args)

    @cases(['79012345678', 79012345678])
    def test_phone_field_is_valid(self, args):
        field = api.PhoneField()
        self.assert_not_raises(ValueError, field.validate, args)

    @cases(['99012345678', '+89012345678', 89012345678, '8901'])
    def test_phone_field_is_not_valid(self, args):
        field = api.PhoneField()
        with self.assertRaises(ValueError):
            field.validate(args)

    @cases(['11.01.1984', '01.01.2000', '02.03.1901'])
    def test_date_field_is_valid(self, args):
        field = api.DateField()
        self.assert_not_raises(ValueError, field.validate, args)

    @cases([33, '11/01/1984', '12.34.8919'])
    def test_date_field_is_not_valid(self, args):
        field = api.DateField()
        with self.assertRaises(ValueError):
            field.validate(args)

    @cases(['16.09.1984', '12.05.1960'])
    def test_birthday_field_is_valid(self, args):
        field = api.BirthDayField()
        self.assert_not_raises(ValueError, field.validate, args)

    @cases(['01.01.1700', '01.01.1812'])
    def test_birthday_field_is_not_valid(self, args):
        field = api.BirthDayField()
        with self.assertRaises(ValueError):
            field.validate(args)

    @cases([api.UNKNOWN, api.MALE, api.FEMALE])
    def test_gender_field_is_valid(self, args):
        field = api.GenderField()
        self.assert_not_raises(ValueError, field.validate, args)

    @cases([3, '4', 'abc'])
    def test_gender_field_is_not_valid(self, args):
        field = api.GenderField()
        with self.assertRaises(ValueError):
            field.validate(args)

    @cases([[], [1, 2, 3, 4], [0]])
    def test_client_ids_field_is_valid(self, args):
        field = api.ClientIDsField()
        self.assert_not_raises(ValueError, field.validate, args)

    @cases([{1, 2, 3, 4}, [123, 'abc'], [None, True, False]])
    def test_client_ids_field_is_not_valid(self, args):
        field = api.ClientIDsField()
        with self.assertRaises(ValueError):
            field.validate(args)

    def assert_not_raises(self, exception, method, *args):
        try:
            method(*args)
        except exception:
            self.fail(f'Method {method.__name__}() raises an {exception.__name__} exception')


class StoreTestSuite(unittest.TestCase):
    def test_available_store(self):
        store = RedisStore(MockCache())
        store.set('key', 'test')
        store.set('another_key', 'another_test')
        self.assertEqual(store.get('key'), 'test')
        self.assertEqual(store.get('another_key'), 'another_test')

    def test_unavailable_store(self):
        store = RedisStore(MockCache().disable_connection())
        with self.assertRaises(ConnectionError):
            store.set('key', 'test')

    def test_available_cache(self):
        store = RedisStore(MockCache())
        store.cache_set('key', 'test')
        store.cache_set('another_key', 'another_test')
        self.assertEqual(store.cache_get('key'), 'test')
        self.assertEqual(store.cache_get('another_key'), 'another_test')


if __name__ == "__main__":
    unittest.main()
