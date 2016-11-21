import logging
import time

from tests import base_test


logger = logging.getLogger(__name__)


class TestOpenStackClients(base_test.BaseLMATest):
    def test_check_os_conn(self):
        from clients.openstack import client_manager
        manager = client_manager.OfficialClientManager
        nonpos_args = dict(
            domain='Default',
            username='admin',
            password='admin',
            tenant_name='admin',
            cert=False,
            # cert="/home/user/stacklight-integration-tests/ca.my.pem",
            auth_url='https://10.109.8.8:5000/'
            # auth_url='http://public.fuel.local:5000/'
        )
        session = manager._get_auth_session(**nonpos_args)
        nonpos_args.update(endpoint_type='adminURL')
        auth = manager.get_auth_client(**nonpos_args)
        print auth.users.list()
        compute = manager.get_compute_client(**nonpos_args)
        print compute.servers.list()
        network = manager.get_network_client(**nonpos_args)
        print network.list_networks()
        volumes = manager.get_volume_client(**nonpos_args)
        print volumes.volumes.list()
        orchestr = manager.get_orchestration_client(**nonpos_args)
        print list(orchestr.stacks.list())
        nonpos_args.pop("endpoint_type")
        images = manager.get_image_client(**nonpos_args)
        print list(images.images.list())

        ################## Auto client test ####################

        # session = manager._get_auth_session(**nonpos_args)
        print self.os_clients.auth.users.list()
        print self.os_clients.compute.servers.list()
        print self.os_clients.network.list_networks()
        print self.os_clients.volume.volumes.list()
        print list(self.os_clients.orchestration.stacks.list())
        print list(self.os_clients.image.images.list())


class TestFunctional(base_test.BaseLMATest):

    def test_nova_metrics_toolchain(self):
        """Verify that the Nova metrics are collecting.

        Scenario:
            1. Check that plugins are online
            2. Check Nova metrics in InfluxDB

        Duration 20m
        """
        time_started = "{}s".format(int(time.time()))
        metrics = self.influxdb_api.get_instance_creation_time_metrics(
            time_started)

        new_instance_count = 3
        for identifier in range(new_instance_count):
            self.create_basic_server()

        updated_metrics = self.influxdb_api.get_instance_creation_time_metrics(
            time_started)
        total_instances = new_instance_count + len(metrics)
        assert len(updated_metrics) == total_instances, (
            "There is a mismatch of instances in Nova metrics, "
            "found {instances_found} instead of {total_instances}".format(
                instances_found=len(updated_metrics),
                total_instances=total_instances)
        )

    def test_nova_logs_in_elasticsearch(self):
        """Check that Nova logs are present in Elasticsearch

        Scenario:
            1. Query Nova logs are present in current Elasticsearch index
            2. Check that Nova logs are collected from all controller and
               compute nodes

        Duration 10m
        """
        self.check_nova_logs()

    def test_nova_notifications_toolchain(self):
        """Check that Nova notifications are present in Elasticsearch

        Scenario:
            1. Revert snapshot with 3 deployed nodes
            2. Launch, update, rebuild, resize, power-off, power-on, snapshot,
               suspend, shutdown, and delete an instance
            3. Check that Nova notifications are present in current
               Elasticsearch index

        Duration 25m
        """
        self.check_nova_notifications()

    def test_glance_notifications_toolchain(self):
        """Check that Glance notifications are present in Elasticsearch

        Scenario:
            1. Revert snapshot with 3 deployed nodes
            2. Run the OSTF platform test "Check create, update and delete
               image actions using Glance v2"
            3. Check that Glance notifications are present in current
               Elasticsearch index

        Duration 25m
        """
        self.check_glance_notifications()

    def test_keystone_notifications_toolchain(self):
        """Check that Keystone notifications are present in Elasticsearch

        Scenario:
            1. Run OSTF functional test "Create user and authenticate with it
               to Horizon"
            2. Check that Keystone notifications are present in current
               Elasticsearch index

        Duration 25m
        """
        self.check_keystone_notifications()

    def test_heat_notifications_toolchain(self):
        """Check that Heat notifications are present in Elasticsearch

        Scenario:
            1. Run OSTF Heat platform tests
            2. Check that Heat notifications are present in current
               Elasticsearch index

        Duration 25m
        """
        self.check_heat_notifications()

    def test_neutron_notifications_toolchain(self):
        """Check that Neutron notifications are present in Elasticsearch

        Scenario:
            1. Run OSTF functional test "Check network connectivity from
               instance via floating IP"
            2. Check that Neutron notifications are present in current
               Elasticsearch index

        Duration 15m
        """
        self.check_neutron_notifications()

    def test_cinder_notifications_toolchain(self):
        """Check that Cinder notifications are present in Elasticsearch

        Scenario:
            1. Create a volume and update it
            2. Check that Cinder notifications are present in current
               Elasticsearch index

        Duration15m
        """

        self.check_cinder_notifications()
