import collections
import itertools as it
import logging
import re
import urlparse

from stacklight_tests import custom_exceptions
from stacklight_tests import utils


check_http_get_response = utils.check_http_get_response

logger = logging.getLogger(__name__)


def get_all_grafana_dashboards_names(datasource=None):
    dashboards_influx = {
        "Cassandra", "Cinder", "Elasticsearch", "GlusterFS", "Glance",
        "Grafana", "HAProxy", "Heat", "Hypervisor", "InfluxDB", "Keystone",
        "Kibana", "Main", "Memcached", "MySQL", "Neutron", "Nginx", "Nova",
        "OpenContrail", "RabbitMQ", "System"
    }
    dashboards_prometheus = {
        "Calico cluster monitoring (via Prometheus)",
        "Kubernetes App Metrics",
        "Kubernetes cluster monitoring (via Prometheus)",
        "Prometheus Performances"
    }

    dashboards = {
        "prometheus": dashboards_prometheus,
        "influxdb": dashboards_influx
    }
    if datasource is None:
        dashboard_names = dashboards_influx | dashboards_prometheus
    else:
        dashboard_names = dashboards[datasource]
    return {
        panel_name.lower().replace(" ", "-").replace("(", "").replace(")", "")
        for panel_name in dashboard_names
    }


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
        query = "show tag values from cpu_idle with key = environment_label"
        return self.do_influxdb_query(
            query).json()["results"][0]["series"][0]["values"][0][1]

    def get_all_measurements(self):
        measurements = (
            self.do_influxdb_query("show measurements").json())["results"][0]
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


def get_influxdb_client_from_config(config):
    influxdb_api = InfluxdbApi(
        address=config["influxdb_vip"],
        port=config["influxdb_port"],
        username=config["influxdb_username"],
        password=config["influxdb_password"],
        db_name=config["influxdb_db_name"]
    )
    return influxdb_api


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


class DepNode(object):
    def __init__(self, value, template_name, parent, dependencies=()):
        self.value = value
        self.name = template_name
        self.parent = parent
        self.children = set()
        self.level = getattr(parent, "level", -1) + 1
        self.dependencies = dependencies
        if parent is not None:
            self.parent.children.add(self)

    def __repr__(self):
        return "{}:{}:{}".format(
            self.__class__.__name__, self.name, self.value)

    def __str__(self):
        return self.value

    def get_full_template(self):
        curr_node = self
        template = {}
        while curr_node.parent:
            parent = curr_node.parent
            template[parent.name] = str(parent)
            curr_node = parent
        template[self.name] = self.value
        return template

    def get_templates_with_children(self):
        base_template = self.get_full_template()
        children_groups = collections.defaultdict(set)
        for child in self.children:
            children_groups[child.name].add(child.value)
        templates = []
        for item in it.product(*children_groups.values()):
            template = base_template.copy()
            for n, key in enumerate(children_groups.keys()):
                template[key] = item[n]
            templates.append(template)
        return templates


class TemplatesTree(object):
    def __init__(self, queries, datasource):
        self.queries = queries
        self.default_templates = {
            "$interval": "1m",
            "$timeFilter": "time > now() - 1h",
        }
        self.dependencies = {
            k: self.parse_dependencies(v) for k, (v, _) in self.queries.items()
        }
        self._compile_query = datasource.compile_query
        self._do_query = datasource.do_query

        self.nodes_by_level = collections.defaultdict(set)
        self.levels_by_name = collections.OrderedDict()
        self._build_abs_tree()

        if self.queries:
            self._build()

    @staticmethod
    def parse_dependencies(query):
        return re.findall("\$\w+", query)

    def _build_abs_tree(self):
        """Builds abstract tree of dependencies.

        For example it will build next tree for next dependencies:
            {'$environment': [],
             '$server': ['$environment'],
             '$peer': ['$environment', '$server'],
             '$volume': ['$environment', '$server']}

            $environment
                  |
                  v
               $server
                /  \
               v    v
            $peer  $volume
        """
        curr_level = 0
        for template, deps in utils.topo_sort(self.dependencies):
            if deps:
                curr_level = self.find_closest_parent_level(deps) + 1
            self.levels_by_name[template] = curr_level

    def _query_values_for_template(self, template, substitutions):
        query = self._compile_query(self.queries[template][0], substitutions)
        try:
            values = self._do_query(query, regex=self.queries[template][1])
        except KeyError:
            values = []
        return values

    def _fill_top_level(self):
        dep_name = self.levels_by_name.keys()[0]
        parent = None
        values = self._query_values_for_template(dep_name, {})
        for value in values:
            self.add_template(value, dep_name, parent)

    def _build(self):
        """Fill tree with all possible values for _templates_tree.

        For example:
                     mkX-lab-name.local
                    /        |        \
                   /         |         \
                  v          v          v
         ...<--ctl01       ctl02        ctl03-->...
                       /-----|--------\
                 /-----      |---\     ---------\
                v            |    ----\          v
           172.16.10.101     v         v     172.16.10.102
                          glance  keystone-keys

        """
        self._fill_top_level()
        for name, level in self.levels_by_name.items()[1:]:
            parents = self.get_closest_parents(self.dependencies[name])
            for parent in parents:
                substitutions = parent.get_full_template()
                values = self._query_values_for_template(name, substitutions)
                for value in values:
                    self.add_template(value, name, parent)

    def get_nodes_on_level(self, level):
        return self.nodes_by_level[level]

    def get_nodes_by_name(self, name):
        return (node for node in
                self.get_nodes_on_level(self.levels_by_name[name])
                if node.name == name)

    def find_closest_parent_level(self, dependencies):
        return max(self.levels_by_name[dep] for dep in dependencies)

    def get_closest_parents(self, dependencies):
        parent_level = self.find_closest_parent_level(dependencies)
        return [node for node in self.get_nodes_on_level(parent_level)
                if node.name in dependencies]

    def add_template(self, value, name, parent):
        tpl = value
        if not isinstance(tpl, (str, unicode)):
            tpl = tpl[1]
        dependencies = self.dependencies[name]
        new_node = DepNode(tpl, name, parent, dependencies)
        self.nodes_by_level[new_node.level].add(new_node)

    def get_all_templates_for_query(self, query):
        dependencies = [dep for dep in self.parse_dependencies(query)
                        if dep not in self.default_templates]
        if not dependencies:
            return [self.default_templates]
        dep_nodes = self.get_closest_parents(dependencies)
        groups = {node.name for node in dep_nodes}
        if len(groups) > 1:
            parents = {node.parent for node in dep_nodes}
            templates = list(it.chain(*[parent.get_templates_with_children()
                                        for parent in parents]))
        else:
            templates = [node.get_full_template() for node in dep_nodes]
        for template in templates:
            template.update(self.default_templates)
        return templates


