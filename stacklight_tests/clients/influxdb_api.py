import collections
import itertools as it
import logging
import re
import urlparse

from stacklight_tests import custom_exceptions
from stacklight_tests import utils


check_http_get_response = utils.check_http_get_response

logger = logging.getLogger(__name__)


class InfluxdbApi(object):
    def __init__(self, address, port, username, password, db_name):
        super(InfluxdbApi, self).__init__()
        self.address = address
        self.port = port
        self.username = username
        self.password = password
        self.db_name = db_name

        self.influx_db_url = "http://{0}:{1}/".format(self.address, self.port)

    @staticmethod
    def compile_query(query, replaces):
        for pattern, value in replaces.items():
            query = query.replace(pattern, value)
        # NOTE(rpromyshlennikov): temporary fix for unknown hostname
        # (node-1 vs node-1.test.domain.local)
        query = query.replace(".test.domain.local", "")
        # NOTE(rpromyshlennikov): fix for regex queries (e.g: for mount points)
        query = query.replace("^/", "^\/")
        return query

    @staticmethod
    def parse_measurement(query):
        result = re.search('from \"(\w+)\"', query, re.IGNORECASE)
        if result:
            return result.group(1)
        # NOTE(rpromyshlennikov): there can be multi-tables requests
        # like "FROM /apache_workers/", so we should not check it
        return None

    def do_influxdb_query(self, query, db="", expected_codes=(200,)):
        logger.debug('Query is: %s', query)
        response = check_http_get_response(
            url=urlparse.urljoin(self.influx_db_url, "query"),
            expected_codes=expected_codes,
            params={
                "db": db if db else self.db_name,
                "u": self.username,
                "p": self.password,
                "q": query})
        logger.debug(response.json())
        return response

    def do_query(self, query, **kwargs):
        """Temporary function to do "clean" query and return values themselves.

        :raises KeyError
        """
        kwargs.pop("regex")
        # TODO(rpromyshlennikov): refactor "do_influxdb_query":
        # rename to "do_query" and do return .json()["results"][0]... as here.
        return self.do_influxdb_query(
            query, **kwargs).json()["results"][0]["series"][0]["values"]

    def check_influxdb_online(self):
        measurements = self.get_all_measurements()
        env_name = self.get_environment_name()
        return measurements, env_name

    def check_status(self, service_type, hostname, value,
                     time_interval="now() - 30s"):
        filters = [
            "time >= {}".format(time_interval),
        ]
        if hostname is not None:
            filters.append("hostname = '{}'".format(hostname))

        query = "select last(value) from {table} where {filters}".format(
            table=service_type,
            filters=" and ".join(filters))
        self._check_influx_query_last_value(query, value)

    def get_rabbitmq_memory_usage(self, host, interval="now() - 5m"):
        query = (
            "select last(value) from rabbitmq_used_memory "
            "where hostname = '{host}' and time >= {interval}".format(
                host=host.hostname, interval=interval)
        )
        result = self.do_influxdb_query(query=query).json()
        return result["results"][0]["series"][0]["values"][0][1]

    def get_instance_creation_time_metrics(self, time_point=None):
        """Gets instance creation metrics for provided interval

        :param time_point: time interval
        :type time_point: str
        :returns: list of metrics
        :rtype: list
        """
        interval = "now() - 1h" if time_point is None else time_point
        query = (
            "select value "
            "from openstack_nova_instance_creation_time "
            "where time >= {interval}".format(interval=interval))
        result = self.do_influxdb_query(query=query).json()["results"][0]

        if result and 'series' in result:
            return result["series"][0]["values"]
        return []

    def _check_influx_query_last_value(self, query, expected_value):
        def check_status():
            logger.debug("Awaiting value: {}".format(expected_value))
            output = self.do_influxdb_query(query)
            result = output.json()['results'][0]
            if not result or 'series' not in result:
                return False
            return result['series'][0]['values'][0][1] == expected_value

        msg = "There is no such value: {} in results of query: {}".format(
            expected_value, query
        )
        utils.wait(lambda: check_status(), timeout=5 * 60, timeout_msg=msg)

    def check_cluster_status(self, name, expected_status, interval='3m'):
        query = ("SELECT last(value) FROM cluster_status WHERE "
                 "time > now() - {0} AND cluster_name='{1}'".format(interval,
                                                                    name))
        self._check_influx_query_last_value(query, expected_status)

    def check_count_of_haproxy_backends(self, service, node_state='down',
                                        expected_count=0, interval='3m'):

        query = ("SELECT last(value) FROM haproxy_backend_servers WHERE "
                 "backend='{0}' AND state='{1}' and "
                 "time > now() - {2}".format(service, node_state, interval))

        self._check_influx_query_last_value(query, expected_count)

    def check_mk_alarm(self, member, warning_level, hostname=None,
                       time_range="now() - 30s", table="status", reraise=True):
        Result = collections.namedtuple(
            "Result", field_names=("status", "host", "value"))
        filters = ["member = '{}'".format(member),
                   "time >= {}".format(time_range)]
        if hostname is not None:
            filters.append("hostname = '{}'".format(hostname))
        query = ("SELECT {{}} FROM {table} "
                 "WHERE {filters}".format(table=table,
                                          filters=" and ".join(filters)))
        try:
            self._check_influx_query_last_value(query.format("last(value)"),
                                                warning_level)
            result = self.do_influxdb_query(query.format(
                "hostname, last(value)")).json()['results'][0]
            host, value = result['series'][0]['values'][0][1:]
            return Result(True, host, value)
        except custom_exceptions.TimeoutError as e:
            if not reraise:
                return Result(False, None, None)
            raise custom_exceptions.TimeoutError(e)

    def get_environment_name(self):
        query = "show tag values from cpu_usage_idle with key = host"
        return self.do_influxdb_query(
            db="prometheus", query=query).json()["results"][0]["series"][0][
            "values"][0][1]

    def get_all_measurements(self):
        measurements = (self.do_influxdb_query(
            db="prometheus", query="show measurements").json())["results"][0]
        measurements = {item[0]
                        for item in measurements["series"][0]["values"]}
        return measurements

    def get_tag_table_bindings(self, tag_name):
        tags = (self.do_influxdb_query("SHOW TAG keys")
                    .json()["results"][0]["series"])
        # NOTE(rpromyshlennikov):tag["values"] is a nested list like this:
        # u'values': [[u'environment_label'], [u'hostname'], [u'region']],
        # so it should be flatten
        tables = [tag["name"] for tag in tags
                  if tag_name in it.chain.from_iterable(tag["values"])]
        return tables


