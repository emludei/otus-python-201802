#!/usr/bin/env python3

from itertools import chain
from functools import update_wrapper, reduce
from operator import xor


def disable(func):
    """
    Disable a decorator by re-assigning the decorator's name
    to this function. For example, to turn off memoization:

    >>> memo = disable

    """
    if not callable(func):
        return lambda fn: fn
    return func


def decorator(deco):
    """
    Decorate a decorator so that it inherits the docstrings
    and stuff from the function it's decorating.
    """
    def _decorator(func):
        return update_wrapper(deco(func), func)
    return _decorator


@decorator
def countcalls(func):
    """Decorator that counts calls made to the function decorated."""
    def _decorator(*args, **kwargs):
        _decorator.calls += 1
        return func(*args, **kwargs)
    _decorator.calls = 0
    return _decorator


@decorator
def memo(func):
    """
    Memoize a function so that it caches all return values for
    faster future lookups.
    """
    maxsize = 1000
    cache = {}

    def _decorator(*args, **kwargs):
        hashes = (chain((hash(arg) for arg in args), (hash(item) for item in kwargs.items())))
        key = reduce(xor, hashes, 0)

        if len(cache) >= maxsize:
            cache.clear()

        if key not in cache:
            cache[key] = func(*args, **kwargs)

        update_wrapper(_decorator, func)
        return cache[key]

    return _decorator


@decorator
def n_ary(func):
    """
    Given binary function f(x, y), return an n_ary function such
    that f(x, y, z) = f(x, f(y,z)), etc. Also allow f(x) = x.
    """
    def _decorator(*args):
        if len(args) <= 2:
            return func(*args)
        return reduce(func, args)
    return _decorator


def trace(prefix):
    """Trace calls made to function decorated.

    @trace("____")
    def fib(n):
        ....

    >>> fib(3)
     --> fib(3)
    ____ --> fib(2)
    ________ --> fib(1)
    ________ <-- fib(1) == 1
    ________ --> fib(0)
    ________ <-- fib(0) == 1
    ____ <-- fib(2) == 2
    ____ --> fib(1)
    ____ <-- fib(1) == 1
     <-- fib(3) == 3

    """

    @decorator
    def _wrapper(func):
        level = 0

        def _decorator(*args, **kwargs):
            nonlocal level

            args_repr = ", ".join(str(arg) for arg in args)
            kwargs_repr = ", ".join("{0}={1}".join([key, val]) for key, val in kwargs.values())
            func_args_repr = args_repr + kwargs_repr

            print(prefix * level, " --> {0}({1})".format(func.__name__, func_args_repr))
            level += 1
            result = func(*args, **kwargs)
            level -= 1
            print(prefix * level, " <-- {0}({1}) == {2}".format(func.__name__, func_args_repr, result))
            return result
        return _decorator

    return _wrapper


@memo
@countcalls
@n_ary
def foo(a, b):
    return a + b


@countcalls
@memo
@n_ary
def bar(a, b):
    return a * b


@countcalls
@trace("####")
@memo
def fib(n):
    """Some doc"""
    return 1 if n <= 1 else fib(n-1) + fib(n-2)


def main():
    print(foo(4, 3))
    print(foo(4, 3, 2))
    print(foo(4, 3))
    print("foo was called", foo.calls, "times")

    print(bar(4, 3))
    print(bar(4, 3, 2))
    print(bar(4, 3, 2, 1))
    print("bar was called", bar.calls, "times")

    print(fib.__doc__)
    fib(3)
    print(fib.calls, 'calls made')


if __name__ == '__main__':
    main()
