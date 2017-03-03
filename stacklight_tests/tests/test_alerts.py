from __future__ import print_function

import contextlib
import functools
import logging
import time

import pika
import pytest

from stacklight_tests import custom_exceptions
from stacklight_tests.tests import base_test
from stacklight_tests import utils


logger = logging.getLogger(__name__)


rabbitmq_alarms = {
    'memory': {
        'warning': (base_test.BaseLMATest.RABBITMQ_MEMORY_WARNING_VALUE,
                    base_test.BaseLMATest.WARNING_STATUS),
        'critical': (base_test.BaseLMATest.RABBITMQ_MEMORY_CRITICAL_VALUE,
                     base_test.BaseLMATest.CRITICAL_STATUS)
    },
    'disk': {
        'warning': (base_test.BaseLMATest.RABBITMQ_DISK_WARNING_PERCENT,
                    base_test.BaseLMATest.WARNING_STATUS),
        'critical': (base_test.BaseLMATest.RABBITMQ_DISK_CRITICAL_PERCENT,
                     base_test.BaseLMATest.CRITICAL_STATUS),
    }
}

log_http_errors_entities = {
    'nova':
        ('nova', 'compute.servers.list', 'nova_logs', 'nova_api_http_errors'),
    'keystone':
        ('keystone', 'auth.users.list',
         'keystone_logs',
         'keystone_public_api_http_errors',
         'keystone_admin_api_http_errors'),
    'neutron':
        ('neutron', 'network.list_networks',
         'neutron_logs_control', 'neutron_api_http_errors'),
    'cinder':
        ('cinder', 'volume.volumes.list',
         'cinder_logs', 'cinder_api_http_errors'),
    'glance':
        ('glance', 'image.images.list',
         'glance_logs', 'glance_api_http_errors'),
    'heat':
        ('heat', 'orchestration.stacks.list',
         'heat_logs', 'heat_api_http_errors'),
}


def determinate_services():
    env_type = utils.load_config().get("env", {}).get("type", "")
    services_checks = {
        'libvirtd': 'libvirt_check',
        'rabbitmq-server': 'rabbitmq_check',
        'memcached': 'memcached_check',
        'mysql': 'mysql_check'
    }
    if not env_type == 'mk':
        services_checks['apache2'] = 'apache_check'

    return {service: (service, check)
            for service, check in services_checks.items()}


