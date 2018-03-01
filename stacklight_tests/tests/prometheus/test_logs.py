import pytest


heka_loggers = {
    "haproxy": ("haproxy", 'system.haproxy'),
    "neutron": ("neutron", 'openstack.neutron'),
    "glance": ("glance", 'openstack.glance'),
    "keystone": ("keystone", 'openstack.keystone'),
    "heat": ("heat", 'openstack.heat'),
    "cinder": ("cinder", 'openstack.cinder'),
    "nova": ("nova", 'openstack.nova'),
    "rabbitmq": ("rabbitmq", 'rabbitmq.ctl01'),
    "system": ("linux", 'system.auth'),
    "zookeeper": ("opencontrail", 'contrail.zookeeper'),
    "cassandra": ("opencontrail", 'contrail.cassandra.system'),
    "contrail": ("opencontrail", 'contrail.discovery')
}


fluentd_loggers = {
    "haproxy": ("haproxy", 'haproxy.general'),
    "neutron": ("neutron", 'openstack.neutron'),
    "glance": ("glance", 'openstack.glance'),
    "keystone": ("keystone", 'openstack.keystone'),
    "heat": ("heat", 'openstack.heat'),
    "cinder": ("cinder", 'openstack.cinder'),
    "nova": ("nova", 'openstack.nova'),
    "rabbitmq": ("rabbitmq", 'rabbitmq'),
    "system": ("linux", 'systemd.source.systemd'),
    "zookeeper": ("opencontrail", 'opencontrail.zookeeper'),
    "cassandra": ("opencontrail", 'opencontrail.cassandra.system'),
    "contrail": ("opencontrail", 'opencontrail.discovery')
}


@pytest.mark.smoke
@pytest.mark.parametrize(argnames="input_data",
                         argvalues=heka_loggers.values(),
                         ids=heka_loggers.keys())
def test_heka_logs(es_client, cluster, input_data):
    requirement, logger = input_data
    if not ("service.heka.log_collector.single"
            in [node.roles for node in cluster][0]):
        pytest.skip("Heka is not installed in the cluster")
    if not any([requirement in node.roles for node in cluster]):
        pytest.skip("No required class {} for queries: {}".format(
            requirement, logger))

    assert logger in es_client.return_loggers()


@pytest.mark.smoke
@pytest.mark.parametrize(argnames="input_data",
                         argvalues=fluentd_loggers.values(),
                         ids=fluentd_loggers.keys())
def test_fluentd_logs(es_client, cluster, input_data):
    requirement, logger = input_data
    if not ("service.fluentd" in [node.roles for node in cluster][0]):
        pytest.skip("Heka is not installed in the cluster")
    if not any([requirement in node.roles for node in cluster]):
        pytest.skip("No required class {} for queries: {}".format(
            requirement, logger))

    assert logger in es_client.return_loggers()
