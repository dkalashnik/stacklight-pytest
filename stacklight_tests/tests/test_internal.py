from __future__ import print_function

import pytest


class TestInternal(object):
    def test_check_os_conn(self, os_clients):
        # Auto client test
        print(os_clients.auth.users.list())
        print(os_clients.compute.servers.list())
        print(os_clients.network.list_networks())
        print(os_clients.volume.volumes.list())
        print(list(os_clients.orchestration.stacks.list()))
        print(list(os_clients.image.images.list()))

    def test_delete_all_resources(self, os_clients, resources_ids=None):
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
            stack = os_clients.orchestration.stacks.get(stack_id)
            os_clients.orchestration.stacks.delete(stack.id)

        for floating_ip_id in resources_ids["floating_ips"]:
            floating_ip = os_clients.compute.floating_ips.get(
                floating_ip_id)
            os_clients.compute.floating_ips.delete(floating_ip)

        for server_id in resources_ids["servers"]:
            server = os_clients.compute.servers.get(server_id)
            os_clients.compute.servers.delete(server)

        routers = []
        for net_res_id in resources_ids["routers"]:
            try:
                router = os_clients.network.show_router(net_res_id)
                if router:
                    routers.append(router["router"])
                    os_clients.network.remove_gateway_router(
                        router["router"]["id"])
            except Exception as e:
                print(e)

        subnets = []
        for net_res_id in resources_ids["subnets"]:
            try:
                subnet = os_clients.network.show_subnet(net_res_id)
                if subnet:
                    subnets.append(subnet["subnet"])
            except Exception as e:
                print(e)

        for router in routers:
            for subnet in subnets:
                try:
                    os_clients.network.remove_interface_router(
                        router["id"], {"subnet_id": subnet['id']})
                except Exception as e:
                    print(e)
            os_clients.network.delete_router(router['id'])

        for port_id in resources_ids["ports"]:
            try:
                port = os_clients.network.show_port(port_id)["port"]
                os_clients.network.delete_port(port['id'])
            except Exception as e:
                print(e)

        if resources_ids["ports"]:
            for port in os_clients.network.list_ports()["ports"]:
                try:
                    os_clients.network.delete_port(port['id'])
                except Exception as e:
                    print(e)

        for subnet in subnets:
            try:
                os_clients.network.delete_subnet(subnet['id'])
            except Exception as e:
                print(e)

        for net_res_id in resources_ids["nets"]:
            try:
                os_clients.network.delete_network(net_res_id)
            except Exception as e:
                print(e)

        for sec_group_id in resources_ids["sec_groups"]:
            try:
                sec_group = os_clients.compute.security_groups.get(
                    sec_group_id)
                if sec_group:
                    os_clients.compute.security_groups.delete(sec_group)
            except Exception as e:
                print(e)

    @pytest.mark.parametrize("component", [1, 0])
    def test_destructive_fixture(self, destructive, component):
        # NOTE(rpromyshlennikov): one should pass, other should fail
        def recovery_action(string="Test destructive"):
            print(string)
        destructive.append(lambda: recovery_action())
        destructive.append(lambda: recovery_action(string="Test 1"))
        destructive.append(lambda: recovery_action(string="Test 2"))
        print("Test itself")
        if component:
            # NOTE(rpromyshlennikov): should fail here
            raise Exception("Boo")
        print("After raise")

    def test_skip_on_no_config(self, nagios_client):
        # NOTE(rpromyshlennikov): should be skipped,
        # if no nagios section in config
        print("Should be skipped")
        assert False

    def test_some_config_presented(self, nodes_config, prometheus_config):
        assert nodes_config != prometheus_config
