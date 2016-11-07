import json
from random import choice
import yaml

import fuelclient
from fuelclient import client as api_client

import utils
from clients.system import general_client


class FuelConfig(object):
    def __init__(self, fuel_address, fuel_username, fuel_password):
        master_ssh = general_client.GeneralActionsClient(
            fuel_address, fuel_username, password=fuel_password)

        self.put_updated_hiera(master_ssh)
        fuel_access = self.get_hiera_value(master_ssh, "FUEL_ACCESS")

        self.api_connection = api_client.Client(
            host=fuel_address,
            port=8000,
            os_username=fuel_access["user"],
            os_password=fuel_access["password"],
            os_tenant_name="admin")

        nailgun_nodes_client = \
            fuelclient.get_client('node', connection=self.api_connection)

        nailgun_nodes = nailgun_nodes_client.get_all()
        private_key = master_ssh.get_file_content("/root/.ssh/id_rsa")

        self.nodes = []
        for nailgun_node in nailgun_nodes:
            node = {
                "address": nailgun_node["ip"],
                "hostname": nailgun_node["fqdn"],
                "username": "root",
                "private_key": private_key,
                "roles": nailgun_node["roles"]
            }
            self.nodes.append(node)

    def put_updated_hiera(self, ssh):
        ssh.put_file(utils.get_fixture("hiera"), "/tmp/hiera")
        ssh.exec_command("chmod +x /tmp/hiera")

    def get_hiera_value(self, ssh, value):
        return json.loads(ssh.exec_command(
            "/tmp/hiera --format json {0}".format(value)))

    # def get_openstack_credentials(self):
    #     controller = choice([node for node in self.nodes
    #                         if "controller" in node["roles"]])
    #     transport = ssh_transport.SSHTransport(
    #         address=controller["address"],
    #         username=controller["username"],
    #         private_key=controller["private_key"])
    #
    #     controller_ssh = general_client.GeneralActionsClient(transport)
    #
    #     controller_ssh.put_file("fixtures/hiera", "/tmp/hiera")
    #     controller_ssh.execute(["chmod", "+x", "/tmp/hiera"])
    #
    #     _, openstack_credentials, _ = controller_ssh.execute(
    #         ["/tmp/hiera", "--format", "json", "access"]
    #     )
    #     openstack_credentials = json.loads(openstack_credentials)
    #
    #     _, openstack_management_vip, _ = controller_ssh.execute(
    #         ["/tmp/hiera", "--format", "json", "management_vip"]
    #     )
    #     _, openstack_public_vip, _ = controller_ssh.execute(
    #         ["/tmp/hiera", "--format", "json", "public_vip"]
    #     )
    #     openstack_credentials.update({
    #         "management_vip": openstack_management_vip,
    #         "public_vip": openstack_public_vip
    #     })
    #
    #     return openstack_credentials

    def get_lma_credentials(self):
        monitoring = choice([node for node in self.nodes
                             if "elasticsearch_kibana" in node["roles"]])

        monitoring_ssh = general_client.GeneralActionsClient(
            address=monitoring["address"],
            username=monitoring["username"],
            private_key=monitoring["private_key"])

        self.put_updated_hiera(monitoring_ssh)

        lma_config = {
            "influxdb_vip":
                self.get_hiera_value(monitoring_ssh,
                                     "lma::influxdb::vip"),
            "influxdb_port":
                self.get_hiera_value(monitoring_ssh,
                                     "lma::influxdb::influxdb_port"),
            "influxdb_username":
                self.get_hiera_value(monitoring_ssh,
                                     "lma::influxdb::admin_username"),
            "influxdb_password":
                self.get_hiera_value(monitoring_ssh,
                                     "lma::influxdb::admin_password"),
            "influxdb_db_name": self.get_hiera_value(monitoring_ssh,
                                                     "lma::influxdb::dbname")
        }
        return lma_config

    def main(self):
        config = {
            "nodes": self.nodes,
            "lma": self.get_lma_credentials(),
        }

        config_filename = utils.get_fixture("config.yaml",
                                            check_existence=False)
        with file(config_filename, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False)


FuelConfig("10.109.0.2", "root", "r00tme").main()
