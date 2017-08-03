import pytest
from prettytable import PrettyTable


def idfy_name(name):
    return name.lower().replace(" ", "-").replace("(", "").replace(")", "")


def query_dict_to_string(query_dict):
    return "\n\n".join(
        [panel + "\n" + query for panel, query in query_dict.items()])


def get_all_grafana_dashboards_names():
    dashboards = {
        "Apache": "apache",
        "Cassandra": "opencontrail",
        "Calico cluster monitoring (via Prometheus)": "kubernetes",
        "Cinder": "cinder",
        "Docker": "docker",
        "Elasticsearch": "elasticsearch",
        "Etcd": "etcd",
        "Glance": "glance",
        "GlusterFS": "glusterfs",
        "HAProxy": "haproxy",
        "Hypervisor": "service.nova.compute.kvm",
        "Heat": "heat",
        "InfluxDB": "influxdb",
        "Keystone": "keystone",
        "Kibana": "kibana",
        "Kubernetes App Metrics": "kubernetes",
        "Kubernetes cluster monitoring (via Prometheus)": "kubernetes",
        "Memcached": "memcached",
        "MySQL": "galera.master",
        "Neutron": "service.neutron.control.cluster",
        "Nova": "nova",
        "Nginx": "nginx",
        "OpenContrail": "opencontrail",
        "Prometheus Performances": "prometheus",
        "RabbitMQ": "rabbitmq",
        "System": "linux",
        "Remote storage adapter": "influxdb",
        "Grafana": "grafana",
    }

    return {idfy_name(k): v for k, v in dashboards.items()}


@pytest.fixture(scope="module",
                params=get_all_grafana_dashboards_names().items(),
                ids=get_all_grafana_dashboards_names().keys())
def dashboard_fixture(request, cluster):
    dash_name, requirement = request.param

    if not any([requirement in node.roles for node in cluster]):
        pytest.skip("No required class {} for dashboard: {}".format(
            requirement, dash_name))

    return dash_name


def test_grafana_dashboard_panel_queries(dashboard_fixture, grafana_client):
    """Verify that the panels on dashboards show up in the Grafana UI.

    Scenario:
        1. Check queries for all panels of given dashboard in Grafana.

    Duration 5m
    """
    datasource = "prometheus"
    dashboard_name = dashboard_fixture
    grafana_client.check_grafana_online()
    dashboard = grafana_client.get_dashboard(dashboard_name, datasource)
    result = dashboard.classify_all_dashboard_queries()
    ok_panels, partially_ok_panels, no_table_panels, failed_panels = result

    fail_dict = {
        "Total OK": len(ok_panels),
        "No table": query_dict_to_string(no_table_panels),
        "Total no table": len(no_table_panels),
        "Partially OK queries": query_dict_to_string(partially_ok_panels),
        "Total partially OK": len(partially_ok_panels),
        "Failed queries": query_dict_to_string(failed_panels),
        "Total failed": len(failed_panels),
    }

    fail_msg = (
        "Total OK: {Total OK}\n"
        "No table: {No table}\n"
        "Total no table: {Total no table}\n"
        "Partially OK queries: {Partially OK queries}\n"
        "Total partially OK: {Total partially OK}\n"
        "Failed queries: {Failed queries}\n"
        "Total failed: {Total failed}".format(
            **fail_dict))

    fail_table = PrettyTable(["Name", "Value"])
    fail_table.align["Value"] = "l"
    fail_table.align["Name"] = "l"

    for name, value in fail_dict.items():
        fail_table.add_row([name, value])

    assert (ok_panels and not
            partially_ok_panels and not
            no_table_panels and not
            failed_panels), fail_table
