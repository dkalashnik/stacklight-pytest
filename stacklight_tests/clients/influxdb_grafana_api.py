import collections
import logging
import re
import urlparse

from stacklight_tests import custom_exceptions
from stacklight_tests import utils


check_http_get_response = utils.check_http_get_response

logger = logging.getLogger(__name__)


def get_all_grafana_dashboards_names():
    env_type = utils.load_config().get("env", {}).get("type", "")
    dashboard_names = {
        "Apache", "LMA self-monitoring",
        "Cinder", "Elasticsearch", "Glance", "HAProxy", "Heat",
        "Hypervisor", "InfluxDB", "Keystone", "Main",
        "Memcached", "MySQL", "Neutron", "Nova", "RabbitMQ", "System"
    }
    if env_type == "mk":
        # Add new dashboards for mk
        dashboard_names.update({
            "Cassandra", "GlusterFS", "Grafana", "Kibana", "Nginx",
            "OpenContrail"})
        # Remove not actual dashboards for mk
        dashboard_names.difference_update(
            {"Apache", "LMA self-monitoring"})

    return {panel_name.lower().replace(" ", "-")
            for panel_name in dashboard_names}


class InfluxdbApi(object):
    def __init__(self, address, port, username, password, db_name):
        super(InfluxdbApi, self).__init__()
        self.address = address
        self.port = port
        self.username = username
        self.password = password
        self.db_name = db_name

        self.influx_db_url = "http://{0}:{1}/".format(self.address, self.port)

    def do_influxdb_query(self, query, expected_codes=(200,)):
        logger.debug('Query is: %s', query)
        response = check_http_get_response(
            url=urlparse.urljoin(self.influx_db_url, "query"),
            expected_codes=expected_codes,
            params={
                "db": self.db_name,
                "u": self.username,
                "p": self.password,
                "q": query})
        logger.debug(response.json())
        return response

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

    def check_alarms(self, alarm_type, filter_value, source, hostname,
                     value, time_interval="now() - 5m"):
        filter_by = "node_role"
        if alarm_type == "service":
            filter_by = "service"
        filters = [
            "time >= {}".format(time_interval),
            "{} = '{}'".format(filter_by, filter_value),
        ]
        if source is not None:
            filters.append("source = '{}'".format(source))
        if hostname is not None:
            filters.append("hostname = '{}'".format(hostname))

        query = "select last(value) from {select_from} where {filters}".format(
            select_from="{}_status".format(alarm_type),
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
                       time_range="now() - 10s", table="status", reraise=True):
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
        query = "show tag values from cpu_idle with key = environment_label"
        return self.do_influxdb_query(
            query).json()['results'][0]["series"][0]["values"][0][1]

    def get_all_measurements(self):
        measurements = (
            self.do_influxdb_query("show measurements").json())['results'][0]
        measurements = {item[0]
                        for item in measurements["series"][0]["values"]}
        return measurements


