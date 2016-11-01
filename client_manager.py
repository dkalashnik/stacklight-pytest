# import aodhclient.client
# import cinderclient.client
# import glanceclient.client
# import keystoneclient
# import novaclient.exceptions as nova_exc
import novaclient.client
import novaclient.v2.client
import time
from influxdb_api.api import InfluxdbPluginApi
from general_client import GeneralActionsClient

#from keystoneauth1.identity import v3
#from keystoneauth1 import session
#from novaclient import client
#auth = v3.Password(auth_url=OS_AUTH_URL,
#                   username=OS_USERNAME,
#                   password=OS_PASSWORD,
#                   project_name=OS_TENANT_NAME,
#                  user_domain_id='default',
#                   project_domain_id='default'
#                   )
#sess = session.Session(auth=auth)
#nova = client.Client("2.0", session=sess)

import logging
LOG = logging.getLogger(__name__)
# Default client libs
try:
    import heatclient.v1.client
except Exception:
    #LOG.exception()
    LOG.warning('Heatclient could not be imported.')
try:
    import muranoclient.v1.client
except Exception:
    #LOG.exception()
    LOG.warning('Muranoclient could not be imported.')
try:
    import saharaclient.client
except Exception:
    #LOG.exception()
    LOG.warning('Sahara client could not be imported.')
try:
    import ceilometerclient.v2.client
except Exception:
    # LOG.exception()
    LOG.warning('Ceilometer client could not be imported.')
try:
    import neutronclient.neutron.client
except Exception:
    # LOG.exception()
    LOG.warning('Neutron client could not be imported.')
try:
    import glanceclient
except Exception:
    # LOG.exception()
    LOG.warning('Glance client could not be imported')
try:
    import ironicclient
except Exception:
    # LOG.exception()
    LOG.warning('Ironic client could not be imported')
try:
    import muranoclient.glance.client as art_client
except Exception:
    # LOG.exception()
    LOG.warning('Artifacts client could not be imported')


class OfficialClientManager(object):
    """Manager that provides access to the official python clients for
    calling various OpenStack APIs.
    """

    NOVACLIENT_VERSION = '2'
    CINDERCLIENT_VERSION = '2'

    def __init__(self):
        self.traceback = ''

        self.client_attr_names = [
            'compute_client'
        ]

    def get_compute_client(self,
                           username=None,
                           password=None,
                           tenant_name=None,
                           identity_url=None):
        """Get client for compute

        :param username:
        :param password:
        :param tenant_name:
        :param identity_url:
        :rtype:  novaclient.v2.client.Client
        """
        if None in (username, password, tenant_name):
            print(username, password, tenant_name)
            msg = ("Missing required credentials for identity client. "
                   "username: {username}, password: {password}, "
                   "tenant_name: {tenant_name}").format(
                       username=username,
                       password=password,
                       tenant_name=tenant_name, )
            raise msg

        client_args = (username, password, tenant_name, identity_url)

        service_type = 'compute'
        print(self.NOVACLIENT_VERSION)
        return novaclient.client.Client(self.NOVACLIENT_VERSION,
                                        *client_args,
                                        service_type=service_type,
                                        no_cache=True,
                                        insecure=True,
                                        endpoint_type='publicURL')

OS_TENANT_NAME='admin'
OS_PROJECT_NAME='admin'
OS_USERNAME='admin'
OS_PASSWORD='admin'
# OS_AUTH_URL='https://10.109.8.6:5000/v2.0/'
OS_AUTH_URL='https://public.fuel.local:5000/v2.0/'

client = OfficialClientManager().get_compute_client(
    username=OS_USERNAME,
    password=OS_PASSWORD,
    tenant_name=OS_PROJECT_NAME,
    identity_url=OS_AUTH_URL)


#ssh_client = GeneralActionsClient('10.109.0.2','root', password='r00tme')
# Get it from master node at /root/.ssh/id_rsa
pkey = open('./fixtures/id_rsa').read()
ssh_client = GeneralActionsClient('10.109.0.3',
                                  'root',
                                  private_key=pkey)