class InfluxDBQueryBuilder(object):
    def __init__(self, source):
        self.tags = source["tags"]
        self.select = source["select"]
        self.policy = source.get("policy", "default")
        self.measurement = source["measurement"]
        self.group_by = source["groupBy"]

    def _render_tags(self):
        res = []
        for tag in self.tags:
            value = tag["value"]
            default_operator = "=~" if "/" in value else "="
            operator = tag.get("operator", default_operator)
            if "~" not in operator:
                value = "'{}'".format(value)
            conditions = (
                tag.get("condition", "AND"),
                '"{}"'.format(tag["key"]),
                operator,
                value,
            )
            res.append(" ".join(conditions if res else conditions[1:]))
        return " ".join(res)

    def _render_selectors(self):
        def align_fns(selector):
            fns = selector[1:]
            value = selector[0]["params"][0]
            for fn in fns:
                if fn["type"] == "math":
                    value += fn["params"][0]
                else:
                    params = fn["params"][:]
                    params.insert(0, value)
                    value = "{}({})".format(fn["type"], ", ".join(params))
            return value

        selectors = [align_fns(sel) for sel in self.select]
        res = "SELECT {}".format(", ".join(selectors))
        return res

    def _render_measurement(self):
        table = self.measurement
        if self.policy != "default":
            table = "{}.{}".format(self.policy, table)
        return ' FROM "{}"'.format(table)

    def _render_where_clause(self):
        tags = "{} AND ".format(self._render_tags()) if self.tags else ""
        return " WHERE {}$timeFilter".format(tags)

    def _render_group_by(self):
        if not self.group_by:
            return ""
        res = []
        for cond in self.group_by:
            value = ", ".join(cond["params"])
            if cond["type"] != "tag":
                value = "{}({})".format(cond["type"], value)
            else:
                value = '"{}"'.format(value)
            res.append(value)
        return " GROUP BY {}".format(
            ", ".join(res)
                .replace(", fill", " fill")  # "fill" should be without comma
                .replace("auto", "$interval"))  # "auto" for time is $interval

    def render_query(self):
        query = self._render_selectors()
        query += self._render_measurement()
        query += self._render_where_clause()
        query += self._render_group_by()
        return query