class Dashboard(object):
    def __init__(self, dash_dict, datasource):
        self.name = dash_dict["meta"]["slug"]
        self.dash_dict = dash_dict
        self._datasource = datasource
        self._templates_tree = self.get_templates_tree()
        self.available_measurements = self._datasource.get_all_measurements()

    def __repr__(self):
        return "{}: {}".format(self.__class__, self.name)

    @property
    def panels(self):
        for row in self.dash_dict["dashboard"]["rows"]:
            for panel in row["panels"]:
                yield panel, row

    def get_templates_tree(self):
        if "templating" not in self.dash_dict["dashboard"]:
            template_queries = {}
        else:
            template_queries = {
                "${}".format(item["name"]): (item["query"], item["regex"])
                for item in self.dash_dict["dashboard"]["templating"]["list"]
            }
        return TemplatesTree(template_queries, self._datasource)

    def get_all_templates_for_query(self, query):
        return self._templates_tree.get_all_templates_for_query(query)

    @staticmethod
    def build_query(target):
        if target.get("rawQuery"):
            return target["query"]
        if target.get("expr"):
            return target["expr"]
        return InfluxDBQueryBuilder(target).render_query()

    def get_panel_queries(self):
        panel_queries = {}
        for panel, row in self.panels:
            panel_name = "{}->{}".format(row["title"], panel["title"] or "n/a")
            for target in panel.get("targets", []):
                query = self.build_query(target)
                table = target.get(
                    "measurement", self._datasource.parse_measurement(query))
                query_name = "{}:{}->{}->RefId:{}".format(
                    panel["id"], panel_name, table, target.get("refId", "A"))
                panel_queries[query_name] = query, table
        return panel_queries

    def classify_query(self, raw_query, table):
        if table and (table not in self.available_measurements):
            return "no_table", raw_query
        results = collections.defaultdict(list)
        possible_templates = self.get_all_templates_for_query(raw_query)
        for template in possible_templates:
            query = self._datasource.compile_query(raw_query, template)
            try:
                result = self._datasource.do_query(query)
                if not result:
                    raise ValueError
                results["ok"].append(template)
            except (KeyError, ValueError):
                results["failed"].append(template)

        if len(results["ok"]) == len(possible_templates):
            return "ok", raw_query
        if len(results["failed"]) == len(possible_templates):
            return "failed", raw_query
        return "partially_ok", (raw_query, results["failed"])

    def classify_all_dashboard_queries(self):
        statuses = ("ok", "partially_ok", "no_table", "failed")
        queries = collections.defaultdict(dict)
        for key, (raw_query, table) in self.get_panel_queries().items():
            query_type, result = self.classify_query(raw_query, table)
            queries[query_type][key] = result
        return [queries[status] for status in statuses]


class GrafanaApi(object):
    def __init__(self, address, port, username, password, datasources,
                 tls=False):
        super(GrafanaApi, self).__init__()
        self.address = address
        self.port = port
        self.username = username
        self.password = password
        self.auth = (username, password)
        scheme = "https" if tls else "http"
        self.grafana_api_url = "{scheme}://{host}:{port}/api".format(
            scheme=scheme, host=address, port=port)
        self._datasources = datasources

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

    def get_dashboard(self, name, datasource_type):
        raw_dashboard = self._get_raw_dashboard(name)
        if raw_dashboard:
            return Dashboard(raw_dashboard.json(),
                             self._datasources[datasource_type])
        return None

    def get_all_dashboards_names(self):
        search_url = self.get_api_url("/search")
        result = check_http_get_response(search_url, auth=self.auth)
        return [dash["uri"].replace("db/", "") for dash in result.json()]

    def is_dashboard_exists(self, name):
        if self._get_raw_dashboard(name):
            return True
        return False
