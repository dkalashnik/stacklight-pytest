from __future__ import print_function

import logging
import time

import pytest

from stacklight_tests import settings
from stacklight_tests.tests import base_test
from stacklight_tests import utils

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
        # from stacklight_tests.clients.openstack import client_manager
        # manager = client_manager.OfficialClientManager
        # nonpos_args = dict(
        #     domain='Default',
        #     username='admin',
        #     password='admin',
        #     tenant_name='admin',
        #     cert=False,
        #     # cert="/home/user/stacklight-integration-tests/ca.my.pem",
        #     auth_url='https://10.109.8.8:5000/'
        #     # auth_url='http://public.fuel.local:5000/'
        # )
        # session = manager._get_auth_session(**nonpos_args)
        # nonpos_args.update(endpoint_type='adminURL')
        # auth = manager.get_auth_client(**nonpos_args)
        # print(auth.users.list())
        # compute = manager.get_compute_client(**nonpos_args)
        # print(compute.servers.list())
        # network = manager.get_network_client(**nonpos_args)
        # print(network.list_networks())
        # volumes = manager.get_volume_client(**nonpos_args)
        # print(volumes.volumes.list())
        # orchestr = manager.get_orchestration_client(**nonpos_args)
        # print(list(orchestr.stacks.list()))
        # nonpos_args.pop("endpoint_type")
        # images = manager.get_image_client(**nonpos_args)
        # print(list(images.images.list()))

        # Auto client test

        # session = manager._get_auth_session(**nonpos_args)
        print(self.os_clients.auth.users.list())
        print(self.os_clients.compute.servers.list())
        print(self.os_clients.network.list_networks())
        print(self.os_clients.volume.volumes.list())
        print(list(self.os_clients.orchestration.stacks.list()))
        print(list(self.os_clients.image.images.list()))

    def test_delete_all_resources(self, resources_ids=None):
        default_resources_ids = {
            "floating_ips": [],
            "nets": [],
            "ports": [],
            "routers": [],
            "sec_groups": [],
            "servers": [],
            "stacks": [],
            "subnets": [],
        }

        resources_ids = resources_ids or default_resources_ids

        for stack_id in resources_ids["stacks"]:
            stack = self.os_clients.orchestration.stacks.get(stack_id)
            self.os_clients.orchestration.stacks.delete(stack.id)

        for floating_ip_id in resources_ids["floating_ips"]:
            floating_ip = self.os_clients.compute.floating_ips.get(
                floating_ip_id)
            self.os_clients.compute.floating_ips.delete(floating_ip)

        for server_id in resources_ids["servers"]:
            server = self.os_clients.compute.servers.get(server_id)
            self.os_clients.compute.servers.delete(server)

        routers = []
        for net_res_id in resources_ids["routers"]:
            try:
                router = self.os_clients.network.show_router(net_res_id)
                if router:
                    routers.append(router["router"])
                    self.os_clients.network.remove_gateway_router(
                        router["router"]["id"])
            except Exception as e:
                print(e)

        subnets = []
        for net_res_id in resources_ids["subnets"]:
            try:
                subnet = self.os_clients.network.show_subnet(net_res_id)
                if subnet:
                    subnets.append(subnet["subnet"])
            except Exception as e:
                print(e)

        for router in routers:
            for subnet in subnets:
                try:
                    self.os_clients.network.remove_interface_router(
                        router["id"], {"subnet_id": subnet['id']})
                except Exception as e:
                    print(e)
            self.os_clients.network.delete_router(router['id'])

        for port_id in resources_ids["ports"]:
            try:
                port = self.os_clients.network.show_port(port_id)["port"]
                self.os_clients.network.delete_port(port['id'])
            except Exception as e:
                print(e)

        for port in self.os_clients.network.list_ports()["ports"]:
            try:
                self.os_clients.network.delete_port(port['id'])
            except Exception as e:
                print(e)

        for subnet in subnets:
            try:
                self.os_clients.network.delete_subnet(subnet['id'])
            except Exception as e:
                print(e)

        for net_res_id in resources_ids["nets"]:
            try:
                self.os_clients.network.delete_network(net_res_id)
            except Exception as e:
                print(e)

        for sec_group_id in resources_ids["sec_groups"]:
            try:
                sec_group = self.os_clients.compute.security_groups.get(
                    sec_group_id)
                if sec_group:
                    self.os_clients.compute.security_groups.delete(sec_group)
            except Exception as e:
                print(e)


