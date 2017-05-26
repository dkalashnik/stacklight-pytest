import logging
import pytest

from stacklight_tests import utils

logger = logging.getLogger(__name__)


class TestPrometheusMetrics(object):
    def test_k8s_metrics(self, cluster, prometheus_api):
        nodes = cluster.filter_by_role("kubernetes")
        expected_hostnames = [node.fqdn.split(".")[0] for node in nodes]
        unexpected_hostnames = []

        metrics = prometheus_api.get_query("kubelet_running_pod_count")

        for metric in metrics:
            hostname = metric["metric"]["instance"]
            try:
                expected_hostnames.remove(hostname)
            except ValueError:
                unexpected_hostnames.append(hostname)
        assert unexpected_hostnames == []
        assert expected_hostnames == []

    def test_etcd_metrics(self, cluster, prometheus_api):
        nodes = cluster.filter_by_role("etcd")
        expected_hostnames = [node.address for node in nodes]
        unexpected_hostnames = []

        metrics = prometheus_api.get_query("etcd_server_has_leader")

        for metric in metrics:
            hostname = metric["metric"]["instance"].split(":")[0]
            try:
                expected_hostnames.remove(hostname)
            except ValueError:
                unexpected_hostnames.append(hostname)
        assert unexpected_hostnames == []
        assert expected_hostnames == []

    def test_telegraf_metrics(self, cluster, prometheus_api):
        nodes = cluster.filter_by_role("telegraf")
        expected_hostnames = [node.fqdn.split(".")[0] for node in nodes]
        unexpected_hostnames = []

        metrics = prometheus_api.get_query("system_uptime")

        for metric in metrics:
            hostname = metric["metric"]["host"]
            try:
                expected_hostnames.remove(hostname)
            except ValueError:
                unexpected_hostnames.append(hostname)
        assert unexpected_hostnames == []
        assert expected_hostnames == []

    def test_prometheus_metrics(self, prometheus_api):
        metric = prometheus_api.get_query(
            "prometheus_local_storage_series_ops_total")
        assert len(metric) != 0


class TestTelegrafMetrics(object):
    target_metrics = {
        "cpu": ['cpu_usage_system', 'cpu_usage_softirq', 'cpu_usage_steal',
                'cpu_usage_user', 'cpu_usage_irq', 'cpu_usage_idle',
                'cpu_usage_guest_nice', 'cpu_usage_iowait', 'cpu_usage_nice',
                'cpu_usage_guest'],
        "mem": ['mem_free', 'mem_inactive', 'mem_active', 'mem_used',
                'mem_available_percent', 'mem_cached', 'mem_buffered',
                'mem_available', 'mem_total', 'mem_used_percent'],
        "system_load": ['system_load15', 'system_load1', 'system_load5'],
        "disk": ['diskio_io_time', 'diskio_reads', 'diskio_writes',
                 'disk_inodes_total', 'disk_used_percent',
                 'diskio_read_bytes', 'disk_free', 'disk_inodes_used',
                 'disk_used', 'diskio_write_time', 'diskio_write_bytes',
                 'diskio_iops_in_progress', 'disk_inodes_free',
                 'diskio_read_time', 'disk_total']
    }

    @pytest.mark.parametrize("target,metrics", target_metrics.items(),
                             ids=target_metrics.keys())
    def test_system_metrics(self, prometheus_api, target, metrics):
        def _verify_notifications(expected_list, query):
            output = prometheus_api.get_query(query)
            got_metrics = set([metric["metric"]["__name__"]
                               for metric in output])
            delta = set(expected_list) - got_metrics
            if delta:
                logger.info("{} metric(s) not found in {}".format(
                    delta, got_metrics))
                return False
            return True

        logger.info("Waiting to get all metrics")
        msg = "Timed out waiting to get all metrics"
        utils.wait(
            lambda: _verify_notifications(
                metrics, '{'+'__name__=~"^{}.*"'.format(target)+'}'),
            timeout=5 * 60, interval=10, timeout_msg=msg)
