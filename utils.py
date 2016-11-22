import os
import random
import tempfile
import time

import custom_exceptions as exceptions


def get_fixture(name, parent_dirs=("",), check_existence=True):
    test_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dirs_path = os.path.join(*parent_dirs)
    path = os.path.join(test_dir, "fixtures", parent_dirs_path, name)
    if check_existence and not os.path.isfile(path):
        raise exceptions.NotFound("File {} not found".format(path))
    return path


def wait(predicate, interval=5, timeout=60, timeout_msg="Waiting timed out"):
    start_time = time.time()
    if not timeout:
        return predicate()
    while not predicate():
        if start_time + timeout < time.time():
            raise exceptions.TimeoutError(timeout_msg)

        seconds_to_sleep = max(
            0,
            min(interval, start_time + timeout - time.time()))
        time.sleep(seconds_to_sleep)

    return timeout + start_time - time.time()


def write_cert(cert_content):
    with tempfile.NamedTemporaryFile(
            prefix="ca_", suffix=".pem", delete=False) as f:
        f.write(cert_content)
    return f.name


def rand_name(base="", prefix="stacklight-pytest-", postfix=""):
    return "{prefix}{base}{rand}{postfix}".format(
        prefix=prefix,
        base=base,
        rand=random.randrange(100, 999),
        postfix=postfix,)