class TestAlerts(base_test.BaseLMATest):
    @pytest.mark.parametrize(
        "levels",
        (rabbitmq_alarms["disk"].values()), ids=rabbitmq_alarms["disk"].keys())
    def test_check_rabbitmq_disk_alarm(self, levels):
        """Check that rabbitmq-disk-limit-warning and
           rabbitmq-disk-limit-critical alarms work as expected.

        Scenario:
            1. Check the last value of the okay alarm in InfluxDB.
            2. Set RabbitMQ disk limit to 99.99 percent of available space.
            3. Check the last value of the warning alarm in InfluxDB.
            4. Set RabbitMQ disk limit to the default value.
            5. Check the last value of the okay alarm in InfluxDB.
            6. Set RabbitMQ disk limit to 100 percent of available space.
            7. Check the last value of the critical alarm in InfluxDB.
            8. Set RabbitMQ disk limit to the default value.
            9. Check the last value of the okay alarm in InfluxDB.

        Duration 10m
        """
        controller = self.cluster.get_random_controller()
        percent, status = levels

        if not self.is_mk:
            volume = "/dev/dm-"
            source = "disk"
        else:
            volume = "/dev/vda"
            source = "rabbitmq_server_disk"
        check_alarm = self.get_generic_alarm_checker(
            controller, source, "rabbitmq-cluster", alarm_type="service")

        check_alarm(value=self.OKAY_STATUS)

        default_value = controller.check_call(
            "rabbitmqctl environment | grep disk_free_limit | "
            "sed -r 's/}.+//' | sed 's|.*,||'")[1]

        self.destructive_actions.append(lambda: controller.check_call(
            "rabbitmqctl set_disk_free_limit {}".format(default_value)))
        cmd = ("rabbitmqctl set_disk_free_limit $"
               "(df | grep {volume} | "
               "awk '{{ printf(\"%.0f\\n\", 1024 * ((($3 + $4) * "
               "{percent} / 100) - $3))}}')")
        controller.check_call(
            cmd.format(volume=volume, percent=percent))

        check_alarm(value=status)

        controller.check_call(
            "rabbitmqctl set_disk_free_limit {}".format(default_value))

        check_alarm(value=self.OKAY_STATUS)
        self.destructive_actions = []

    @pytest.mark.parametrize(
        "levels",
        (rabbitmq_alarms["memory"].values()),
        ids=rabbitmq_alarms["memory"].keys())
    def test_check_rabbitmq_memory_alarm(self, levels):
        """Check that rabbitmq-memory-limit-warning and
           rabbitmq-memory-limit-critical alarms work as expected.

        Scenario:
            1. Check the last value of the okay alarm in InfluxDB.
            2. Set RabbitMQ memory limit to 101 percent of currently
            used memory.
            3. Check the last value of the warning alarm in InfluxDB.
            4. Set RabbitMQ memory limit to the default value.
            5. Check the last value of the okay alarm in InfluxDB.
            6. Set RabbitMQ memory limit to 100.01 percent of currently
            used memory.
            7. Check the last value of the critical alarm in InfluxDB.
            8. Set RabbitMQ memory limit to the default value.
            9. Check the last value of the okay alarm in InfluxDB.

        Duration 10m
        """
        controller = self.cluster.get_random_controller()
        ratio, status = levels

        source = "memory" if not self.is_mk else "rabbitmq_server_memory"
        check_alarm = self.get_generic_alarm_checker(
            controller, source, "rabbitmq-cluster", alarm_type="service")

        check_alarm(value=self.OKAY_STATUS)
        default_value = controller.check_call(
            "rabbitmqctl environment | grep vm_memory_high_watermark, | "
            "sed -r 's/}.+//' | sed 's|.*,||'")[1]
        mem_usage = self.influxdb_api.get_rabbitmq_memory_usage(controller)

        cmd = (
            'rabbitmqctl '
            'set_vm_memory_high_watermark absolute "{memory}"'.format(
                memory=int(mem_usage * ratio),
            ))
        self.destructive_actions.append(
            lambda: controller.os.check_call(
                "rabbitmqctl set_vm_memory_high_watermark {}".format(
                    default_value)))
        controller.check_call(cmd)
        check_alarm(value=status)

        controller.os.check_call(
            "rabbitmqctl set_vm_memory_high_watermark {}".format(default_value)
        )
        check_alarm(value=self.OKAY_STATUS)
        self.destructive_actions = []

    def test_check_root_fs_alarms(self):
        """Check that root-fs-warning and root-fs-critical alarms work as
           expected.

        Scenario:
            1. Fill up root filesystem to 91 percent.
            2. Check the last value of the warning alarm in InfluxDB.
            3. Clean the filesystem.
            4. Fill up root filesystem to 96 percent.
            5. Check the last value of the critical alarm in InfluxDB.
            6. Clean the filesystem.

        Duration 10m
        """
        compute = self.cluster.get_random_compute()
        alarm_name = (
            "root-fs" if not self.is_mk else "linux_system_root_fs")
        filename = "/bigfile"
        filesystem = "/$"

        check_alarm = self.get_generic_alarm_checker(
            node=compute, source=alarm_name, node_role="compute")

        check_alarm(value=self.OKAY_STATUS)

        compute.os.fill_up_filesystem(
            filesystem, self.WARNING_PERCENT, filename)
        logger.info("Checking {}-warning alarm".format(alarm_name))
        check_alarm(value=self.WARNING_STATUS)

        compute.os.clean_filesystem(filename)
        check_alarm(value=self.OKAY_STATUS)

        compute.os.fill_up_filesystem(
            filesystem, self.CRITICAL_PERCENT, filename)
        logger.info("Checking {}-critical alarm".format(alarm_name))
        check_alarm(value=self.CRITICAL_STATUS)

        compute.os.clean_filesystem(filename)
        check_alarm(value=self.OKAY_STATUS)

    @contextlib.contextmanager
    def make_logical_db_unavailable(self, db_name, controller):
        """Context manager that renames all tables in provided database
           to make it unavailable and renames it back on exit.

        :param db_name: logical database name
        :type db_name: str
        :param controller: controller with MySQL database
        :type controller: nailgun node
        :returns: None, works as context manager
        """
        creds = ''
        if self.is_mk:
            user = self.config['auth'].get('mysql_user', '')
            password = self.config['auth'].get('mysql_password', '')
            creds = '-u{user}  -p{password}'.format(
                user=user, password=password)
        cmd = (
            "mysql -AN {creds} -e "
            "\"select concat("
            "'rename table {db_name}.', table_name, ' "
            "to {db_name}.' , {method}(table_name) , ';') "
            "from information_schema.tables "
            "where table_schema = '{db_name}';"
            "\" | mysql {creds} ")

        controller.os.check_call(
            cmd.format(db_name=db_name, method='upper', creds=creds))
        try:
            yield
        finally:
            controller.os.check_call(
                cmd.format(db_name=db_name, method='lower', creds=creds))

    @pytest.mark.check_env('is_mk')
    @pytest.mark.parametrize(
        "entities",
        log_http_errors_entities.values(), ids=log_http_errors_entities.keys())
    def test_logs_and_http_errors_alarms(self, entities):
        """Check that nova-logs and nova-api-http-errors alarms work as
           expected.

        Scenario:
            1. Check that the last value of the service-logs
               alarm in InfluxDB is OK.
            2. Check that the last value of the service-api-http-errors alarm
               in InfluxDB is OK.
            3. Rename all service tables to UPPERCASE in DB.
            4. Check the last value of the service-logs
               alarm in InfluxDB is WARN.
            5. Check the last value of the service-api-http-errors alarm
               in InfluxDB is WARN.
            6. Revert all service tables names to lowercase.
            7. Check the last value of the service-logs alarm
               in InfluxDB is OK.
            8. Check the last value of the service-api-http-errors alarm
               in InfluxDB is OK.

        Duration 10m
        """
        controller = self.cluster.filter_by_role("galera.master")[0]
        db_name = entities[0]
        method = entities[1]
        alarm_entities = entities[2:]
        results = {}
        # Pre-check that alarms are not triggered
        for alarm in alarm_entities:
            res = self.influxdb_api.check_mk_alarm(alarm, self.OKAY_STATUS,
                                                   reraise=False)
            results["pre_check_{}".format(alarm)] = res.status

        # Every service is doing some heartbeats/checks,
        # so it is guaranteed to get into failing state
        checked_hosts = {}

        # Determining provoke method
        curr_attr = self.os_clients
        for attr in method.split("."):
            curr_attr = getattr(curr_attr, attr)
        with self.make_logical_db_unavailable(db_name, controller):
            # Run provoke method several times
            for _ in range(20):
                # List conversion is needed by heat and glance list cmd,
                # because it returns generator
                try:
                    list(curr_attr())
                except Exception:
                    # we passing all client errors, because they are expected
                    pass
            for alarm in alarm_entities:
                res = self.influxdb_api.check_mk_alarm(
                    alarm, self.WARNING_STATUS, reraise=False)
                results["check_{}".format(alarm)] = res.status
                checked_hosts[alarm] = res.host

        # Post-check that alarms returned in OK state
        for alarm in alarm_entities:
            res = self.influxdb_api.check_mk_alarm(
                alarm, self.OKAY_STATUS, checked_hosts[alarm], reraise=False)
            results["post_check_{}".format(alarm)] = res.status
        failed_checks = {key for key, value in results.items() if not value}
        assert not failed_checks, (
            "Checks failed: {}".format(", ".join(failed_checks)))

    @pytest.mark.check_env('is_fuel')
    def test_nova_api_logs_errors_alarms_fuel(self):
        """Check that nova-logs-error and nova-api-http-errors alarms work as
           expected.

        Scenario:
            1. Rename all nova tables to UPPERCASE.
            2. Run some nova list command repeatedly.
            3. Check the last value of the nova-logs-error alarm in InfluxDB.
            4. Check the last value of the nova-api-http-errors alarm
               in InfluxDB.
            5. Revert all nova tables names to lowercase.

        Duration 10m
        """
        client = self.os_clients.compute

        def get_servers_list():
            print('get servers')
            try:
                client.servers.list()
            except Exception:
                pass

        controller = self.cluster.get_random_controller()

        with self.make_logical_db_unavailable("nova", controller):
            metrics = {"nova-api": 'http_errors'}
            self.verify_service_alarms(
                get_servers_list, 1, metrics, self.WARNING_STATUS)

    @pytest.mark.check_env('is_fuel')
    def test_neutron_api_logs_errors_alarms_fuel(self):
        """Check that neutron-logs-error and neutron-api-http-errors
           alarms work as expected.

        Scenario:
            1. Rename all neutron tables to UPPERCASE.
            2. Run some neutron agents list command repeatedly.
            3. Check the last value of the neutron-logs-error alarm
               in InfluxDB.
            4. Check the last value of the neutron-api-http-errors alarm
               in InfluxDB.
            5. Revert all neutron tables names to lowercase.

        Duration 10m
        """
        net_client = self.os_clients.network

        def get_agents_list():
            try:
                net_client.list_agents()
            except Exception:
                pass

        controller = self.cluster.get_random_controller()

        with self.make_logical_db_unavailable('neutron', controller):
            metrics = {'neutron-api': 'http_errors'}
            self.verify_service_alarms(
                get_agents_list, 1, metrics, self.WARNING_STATUS)

    @pytest.mark.check_env('is_fuel')
    def test_glance_api_logs_errors_alarms_fuel(self):
        """Check that glance-logs-error and glance-api-http-errors alarms
           work as expected.

        Scenario:
            1. Rename all glance tables to UPPERCASE.
            2. Run some glance image list command repeatedly.
            3. Check the last value of the glance-logs-error alarm
               in InfluxDB.
            4. Check the last value of the glance-api-http-errors alarm
               in InfluxDB.
            5. Revert all glance tables names to lowercase.

        Duration 10m
        """
        image_client = self.os_clients.image

        def get_images_list():
            try:
                # NOTE(rpromyshlennikov): List is needed here
                # because glance image list is lazy method
                return [image for image in image_client.images.list()]
            except Exception:
                pass

        controller = self.cluster.get_random_controller()

        with self.make_logical_db_unavailable('glance', controller):
            metrics = {'glance-api': 'http_errors'}
            self.verify_service_alarms(
                get_images_list, 1, metrics, self.WARNING_STATUS)

    @pytest.mark.check_env('is_fuel')
    def check_heat_api_logs_errors_alarms_fuel(self):
        """Check that heat-logs-error and heat-api-http-errors alarms work as
           expected.

        Scenario:
            1. Rename all heat tables to UPPERCASE.
            2. Run some heat stack list command repeatedly.
            3. Check the last value of the heat-logs-error alarm in InfluxDB.
            4. Check the last value of the heat-api-http-errors alarm
               in InfluxDB.
            5. Revert all heat tables names to lowercase.

        Duration 10m
        """
        controller = self.cluster.get_random_controller()

        def get_stacks_list():
            try:
                cmd = ". openrc && heat stack-list > /dev/null 2>&1"
                controller.os.transport.exec_sync(cmd)
            except Exception:
                pass

        with self.make_logical_db_unavailable('heat', controller):
            metrics = {'heat-api': 'http_errors'}
            self.verify_service_alarms(
                get_stacks_list, 100, metrics, self.WARNING_STATUS)

    @pytest.mark.check_env('is_fuel')
    def test_cinder_api_logs_errors_alarms_fuel(self):
        """Check that cinder-logs-error and cinder-api-http-errors alarms
           work as expected.

        Scenario:
            1. Rename all cinder tables to UPPERCASE.
            2. Run some cinder list command repeatedly.
            3. Check the last value of the cinder-logs-error alarm
               in InfluxDB.
            4. Check the last value of the cinder-api-http-errors alarm
               in InfluxDB.
            5. Revert all cinder tables names to lowercase.

        Duration 10m
        """
        controller = self.cluster.get_random_controller()
        cinder_client = self.os_clients.volume

        def get_volumes_list():
            try:
                return [image for image in cinder_client.images.list()]
            except Exception:
                pass

        with self.make_logical_db_unavailable('cinder', controller):
            metrics = {'cinder-api': 'http_errors'}
            self.verify_service_alarms(
                get_volumes_list, 1, metrics, self.WARNING_STATUS)

    @pytest.mark.check_env('is_fuel')
    def test_keystone_api_logs_errors_alarms_fuel(self):
        """Check that keystone-logs-error, keystone-public-api-http-errors and
           keystone-admin-api-http-errors alarms work as expected.

        Scenario:
            1. Rename all keystone tables to UPPERCASE.
            2. Run some keystone stack list command repeatedly.
            3. Check the last value of the keystone-logs-error alarm
               in InfluxDB.
            4. Check the last value of the keystone-public-api-http-errors
               alarm in InfluxDB.
            5. Check the last value of the keystone-admin-api-http-errors
               alarm in InfluxDB.
            6. Revert all keystone tables names to lowercase.

        Duration 10m
        """
        def get_users_list(level):
            additional_cmds = {
                "user": ("&& export OS_AUTH_URL="
                         "`(echo $OS_AUTH_URL "
                         "| sed 's%:5000/%:5000/v2.0%')` "),
                "admin": ("&& export OS_AUTH_URL="
                          "`(echo $OS_AUTH_URL "
                          "| sed 's%:5000/%:35357/v2.0%')` ")
            }

            def get_users_list_parametrized():
                cmd = (". openrc {additional_cmd} && keystone user-list > "
                       "/dev/null 2>&1"
                       .format(additional_cmd=additional_cmds[level]))
                try:
                    controller.os.transport.exec_sync(cmd)
                except Exception:
                    pass
            return get_users_list_parametrized

        controller = self.cluster.get_random_controller()

        with self.make_logical_db_unavailable("keystone", controller):
            metrics = {
                # "keystone-logs": "error",
                "keystone-public-api": "http_errors"}
            self.verify_service_alarms(
                get_users_list("user"), 100, metrics, self.WARNING_STATUS)

            metrics = {"keystone-admin-api": "http_errors"}
            self.verify_service_alarms(
                get_users_list("admin"), 100, metrics, self.WARNING_STATUS)

    @pytest.mark.check_env('is_fuel')
    def test_swift_api_logs_errors_alarms_fuel(self):
        """Check that swift-logs-error and swift-api-http-error alarms
           work as expected.

        Scenario:
            1. Stop swift-account service on controller.
            2. Run some swift stack list command repeatedly.
            3. Check the last value of the swift-logs-error alarm
               in InfluxDB.
            4. Check the last value of the swift-api-http-errors alarm
               in InfluxDB.
            5. Start swift-account service on controller.

        Duration 15m
        """
        controller = self.cluster.get_random_controller()

        def get_objects_list():
            try:
                cmd = (". openrc "
                       "&& export OS_AUTH_URL="
                       "`(echo $OS_AUTH_URL | sed 's%:5000/%:5000/v2.0%')` "
                       "&& swift list > /dev/null 2>&1")
                controller.os.transport.exec_sync(cmd)
            except Exception:
                pass

        controller.os.transport.exec_sync('initctl stop swift-account')

        metrics = {"swift-api": "http_errors"}
        self.verify_service_alarms(
            get_objects_list, 10, metrics, self.WARNING_STATUS)

        controller.os.transport.exec_sync('initctl start swift-account')

    @pytest.mark.skip(reason="Destructive")
    def test_hdd_errors_alarms(self):
        """Check that hdd-errors-critical alarm works as expected.

        Scenario:
            1. Generate errors entries in kernel log: in /var/log/kern.log
            2. Check the last value of the hdd-errors-critical
               alarm in InfluxDB.

        Duration 10m
        """

        def poison_kern_log_with_hdd_errors():
            kernel_log = "/var/log/kern.log"
            prefix = "<5>{timestamp} {hostname} kernel: [ 3525.262016] "
            messages = (
                "Buffer I/O error on device vda2, logical block 51184",
                "XFS (vda): xfs_log_force: error 5 returned.",
                "XFS (vdb2): metadata I/O error: block 0x68c2b7d8 "
                "(\"xfs_trans_read_buf_map\") error 121 numblks 8",
            )
            for msg in messages:
                for repeat in range(10):
                    curr_timestamp = time.strftime("%b  %-d %H:%M:%S")
                    curr_msg = "{prefix}{msg}".format(
                        prefix=prefix.format(timestamp=curr_timestamp,
                                             hostname=hostname),
                        msg=msg)
                    compute.os.write_to_file(kernel_log, curr_msg)
                    time.sleep(1)

        compute = self.cluster.filter_by_role("compute").first()
        hostname = compute.hostname
        poison_kern_log_with_hdd_errors()
        self.influxdb_api.check_alarms(
            "node", "compute", "hdd-errors", hostname, self.CRITICAL_STATUS)

    @pytest.mark.parametrize(
        "entities",
        determinate_services().values(),
        ids=determinate_services().keys())
    def test_services_alarms(self, entities):
        """Check sanity services alarms.

        Scenario:
            1. Connect to the node where the service from the list
               below is started:
                 * libvirt
                 * rabbitmq-server
                 * memcached
                 * apache2 (for fuel only)
                 * mysql
               and stop the service.
            2. Check that <service-name>-check value is operating.
            3. Stop service and check that the corresponding
               <service-name>-check alarm is triggered.
            4. Start the service resource and check that value is operating.
        """
        status_operating = 1
        status_down = 0

        def find_server(some_service):
            if service == 'apache2':
                return self.cluster.get_random_controller()
            server = None
            for cluster_host in self.cluster.hosts:
                try:
                    res = cluster_host.os.transport.exec_sync(
                        'pgrep {service}'.format(service=some_service))
                except Exception:
                    continue
                if res[0] == 0:
                    server = cluster_host
                    break
            if server is None:
                raise custom_exceptions.NoValidHost('')
            return server

        service, check = entities
        host = find_server(service)
        self.influxdb_api.check_status(check, host.hostname, status_operating)
        self.destructive_actions.append(
            lambda: host.os.manage_service(service, "start"))
        if service == 'rabbitmq-server':
            self.destructive_actions.append(
                lambda: host.os.check_call('rabbitmqctl force_boot'))
        host.os.manage_service(service, "stop")
        self.influxdb_api.check_status(check, host.hostname, status_down)
        if service == 'rabbitmq-server':
            host.os.check_call('rabbitmqctl force_boot')
        host.os.manage_service(service, "start")
        self.influxdb_api.check_status(check, host.hostname, status_operating)
        self.destructive_actions = []

    @pytest.mark.check_env('is_mk')
    def test_rabbitmq_pacemaker_alarms(self):
        """Check that rabbitmq-pacemaker-* alarms work as expected.

        Scenario:
            1. Stop one slave RabbitMQ instance.
            2. Check that the status of the RabbitMQ cluster is warning.
            3. Stop the second slave RabbitMQ instance.
            4. Check that the status of the RabbitMQ cluster is critical.
            5. Stop the master RabbitMQ instance.
            6. Check that the status of the RabbitMQ cluster is down.
            7. Clear the RabbitMQ resource.
            8. Check that the status of the RabbitMQ cluster is okay.

        Duration 10m
        """
        check_status = functools.partial(
            self.influxdb_api.check_cluster_status,
            name="rabbitmq", interval="10s")

        controllers = self.cluster.get_controllers()[:3]
        statuses = (
            self.WARNING_STATUS, self.CRITICAL_STATUS, self.DOWN_STATUS)
        service = 'rabbitmq-server'

        check_status(expected_status=self.OKAY_STATUS)

        for ctl, status in zip(controllers, statuses):
            self.destructive_actions.append(
                lambda: ctl.os.manage_service(service, 'start'))
            self.destructive_actions.append(
                lambda: ctl.os.check_call('rabbitmqctl force_boot'))
            ctl.os.manage_service(service, 'stop')
            check_status(expected_status=status)

        for ctl in controllers:
            ctl.os.transport.check_call('rabbitmqctl force_boot')
            ctl.os.manage_service(service, 'start')
            time.sleep(10)

        check_status(expected_status=self.OKAY_STATUS)
        self.destructive_actions = []

    @pytest.mark.check_env('is_fuel')
    def test_rabbitmq_pacemaker_alarms_fuel(self):
        """Check that rabbitmq-pacemaker-* alarms work as expected.

        Scenario:
            1. Stop one slave RabbitMQ instance.
            2. Check that the status of the RabbitMQ cluster is warning.
            3. Stop the second slave RabbitMQ instance.
            4. Check that the status of the RabbitMQ cluster is critical.
            5. Stop the master RabbitMQ instance.
            6. Check that the status of the RabbitMQ cluster is down.
            7. Clear the RabbitMQ resource.
            8. Check that the status of the RabbitMQ cluster is okay.

        Duration 10m
        """
        check_alarms = functools.partial(
            self.influxdb_api.check_alarms,
            'service',
            'rabbitmq-cluster',
            None,
            None)

        controllers = self.cluster.get_controllers()[:3]
        statuses = (
            self.WARNING_STATUS, self.CRITICAL_STATUS, self.DOWN_STATUS)
        service = 'rabbitmq-server'

        check_alarms(value=self.OKAY_STATUS)

        for ctl, status in zip(controllers, statuses):
            self.destructive_actions.append(
                lambda: ctl.os.manage_service(service, 'start'))
            ctl.os.manage_service(service, 'stop')
            check_alarms(value=status)

        for ctl in controllers:
            ctl.os.manage_service(service, 'start')

        check_alarms(value=self.OKAY_STATUS)
        self.destructive_actions = []

    @pytest.mark.check_env('is_mk')
    def test_rabbit_queue(self):
        # NOTE(rpromyshlennikov): Test marked only for run on mk env,
        # because it can't load Rabbit on Fuel Lab
        self.influxdb_api.check_mk_alarm(
            'rabbitmq_server_queue', self.OKAY_STATUS)
        controller = self.cluster.get_random_controller()
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=controller.hostname))
        channel = connection.channel()

        channel.queue_declare(queue='test_rabbit_queue')
        for i in range(500):
            channel.basic_publish(exchange='',
                                  routing_key='test_rabbit_queue',
                                  body='test_rabbit_queue')
        connection.close()
        self.influxdb_api.check_mk_alarm(
            'rabbitmq_server_queue', self.WARNING_STATUS)
        self.influxdb_api.check_mk_alarm(
            'rabbitmq_server_queue', self.OKAY_STATUS)
