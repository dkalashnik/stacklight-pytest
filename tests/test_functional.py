import logging
import time

from tests import base_test
import utils


logger = logging.getLogger(__name__)


def wait_for_resource_status(resource_client, resource,
                             expected_status, timeout=180,
                             interval=10):
    msg = "Timed out waiting to become {}".format(expected_status)
    utils.wait(
        (lambda:
         resource_client.get(resource).status == expected_status),
        interval=interval,
        timeout=timeout,
        timeout_msg=msg
    )


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
            1. Create 3 new instances
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
        output = self.es_kibana_api.query_elasticsearch(
            index_type="log", query_filter="programname:nova*", size=500)
        assert output['hits']['total'] != 0, "Indexes don't contain Nova logs"
        controllers_hostnames = [controller.hostname for controller
                                 in self.cluster.filter_by_role("controller")]
        computes_hostnames = [compute.hostname for compute
                              in self.cluster.filter_by_role("compute")]
        target_hostnames = set(controllers_hostnames + computes_hostnames)
        actual_hostnames = set([hit['_source']['Hostname']
                                for hit in output['hits']['hits']])
        assert target_hostnames == actual_hostnames, (
            "There are insufficient entries in elasticsearch")

    def test_nova_notifications_toolchain(self):
        """Check that Nova notifications are present in Elasticsearch

        Scenario:
            1. Launch, update, rebuild, resize, power-off, power-on, snapshot,
               suspend, shutdown, and delete an instance
            2. Check that Nova notifications are present in current
               Elasticsearch index

        Duration 25m
        """
        nova_event_types = [
            "compute.instance.create.start", "compute.instance.create.end",
            "compute.instance.delete.start", "compute.instance.delete.end",
            "compute.instance.rebuild.start", "compute.instance.rebuild.end",
            "compute.instance.rebuild.scheduled",
            "compute.instance.resize.prep.start",
            "compute.instance.resize.prep.end",
            "compute.instance.resize.confirm.start",
            "compute.instance.resize.confirm.end",
            "compute.instance.resize.revert.start",
            "compute.instance.resize.revert.end",
            "compute.instance.exists", "compute.instance.update",
            "compute.instance.shutdown.start", "compute.instance.shutdown.end",
            "compute.instance.power_off.start",
            "compute.instance.power_off.end",
            "compute.instance.power_on.start", "compute.instance.power_on.end",
            "compute.instance.snapshot.start", "compute.instance.snapshot.end",
            "compute.instance.resize.start", "compute.instance.resize.end",
            "compute.instance.finish_resize.start",
            "compute.instance.finish_resize.end",
            "compute.instance.suspend.start", "compute.instance.suspend.end",
            "scheduler.select_destinations.start",
            "scheduler.select_destinations.end"]
        instance_event_types = nova_event_types[:-2]
        instance = self.create_basic_server()
        logger.info("Update the instance")
        self.os_clients.compute.servers.update(instance, name="test-server")
        wait_for_resource_status(
            self.os_clients.compute.servers, instance, "ACTIVE")
        image = self.get_cirros_image()
        logger.info("Rebuild the instance")
        self.os_clients.compute.servers.rebuild(
            instance, image, name="rebuilded_instance")
        wait_for_resource_status(
            self.os_clients.compute.servers, instance, "ACTIVE")
        logger.info("Resize the instance")
        flavors = self.os_clients.compute.flavors.list(sort_key="memory_mb")
        self.os_clients.compute.servers.resize(instance, flavors[1])
        wait_for_resource_status(
            self.os_clients.compute.servers, instance, "VERIFY_RESIZE")
        logger.info("Confirm the resize")
        self.os_clients.compute.servers.confirm_resize(instance)
        wait_for_resource_status(
            self.os_clients.compute.servers, instance, "ACTIVE")
        logger.info("Resize the instance")
        self.os_clients.compute.servers.resize(instance, flavors[2])
        wait_for_resource_status(
            self.os_clients.compute.servers, instance, "VERIFY_RESIZE")
        logger.info("Revert the resize")
        self.os_clients.compute.servers.revert_resize(instance)
        wait_for_resource_status(
            self.os_clients.compute.servers, instance, "ACTIVE")
        logger.info("Stop the instance")
        self.os_clients.compute.servers.stop(instance)
        wait_for_resource_status(
            self.os_clients.compute.servers, instance, "SHUTOFF")
        logger.info("Start the instance")
        self.os_clients.compute.servers.start(instance)
        wait_for_resource_status(
            self.os_clients.compute.servers, instance, "ACTIVE")
        logger.info("Suspend the instance")
        self.os_clients.compute.servers.suspend(instance)
        wait_for_resource_status(
            self.os_clients.compute.servers, instance, "SUSPENDED")
        logger.info("Resume the instance")
        self.os_clients.compute.servers.resume(instance)
        wait_for_resource_status(
            self.os_clients.compute.servers, instance, "ACTIVE")
        logger.info("Create an instance snapshot")
        snapshot = self.os_clients.compute.servers.create_image(
            instance, "test-image")
        wait_for_resource_status(
            self.os_clients.compute.images, snapshot, "ACTIVE")
        logger.info("Delete the instance")
        self.os_clients.compute.servers.delete(instance)
        logger.info("Check that the instance was deleted")
        utils.wait(
            lambda: (instance.id not in self.os_clients.compute.servers.list())
        )
        self.es_kibana_api.check_notifications(
            instance_event_types, index_type="notification",
            query_filter='instance_id:"{}"'.format(instance.id), size=500)
        self.es_kibana_api.check_notifications(
            nova_event_types, index_type="notification",
            query_filter="Logger:nova", size=500)

    def test_glance_notifications_toolchain(self):
        """Check that Glance notifications are present in Elasticsearch

        Scenario:
            1. Create, update and delete image actions using Glance v2
            2. Check that Glance notifications are present in current
               Elasticsearch index

        Duration 25m
        """
        glance_event_types = ["image.create", "image.prepare", "image.upload",
                              "image.activate", "image.update", "image.delete"]

        image_name = utils.rand_name("image-")
        client = self.os_clients.image
        image = client.images.create(
            name=image_name,
            container_format="bare",
            disk_format="raw")
        client.images.upload(image.id, "dummy_data")
        wait_for_resource_status(client.images, image.id, "active")

        prop = utils.rand_name("prop")
        value_prop = utils.rand_name("value")
        properties = '{0}: {1}'.format(prop, value_prop)
        image = client.images.update(image.id, group_props=properties)
        assert any(image[key] == properties for key in image) is True

        client.images.delete(image.id)
        utils.wait(
            lambda: (image.id not in client.images.list())
        )

        self.es_kibana_api.check_notifications(
            glance_event_types, index_type="notification",
            query_filter="Logger:glance", size=500)

    def test_keystone_notifications_toolchain(self):
        """Check that Keystone notifications are present in Elasticsearch

        Scenario:
            1. Create user and authenticate with it to Horizon
            2. Check that Keystone notifications are present in current
               Elasticsearch index

        Duration 25m
        """
        keystone_event_types = [
            "identity.role.created", "identity.role.deleted",
            "identity.user.created", "identity.user.deleted",
            "identity.project.created", "identity.project.deleted",
            "identity.authenticate"
        ]

        client = self.os_clients.auth
        tenant = client.tenants.create(utils.rand_name("tenant-"))

        password = "123456"
        name = utils.rand_name("user-")
        user = client.users.create(name, password, "test@test.com", tenant.id)

        role = client.roles.create(utils.rand_name("role-"))

        auth = client.tokens.authenticate(
            username=user.name,
            password=password,
            tenant_id=tenant.id,
            tenant_name=tenant.name
        )
        assert auth

        client.roles.delete(role)
        client.users.delete(user)
        client.tenants.delete(tenant)

        self.es_kibana_api.check_notifications(
            keystone_event_types, index_type="notification",
            query_filter="Logger:keystone", size=500)

    def test_heat_notifications_toolchain(self):
        """Check that Heat notifications are present in Elasticsearch

        Scenario:
            1. Run Heat platform actions
            2. Check that Heat notifications are present in current
               Elasticsearch index

        Duration 25m
        """
        heat_event_types = [
            "orchestration.stack.check.start",
            "orchestration.stack.check.end",
            "orchestration.stack.create.start",
            "orchestration.stack.create.end",
            "orchestration.stack.delete.start",
            "orchestration.stack.delete.end",
            "orchestration.stack.resume.start",
            "orchestration.stack.resume.end",
            "orchestration.stack.rollback.start",
            "orchestration.stack.rollback.end",
            "orchestration.stack.suspend.start",
            "orchestration.stack.suspend.end"
        ]

        name = utils.rand_name("heat-flavor-")
        flavor = self.create_flavor(name)

        filepath = utils.get_fixture("heat_create_neutron_stack_template.yaml",
                                     parent_dirs=("heat",))
        with open(filepath) as template_file:
            template = template_file.read()

        parameters = {
            'InstanceType': flavor.name,
            'ImageId': self.get_cirros_image()["name"],
            'network': self.get_internal_network()["id"],
        }

        stack = self.create_stack(template, parameters=parameters)

        self.os_clients.orchestration.actions.suspend(stack.id)
        utils.wait(
            (lambda:
             self.os_clients.orchestration.stacks.get(
                 stack.id).stack_status == "SUSPEND_COMPLETE"),
            interval=10,
            timeout=180,
        )

        resources = self.os_clients.orchestration.resources.list(stack.id)
        resource_server = [res for res in resources
                           if res.resource_type == "OS::Nova::Server"][0]
        instance = self.os_clients.compute.servers.get(
            resource_server.physical_resource_id)

        assert instance.status == "SUSPENDED"

        self.os_clients.orchestration.actions.resume(stack.id)
        utils.wait(
            (lambda:
             self.os_clients.orchestration.stacks.get(
                 stack.id).stack_status == "RESUME_COMPLETE"),
            interval=10,
            timeout=180,
        )

        instance = self.os_clients.compute.servers.get(
            resource_server.physical_resource_id)
        assert instance.status == "ACTIVE"

        self.os_clients.orchestration.actions.check(stack.id)

        utils.wait(
            (lambda:
             self.os_clients.orchestration.stacks.get(
                 stack.id).stack_status == "CHECK_COMPLETE"),
            interval=10,
            timeout=180,
        )

        self.os_clients.orchestration.stacks.delete(stack.id)
        self.os_clients.compute.flavors.delete(flavor.id)

        name = utils.rand_name("heat-flavor-")
        extra_large_flavor = self.create_flavor(name, 1048576)
        parameters['InstanceType'] = extra_large_flavor.name
        stack = self.create_stack(template, disable_rollback=False,
                                  parameters=parameters, wait_active=False)
        assert stack.stack_status == "CREATE_IN_PROGRESS"

        utils.wait(
            (lambda:
             self.os_clients.orchestration.stacks.get(
                 stack.id).stack_status in (
                 "DELETE_COMPLETE", "ROLLBACK_COMPLETE")),
            interval=10,
            timeout=360,
        )

        resources = self.os_clients.orchestration.resources.list(stack.id)
        resource_servers = [res for res in resources
                            if res.resource_type == "OS::Nova::Server"]
        assert (not resource_servers
                or resource_servers[0].physical_resource_id == "")

        self.os_clients.compute.flavors.delete(extra_large_flavor.id)

        self.es_kibana_api.check_notifications(
            heat_event_types, index_type="notification",
            query_filter="Logger:heat", size=500)

    def test_neutron_notifications_toolchain(self):
        """Check that Neutron notifications are present in Elasticsearch

        Scenario:
            1. Create and delete some of neutron entities.
            2. Check that Neutron notifications are present in current
               Elasticsearch index

        Duration 15m
        """
        neutron_event_types = [
            "subnet.delete.start", "subnet.delete.end",
            "subnet.create.start", "subnet.create.end",
            "security_group_rule.create.start",
            "security_group_rule.create.end",
            "security_group.delete.start", "security_group.delete.end",
            "security_group.create.start", "security_group.create.end",
            "router.update.start", "router.update.end",
            "router.interface.delete", "router.interface.create",
            "router.delete.start", "router.delete.end",
            "router.create.start", "router.create.end",
            "port.delete.start", "port.delete.end",
            "port.create.start", "port.create.end",
            "network.delete.start", "network.delete.end",
            "network.create.start", "network.create.end",
            "floatingip.update.start", "floatingip.update.end",
            "floatingip.delete.start", "floatingip.delete.end",
            "floatingip.create.start", "floatingip.create.end"
        ]

        sec_group = self.create_sec_group()
        tenant_id = self.get_admin_tenant().id

        ext_net = self.get_external_network()
        net = self.create_network(tenant_id)
        subnet = self.create_subnet(net, tenant_id)
        router = self.create_router(ext_net, tenant_id)
        self.os_clients.network.add_interface_router(
            router['id'], {'subnet_id': subnet['id']})

        server = self.create_basic_server(net=net, sec_groups=[sec_group.name])
        floating_ips_pool = self.os_clients.compute.floating_ip_pools.list()
        floating_ip = self.os_clients.compute.floating_ips.create(
            pool=floating_ips_pool[0].name)
        self.os_clients.compute.servers.add_floating_ip(server, floating_ip)

        # Clean
        self.os_clients.compute.servers.remove_floating_ip(server, floating_ip)
        self.os_clients.compute.floating_ips.delete(floating_ip)
        self.os_clients.compute.servers.delete(server)
        self.os_clients.network.remove_gateway_router(router["id"])
        self.os_clients.network.remove_interface_router(
            router["id"], {"subnet_id": subnet['id']})
        self.os_clients.network.delete_subnet(subnet['id'])
        self.os_clients.network.delete_router(router['id'])
        self.os_clients.network.delete_network(net['id'])
        self.os_clients.compute.security_groups.delete(sec_group)

        self.es_kibana_api.check_notifications(
            neutron_event_types, index_type="notification",
            query_filter="Logger:neutron", size=500)

    def test_cinder_notifications_toolchain(self):
        """Check that Cinder notifications are present in Elasticsearch

        Scenario:
            1. Create a volume and update it
            2. Check that Cinder notifications are present in current
               Elasticsearch index

        Duration15m
        """
        cinder_event_types = ["volume.update.start", "volume.update.end"]
        cinder = self.os_clients.volume
        logger.info("Create a volume")
        volume = cinder.volumes.create(size=1)
        wait_for_resource_status(
            self.os_clients.volume.volumes, volume.id, "available")
        logger.info("Update the volume")
        if cinder.version == 1:
            cinder.volumes.update(volume, display_name="updated_volume")
        else:
            cinder.volumes.update(volume, name="updated_volume")
        wait_for_resource_status(
            self.os_clients.volume.volumes, volume.id, "available")
        logger.info("Delete the volume")
        cinder.volumes.delete(volume)
        utils.wait(
            lambda: (volume.id not in cinder.volumes.list())
        )
        self.es_kibana_api.check_notifications(
            cinder_event_types, index_type="notification",
            query_filter='volume_id:"{}"'.format(volume.id), size=500)