class Dashboard(object):
    def __init__(self, dash_dict, influxdb):
        self.name = dash_dict["meta"]["slug"]
        self.dash_dict = dash_dict
        self._influxdb_api = influxdb
        self.persistent_templates = {
            "$interval": "1m",
            "$timeFilter": "time > now() - 1h",
            "$environment": self._influxdb_api.get_environment_name()
        }
        self.templates = self.get_templates()
        self.available_measurements = self._influxdb_api.get_all_measurements()

    def __repr__(self):
        return "{}: {}".format(self.__class__, self.name)

    @staticmethod
    def _compile_query(query, replaces):
        for pattern, value in replaces.items():
            query = query.replace(pattern, value)
        # NOTE(rpromyshlennikov): temporary fix for unknown hostname
        # (node-1 vs node-1.test.domain.local)
        query = query.replace(".test.domain.local", "")
        # NOTE(rpromyshlennikov): fix for regex queries (e.g: for mount points)
        query = query.replace("^/", "^\/")
        return query

    @staticmethod
    def _parse_measurement_from_query(query):
        result = re.search('from "(\w+)"', query, re.IGNORECASE)
        if result:
            return result.group(1)
        # NOTE(rpromyshlennikov): there can be multi-tables requests
        # like "FROM /apache_workers/", so we should not check it
        return None

    def _compile_templates(self, template_queries):
        templates = self.persistent_templates.copy()
        dependencies = {k: re.findall("\$\w+", v) for k, v in
                        template_queries.items()}
        queries_queue = [item[0]
                         for item in utils.topo_sort(dependencies)]
        for item in queries_queue:
            compiled_tmp = self._compile_query(
                template_queries[item], templates)
            try:
                result = self._influxdb_api.do_influxdb_query(
                    compiled_tmp).json()["results"][0]["series"][0]["values"]
            except KeyError:
                result = [("", "")]
            # NOTE(rpromyshlennikov): future enhancements:
            # do multiple values request, not only "0" option
            templates[item] = [result[1] for result in result][0]
        return templates

    def get_templates(self):
        template_queries = {
            "${}".format(item["name"]): item["query"]
            for item in self.dash_dict["dashboard"]["templating"]["list"]
        }
        return self._compile_templates(template_queries)

    def get_panel_queries(self):
        panel_queries = {}
        identifier = 0
        for row in self.dash_dict["dashboard"]["rows"]:
            for panel in row["panels"]:
                panel_name = "{}: {}".format(row["title"], panel["title"])
                for target in panel.get("targets", [{}]):
                    query = target.get("query")
                    if query:
                        query_name = "{}: {}: {}".format(
                            identifier, panel_name, target.get(
                                "measurement",
                                self._parse_measurement_from_query(query)))
                        identifier += 1
                        assert query_name not in panel_queries, query_name
                        panel_queries[query_name] = (
                            (query,
                             self._compile_query(query, self.templates)))
        return panel_queries

    def classify_all_dashboard_queries(self):
        ok_queries = {}
        failed_queries = {}
        no_measurements_queries = {}
        for key, (raw_query, query) in self.get_panel_queries().items():
            try:
                query_table = self._parse_measurement_from_query(query)
                if query_table and (
                        query_table not in self.available_measurements):
                    no_measurements_queries[key] = raw_query, query, {}
                    continue
                raw_result = self._influxdb_api.do_influxdb_query(query).json()
                result = raw_result["results"][0]
                assert result["series"][0]["values"]
                ok_queries[key] = raw_query, query, result
            except KeyError:
                failed_queries[key] = raw_query, query, raw_result
        return ok_queries, no_measurements_queries, failed_queries


class GrafanaApi(object):
    def __init__(self, address, port, username, password, influxdb, tls=False):
        super(GrafanaApi, self).__init__()
        self.address = address
        self.port = port
        self.username = username
        self.password = password
        self.auth = (username, password)
        scheme = "https" if tls else "http"
        self.grafana_api_url = "{scheme}://{host}:{port}/api".format(
            scheme=scheme, host=address, port=port)
        self._influxdb_api = influxdb

    def get_api_url(self, resource=""):
        return "{}{}".format(self.grafana_api_url, resource)

    def check_grafana_online(self):
        check_http_get_response(self.grafana_api_url.replace("/api", "/login"))
        check_http_get_response(self.get_api_url('/org'), auth=self.auth)
        check_http_get_response(self.get_api_url('/org'),
                                auth=('agent', 'rogue'), expected_codes=(401,))
        check_http_get_response(self.get_api_url('/org'),
                                auth=('admin', 'rogue'), expected_codes=(401,))
        check_http_get_response(self.get_api_url('/org'),
                                auth=('agent', 'admin'), expected_codes=(401,))

    def _get_raw_dashboard(self, name):
        dashboard_url = self.get_api_url("/dashboards/db/{}".format(name))
        response = check_http_get_response(
            dashboard_url, expected_codes=[], auth=self.auth)
        if response.status_code == 200:
            return response
        elif response.status_code == 404:
            return None
        else:
            response.raise_for_status()

    def get_dashboard(self, name):
        raw_dashboard = self._get_raw_dashboard(name)
        if raw_dashboard:
            return Dashboard(raw_dashboard.json(), self._influxdb_api)
        return None

    def get_all_dashboards(self):
        search_url = self.get_api_url("/search")
        result = check_http_get_response(search_url, auth=self.auth)
        return (self.get_dashboard(dash["uri"].replace("db/", ""))
                for dash in result.json())

    def is_dashboard_exists(self, name):
        if self._get_raw_dashboard(name):
            return True
        return False
