import subprocess

import yaml

from stacklight_tests import utils

if __name__ == '__main__':
    config = yaml.load(open(utils.get_fixture("config.yaml")))
    auth = config.get("auth")
    cert_content = auth["public_ssl"]["cert_data"]["content"]
    if not cert_content:
        exit()
    ip = auth["public_vip"]
    hostname = auth["public_ssl"]["hostname"]
    script = utils.get_fixture("update_hosts.sh")
    subprocess.check_call(["sudo", script, ip, hostname])
