import socket


class TestPrometheusSmoke(object):
    def test_prometheus_container(self, cluster):
        prometheus_nodes = cluster.filter_by_role("prometheus")

        def test_prometheus_container_up(node):
            status = node.exec_command(
                "docker ps --filter ancestor=prometheus "
                "--format '{{.Status}}'")
            return "Up" in status

        assert any([test_prometheus_container_up(node)
                    for node in prometheus_nodes])


class TestAlertmanagerSmoke(object):
    def test_alertmanager_endpoint_availability(self, cluster, prometheus_config):
        """Check that alertmanager endpoint is available.

        Scenario:
            1. Get alertmanager endpoint
            2. Check that alertmanager endpoint is available
        Duration 1m
        """
        port = int(prometheus_config["prometheus_alertmanager"])
        cfg = [host for host in cluster.hosts
               if host.fqdn.startswith("cfg")][0].address
        try:
            s = socket.socket()
            s.connect((cfg, port))
            s.close()
            result = True
        except socket.error:
            result = False
        assert result
