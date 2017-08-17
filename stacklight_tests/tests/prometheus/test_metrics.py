import logging
import pytest

from stacklight_tests import utils

logger = logging.getLogger(__name__)


class TestMetrics(object):
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
                 'diskio_read_time', 'disk_total'],
        "swap": ['swap_free', 'swap_in', 'swap_out', 'swap_total', 'swap_used',
                 'swap_used_percent'],
        "processes": ['processes_blocked', 'processes_paging',
                      'processes_running', 'processes_sleeping',
                      'processes_stopped', 'processes_total',
                      'processes_total_threads', 'processes_unknown',
                      'processes_zombies'],
        "kernel": ['kernel_boot_time', 'kernel_context_switches',
                   'kernel_interrupts', 'kernel_processes_forked']
    }

    def verify_notifications(self, prometheus_api, expected_list, query):
            output = prometheus_api.get_query(query)
            got_metrics = set([metric["metric"]["__name__"]
                               for metric in output])
            delta = set(expected_list) - got_metrics
            if delta:
                logger.info("{} metric(s) not found in {}".format(
                    delta, got_metrics))
                return False
            return True

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

    @pytest.mark.parametrize("target,metrics", target_metrics.items(),
                             ids=target_metrics.keys())
    def test_system_metrics(self, prometheus_api, cluster, target, metrics):
        expected_hostnames = [h.hostname for h in cluster.hosts]
        for hostname in expected_hostnames:
            q = ('{{__name__=~"^{}.*", host="{}"}}'.format(target, hostname))
            logger.info("Waiting to get all metrics")
            msg = "Timed out waiting to get all metrics"
            utils.wait(
                lambda: self.verify_notifications(prometheus_api, metrics, q),
                timeout=5 * 60, interval=10, timeout_msg=msg)

    def test_k8s_metrics(self, cluster, prometheus_api):
        nodes = cluster.filter_by_role("kubernetes")

        if not nodes:
            pytest.skip("There are no kubernetes nodes in the cluster")

        metrics = [
            'kubelet_runtime_operations_latency_microseconds_count',
            'kubelet_runtime_operations_latency_microseconds',
            'kubelet_containers_per_pod_count_sum',
            'kubelet_running_pod_count', 'kubernetes_build_info',
            'kubelet_pod_start_latency_microseconds_count',
            'kubelet_sync_pods_latency_microseconds',
            'kubelet_pleg_relist_latency_microseconds_count',
            'kubelet_generate_pod_status_latency_microseconds_sum',
            'kubelet_containers_per_pod_count_count',
            'kubelet_pod_start_latency_microseconds_sum',
            'kubelet_pod_worker_start_latency_microseconds',
            'kubelet_containers_per_pod_count', 'kubelet_runtime_operations',
            'kubelet_sync_pods_latency_microseconds_count',
            'kubelet_sync_pods_latency_microseconds_sum',
            'kubelet_running_container_count',
            'kubelet_pleg_relist_interval_microseconds',
            'kubelet_generate_pod_status_latency_microseconds',
            'kubelet_cgroup_manager_latency_microseconds',
            'kubelet_pleg_relist_interval_microseconds_sum',
            'kubelet_pod_worker_start_latency_microseconds_count',
            'kubelet_pod_worker_start_latency_microseconds_sum',
            'kubelet_pleg_relist_interval_microseconds_count',
            'kubelet_pleg_relist_latency_microseconds_sum',
            'kubelet_cgroup_manager_latency_microseconds_count',
            'kubelet_generate_pod_status_latency_microseconds_count',
            'kubelet_pleg_relist_latency_microseconds',
            'kubelet_pod_start_latency_microseconds',
            'kubelet_runtime_operations_latency_microseconds_sum',
            'kubelet_cgroup_manager_latency_microseconds_sum'
        ]
        expected_hostnames = [node.hostname for node in nodes]

        for hostname in expected_hostnames:
            q = ('{{__name__=~"^kube.*", host="{}"}}'.format(hostname))
            logger.info("Waiting to get all metrics")
            msg = "Timed out waiting to get all metrics"
            utils.wait(
                lambda: self.verify_notifications(prometheus_api, metrics, q),
                timeout=5 * 60, interval=10, timeout_msg=msg)

    def test_mysql_metrics(self, cluster):
        mysql_hosts = cluster.filter_by_role("galera")
        expected_metrics = [
            'mysql_wsrep_connected', 'mysql_wsrep_local_cert_failures',
            'mysql_wsrep_local_commits', 'mysql_wsrep_local_send_queue',
            'mysql_wsrep_ready', 'mysql_wsrep_received',
            'mysql_wsrep_received_bytes', 'mysql_wsrep_replicated',
            'mysql_wsrep_replicated_bytes', 'mysql_wsrep_cluster_size',
            'mysql_wsrep_cluster_status', 'mysql_table_locks_immediate',
            'mysql_table_locks_waited', 'mysql_slow_queries',
            'mysql_threads_cached', 'mysql_threads_connected',
            'mysql_threads_created', 'mysql_threads_running'
        ]

        postfixes = [
            'admin_commands', 'alter_db', 'alter_table', 'begin',
            'call_procedure', 'change_db', 'check', 'commit', 'create_db',
            'create_index', 'create_procedure', 'create_table', 'create_user',
            'dealloc_sql', 'delete', 'drop_db', 'drop_index', 'drop_procedure',
            'drop_table', 'execute_sql', 'flush', 'grant', 'insert',
            'insert_select', 'prepare_sql', 'release_savepoint', 'rollback',
            'savepoint', 'select', 'set_option', 'show_collations',
            'show_create_table', 'show_databases', 'show_fields',
            'show_grants', 'show_master_status', 'show_status',
            'show_table_status', 'show_tables', 'show_variables',
            'show_warnings', 'unlock_tables', 'update'
        ]

        handlers = [
            'commit', 'delete', 'external_lock', 'prepare', 'read_first',
            'read_key', 'read_next', 'read_rnd', 'read_rnd_next', 'rollback',
            'savepoint', 'update', 'write'
        ]

        for postfix in postfixes:
            expected_metrics.append("mysql_commands_{}".format(postfix))
        for handler in handlers:
            expected_metrics.append("mysql_handler_{}".format(handler))

        for host in mysql_hosts:
            got_metrics = host.os.exec_command(
                "curl -s localhost:9126/metrics | awk '/^mysql/{print $1}'")
            hostname = host.hostname
            for metric in expected_metrics:
                metric = metric + '{host="' + hostname + '"}'
                err_msg = ("Metric {} not found in received list of mysql "
                           "metrics on {} node".format(metric, hostname))
                assert metric in got_metrics, err_msg
