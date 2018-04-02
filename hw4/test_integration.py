import os
import unittest

import api


class TestIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        redis_host = os.environ["REDIS_HOST"]
        redis_port = os.environ["REDIS_PORT"]

        config = {
            "HOST": redis_host,
            "PORT": redis_port,
            "DB": 0,
            "CONNECT_TIMEOUT": 1,
            "RESPONSE_TIMEOUT": 1,
        }

        cls.redis_connection_pool = api.get_redis_connection_pool(config)

    def test_cache_get_successfully(self):
        self.redis_connection_pool.flushdb()

        test_key = "test_key"
        test_value = "test_value"
        self.redis_connection_pool.set(test_key, test_value)
        store = api.Store(
            self.redis_connection_pool,
            self.redis_connection_pool,
            5
        )
        value = store.cache_get(test_key)
        self.assertEqual(value, test_value)

    def test_cache_set_successfully(self):
        self.redis_connection_pool.flushdb()

        test_key = "test_key"
        test_value = "test_value"
        store = api.Store(
            self.redis_connection_pool,
            self.redis_connection_pool,
            5
        )
        store.cache_set(test_key, test_value, 60*60)
        value = store.cache_get(test_key)
        self.assertEqual(value, test_value)

    def test_get_successfully(self):
        self.redis_connection_pool.flushdb()

        test_key = "test_key"
        test_value = "test_value"
        self.redis_connection_pool.set(test_key, test_value)
        store = api.Store(
            self.redis_connection_pool,
            self.redis_connection_pool,
            5
        )
        value = store.get(test_key)
        self.assertEqual(value, test_value)


if __name__ == "__main__":
    unittest.main()
