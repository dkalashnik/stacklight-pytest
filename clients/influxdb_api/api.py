import json

#from proboscis import asserts

#from stacklight_tests import base_test
#from stacklight_tests.influxdb_grafana.grafana_ui import api as ui_api
#from stacklight_tests.influxdb_grafana import plugin_settings
import plugin_settings
import requests
from requests.packages.urllib3 import poolmanager

import logging
logger = logging.getLogger('fuel-qa.{}'.format(__name__))


class NotFound(Exception):
    pass


class InfluxdbApi(object):
    def __init__(self, address, port, protocol):
        super(InfluxdbApi, self).__init__()
        self._grafana_port = None
        self._grafana_protocol = None

    @property
    def grafana_port(self):
        if self._grafana_port is None:
            if self.grafana_protocol == 'http':
                self._grafana_port = 80
            else:
                self._grafana_port = 443
        return self._grafana_port

    @property
    def grafana_protocol(self):
        if self._grafana_protocol is None:
            self._grafana_protocol = self.get_http_protocol()
        return self._grafana_protocol

    def get_influxdb_vip(self):
        return '10.109.1.10'
        #return self.helpers.get_vip_address('influxdb')

    def get_influxdb_url(self, path=''):
        return "http://{0}:8086/{1}".format(self.get_influxdb_vip(), path)

    def do_influxdb_query(self,
                          query,
                          db=plugin_settings.influxdb_db_name,
                          user=plugin_settings.influxdb_user,
                          password=plugin_settings.influxdb_pass,
                          expected_code=200):
        """

        :param query:
        :param db:
        :param user:
        :param password:
        :param expected_code:
        :rtype: requests.Response
        """
        logger.info("Making query to Influx DB: {}".format(query))
        return check_http_get_response(
            url=self.get_influxdb_url('query'),
            expected_code=expected_code,
            params={"db": db, "u": user, "p": password, "q": query})


def check_http_get_response(url, expected_code=200, msg=None, **kwargs):
    """Perform a HTTP GET request and assert that the HTTP server replies with
    the expected code.

    :param url: the requested URL
    :type url: str
    :param expected_code: the expected HTTP response code. Defaults to 200
    :type expected_code: int
    :param msg: the assertion message. Defaults to None
    :type msg: str
    :returns: HTTP response object
    :rtype: requests.Response
    """
    s = requests.Session()
    s.mount("https://", TestHTTPAdapter())
    cert = get_fixture("rootCA.pem")
    msg = msg or "%s responded with {0}, expected {1}" % url
    r = s.get(url, verify=cert, **kwargs)

    assert(r.status_code == expected_code)
    print(r.content)
    return r

class TestHTTPAdapter(requests.adapters.HTTPAdapter):
    """Custom transport adapter to disable host checking in https requests."""

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = poolmanager.PoolManager(assert_hostname=False)

import os
def get_fixture(name):
    """Return the full path to a fixture."""
    path = os.path.join(os.environ.get("WORKSPACE", "./"), "fixtures", name)
    if not os.path.isfile(path):
        raise NotFound("File {} not found".format(path))
    return path
