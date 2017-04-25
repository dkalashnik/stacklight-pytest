from stacklight_tests.tests.prometheus import base_test


class TestPrometheusSmoke(base_test.BaseLMAPrometheusTest):
    def test_prometheus_container(self):
        prometheus_nodes = self.cluster.filter_by_role("prometheus")

        def test_prometheus_container_up(node):
            status = node.exec_command(
                "docker ps --filter ancestor=prometheus "
                "--format '{{.Status}}'")
            return "Up" in status

        assert any([test_prometheus_container_up(node)
                    for node in prometheus_nodes])
