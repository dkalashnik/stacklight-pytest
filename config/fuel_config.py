import json
from random import choice
import yaml

import fuelclient
from fuelclient import client as api_client

import utils
from clients.system import general_client


class FuelConfig(object):
    def __init__(self, fuel_address, fuel_username, fuel_password):
        self.address = fuel_address

        self.master_ssh = general_client.GeneralActionsClient(
            fuel_address, fuel_username, fuel_password)

    def get_nailgun_config(self):
        self.master_ssh.put_file("fixtures/hiera", "/tmp/hiera")
        self.master_ssh.execute(["chmod", "+x", "/tmp/hiera"])

        exit_status, stdout, stderr = self.master_ssh.execute(
            ["/tmp/hiera", "--format", "json", "FUEL_ACCESS"])

        return json.loads(stdout)

    def setup_fuelclient(self, address,
                         port=8000,
                         os_username="admin",
                         os_password="admin",
                         os_tenant_name="admin"):
        self.api_connection = api_client.Client(host=address,
                                                port=port,
                                                os_username=os_username,
                                                os_password=os_password,
                                                os_tenant_name=os_tenant_name)

    def get_nodes_from_nailgun(self):
        nailgun_nodes_client = \
            fuelclient.get_client('node', connection=self.api_connection)
        nailgun_nodes = nailgun_nodes_client.get_all()
        private_key = self.master_ssh.get_file_content("/root/.ssh/id_rsa")

        nodes = []
        for nailgun_node in nailgun_nodes:
            node = {
                "address": nailgun_node["ip"],
                "hostname": nailgun_node["fqdn"],
                "username": "root",
                "private_key": private_key,
                "roles": nailgun_node["roles"]
            }
            nodes.append(node)
        return nodes

    def get_openstack_credentials(self):
        controller = choice([node for node in self.nodes
                            if "controller" in node["roles"]])
        controller_ssh = general_client.GeneralActionsClient(
            address=controller["address"],
            username=controller["username"],
            private_key=controller["private_key"])

        controller_ssh.put_file("fixtures/hiera", "/tmp/hiera")
        controller_ssh.execute(["chmod", "+x", "/tmp/hiera"])

        _, openstack_credentials, _ = controller_ssh.execute(
            ["/tmp/hiera", "--format", "json", "access"]
        )
        openstack_credentials = json.loads(openstack_credentials)

        _, openstack_management_vip, _ = controller_ssh.execute(
            ["/tmp/hiera", "--format", "json", "management_vip"]
        )
        _, openstack_public_vip, _ = controller_ssh.execute(
            ["/tmp/hiera", "--format", "json", "public_vip"]
        )
        openstack_credentials.update({
            "management_vip": openstack_management_vip,
            "public_vip": openstack_public_vip
        })

        return openstack_credentials

    def get_lma_credentials(self):
        monitoring = choice([node for node in self.nodes
                             if "elasticsearch_kibana" in node["roles"]])
        monitoring_ssh = general_client.GeneralActionsClient(
            address=monitoring["address"],
            username=monitoring["username"],
            private_key=monitoring["private_key"])

        monitoring_ssh.put_file("fixtures/hiera", "/tmp/hiera")
        monitoring_ssh.execute(["chmod", "+x", "/tmp/hiera"])

        _, lma_credentials, _ = monitoring_ssh.execute(
            ["/tmp/hiera", "--format", "json", "lma::kibana::authnz"]
        )
        lma_credentials = json.loads(lma_credentials)

        lma_credentials.update({
            "lma::kibana::vip": monitoring_ssh.execute(
                ["/tmp/hiera", "--format", "json", "lma::kibana::vip"]
            ),
            "lma::elasticsearch::vip": monitoring_ssh.execute(
                ["/tmp/hiera", "--format", "json", "lma::elasticsearch::vip"]
            ),
        })

        return lma_credentials

    def main(self):
        fuel_access = self.get_nailgun_config()
        self.setup_fuelclient(self.address,
                              os_username=fuel_access["user"],
                              os_password=fuel_access["password"])
        self.nodes = self.get_nodes_from_nailgun()
        self.openstack_credentials = self.get_openstack_credentials()
        self.lma_credentials = self.get_lma_credentials()
        config = {
            "nodes": self.nodes,
            "openstack": self.openstack_credentials,
            "lma": self.lma_credentials,
            "general": {
                "transport": "clients.system.ssh.ssh_transport.SSHTransport"
            }
        }

        config_filename = utils.get_fixture("config.yaml")
        with file(config_filename, "w") as f:
            yaml.dump(config, f)


FuelConfig("10.109.0.2", "root", "r00tme").main()
