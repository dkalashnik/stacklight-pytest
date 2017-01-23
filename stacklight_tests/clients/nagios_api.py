import collections
import urlparse

from stacklight_tests import custom_exceptions
from stacklight_tests import static_elements
from stacklight_tests import utils


class NagiosBasePage(static_elements.Page):
    title_locator = (static_elements.By.CLASS_NAME, "statusTitle")

    main_table_locator = (static_elements.By.XPATH, "//table[@class='status']")

    @property
    def main_table(self):
        return self.find_element(*self.main_table_locator)


class NagiosApi(object):
    pages = {
        "Services": "status.cgi?host=all&limit=0",
        "Hosts": "status.cgi?hostgroup=all&style=hostdetail&limit=0"
    }

    def __init__(self, address, port, username, password, tls_enabled=True):
        super(NagiosApi, self).__init__()
        self.address = address
        self.port = port
        self.username = username
        self.password = password
        self.scheme = "https" if tls_enabled else "http"
        self.nagios_url = (
            "{scheme}://{user}:{password}@{address}:{port}"
            "/cgi-bin/nagios3/".format(
                scheme=self.scheme,
                user=self.username, password=self.password,
                address=self.address, port=self.port))

    def get_page(self, page_name, expected_codes=(200,)):
        url = urlparse.urljoin(self.nagios_url, self.pages[page_name])
        response = utils.check_http_get_response(
            url=url, expected_codes=expected_codes)
        return NagiosBasePage(response.content)

    @property
    def services_page(self):
        return self.get_page("Services")

    @property
    def hosts_page(self):
        return self.get_page("Hosts")

    def get_all_nodes_statuses(self):
        nodes = {}
        node_name_index = 1
        status_index = 2
        for row in self.hosts_page.main_table.rows:
            try:
                curr_node_name = row.get_cell(node_name_index).text_
                status = row.get_cell(status_index).text_
                nodes[curr_node_name] = status
            except custom_exceptions.NotFound:
                # In case on empty row, because there can be rows without info
                continue
        return nodes

    def get_all_services_statuses(self):
        services = collections.defaultdict(dict)
        node_name_index = 1
        service_name_index = 2
        status_index = 3
        curr_node_name = ""
        for row in self.services_page.main_table.rows:
            try:
                node_name_cell_text = row.get_cell(node_name_index).text_
                if node_name_cell_text:
                    curr_node_name = node_name_cell_text
                service_name = row.get_cell(service_name_index).text_
                status = row.get_cell(status_index).text_
                services[curr_node_name].update({service_name: status})
            except custom_exceptions.NotFound:
                # In case on empty row, because there can be rows without info
                continue
        return services

    def get_services_for_node(self, node_name):
        return self.get_all_services_statuses()[node_name]

    def check_service_state_on_nagios(self, service_state=None,
                                      node_names=None):
        table = self.services_page.main_table
        if not node_names:
            # First node name is given for global cluster section
            node_names = [table.get_cell(2, 1).text_]
        for node in node_names:
            services_statuses = self.get_all_services_statuses()
            node_services = services_statuses[node]
            if service_state:
                for service in service_state:
                    if service_state[service] != node_services[service]:
                        return False
            else:
                # Case when all services of node should be in OK state
                for service in node_services:
                    if node_services[service] != 'OK':
                        return False
        return True

    def wait_service_state_on_nagios(self, service_state=None,
                                     node_names=None):
        msg = ("Fail to get expected service states for services: {0} "
               "on nodes: {1}")
        msg = msg.format(
            [key for key in service_state]
            if service_state is not None else "all",
            node_names if node_names is not None else "global-cluster")

        utils.wait(lambda: self.check_service_state_on_nagios(
            service_state, node_names), timeout=60 * 5,
            timeout_msg=msg)
