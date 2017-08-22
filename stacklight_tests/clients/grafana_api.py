import logging

from stacklight_tests.clients import grafana_templates_builder
from stacklight_tests import utils


check_http_get_response = utils.check_http_get_response

logger = logging.getLogger(__name__)


class Dashboard(object):
    def __init__(self, dash_dict, datasource):
        self.name = dash_dict["meta"]["slug"]
        self.dash_dict = dash_dict
        self._datasource = datasource
        self._templates_tree = self.get_templates_tree()

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
        return grafana_templates_builder.TemplatesTree(template_queries,
                                                       self._datasource)

    def get_all_templates_for_query(self, query):
        return self._templates_tree.get_all_templates_for_query(query)

    @staticmethod
    def build_query(target):
        if target.get("rawQuery"):
            return target["query"]
        if target.get("expr"):
            return target["expr"]
        raise Exception("Something is going wrong")

    def get_panel_queries(self):
        panel_queries = {}
        for panel, row in self.panels:
            panel_name = "{}->{}".format(row["title"], panel["title"] or "n/a")
            for target in panel.get("targets", []):
                query = self.build_query(target)
                query_name = "{}:{}->RefId:{}".format(
                    panel["id"], panel_name, target.get("refId", "A"))
                panel_queries[query_name] = query
        return panel_queries


class GrafanaApi(object):
    def __init__(self, address, port, username, password, datasource,
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
        self.datasource = datasource

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
        else:
            response.raise_for_status()

    def get_dashboard(self, name):
        raw_dashboard = self._get_raw_dashboard(name)
        if raw_dashboard:
            return Dashboard(raw_dashboard.json(),
                             self.datasource)

    def get_all_dashboards_names(self):
        search_url = self.get_api_url("/search")
        result = check_http_get_response(search_url, auth=self.auth)
        return [dash["uri"].replace("db/", "") for dash in result.json()]

    def is_dashboard_exists(self, name):
        if self._get_raw_dashboard(name):
            return True
        return False
