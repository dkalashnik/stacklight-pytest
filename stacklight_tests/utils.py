import datetime as dt
import os
import random
import tempfile
import time

import requests
from requests.packages.urllib3 import poolmanager
import yaml

from stacklight_tests import custom_exceptions as exceptions


class TestHTTPAdapter(requests.adapters.HTTPAdapter):
    """Custom transport adapter to disable host checking in https requests."""

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = poolmanager.PoolManager(assert_hostname=False)


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


def topo_sort(graph_unsorted):
    result_graph = []
    graph_unsorted = graph_unsorted.copy()
    while graph_unsorted:
        acyclic = False
        for node, edges in graph_unsorted.items():
            for edge in edges:
                if edge in graph_unsorted:
                    break
            else:
                acyclic = True
                del graph_unsorted[node]
                result_graph.append((node, edges))

        if not acyclic:
            raise exceptions.NotFound("A cyclic dependency occurred")
    return result_graph


def load_config():
    with open(get_fixture("config.yaml")) as config_file:
        config = yaml.load(config_file)
    return config


def check_http_get_response(url, expected_codes=(200,), msg=None, **kwargs):
    """Perform a HTTP GET request and assert that the HTTP server replies with
    the expected code.
    :param url: the requested URL
    :type url: str
    :param expected_codes: the expected HTTP response codes. Defaults to 200
    :type expected_codes: tuple or list
    :param msg: the assertion message. Defaults to None
    :type msg: str
    :returns: HTTP response object
    :rtype: requests.Response
    """
    session = requests.Session()
    session.mount("https://", TestHTTPAdapter())
    cert = get_fixture("rootCA.pem")
    msg = msg or "%s responded with {0}, expected {1}" % url
    response = session.get(url, verify=cert, **kwargs)
    if expected_codes:
        assert response.status_code in expected_codes, msg.format(
            response.status_code, expected_codes)
    return response


def parse_time_rfc_3339(timestamp):
    dt_format = "%Y-%m-%dT%H:%M:%S.%fZ"
    dt_fallback_format = "%Y-%m-%dT%H:%M:%SZ"
    # zero_dt = dt.datetime.strptime("0001-01-01T00:00:00Z",
    #                                dt_fallback_format)
    try:
        result = dt.datetime.strptime(timestamp, dt_format)
    except ValueError:
        result = dt.datetime.strptime(timestamp, dt_fallback_format)
    return result
