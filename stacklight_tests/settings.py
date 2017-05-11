import logging
import os


# Logging settings
CONSOLE_LOG_LEVEL = os.environ.get('LOG_LEVEL', logging.DEBUG)

# FUEL connection options
ENV_FUEL_IP = os.environ.get("ENV_FUEL_IP", "10.109.0.2")
ENV_FUEL_LOGIN = os.environ.get("ENV_FUEL_LOGIN", "root")
ENV_FUEL_PASSWORD = os.environ.get("ENV_FUEL_PASSWORD", "r00tme")

# Plugins info
INFLUXDB_GRAFANA_PLUGIN_VERSION = os.environ.get(
    "INFLUXDB_GRAFANA_PLUGIN_VERSION", "1.0")
ENV_CLUSTER_NAME = os.environ.get("ENV_CLUSTER_NAME", None)

# Images dir
IMAGES_PATH = os.environ.get("IMAGES_PATH", os.path.expanduser('~/images'))
CIRROS_QCOW2_URL = os.environ.get(
    "CIRROS_QCOW2_URL",
    "http://download.cirros-cloud.net/0.3.4/cirros-0.3.4-x86_64-disk.img"
)

CONFIGURE_APPS = ["nodes", "influxdb", "elasticsearch", "grafana",
                  "nagios", "keystone", "mysql", "prometheus"]
