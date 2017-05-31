import logging
import pytest

from stacklight_tests import utils
from stacklight_tests.tests.test_functional import wait_for_resource_status

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

    def check_openstack_metrics(self, prometheus_api, query, value, msg):
        def _verify_notifications(q, v):
            output = prometheus_api.get_query(q)
            logger.info("Check {} in {}".format(v, output))
            return v in output[0]["value"]
        utils.wait(
            lambda: _verify_notifications(query, str(value)),
            interval=10, timeout=2 * 60, timeout_msg=msg
        )

    def test_glance_metrics(self, destructive, prometheus_api, os_clients):
        image_name = utils.rand_name("image-")
        client = os_clients.image
        image = client.images.create(
            name=image_name,
            container_format="bare",
            disk_format="raw",
            visibility="public")
        client.images.upload(image.id, "dummy_data")
        wait_for_resource_status(client.images, image.id, "active")
        destructive.append(lambda: client.images.delete(image.id))

        images_count = len([im for im in client.images.list()])
        images_size = sum([im["size"] for im in client.images.list()])

        count_query = ('{__name__="openstack_glance_images",'
                       'visibility="public",status="active"}')
        err_count_msg = "Incorrect image count in metric {}".format(count_query)
        self.check_openstack_metrics(
            prometheus_api, count_query, images_count, err_count_msg)

        size_query = ('{__name__="openstack_glance_images_size",'
                      'visibility="public", status="active"}')
        error_size_msg = "Incorrect image size in metric {}".format(size_query)
        self.check_openstack_metrics(
            prometheus_api, size_query, images_size, error_size_msg)

        client.images.delete(image.id)
        utils.wait(
            lambda: (image.id not in [im["id"] for im in client.images.list()])
        )

    def test_keystone_metrics(self, prometheus_api, os_clients):
        client = os_clients.auth

        tenants = client.tenants.list()
        tenants_query = '{__name__="openstack_keystone_tenants_total"}'
        self.check_openstack_metrics(
            prometheus_api, tenants_query, len(tenants),
            "Incorrect tenant count in metric {}".format(tenants_query))
        enabled_tenants_query = 'openstack_keystone_tenants{state="enabled"}'
        self.check_openstack_metrics(
            prometheus_api, enabled_tenants_query,
            len(filter(lambda x: x.enabled, tenants)),
            "Incorrect enabled tenant count in metric {}".format(
                enabled_tenants_query))
        disabled_tenants_query = 'openstack_keystone_tenants{state="disabled"}'
        self.check_openstack_metrics(
            prometheus_api, disabled_tenants_query,
            len(filter(lambda x: not x.enabled, tenants)),
            "Incorrect disabled tenant count in metric {}".format(
                disabled_tenants_query))

        roles_count = len(client.roles.list())
        roles_query = '{__name__="openstack_keystone_roles_roles"}'
        err_roles_count_msg = ("Incorrect roles count in "
                               "metric {}".format(roles_query))
        self.check_openstack_metrics(prometheus_api, roles_query,
                                     roles_count, err_roles_count_msg)

        users = client.users.list()
        users_query = '{__name__="openstack_keystone_users_total"}'
        self.check_openstack_metrics(
            prometheus_api, users_query, len(users),
            "Incorrect user count in metric {}".format(users_query))

        enabled_users_query = 'openstack_keystone_users{state="enabled"}'
        self.check_openstack_metrics(
            prometheus_api, enabled_users_query,
            len(filter(lambda x: x.enabled, users)),
            "Incorrect enabled user count in metric {}".format(
                enabled_users_query))
        disabled_users_query = 'openstack_keystone_users{state="disabled"}'
        self.check_openstack_metrics(
            prometheus_api, disabled_users_query,
            len(filter(lambda x: not x.enabled, users)),
            "Incorrect disabled user count in metric {}".format(
                disabled_users_query))
