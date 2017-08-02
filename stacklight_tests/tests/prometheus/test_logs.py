import pytest


service_log_queries = {
    "haproxy":
        ("haproxy", ['programname:haproxy']),

    "ovs":
        ("ovs", ['Logger:ovs AND programname:ovs-vswitchd',
                 'Logger:ovs AND programname:ovsdb-server']),

    "neutron_agents":
        ("neutron.agent",
         ['Logger:openstack.neutron AND programname:dhcp-agent',
          'Logger:openstack.neutron AND programname:l3-agent',
          'Logger:openstack.neutron AND programname:metadata-agent']),

    "glance":
        ("glance",
         ['Logger:openstack.glance AND programname:api',
          'Logger:glusterfs AND programname:glusterd',
          'Logger:openstack.glance AND programname:registry']),

    "keystone":
        ("keystone",
         ['Logger:openstack.keystone AND programname:keystone']),

    "heat":
        ("heat",
         ['Logger:openstack.heat AND programname:heat']),

    "cinder":
        ("cinder",
         ['Logger:openstack.cinder AND programname:cinder-api',
          'Logger:openstack.cinder AND programname:cinder-backup',
          'Logger:openstack.cinder AND programname:cinder-scheduler',
          'Logger:openstack.cinder AND programname:cinder-volume',
          'Logger:openstack.cinder AND programname:cinder-manage']),

    "nova":
        ("nova",
         ['Logger:openstack.nova AND programname:nova-api',
          'Logger:openstack.nova AND programname:nova-compute',
          'Logger:openstack.nova AND programname:nova-scheduler']),

    "rabbitmq":
        ("rabbitmq",
         ['Logger:rabbitmq* AND programname:rabbitmq']),

    "horizon":
        ("horizon",
         ['Logger:openstack.horizon AND programname:openstack.horizon']),

    "system":
        ("linux",
         ['Logger:system.auth',
          'Logger:system.kern',
          'Logger:system.syslog']),

    "zookeeper":
        ("opencontrail",
         ['Logger:contrail.zookeeper AND programname:zookeeper']),

    "cassandra":
        ("opencontrail",
         ['Logger:contrail.cassandra.system AND programname:cassandra',
          'Logger:contrail.cassandra.status AND programname:cassandra']),

    "contrail":
        ("opencontrail",
         ['Logger:contrail.alarm*',
          'Logger:contrail.discovery*'])
}


@pytest.mark.smoke
@pytest.mark.parametrize(argnames="input_data",
                         argvalues=service_log_queries .values(),
                         ids=service_log_queries .keys())
def test_log(es_client, cluster, input_data):
    requirement, queries = input_data

    if not any([requirement in node.roles for node in cluster]):
        pytest.skip("No required class {} for queries: {}".format(
            requirement, queries))

    default_time = "now-7d"

    absent_logs = es_client.get_absent_programs_for_group(
        queries, time_range=default_time)

    assert not absent_logs
