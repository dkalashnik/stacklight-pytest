import urlparse

import requests
from requests.packages.urllib3 import poolmanager

import utils


class TestHTTPAdapter(requests.adapters.HTTPAdapter):
    """Custom transport adapter to disable host checking in https requests."""

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = poolmanager.PoolManager(assert_hostname=False)


class InfluxdbApi(object):
    def __init__(self, address, port, username, password, db_name):
        super(InfluxdbApi, self).__init__()
        self.address = address
        self.port = port
        self.username = username
        self.password = password
        self.db_name = db_name

        self.influx_db_url = "http://{0}:{1}/".format(self.address, self.port)

    def check_http_get_response(self, url, expected_code=200,
                                msg=None, **kwargs):
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
        cert = utils.get_fixture("rootCA.pem")
        msg = msg or "%s responded with {0}, expected {1}" % url
        r = s.get(url, verify=cert, **kwargs)

        assert(r.status_code == expected_code)
        print(r.content)
        return r

    def do_influxdb_query(self, query, expected_code=200):
        return self.check_http_get_response(
            url=urlparse.urljoin(self.influx_db_url, "query"),
            expected_code=expected_code,
            params={
                "db": self.db_name,
                "u": self.username,
                "p": self.password,
                "q": query})

    def check_alarms(self, alarm_type, filter_value, source, hostname,
                     value, time_interval="now() - 5m"):
        filter_by = "node_role"
        if alarm_type == "service":
            filter_by = "service"
        filters = [
            "time >= {}".format(time_interval),
            "source = '{}'".format(source),
            "{} = '{}'".format(filter_by, filter_value),
            "value = {}".format(value)
        ]
        if hostname is not None:
            filters.append("hostname = '{}'".format(hostname))

        query = "select last(value) from {select_from} where {filters}".format(
            select_from="{}_status".format(alarm_type),
            filters=" and ".join(filters))

        def check_result():
            return len(self.do_influxdb_query(query=query)
                       .json()['results'][0])

        msg = ("Alarm of type: {}: entity: {}, source:{}, hostname: {}, "
               "value: {} wasn't triggered".format(alarm_type, filter_value,
                                                   source, hostname, value))

        utils.wait(check_result, timeout=60 * 5, interval=10, timeout_msg=msg)

    def get_rabbitmq_memory_usage(self, interval="now() - 5m"):
        query = ("select last(value) from rabbitmq_used_memory "
                 "where time >= {interval}".format(interval=interval))
        result = self.do_influxdb_query(query=query).json()
        return result["results"][0]["series"][0]["values"][0][1]
