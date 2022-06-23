import logging
import time

import redis
from redis import ConnectionError, TimeoutError


def reconnect(func):
    def wrapper(self, *args):
        try:
            return func(self, *args)
        except (ConnectionError, TimeoutError):
            self.connect()
            return func(self, *args)
    return wrapper


class RedisStore:
    def __init__(self,
                 host='127.0.0.1',
                 port=6379,
                 timeout=3,
                 connect_timeout=10,
                 max_retries=3):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self.max_retries = max_retries
        self.redis = None
        self.connect()

    def connect(self):
        retries = 0
        while retries < self.max_retries:
            try:
                self.redis = redis.Redis(
                    host=self.host,
                    port=self.port,
                    socket_timeout=self.timeout,
                    socket_connect_timeout=self.connect_timeout
                )
                return self.redis
            except (ConnectionError, TimeoutError) as err:
                logging.info('Connection error to Redis {}'.format(err))
                time.sleep(self.timeout)
                retries += 1

    @reconnect
    def cache_get(self, key):
        result = self.redis.get(key)
        if result:
            return result.decode("UTF-8")

    @reconnect
    def cache_set(self, key, value, expire=10):
        return self.redis.set(key, value, ex=expire)

    @reconnect
    def get(self, key):
        result = self.redis.get(key)
        if result:
            return result.decode("UTF-8")

    @reconnect
    def set(self, key, value, expires=10):
        return self.redis.set(key, value, ex=expires)
