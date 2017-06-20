import pytest


def idfy_name(name):
    return name.lower().replace(" ", "-").replace("(", "").replace(")", "")


def get_all_grafana_dashboards_names():
    dashboards = {
        "Cinder (via Prometheus)": "cinder",
        "Elasticsearch": "elasticsearch",
        "Etcd": "etcd",
        "MySQL": "galera.master",
        "Glance": "glance",
        "HAProxy": "haproxy",
        "Keystone": "keystone",
        "Calico cluster monitoring (via Prometheus)": "kubernetes",
        "Kubernetes App Metrics": "kubernetes",
        "Kubernetes cluster monitoring (via Prometheus)": "kubernetes",
        "System": "linux",
        "Neutron": "service.neutron.control.cluster",
        "Hypervisor": "service.nova.compute.kvm",
        "Nova": "nova",
        "Prometheus Performances": "prometheus",
    }

    not_ready_dashboards = {
        "Cassandra": "",
        "Grafana": "grafana",
        "Heat": "heat",
        "InfluxDB": "influxdb",
        "Kibana": "kibana",
        "Memcached": "memcached",
        "Nginx": "nginx",
        "OpenContrail": "",
        "RabbitMQ": "rabbitmq",
        "GlusterFS": "glusterfs",
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
    fail_msg = (
        "Total OK: {len_ok}\n"
        "No table: {no_table}\n"
        "Total no table: {len_no}\n"
        "Partially ok queries: {partially_ok}\n"
        "Total partially ok: {len_partially_ok}\n"
        "Failed queries: {failed}\n"
        "Total failed: {len_fail}".format(
            len_ok=len(ok_panels),
            partially_ok=partially_ok_panels.items(),
            len_partially_ok=len(partially_ok_panels),
            no_table=no_table_panels.items(),
            len_no=len(no_table_panels),
            failed=failed_panels.items(),
            len_fail=len(failed_panels))
    )
    assert (ok_panels and not
            partially_ok_panels and not
            no_table_panels and not
            failed_panels), fail_msg
