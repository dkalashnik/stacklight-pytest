from stacklight_tests.tests.prometheus import base_test


class TestPrometheusMetrics(base_test.BaseLMATest):
    def test_k8s_metrics(self):
        nodes = self.cluster.filter_by_role("kubernetes")
        expected_hostnames = [node.fqdn.split(".")[0] for node in nodes]
        unexpected_hostnames = []

        metrics = self.prometheus_api.get_query("kubelet_running_pod_count")

        for metric in metrics:
            hostname = metric["metric"]["instance"]
            try:
                expected_hostnames.remove(hostname)
            except ValueError:
                unexpected_hostnames.append(hostname)
        assert unexpected_hostnames == []
        assert expected_hostnames == []

    def test_etcd_metrics(self):
        nodes = self.cluster.filter_by_role("etcd")
        expected_hostnames = [node.address for node in nodes]
        unexpected_hostnames = []

        metrics = self.prometheus_api.get_query("etcd_server_has_leader")

        for metric in metrics:
            hostname = metric["metric"]["instance"].split(":")[0]
            try:
                expected_hostnames.remove(hostname)
            except ValueError:
                unexpected_hostnames.append(hostname)
        assert unexpected_hostnames == []
        assert expected_hostnames == []

    def test_telegraf_metrics(self):
        nodes = self.cluster.filter_by_role("telegraf")
        expected_hostnames = [node.fqdn.split(".")[0] for node in nodes]
        unexpected_hostnames = []

        metrics = self.prometheus_api.get_query("system_uptime")

        for metric in metrics:
            hostname = metric["metric"]["host"]
            try:
                expected_hostnames.remove(hostname)
            except ValueError:
                unexpected_hostnames.append(hostname)
        assert unexpected_hostnames == []
        assert expected_hostnames == []

    def test_prometheus_metrics(self):
        metric = self.prometheus_api.get_query("prometheus_local_storage_series_ops_total")
        assert len(metric) != 0
