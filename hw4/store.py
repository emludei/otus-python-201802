
class Store:
    def __init__(self, cache_conn_pool, persistent_conn_pool, max_retries):
        self._redis_cache_pool = cache_conn_pool
        self._redis_persistent_pool = persistent_conn_pool
        self._max_retries = max_retries

    def cache_get(self, key):
        byte_value = None
        retries = 1
        while retries <= self._max_retries:
            try:
                byte_value = self._redis_cache_pool.get(key)
                break
            except (ConnectionError, TimeoutError) as e:
                if isinstance(e, TimeoutError) or retries >= self._max_retries:
                    return

                retries += 1

        try:
            value = byte_value.decode("utf-8")
        except (AttributeError, ValueError):
            return

        try:
            value = float(value)
        except ValueError:
            pass

        return value

    def cache_set(self, key, value, ttl):
        retries = 1
        while retries <= self._max_retries:
            try:
                self._redis_cache_pool.set(key, value, ex=ttl)
                break
            except (ConnectionError, TimeoutError) as e:
                if isinstance(e, TimeoutError) or retries >= self._max_retries:
                    return

                retries += 1

    def get(self, key):
        byte_value = None
        retries = 1
        while retries <= self._max_retries:
            try:
                byte_value = self._redis_persistent_pool.get(key)
                break
            except (ConnectionError, TimeoutError):
                if retries >= self._max_retries:
                    raise

                retries += 1

        try:
            value = byte_value.decode("utf-8")
        except (AttributeError, ValueError):
            return

        return value
