import pytest


def check_service_installed(cluster, name, role=None):
    """Checks that service is installed on nodes with provided role."""
    if role is None:
        role = "monitoring"
    nodes = cluster.filter_by_role(role)
    for node in nodes:
        node.os.check_package_installed(name)


def check_service_running(cluster, name, role=None):
    """Checks that service is running on nodes with provided role."""
    if role is None:
        role = "monitoring"
    nodes = cluster.filter_by_role(role)
    for node in nodes:
        node.os.manage_service(name, "status")


class TestInfluxDbSmoke(object):

    def test_influxdb_installed(self, cluster, influxdb_client):
        """Smoke test that checks basic features of InfluxDb.

        Scenario:
            1. Check InfluxDB package is installed
            2. Check InfluxDB is up and running
            3. Check that InfluxDB is online and can serve requests

        Duration 1m
        """
        service = "influxdb"
        check_service_installed(cluster, service)
        check_service_running(cluster, service)
        influxdb_client.check_influxdb_online()

    def test_influxdb_relay_installed(self, cluster):
        """Smoke test that checks basic features of InfluxDb.

        Scenario:
            1. Check InfluxDB relay package is installed
            2. Check InfluxDB relay is up and running

        Duration 1m
        """
        service = "influxdb-relay"
        check_service_installed(cluster, service)
        check_service_running(cluster, service)
