import json

from clients.system import general_client


def get_nailgun_config(address, username, password, key_file=None, key=None):
    ssh = general_client.GeneralActionsClient(address, username, password)
    ssh.put_file("fixtures/hiera", "/tmp/hiera")
    ssh.execute(["chmod", "+x", "/tmp/hiera"])

    exit_status, stdout, stderr = ssh.execute(
        ["/tmp/hiera", "--format", "json", "FUEL_ACCESS"])
    print stdout
    print json.loads(stdout)


def get_nodes_from_nailgun():
    pass


def get_openstack_credentials():
    pass


def get_lma_credentials():
    pass


def main():
    get_nailgun_config("10.109.0.2", "root", "r00tme")

main()
