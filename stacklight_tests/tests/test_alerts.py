from __future__ import print_function

import contextlib
import logging
import pytest
import time

from stacklight_tests import custom_exceptions
from stacklight_tests import utils
from stacklight_tests.custom_exceptions import FuelEnvAtMK
from stacklight_tests.tests import base_test

logger = logging.getLogger(__name__)


class TestAlerts(base_test.BaseLMATest):
    @pytest.mark.mk_in_progress
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

    @pytest.mark.mk_in_progress
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

    @pytest.mark.skip(reason="Destructive")
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
        self.check_filesystem_alarms(
            compute, "/$", "root-fs", "/bigfile", "compute")

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
            creds = '-u debian-sys-maint -pworkshop'
        cmd = (
            "mysql -AN {creds} -e "
            "\"select concat("
            "'rename table {db_name}.', table_name, ' "
            "to {db_name}.' , {method}(table_name) , ';') "
            "from information_schema.tables "
            "where table_schema = '{db_name}';"
            "\" | mysql {creds} ").format(creds=creds)

        # TODO(rpromyshlennikov): use "check_call" instead of exec_command
        exit_code, _, _ = controller.os.transport.exec_sync(
            cmd.format(db_name=db_name, method='upper'))
        try:
            yield
        finally:
            # TODO(rpromyshlennikov): use "check_call" instead of exec_command
            exit_code, _, _ = controller.os.transport.exec_sync(
                cmd.format(db_name=db_name, method='lower'))

    @pytest.mark.mk
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
        controller = self.cluster.get_random_controller()
        influxdb_api = self.influxdb_api
        warning = self.WARNING_STATUS

        def check_nova_result():
            query = 'SELECT * FROM "cluster_status" WHERE "cluster_name" = \'nova-control\' and time >= now() - 10s and value = {value} ;'.format(
                value=warning)
            return len(influxdb_api.do_influxdb_query(
                query=query).json()['results'][0])
        # nova_service
        with self.make_logical_db_unavailable('nova', controller):
            utils.wait(check_nova_result,
                       timeout=60 * 5,
                       interval=10,
                       timeout_msg='No message')

    @pytest.mark.skip(reason="Not enough destructive metrics")
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
        # TODO(akostrikov) Should we skip neutron or add to lma more metrics?
        # Available neutron metrics:
        # openstack_neutron_http_response_times
        # openstack_neutron_networks
        # openstack_neutron_subnets
        controller = self.cluster.get_random_controller()
        influxdb_api = self.influxdb_api
        warning = self.WARNING_STATUS

        def check_neutron_result():
            query = 'SELECT * FROM "cluster_status" WHERE "cluster_name" = \'neutron-control\' and time >= now() - 10s and value = {value} ;'.format(
                value=warning)
            return len(influxdb_api.do_influxdb_query(
                query=query).json()['results'][0])
        # nova_service
        with self.make_logical_db_unavailable('neutron', controller):
            utils.wait(check_neutron_result,
                       timeout=60 * 5,
                       interval=10,
                       timeout_msg='No message')

    @pytest.mark.mk
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
        controller = self.cluster.get_random_controller()
        influxdb_api = self.influxdb_api
        warning = self.WARNING_STATUS

        def check_neutron_result():
            query = 'SELECT * FROM "cluster_status" WHERE "cluster_name" = \'glance\' and time >= now() - 10s and value = {value} ;'.format(
                value=warning)
            return len(influxdb_api.do_influxdb_query(
                query=query).json()['results'][0])

        with self.make_logical_db_unavailable('glance', controller):
            utils.wait(check_neutron_result,
                       timeout=60 * 5,
                       interval=10,
                       timeout_msg='No message')

    @pytest.mark.mk
    def test_heat_api_logs_errors_alarms(self):
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
        influxdb_api = self.influxdb_api
        warning = self.WARNING_STATUS

        def check_neutron_result():
            query = 'SELECT * FROM "cluster_status" WHERE "cluster_name" = \'heat\' and time >= now() - 10s and value = {value} ;'.format(
                value=warning)
            return len(influxdb_api.do_influxdb_query(
                query=query).json()['results'][0])

        with self.make_logical_db_unavailable('heat', controller):
            utils.wait(check_neutron_result,
                       timeout=60 * 5,
                       interval=10,
                       timeout_msg='No message')

    @pytest.mark.skip(reason="Not enough destructive metrics")
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
        influxdb_api = self.influxdb_api
        warning = self.WARNING_STATUS

        def check_neutron_result():
            query = 'SELECT * FROM "cluster_status" WHERE "cluster_name" = \'cinder-control\' and time >= now() - 10s and value = {value} ;'.format(
                value=warning)
            return len(influxdb_api.do_influxdb_query(
                query=query).json()['results'][0])

        with self.make_logical_db_unavailable('cinder', controller):
            utils.wait(check_neutron_result,
                       timeout=60 * 5,
                       interval=10,
                       timeout_msg='No message')

    @pytest.mark.mk
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
        controller = self.cluster.get_random_controller()
        influxdb_api = self.influxdb_api
        warning = self.WARNING_STATUS

        def check_neutron_result():
            query = 'SELECT * FROM "cluster_status" WHERE "cluster_name" = \'keystone\' and time >= now() - 10s and value = {value} ;'.format(
                value=warning)
            return len(influxdb_api.do_influxdb_query(
                query=query).json()['results'][0])
        # nova_service
        with self.make_logical_db_unavailable('keystone', controller):
            utils.wait(check_neutron_result,
                       timeout=60 * 5,
                       interval=10,
                       timeout_msg='No message')

    @pytest.mark.skip(reason="No swift in grafana")
    def test_swift_api_logs_errors_alarms(self): # There is no swift
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

    @pytest.mark.mk
    def test_services_alarms(self):
        """Check sanity services alarms.

        Scenario:
            1. Connect to the node where the service from the list
               below is started:
                 * libvirt
                 * rabbitmq-server
                 * memcached
                 * apache2
                 * mysql
               and stop the service.
            2. Check that the corresponding <service-name>-check alarm
               is triggered.
            3. Start the service resource and check that value is operating.
        """
        service_mapper = {
            'libvirtd': 'libvirt_check',
            'rabbitmq-server': 'rabbitmq_check',
            'memcached': 'memcached_check',
            'mysql': 'mysql_check'
        }
        if not self.is_mk:
            service_mapper['apache2'] = 'apache_check'

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
                except:
                    continue
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
            if service == 'rabbitmq-server':
                host.os.transport.exec_sync(
                    'rabbitmqctl force_boot'.format(service))
            host.os.transport.exec_sync('service {} start'.format(service))
            self.influxdb_api.check_status(
                service_mapper[service], host.hostname, status_operating)

    @pytest.mark.mk
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
        # SELECT last("value") FROM "cluster_status" WHERE "cluster_name" = 'rabbitmq';
        controllers = self.cluster.get_controllers()
        influxdb_api = self.influxdb_api
        ctl1 = controllers[0]
        ctl2 = controllers[1]
        ctl3 = controllers[2]

        ok_status = self.OKAY_STATUS

        def check_ok_result():
            query = 'SELECT last("value") FROM "cluster_status" WHERE "cluster_name" = \'rabbitmq\' and time >= now() - 10s and value = {value} ;'.format(value=ok_status)
            return len(influxdb_api.do_influxdb_query(
                query=query).json()['results'][0])
        utils.wait(check_ok_result,
                   timeout=60 * 5,
                   interval=10,
                   timeout_msg='No message')

        ctl1.os.transport.exec_sync('service rabbitmq-server stop')
        warn_status = self.WARNING_STATUS

        def check_warn_result():
            query = 'SELECT last("value") FROM "cluster_status" WHERE "cluster_name" = \'rabbitmq\' and time >= now() - 10s and value = {value} ;'.format(value=warn_status)
            return len(influxdb_api.do_influxdb_query(
                query=query).json()['results'][0])
        utils.wait(check_warn_result,
                   timeout=60 * 5,
                   interval=10,
                   timeout_msg='No message')

        ctl1.os.transport.exec_sync('service rabbitmq-server stop')
        ctl2.os.transport.exec_sync('service rabbitmq-server stop')

        crit_status = self.CRITICAL_STATUS

        def check_crit_result():
            query = 'SELECT last("value") FROM "cluster_status" WHERE "cluster_name" = \'rabbitmq\' and time >= now() - 10s and value = {value} ;'.format(value=crit_status)
            return len(influxdb_api.do_influxdb_query(
                query=query).json()['results'][0])
        utils.wait(check_crit_result,
                   timeout=60 * 5,
                   interval=10,
                   timeout_msg='No message')

        ctl1.os.transport.exec_sync('service rabbitmq-server stop')
        ctl2.os.transport.exec_sync('service rabbitmq-server stop')
        ctl3.os.transport.exec_sync('service rabbitmq-server stop')

        down_status = self.DOWN_STATUS

        def check_down_result():
            query = 'SELECT last("value") FROM "cluster_status" WHERE "cluster_name" = \'rabbitmq\' and time >= now() - 10s and value = {value} ;'.format(value=down_status)
            return len(influxdb_api.do_influxdb_query(
                query=query).json()['results'][0])
        utils.wait(check_down_result,
                   timeout=60 * 5,
                   interval=10,
                   timeout_msg='No message')
        ctl1.os.transport.exec_sync('rabbitmqctl force_boot')
        ctl1.os.transport.exec_sync('service rabbitmq-server start')

        time.sleep(10)
        ctl2.os.transport.exec_sync('rabbitmqctl force_boot')
        ctl2.os.transport.exec_sync('service rabbitmq-server start')
        time.sleep(10)
        ctl3.os.transport.exec_sync('rabbitmqctl force_boot')
        ctl3.os.transport.exec_sync('service rabbitmq-server start')

        utils.wait(check_ok_result,
                   timeout=60 * 5,
                   interval=10,
                   timeout_msg='No message')

    @pytest.mark.fuel
    @pytest.mark.skipif(raises=FuelEnvAtMK)
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
        if not self.is_mk:
            raise FuelEnvAtMK()
        controllers = self.cluster.get_controllers()
        self.influxdb_api.check_alarms(
            'service',
            'rabbitmq-cluster',
            None,
            None,
            self.OKAY_STATUS)

        controllers[0].os.transport.exec_sync('service rabbitmq-server stop')
        self.influxdb_api.check_alarms(
            'service', 'rabbitmq-cluster',
            None,
            None, self.WARNING_STATUS)

        controllers[0].os.transport.exec_sync('service rabbitmq-server stop')
        controllers[1].os.transport.exec_sync('service rabbitmq-server stop')
        self.influxdb_api.check_alarms(
            'service', 'rabbitmq-cluster',
            None,
            None, self.CRITICAL_STATUS)

        controllers[0].os.transport.exec_sync('service rabbitmq-server stop')
        controllers[1].os.transport.exec_sync('service rabbitmq-server stop')
        controllers[2].os.transport.exec_sync('service rabbitmq-server stop')
        self.influxdb_api.check_alarms(
            'service', 'rabbitmq-cluster',
            None,
            None, self.DOWN_STATUS)  # TODO: fails here

        controllers[0].os.transport.exec_sync('service rabbitmq-server start')
        controllers[1].os.transport.exec_sync('service rabbitmq-server start')
        controllers[2].os.transport.exec_sync('service rabbitmq-server start')
        self.influxdb_api.check_alarms(
            'service',
            'rabbitmq-cluster',
            None,
            None,
            self.OKAY_STATUS)
