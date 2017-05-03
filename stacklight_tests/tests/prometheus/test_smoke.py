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
