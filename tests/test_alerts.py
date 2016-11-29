from __future__ import print_function
import contextlib
import logging
import time

from tests import base_test
import custom_exceptions


logger = logging.getLogger(__name__)


class TestAlerts(base_test.BaseLMATest):
    def test_check_mysql_fs_alarms(self):
        """Check that mysql-fs-warning and mysql-fs-critical alarms work as
        expected.

        Scenario:
            1. Fill up /var/lib/mysql filesystem to 91 percent.
            2. Check the last value of the warning alarm in InfluxDB.
            3. Clean the filesystem.
            4. Fill up /var/lib/mysql filesystem to 96 percent.
            5. Check the last value of the critical alarm in InfluxDB.
            6. Clean the filesystem.

        Duration 10m
        """
        controller = self.cluster.get_random_controller()
        self.check_filesystem_alarms(
            controller, "/dev/mapper/mysql-root", "mysql-fs",
            "/var/lib/mysql/test/bigfile", "mysql-nodes")

    def test_check_rabbitmq_disk_alarm(self):
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
        self.check_rabbit_mq_disk_alarms(controller, self.WARNING_STATUS,
                                         self.RABBITMQ_DISK_WARNING_PERCENT)
        self.check_rabbit_mq_disk_alarms(controller, self.CRITICAL_STATUS,
                                         self.RABBITMQ_DISK_CRITICAL_PERCENT)

    def test_check_rabbitmq_memory_alarm(self):
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
        self.check_rabbit_mq_memory_alarms(controller, self.WARNING_STATUS,
                                           self.RABBITMQ_MEMORY_WARNING_VALUE)
        self.check_rabbit_mq_memory_alarms(controller, self.CRITICAL_STATUS,
                                           self.RABBITMQ_MEMORY_CRITICAL_VALUE)

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
        controller = self.cluster.get_random_controller()
        self.check_filesystem_alarms(
            controller, "/$", "root-fs", "/bigfile", "controller")

    def test_check_log_fs_alarms(self):
        """Check that log-fs-warning and log-fs-critical alarms work as
        expected.

        Scenario:
            1. Fill up /var/log filesystem to 91 percent.
            2. Check the last value of the warning alarm in InfluxDB.
            3. Clean the filesystem.
            4. Fill up /var/log filesystem to 96 percent.
            5. Check the last value of the critical alarm in InfluxDB.
            6. Clean the filesystem.

        Duration 10m
        """
        controller = self.cluster.get_random_controller()
        self.check_filesystem_alarms(
            controller, "/var/log", "log-fs", "/var/log/bigfile", "controller")

    def test_check_nova_fs_alarms(self):
        """Check that nova-fs-warning and nova-fs-critical alarms work as
        expected.

        Scenario:
            1. Fill up /var/lib/nova filesystem to 91 percent.
            2. Check the last value of the warning alarm in InfluxDB.
            3. Clean the filesystem.
            4. Fill up /var/lib/nova filesystem to 96 percent.
            5. Check the last value of the critical alarm in InfluxDB.
            6. Clean the filesystem.

        Duration 10m
        """
        compute = self.cluster.filter_by_role("compute").first()
        self.check_filesystem_alarms(compute, "/var/lib/nova", "nova-fs",
                                     "/var/lib/nova/bigfile", "compute")

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
        cmd = (
            "mysql -AN -e "
            "\"select concat("
            "'rename table {db_name}.', table_name, ' "
            "to {db_name}.' , {method}(table_name) , ';') "
            "from information_schema.tables "
            "where table_schema = '{db_name}';"
            "\" | mysql")
        # TODO(rpromyshlennikov): use "check_call" instead of exec_command
        exit_code, _, _ = controller.os.transport.exec_sync(
            cmd.format(db_name=db_name, method="upper"))
        try:
            yield
        finally:
            # TODO(rpromyshlennikov): use "check_call" instead of exec_command
            exit_code, _, _ = controller.os.transport.exec_sync(
                cmd.format(db_name=db_name, method="lower"))

    def test_nova_api_logs_errors_alarms(self):
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

    def test_neutron_api_logs_errors_alarms(self):
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

    def test_glance_api_logs_errors_alarms(self):
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

    def check_heat_api_logs_errors_alarms(self):
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

    def test_cinder_api_logs_errors_alarms(self):
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

    def test_keystone_api_logs_errors_alarms(self):
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
                cmd = ". openrc {additional_cmd} && keystone user-list > /dev/null 2>&1".format(additional_cmd=additional_cmds[level])
                try:
                    controller.os.transport.exec_sync(cmd)
                except Exception:
                    pass
            return get_users_list_parametrized

        controller = self.cluster.get_random_controller()

        with self.make_logical_db_unavailable("keystone", controller):
            metrics = {#"keystone-logs": "error",
                       "keystone-public-api": "http_errors"}
            self.verify_service_alarms(
                get_users_list("user"), 100, metrics, self.WARNING_STATUS)

            metrics = {"keystone-admin-api": "http_errors"}
            self.verify_service_alarms(
                get_users_list("admin"), 100, metrics, self.WARNING_STATUS)

    def test_swift_api_logs_errors_alarms(self):
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

    def test_services_alarms(self):
        """Check sanity services alarms
        1) Connect to the node where the service from the list below is started:
          libvirt
          rabbitmq-server
          memcached
          apache2
          mysql
        ans stop the service
        2) Check that the corresponding <service-name>-check alarm is triggered
        3) Start the service resource and check that value is operating
        """
        service_mapper = {
            'libvirtd': 'libvirt_check',
            'rabbitmq-server': 'rabbitmq_check',
            'memcached': 'memcached_check',
            'apache2': 'apache_check',
            'mysql': 'mysql_check'
        }
        status_operating = 1
        status_down = 0

        def find_server(some_service):
            if service == 'apache2':
                return self.cluster.get_random_controller()
            server = None
            for cluster_host in self.cluster.hosts:
                res = cluster_host.os.transport.exec_sync(
                    'pgrep {service}'.format(service=some_service))
                if res[0] == 0:
                    server = cluster_host
                    break
            if server is None:
                raise custom_exceptions.NoValidHost('')
            return server

        for service in service_mapper.keys():
            host = find_server(service)
            host.os.transport.exec_sync('service {} stop'.format(service))
            self.influxdb_api.check_status(
                service_mapper[service], host.hostname, status_down)
            host.os.transport.exec_sync('service {} start'.format(service))
            self.influxdb_api.check_status(
                service_mapper[service], host.hostname, status_operating)

            # def check_rabbitmq_pacemaker_alarms(self):
    #     """Check that rabbitmq-pacemaker-* alarms work as expected.
    #
    #     Scenario:
    #         1. Stop one slave RabbitMQ instance.
    #         2. Check that the status of the RabbitMQ cluster is warning.
    #         3. Stop the second slave RabbitMQ instance.
    #         4. Check that the status of the RabbitMQ cluster is critical.
    #         5. Stop the master RabbitMQ instance.
    #         6. Check that the status of the RabbitMQ cluster is down.
    #         7. Clear the RabbitMQ resource.
    #         8. Check that the status of the RabbitMQ cluster is okay.
    #
    #     Duration 10m
    #     """
    #     def ban_and_check_status(node, status, wait=None):
    #         with self.fuel_web.get_ssh_for_node(node.name) as remote:
    #             logger.info("Ban rabbitmq resource on {}".format(node.name))
    #             self.remote_ops.ban_resource(remote,
    #                                          'master_p_rabbitmq-server',
    #                                          wait=wait)
    #         self.check_alarms('service', 'rabbitmq-cluster', 'pacemaker',
    #                           None, status)
    #
    #     self.env.revert_snapshot("deploy_ha_toolchain")
    #
    #     self.check_alarms('service', 'rabbitmq-cluster', 'pacemaker',
    #                       None, OKAY_STATUS)
    #
    #     controllers = self.fuel_web.get_nailgun_cluster_nodes_by_roles(
    #         self.helpers.cluster_id, ["controller"])
    #
    #     controller = controllers[0]
    #     controller_node = self.fuel_web.get_devops_node_by_nailgun_node(
    #         controller)
    #     rabbitmq_master = self.fuel_web.get_rabbit_master_node(
    #         controller_node.name)
    #     rabbitmq_slaves = self.fuel_web.get_rabbit_slaves_node(
    #         controller_node.name)
    #     ban_and_check_status(rabbitmq_slaves[0], WARNING_STATUS, 120)
    #     ban_and_check_status(rabbitmq_slaves[1], CRITICAL_STATUS, 120)
    #     # Don't wait for the pcs operation to complete as it will fail since
    #     # the resource isn't running anywhere
    #     ban_and_check_status(rabbitmq_master, DOWN_STATUS)
    #
    #     logger.info("Clear rabbitmq resource")
    #     with self.fuel_web.get_ssh_for_node(rabbitmq_master.name) as remote:
    #         self.remote_ops.clear_resource(remote,
    #                                        'master_p_rabbitmq-server',
    #                                        wait=240)
    #     self.check_alarms('service', 'rabbitmq-cluster', 'pacemaker',
    #                       None, OKAY_STATUS)