class TestFunctional(base_test.BaseLMATest):

    def test_nova_metrics_toolchain(self):
        """Verify that the Nova metrics are collecting.

        Scenario:
            1. Create 3 new instances
            2. Check Nova metrics in InfluxDB

        Duration 5m
        """
        time_started = "{}s".format(int(time.time()))
        check_metrics = self.influxdb_api.get_instance_creation_time_metrics
        metrics = check_metrics(time_started)

        new_instance_count = 3
        new_servers = []
        for _ in range(new_instance_count):
            new_servers.append(self.create_basic_server())

        total_instances = new_instance_count + len(metrics)

        msg = ("There is a mismatch of instances in Nova metrics, "
               "found less than {}".format(total_instances))
        utils.wait(
            (lambda: len(check_metrics(time_started)) == total_instances),
            interval=10, timeout=180, timeout_msg=msg)
        for server in new_servers:
            self.os_clients.compute.servers.delete(server)

    def test_nova_logs_in_elasticsearch(self):
        """Check that Nova logs are present in Elasticsearch

        Scenario:
            1. Query Nova logs are present in current Elasticsearch index
            2. Check that Nova logs are collected from all controller and
               compute nodes

        Duration 5m
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

        Duration 15m
        """
        nova_event_types = [
            "compute.instance.create.start", "compute.instance.create.end",
            "compute.instance.delete.start", "compute.instance.delete.end",
            "compute.instance.rebuild.start", "compute.instance.rebuild.end",
            # NOTE(rpromyshlennikov):
            # Disabled in favor of compatibility with Mk2x
            # "compute.instance.rebuild.scheduled",
            # "compute.instance.resize.prep.start",
            # "compute.instance.resize.prep.end",
            # "compute.instance.resize.confirm.start",
            # "compute.instance.resize.confirm.end",
            # "compute.instance.resize.revert.start",
            # "compute.instance.resize.revert.end",
            "compute.instance.exists",
            # "compute.instance.update",
            "compute.instance.shutdown.start", "compute.instance.shutdown.end",
            "compute.instance.power_off.start",
            "compute.instance.power_off.end",
            "compute.instance.power_on.start", "compute.instance.power_on.end",
            "compute.instance.snapshot.start", "compute.instance.snapshot.end",
            # "compute.instance.resize.start", "compute.instance.resize.end",
            # "compute.instance.finish_resize.start",
            # "compute.instance.finish_resize.end",
            "compute.instance.suspend.start", "compute.instance.suspend.end",
            # "scheduler.select_destinations.start",
            # "scheduler.select_destinations.end"
        ]
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
        # NOTE(rpromyshlennikov):
        # Disabled in favor of compatibility with Mk2x
        # logger.info("Resize the instance")
        # flavors = self.os_clients.compute.flavors.list(sort_key="memory_mb")
        # self.os_clients.compute.servers.resize(instance, flavors[1])
        # wait_for_resource_status(
        #     self.os_clients.compute.servers, instance, "VERIFY_RESIZE")
        # logger.info("Confirm the resize")
        # self.os_clients.compute.servers.confirm_resize(instance)
        # wait_for_resource_status(
        #     self.os_clients.compute.servers, instance, "ACTIVE")
        # logger.info("Resize the instance")
        # self.os_clients.compute.servers.resize(instance, flavors[2])
        # wait_for_resource_status(
        #     self.os_clients.compute.servers, instance, "VERIFY_RESIZE")
        # logger.info("Revert the resize")
        # self.os_clients.compute.servers.revert_resize(instance)
        # wait_for_resource_status(
        #     self.os_clients.compute.servers, instance, "ACTIVE")
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

        Duration 15m
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

        Duration 15m
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
            # "orchestration.stack.check.start",
            # "orchestration.stack.check.end",
            "orchestration.stack.create.start",
            "orchestration.stack.create.end",
            "orchestration.stack.delete.start",
            "orchestration.stack.delete.end",
            # "orchestration.stack.resume.start",
            # "orchestration.stack.resume.end",
            # "orchestration.stack.rollback.start",
            # "orchestration.stack.rollback.end",
            # "orchestration.stack.suspend.start",
            # "orchestration.stack.suspend.end"
        ]

        name = utils.rand_name("heat-flavor-")
        flavor = self.create_flavor(name)

        filepath = utils.get_fixture("heat_create_neutron_stack_template.yaml",
                                     parent_dirs=("heat",))
        with open(filepath) as template_file:
            template = template_file.read()

        parameters = {
            'InstanceType': flavor.name,
            'ImageId': self.get_cirros_image().id,
            'network': self.get_internal_network()["id"],
        }

        stack = self.create_stack(template, parameters=parameters)

        # self.os_clients.orchestration.actions.suspend(stack.id)
        # utils.wait(
        #     (lambda:
        #      self.os_clients.orchestration.stacks.get(
        #          stack.id).stack_status == "SUSPEND_COMPLETE"),
        #     interval=10,
        #     timeout=180,
        # )

        resources = self.os_clients.orchestration.resources.list(stack.id)
        resource_server = [res for res in resources
                           if res.resource_type == "OS::Nova::Server"][0]
        # instance = self.os_clients.compute.servers.get(
        #     resource_server.physical_resource_id)

        # assert instance.status == "SUSPENDED"
        #
        # self.os_clients.orchestration.actions.resume(stack.id)
        # utils.wait(
        #     (lambda:
        #      self.os_clients.orchestration.stacks.get(
        #          stack.id).stack_status == "RESUME_COMPLETE"),
        #     interval=10,
        #     timeout=180,
        # )

        instance = self.os_clients.compute.servers.get(
            resource_server.physical_resource_id)
        assert instance.status == "ACTIVE"

        # self.os_clients.orchestration.actions.check(stack.id)
        #
        # utils.wait(
        #     (lambda:
        #      self.os_clients.orchestration.stacks.get(
        #          stack.id).stack_status == "CHECK_COMPLETE"),
        #     interval=10,
        #     timeout=180,
        # )

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
        assert (not resource_servers or
                resource_servers[0].physical_resource_id == "")

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
            # "router.interface.delete", "router.interface.create",
            "router.delete.start", "router.delete.end",
            "router.create.start", "router.create.end",
            # "port.delete.start", "port.delete.end",
            # "port.create.start", "port.create.end",
            "network.delete.start", "network.delete.end",
            "network.create.start", "network.create.end",
            # "floatingip.update.start", "floatingip.update.end",
            # "floatingip.delete.start", "floatingip.delete.end",
            # "floatingip.create.start", "floatingip.create.end"
        ]

        sec_group = self.create_sec_group()
        tenant_id = self.get_admin_tenant().id

        ext_net = self.get_external_network()
        net = self.create_network(tenant_id)
        subnet = self.create_subnet(net, tenant_id)
        router = self.create_router(ext_net, tenant_id)
        self.os_clients.network.add_interface_router(
            router['id'], {'subnet_id': subnet['id']})

        # server = self.create_basic_server(net=net, sec_groups=[sec_group.name])
        # floating_ips_pool = self.os_clients.compute.floating_ip_pools.list()
        # floating_ip = self.os_clients.compute.floating_ips.create(
        #     pool=floating_ips_pool[0].name)
        # self.os_clients.compute.servers.add_floating_ip(server, floating_ip)

        # Clean
        # self.os_clients.compute.servers.remove_floating_ip(server, floating_ip)
        # self.os_clients.compute.floating_ips.delete(floating_ip)
        # self.os_clients.compute.servers.delete(server)
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

    # This test is suitable only for fuel env,
    # because there is no working cinder on Mk2x now
    @pytest.mark.check_env("is_fuel")
    def test_cinder_notifications_toolchain(self):
        """Check that Cinder notifications are present in Elasticsearch

        Scenario:
            1. Create a volume and update it
            2. Check that Cinder notifications are present in current
               Elasticsearch index

        Duration 15m
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

    @pytest.mark.parametrize(
        "controllers_count", [1, 2], ids=["warning", "critical"])
    def test_toolchain_alert_service(self, controllers_count):
        """Verify that the warning and critical alerts for services
        show up in the Grafana and Nagios UI.

        Scenario:
            1. Connect to one (for warning) or two (for critical) of
               the controller nodes using ssh and stop the nova-api service.
            2. Wait for at least 1 minute.
            3. On Grafana, check the following items:
                    - the box in the upper left corner of the dashboard
                      displays 'WARN' or 'CRIT' with an orange/red background,
                    - the API panels report 1/2 entity as down.
            4. Check count of haproxy backends with down state in InfluxDB
               if there is backend in haproxy for checked service.
            5. Check email about service state.
            6. Start the nova-api service.
            7. Wait for at least 1 minute.
            8. On Grafana, check the following items:
                    - the box in the upper left corner of the dashboard
                      displays 'OKAY' with an green background,
                    - the API panels report 0 entity as down.
            9. Check count of haproxy backends with down state in InfluxDB.
            10. Check email about service state.
            11. Repeat steps 2 to 8 for the following services:
                    - Nova (stopping and starting the nova-api and
                      nova-scheduler)
                    - Cinder (stopping and starting the cinder-api and
                      cinder-scheduler services respectively).
                    - Neutron (stopping and starting the neutron-server
                      and neutron-openvswitch-agent services respectively).
                    - Glance (stopping and starting the glance-api service).
                    - Heat (stopping and starting the heat-api service).
                    - Keystone (stopping and starting the Apache service).

        Duration 25m
        """
        def verify_service_state_change(service_names, action, new_state,
                                        service_state_in_influx,
                                        down_backends_in_haproxy,):

            logger.info("Changing state of service {0}. "
                        "New state is {1}".format(service_names[0], new_state))

            for toolchain_node in toolchain_nodes:
                toolchain_node.os.clear_local_mail()
            for node in controller_nodes:
                node.os.manage_service(service_names[0], action)
            self.influxdb_api.check_cluster_status(
                service_names[1], service_state_in_influx)
            if service_names[3]:
                self.influxdb_api.check_count_of_haproxy_backends(
                    service_names[3], expected_count=down_backends_in_haproxy)
            utils.wait(
                lambda: (
                    any(t_node.os.check_local_mail(service_names[2], new_state)
                        for t_node in toolchain_nodes)),
                timeout=5 * 60, interval=15)

        statuses = {1: (self.WARNING_STATUS, "WARNING"),
                    2: (self.CRITICAL_STATUS, "CRITICAL")}

        components = {
            "nova": [("nova-api", "nova-api"), ("nova-scheduler", None)],
            "cinder": [("cinder-api", "cinder-api"),
                       ("cinder-scheduler", None)],
            "neutron": [
                ("neutron-server", "neutron-api"),
                # TODO(rpromyshlennikov): temporary fix,
                # because openvswitch-agent is managed by pacemaker
                # ("neutron-openvswitch-agent", None)
            ],
            "glance": [("glance-api", "glance-api")],
            "heat": [("heat-api", "heat-api")],
            "keystone": [("apache2", "keystone-public-api")]
        }

        services_names_in_alerting = {}
        services_names_in_influx = {}
        for component in components:
            influx_service_name = component
            if settings.INFLUXDB_GRAFANA_PLUGIN_VERSION.startswith("0."):
                nagios_service_name = component
            else:
                nagios_service_name = "global-{}".format(component)
                if component in ("nova", "neutron", "cinder"):
                    nagios_service_name = "{}-control-plane".format(
                        nagios_service_name)
                    influx_service_name = "{}-control-plane".format(
                        influx_service_name)

            services_names_in_alerting[component] = nagios_service_name
            services_names_in_influx[component] = influx_service_name

        toolchain_nodes = self.cluster.filter_by_role(
            "infrastructure_alerting")
        controller_nodes = self.cluster.filter_by_role(
            "controller")[:controllers_count]

        for component in components:
            for (service, haproxy_backend) in components[component]:
                logger.info("Checking service {0}".format(service))
                verify_service_state_change(
                    service_names=[
                        service,
                        services_names_in_influx[component],
                        services_names_in_alerting[component],
                        haproxy_backend],
                    action="stop",
                    new_state=statuses[controllers_count][1],
                    service_state_in_influx=statuses[controllers_count][0],
                    down_backends_in_haproxy=controllers_count,)
                verify_service_state_change(
                    service_names=[
                        service,
                        services_names_in_influx[component],
                        services_names_in_alerting[component],
                        haproxy_backend],
                    action="start",
                    new_state="OK",
                    service_state_in_influx=self.OKAY_STATUS,
                    down_backends_in_haproxy=0,)

    # This test is suitable only for fuel env,
    # because there is no "/dev/mapper/mysql-root" mount point on mk2x
    @pytest.mark.check_env("is_fuel")
    @pytest.mark.parametrize(
        "disk_usage_percent", [91, 96], ids=["warning", "critical"])
    def test_toolchain_alert_node(self, disk_usage_percent):
        """Verify that the warning alerts for nodes show up in the
         Grafana and Nagios UI.

        Scenario:
            1. Connect to one of the controller nodes using ssh and
               run:
                    fallocate -l $(df | grep /dev/mapper/mysql-root
                    | awk '{ printf("%.0f\n", 1024 * ((($3 + $4) * 96
                     / 100) - $3))}') /var/lib/mysql/test
            2. Wait for at least 1 minute.
            3. On Grafana, check the following items:
                    - the box in the upper left corner of the dashboard
                     displays 'OKAY' with an green background,
            4. Connect to a second controller node using ssh and run:
                    fallocate -l $(df | grep /dev/mapper/mysql-root
                    | awk '{ printf("%.0f\n", 1024 * ((($3 + $4) * 96
                     / 100) - $3))}') /var/lib/mysql/test
            5. Wait for at least 1 minute.
            6. On Grafana, check the following items:
                    - the box in the upper left corner of the dashboard
                     displays 'WARN' with an orange background,
                    - an annotation telling that the service went from 'OKAY'
                     to 'WARN' is displayed.
            7. Check email about service state.
            8. Run the following command on both controller nodes:
                    rm /var/lib/mysql/test
            9. Wait for at least 1 minutes.
            10. On Grafana, check the following items:
                    - the box in the upper left corner of the dashboard
                     displays 'OKAY' with an green background,
                    - an annotation telling that the service went from 'WARN'
                     to 'OKAY' is displayed.
            11. Check email about service state.

        Duration 5m
        """
        statuses = {91: (self.WARNING_STATUS, "WARNING"),
                    96: (self.CRITICAL_STATUS, "CRITICAL")}
        toolchain_nodes = self.cluster.filter_by_role(
            "infrastructure_alerting")
        controller_nodes = self.cluster.filter_by_role(
            "controller")[:2]

        nagios_service_name = (
            "mysql"
            if settings.INFLUXDB_GRAFANA_PLUGIN_VERSION.startswith("0.")
            else "global-mysql")

        nagios_state = statuses[disk_usage_percent][1]
        influx_state = statuses[disk_usage_percent][0]

        mysql_fs = "/dev/mapper/mysql-root"
        mysql_fs_alarm_test_file = "/var/lib/mysql/bigfile"

        for toolchain_node in toolchain_nodes:
            toolchain_node.os.clear_local_mail()

        controller_nodes[0].os.fill_up_filesystem(
            mysql_fs, disk_usage_percent, mysql_fs_alarm_test_file)

        self.influxdb_api.check_cluster_status("mysql", self.OKAY_STATUS)

        controller_nodes[1].os.fill_up_filesystem(
            mysql_fs, disk_usage_percent, mysql_fs_alarm_test_file)

        self.influxdb_api.check_cluster_status("mysql", influx_state)
        utils.wait(
            lambda: (
                any(t_node.os.check_local_mail(nagios_service_name,
                                               nagios_state)
                    for t_node in toolchain_nodes)),
            timeout=5 * 60, interval=15)

        for node in controller_nodes:
            node.os.clean_filesystem(mysql_fs_alarm_test_file)

        self.influxdb_api.check_cluster_status("mysql", self.OKAY_STATUS)
        utils.wait(
            lambda: (
                any(t_node.os.check_local_mail(nagios_service_name, "OK")
                    for t_node in toolchain_nodes)),
            timeout=5 * 60, interval=15)

    def test_grafana_dashboard_panel_queries_toolchain(self):
        """Verify that the panels on dashboards show up in the Grafana UI.

        Scenario:
            1. Check queries for all panels on all dashboards in Grafana.

        Duration 20m
        """
        self.grafana_api.check_grafana_online()
        dashboards = self.grafana_api.get_all_dashboards()
        ok_queries = {}
        failed_queries = {}
        no_table_queries = {}
        for dashboard in dashboards:
            if dashboard.name.startswith("ceph"):
                # NOTE(rpromyshlennikov): ceph is disabled in most cases
                continue
            result = dashboard.classify_all_dashboard_queries()
            ok_queries[dashboard.name] = result[0]
            no_table_queries[dashboard.name] = result[1]
            failed_queries[dashboard.name] = result[2]

        broken_panels = [
            items
            for result in no_table_queries.values()
            if result
            for items in result.items()]
        assert not len(broken_panels), (
            [broken_panel[0] for broken_panel in broken_panels])
