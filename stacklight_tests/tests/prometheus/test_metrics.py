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
                metrics, '{' + '__name__=~"^{}.*"'.format(target) + '}'),
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
        err_count_msg = "Incorrect image count in metric {}".format(
            count_query)
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

    def test_neutron_metrics(self, prometheus_api, os_clients):
        client = os_clients.network
        net_count = len(client.list_networks()["networks"])
        net_query = '{__name__="openstack_neutron_networks_total"}'
        net_err_msg = "Incorrect net count in metric {}".format(net_query)
        self.check_openstack_metrics(
            prometheus_api, net_query, net_count, net_err_msg)

        subnet_count = len(client.list_subnets()["subnets"])
        subnet_query = '{__name__="openstack_neutron_subnets_total"}'
        subnet_err_msg = "Incorrect subnet count in metric {}".format(
            subnet_query)
        self.check_openstack_metrics(
            prometheus_api, subnet_query, subnet_count, subnet_err_msg)

        flip_count = len(client.list_floatingips()["floatingips"])
        flip_query = '{__name__="openstack_neutron_floatingips_total"}'
        flip_err_msg = "Incorrect floating ip count in metric {}".format(
            flip_query)
        self.check_openstack_metrics(
            prometheus_api, flip_query, flip_count, flip_err_msg)

        router_count = len(client.list_routers()["routers"])
        router_query = '{__name__="openstack_neutron_routers_total"}'
        router_err_msg = "Incorrect router count in metric {}".format(
            router_query)
        self.check_openstack_metrics(
            prometheus_api, router_query, router_count, router_err_msg)

        active_router_count = len(filter(lambda x: x["status"] == "ACTIVE",
                                         client.list_routers()["routers"]))
        active_router_query = 'openstack_neutron_routers{state="active"}'
        active_router_err_msg = ("Incorrect active router count in metric "
                                 "{}".format(active_router_query))
        self.check_openstack_metrics(
            prometheus_api, active_router_query, active_router_count,
            active_router_err_msg)

        port_count = len(client.list_ports()["ports"])
        port_query = '{__name__="openstack_neutron_ports_total"}'
        port_err_msg = ("Incorrect port count in metric {}".format(port_query))
        self.check_openstack_metrics(
            prometheus_api, port_query, port_count, port_err_msg)

    def test_cinder_metrics(self, destructive, prometheus_api, os_clients):
        volume_name = utils.rand_name("volume-")
        client = os_clients.volume
        volume = client.volumes.create(size=1, name=volume_name)
        wait_for_resource_status(client.volumes, volume.id, "error")
        destructive.append(lambda: client.volume.delete(volume))

        volumes_count = len([vol for vol in client.volumes.list()])
        volumes_size = sum([vol.size for vol in client.volumes.list()]) * 10**9

        count_query = ('{__name__="openstack_cinder_volumes",'
                       'status="error"}')
        err_count_msg = "Incorrect volume count in metric {}".format(
            count_query)
        self.check_openstack_metrics(
            prometheus_api, count_query, volumes_count, err_count_msg)

        size_query = ('{__name__="openstack_cinder_volumes_size",'
                      'status="error"}')
        error_size_msg = "Incorrect volume size in metric {}".format(
            size_query)
        self.check_openstack_metrics(
            prometheus_api, size_query, volumes_size, error_size_msg)

        client.volumes.delete(volume)
        utils.wait(
            lambda: (volume.id not in [v.id for v in client.volumes.list()])
        )

    def test_nova_telegraf_metrics(self, prometheus_api, os_clients):
        client = os_clients.compute

        def get_servers_count(st):
            return len(filter(
                lambda x: x.status == st, client.servers.list()))

        err_msg = "Incorrect servers count in metric {}"
        for status in ["active", "error"]:
            q1 = '{' + '__name__="openstack_nova_instances_{}"'.format(
                status) + '}'
            q2 = 'openstack_nova_{}'.format(status)
            q3 = 'openstack_nova_instances{' + 'state="{}"'.format(
                status) + '}'
            self.check_openstack_metrics(
                prometheus_api, q1, get_servers_count(status.upper()),
                err_msg.format(q1))
            self.check_openstack_metrics(
                prometheus_api, q2, get_servers_count(status.upper()),
                err_msg.format(q2))
            self.check_openstack_metrics(
                prometheus_api, q3, get_servers_count(status.upper()),
                err_msg.format(q3))

    def test_nova_services_metrics(self, prometheus_api, cluster):
        controllers = filter(lambda x: "controller" in x.roles, cluster.hosts)
        computes = filter(lambda x: "compute" in x.roles, cluster.hosts)
        controller_services = ["nova-cert", "nova-conductor",
                               "nova-consoleauth", "nova-scheduler"]
        compute_services = ["nova-compute"]
        err_service_msg = "Service {} is down on the {} node"
        for controller in controllers:
            for service in controller_services:
                q = 'hostname="{}",service="{}"'.format(
                    controller.hostname, service)
                self.check_openstack_metrics(
                    prometheus_api,
                    'openstack_nova_service{' + q + ',state="up"}',
                    0, err_service_msg.format(service, controller.hostname))
        for compute in computes:
            for service in compute_services:
                q = 'hostname="{}",service="{}"'.format(
                    compute.hostname, service)
                self.check_openstack_metrics(
                    prometheus_api,
                    'openstack_nova_service{' + q + ',state="up"}',
                    0, err_service_msg.format(service, compute.hostname))

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
