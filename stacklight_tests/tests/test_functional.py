import logging
import time

import pytest
import yaml

from stacklight_tests.clients import influxdb_grafana_api
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


def determinate_components_names():
    with open(utils.get_fixture(
            "components_names.yaml", ("tests",))) as names_file:
        components_names = yaml.load(names_file)

    # TODO(rpromyshlennikov): temporary fix: ovs service was not included,
    # because openvswitch-agent is managed by pacemaker
    # ["neutron-openvswitch-agent", ""]

    components = components_names["mk"]
    return components


class TestFunctional(base_test.BaseLMATest):

    def test_nova_metrics_toolchain(self, os_clients, os_actions,
                                    influxdb_client):
        """Verify that the Nova metrics are collecting.

        Scenario:
            1. Create 3 new instances
            2. Check Nova metrics in InfluxDB

        Duration 5m
        """
        time_started = "{}s".format(int(time.time()))
        check_metrics = influxdb_client.get_instance_creation_time_metrics
        metrics = check_metrics(time_started)

        new_instance_count = 3
        new_servers = []
        for _ in range(new_instance_count):
            new_servers.append(os_actions.create_basic_server())

        total_instances = new_instance_count + len(metrics)

        msg = ("There is a mismatch of instances in Nova metrics, "
               "found less than {}".format(total_instances))
        utils.wait(
            (lambda: len(check_metrics(time_started)) == total_instances),
            interval=10, timeout=180, timeout_msg=msg)
        for server in new_servers:
            os_clients.compute.servers.delete(server)

    def test_nova_logs_in_elasticsearch(self, cluster, es_client):
        """Check that Nova logs are present in Elasticsearch

        Scenario:
            1. Query Nova logs are present in current Elasticsearch index
            2. Check that Nova logs are collected from all controller and
               compute nodes

        Duration 5m
        """
        output = es_client.query_elasticsearch(
            query_filter="programname:nova*", size=50)
        assert output['hits']['total'] != 0, "Indexes don't contain Nova logs"
        controllers_hostnames = [controller.hostname for controller
                                 in cluster.filter_by_role("controller")]
        computes_hostnames = [compute.hostname for compute
                              in cluster.filter_by_role("compute")]
        target_hostnames = set(controllers_hostnames + computes_hostnames)
        actual_hostnames = set()
        for host in target_hostnames:
            host_presence = es_client.query_elasticsearch(
                query_filter="programname:nova* AND Hostname:{}".format(host),
                size=50)
            if host_presence['hits']['total'] > 0:
                actual_hostnames.add(host)
        assert target_hostnames == actual_hostnames, (
            "There are insufficient entries in elasticsearch")
        assert es_client.query_elasticsearch(
            query_filter="programname:nova* AND Hostname:mon01",
            size=50)['hits']['total'] == 0, (
            "There are logs collected from irrelevant host")

    def test_nova_notifications_toolchain(self, os_clients, os_actions,
                                          es_client):
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
        instance = os_actions.create_basic_server()
        logger.info("Update the instance")
        os_clients.compute.servers.update(instance, name="test-server")
        wait_for_resource_status(
            os_clients.compute.servers, instance, "ACTIVE")
        image = os_actions.get_cirros_image()
        logger.info("Rebuild the instance")
        os_clients.compute.servers.rebuild(
            instance, image, name="rebuilded_instance")
        wait_for_resource_status(
            os_clients.compute.servers, instance, "ACTIVE")
        # NOTE(rpromyshlennikov):
        # Disabled in favor of compatibility with Mk2x
        # logger.info("Resize the instance")
        # flavors = os_clients.compute.flavors.list(sort_key="memory_mb")
        # os_clients.compute.servers.resize(instance, flavors[1])
        # wait_for_resource_status(
        #     os_clients.compute.servers, instance, "VERIFY_RESIZE")
        # logger.info("Confirm the resize")
        # os_clients.compute.servers.confirm_resize(instance)
        # wait_for_resource_status(
        #     os_clients.compute.servers, instance, "ACTIVE")
        # logger.info("Resize the instance")
        # os_clients.compute.servers.resize(instance, flavors[2])
        # wait_for_resource_status(
        #     os_clients.compute.servers, instance, "VERIFY_RESIZE")
        # logger.info("Revert the resize")
        # os_clients.compute.servers.revert_resize(instance)
        # wait_for_resource_status(
        #     os_clients.compute.servers, instance, "ACTIVE")
        logger.info("Stop the instance")
        os_clients.compute.servers.stop(instance)
        wait_for_resource_status(
            os_clients.compute.servers, instance, "SHUTOFF")
        logger.info("Start the instance")
        os_clients.compute.servers.start(instance)
        wait_for_resource_status(
            os_clients.compute.servers, instance, "ACTIVE")
        logger.info("Suspend the instance")
        os_clients.compute.servers.suspend(instance)
        wait_for_resource_status(
            os_clients.compute.servers, instance, "SUSPENDED")
        logger.info("Resume the instance")
        os_clients.compute.servers.resume(instance)
        wait_for_resource_status(
            os_clients.compute.servers, instance, "ACTIVE")
        logger.info("Create an instance snapshot")
        snapshot = os_clients.compute.servers.create_image(
            instance, "test-image")
        wait_for_resource_status(
            os_clients.compute.images, snapshot, "ACTIVE")
        logger.info("Delete the instance")
        os_clients.compute.servers.delete(instance)
        logger.info("Check that the instance was deleted")
        utils.wait(
            lambda: instance.id not in os_clients.compute.servers.list()
        )
        es_client.check_notifications(
            instance_event_types,
            query_filter='instance_id:"{}"'.format(instance.id), size=500)
        es_client.check_notifications(
            nova_event_types,
            query_filter="Logger:nova", size=500)

    def test_glance_notifications_toolchain(self, os_clients, es_client):
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
        client = os_clients.image
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

        es_client.check_notifications(
            glance_event_types,
            query_filter="Logger:glance", size=500)

    def test_keystone_notifications_toolchain(self, os_clients, es_client):
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

        client = os_clients.auth
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

        es_client.check_notifications(
            keystone_event_types,
            query_filter="Logger:keystone", size=500)

    def test_heat_notifications_toolchain(self, os_clients, os_actions,
                                          es_client):
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
        flavor = os_actions.create_flavor(name)

        filepath = utils.get_fixture("heat_create_neutron_stack_template.yaml",
                                     parent_dirs=("heat",))
        with open(filepath) as template_file:
            template = template_file.read()

        parameters = {
            'InstanceType': flavor.name,
            'ImageId': os_actions.get_cirros_image().id,
            'network': os_actions.get_internal_network()["id"],
        }

        stack = os_actions.create_stack(template, parameters=parameters)

        # os_clients.orchestration.actions.suspend(stack.id)
        # utils.wait(
        #     (lambda:
        #      os_clients.orchestration.stacks.get(
        #          stack.id).stack_status == "SUSPEND_COMPLETE"),
        #     interval=10,
        #     timeout=180,
        # )

        resources = os_clients.orchestration.resources.list(stack.id)
        resource_server = [res for res in resources
                           if res.resource_type == "OS::Nova::Server"][0]
        # instance = os_clients.compute.servers.get(
        #     resource_server.physical_resource_id)

        # assert instance.status == "SUSPENDED"
        #
        # os_clients.orchestration.actions.resume(stack.id)
        # utils.wait(
        #     (lambda:
        #      os_clients.orchestration.stacks.get(
        #          stack.id).stack_status == "RESUME_COMPLETE"),
        #     interval=10,
        #     timeout=180,
        # )

        instance = os_clients.compute.servers.get(
            resource_server.physical_resource_id)
        assert instance.status == "ACTIVE"

        # os_clients.orchestration.actions.check(stack.id)
        #
        # utils.wait(
        #     (lambda:
        #      os_clients.orchestration.stacks.get(
        #          stack.id).stack_status == "CHECK_COMPLETE"),
        #     interval=10,
        #     timeout=180,
        # )

        os_clients.orchestration.stacks.delete(stack.id)
        os_clients.compute.flavors.delete(flavor.id)

        name = utils.rand_name("heat-flavor-")
        extra_large_flavor = os_actions.create_flavor(name, 1048576)
        parameters['InstanceType'] = extra_large_flavor.name
        stack = os_actions.create_stack(
            template, disable_rollback=False,
            parameters=parameters, wait_active=False)
        assert stack.stack_status == "CREATE_IN_PROGRESS"

        utils.wait(
            (lambda:
             os_clients.orchestration.stacks.get(
                 stack.id).stack_status in (
                 "DELETE_COMPLETE", "ROLLBACK_COMPLETE")),
            interval=10,
            timeout=360,
        )

        resources = os_clients.orchestration.resources.list(stack.id)
        resource_servers = [res for res in resources
                            if res.resource_type == "OS::Nova::Server"]
        assert (not resource_servers or
                resource_servers[0].physical_resource_id == "")

        os_clients.compute.flavors.delete(extra_large_flavor.id)

        es_client.check_notifications(
            heat_event_types,
            query_filter="Logger:heat", size=500)

    def test_neutron_notifications_toolchain(self, os_clients, os_actions,
                                             es_client):
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

        sec_group = os_actions.create_sec_group()
        tenant_id = os_actions.get_admin_tenant().id

        ext_net = os_actions.get_external_network()
        net = os_actions.create_network(tenant_id)
        subnet = os_actions.create_subnet(net, tenant_id)
        router = os_actions.create_router(ext_net, tenant_id)
        os_clients.network.add_interface_router(
            router['id'], {'subnet_id': subnet['id']})

        # server = os_actions.create_basic_server(
        # net=net, sec_groups=[sec_group.name])
        # floating_ips_pool = os_clients.compute.floating_ip_pools.list()
        # floating_ip = os_clients.compute.floating_ips.create(
        #     pool=floating_ips_pool[0].name)
        # os_clients.compute.servers.add_floating_ip(server, floating_ip)

        # Clean
        # os_clients.compute.servers.remove_floating_ip(
        #     server, floating_ip)
        # os_clients.compute.floating_ips.delete(floating_ip)
        # os_clients.compute.servers.delete(server)
        os_clients.network.remove_gateway_router(router["id"])
        os_clients.network.remove_interface_router(
            router["id"], {"subnet_id": subnet['id']})
        os_clients.network.delete_subnet(subnet['id'])
        os_clients.network.delete_router(router['id'])
        os_clients.network.delete_network(net['id'])
        os_clients.compute.security_groups.delete(sec_group)

        es_client.check_notifications(
            neutron_event_types,
            query_filter="Logger:neutron", size=500)

    def test_cinder_notifications_toolchain(self, os_clients, es_client):
        """Check that Cinder notifications are present in Elasticsearch

        Scenario:
            1. Create a volume and update it
            2. Check that Cinder notifications are present in current
               Elasticsearch index

        Duration 15m
        """
        cinder_event_types = ["volume.update.start", "volume.update.end"]
        cinder = os_clients.volume
        logger.info("Create a volume")
        volume = cinder.volumes.create(size=1)
        wait_for_resource_status(
            os_clients.volume.volumes, volume.id, "available")
        logger.info("Update the volume")
        if cinder.version == 1:
            cinder.volumes.update(volume, display_name="updated_volume")
        else:
            cinder.volumes.update(volume, name="updated_volume")
        wait_for_resource_status(
            os_clients.volume.volumes, volume.id, "available")
        logger.info("Delete the volume")
        cinder.volumes.delete(volume)
        utils.wait(lambda: volume.id not in cinder.volumes.list())
        es_client.check_notifications(
            cinder_event_types,
            query_filter='volume_id:"{}"'.format(volume.id), size=500)

    @pytest.mark.parametrize(
        "components", determinate_components_names().values(),
        ids=determinate_components_names().keys())
    @pytest.mark.parametrize(
        "controllers_count", [1, 2], ids=["warning", "critical"])
    def test_toolchain_alert_service(self, destructive, cluster,
                                     influxdb_client, nagios_client,
                                     components, controllers_count):
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
                if action == "stop":
                    destructive.append(
                        lambda: node.os.manage_service(service_names[0],
                                                       "start"))
                node.os.manage_service(service_names[0], action)
            influxdb_client.check_cluster_status(
                service_names[1], service_state_in_influx)
            if service_names[3]:
                influxdb_client.check_count_of_haproxy_backends(
                    service_names[3], expected_count=down_backends_in_haproxy)
            nagios_client.wait_service_state_on_nagios(
                {service_names[2]: new_state})
            msg = (
                "Mail check failed for service: {} "
                "with new status: {}.".format(service_names[2], new_state))
            utils.wait(
                lambda: (
                    any(t_node.os.check_local_mail(service_names[2], new_state)
                        for t_node in toolchain_nodes)),
                timeout=5 * 60, interval=15, timeout_msg=msg)

        statuses = {1: (self.WARNING_STATUS, "WARNING"),
                    2: (self.CRITICAL_STATUS, "CRITICAL")}
        name_in_influx, name_in_alerting, services = components

        toolchain_nodes = cluster.filter_by_role("monitoring")

        controller_nodes = cluster.filter_by_role(
            "controller")[:controllers_count]

        for (service, haproxy_backend) in services:
            logger.info("Checking service {0}".format(service))
            verify_service_state_change(
                service_names=[
                    service,
                    name_in_influx,
                    name_in_alerting,
                    haproxy_backend],
                action="stop",
                new_state=statuses[controllers_count][1],
                service_state_in_influx=statuses[controllers_count][0],
                down_backends_in_haproxy=controllers_count,)
            verify_service_state_change(
                service_names=[
                    service,
                    name_in_influx,
                    name_in_alerting,
                    haproxy_backend],
                action="start",
                new_state="OK",
                service_state_in_influx=self.OKAY_STATUS,
                down_backends_in_haproxy=0,)

    @pytest.mark.parametrize(
        "dashboard_name",
        influxdb_grafana_api.get_all_grafana_dashboards_names())
    def test_grafana_dashboard_panel_queries(self, dashboard_name,
                                             grafana_client):
        """Verify that the panels on dashboards show up in the Grafana UI.

        Scenario:
            1. Check queries for all panels of given dashboard in Grafana.

        Duration 5m
        """
        grafana_client.check_grafana_online()
        dashboard = grafana_client.get_dashboard(dashboard_name)
        result = dashboard.classify_all_dashboard_queries()
        ok_panels, partially_ok_panels, no_table_panels, failed_panels = result
        fail_msg = (
            "Total OK: {len_ok}\n"
            "No table: {no_table}\n"
            "Total no table: {len_no}\n"
            "Partially ok queries: {partially_ok}\n"
            "Total partially ok: {len_partially_ok}\n"
            "Failed queries: {failed}\n"
            "Total failed: {len_fail}".format(
                len_ok=len(ok_panels),
                partially_ok=partially_ok_panels.items(),
                len_partially_ok=len(partially_ok_panels),
                no_table=no_table_panels.items(),
                len_no=len(no_table_panels),
                failed=failed_panels.items(),
                len_fail=len(failed_panels))
        )
        assert (ok_panels and not
                partially_ok_panels and not
                no_table_panels and not
                failed_panels), fail_msg