OKAY_STATUS = 0 #
WARNING_STATUS = 1
UNKNOWN_STATUS = 2
CRITICAL_STATUS = 3
DOWN_STATUS = 4

RABBITMQ_DISK_WARNING_PERCENT = 99.99
RABBITMQ_DISK_CRITICAL_PERCENT = 100
RABBITMQ_MEMORY_WARNING_VALUE = 1.01
RABBITMQ_MEMORY_CRITICAL_VALUE = 1.0001


INFLUXDB_GRAFANA = InfluxdbPluginApi()
# TEST grafana api


def check_rabbit_mq_disk_alarms(controller,
                                status,
                                percent,
                                ssh_client,
                                timeout=60):
    """

    :param controller:
    :param status:
    :param percent:
    :param timeout:
    """
    check_alarms("service", "rabbitmq-cluster", "disk",
                 controller["hostname"], OKAY_STATUS, timeout=timeout)
    default_value = ssh_client.execute(
        "rabbitmqctl environment | grep disk_free_limit | "
        "sed -r 's/}.+//' | sed 's|.*,||'").rstrip()

    cmd = ("rabbitmqctl -n rabbit@messaging-node-3 set_disk_free_limit $(df | grep /dev/dm- | "
           "awk '{{ printf(\"%.0f\\n\", 1024 * ((($3 + $4) * "
           "{percent} / 100) - $3))}}')")
    ssh_client.execute(cmd.format(percent=percent))
    check_alarms("service", "rabbitmq-cluster", "disk",
                 controller["hostname"], status)
    ssh_client.execute(
        "rabbitmqctl set_disk_free_limit {}".format(default_value))
    check_alarms("service",
                 "rabbitmq-cluster",
                 "disk",
                 controller["hostname"],
                 OKAY_STATUS)


def check_alarms(alarm_type, filter_value, source, hostname,
                 value,
                 time_interval="now() - 5m",
                 timeout=60):
    """

    :param alarm_type:
    :param filter_value:
    :param source:
    :param hostname:
    :param value:
    :param time_interval:
    :param timeout:
    """
    filter_by = "node_role"
    if alarm_type == "service":
        filter_by = "service"
    filters = [
        "time >= {}".format(time_interval),
        "source = '{}'".format(source),
        "{} = '{}'".format(filter_by, filter_value),
        "value = {}".format(value)
    ]
    if hostname is not None:
        filters.append("hostname = '{}'".format(hostname))

    query = "select last(value) from {select_from} where {filters}".format(
        select_from="{}_status".format(alarm_type),
        filters=" and ".join(filters))

    def check_result():
        result = INFLUXDB_GRAFANA.do_influxdb_query(
            query=query).json()['results'][0]
        return len(result)

    msg = ('Alarm of type: {}: entity: {}, source:{}, hostname: {}, '
           'value: {} wasn\'t triggered'.format(alarm_type, filter_value,
                                                source, hostname, value))
    # TODO devops_helpers?
    wait(check_result, timeout=timeout * 5,
         interval=10, timeout_msg=msg)


class TimeoutError(RuntimeError):
    pass


def wait(predicate, interval=5, timeout=60, timeout_msg="Waiting timed out"):
    """Wait until predicate will become True.

    returns number of seconds that is left or 0 if timeout is None.

    Options:

    interval - seconds between checks.

    timeout  - raise TimeoutError if predicate won't become True after
    this amount of seconds. 'None' disables timeout.

    timeout_msg - text of the TimeoutError
    """
    start_time = time.time()
    if not timeout:
        return predicate()
    while not predicate():
        if start_time + timeout < time.time():
            raise TimeoutError(timeout_msg)

        seconds_to_sleep = max(
            0,
            min(interval, start_time + timeout - time.time()))
        time.sleep(seconds_to_sleep)

    return timeout + start_time - time.time()


if __name__ == '__main__':
    check_rabbit_mq_disk_alarms(
        {'hostname': 'node-3'},
        WARNING_STATUS,
        RABBITMQ_DISK_WARNING_PERCENT,
        ssh_client)
    ssh_client.get_date()
    # client.flavors.list()
