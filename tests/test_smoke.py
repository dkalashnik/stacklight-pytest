from tests import base_test


class TestSmoke(base_test.BaseLMATest):
    def test_logs_in_elasticsearch(self):
        """Check that logs of all known services are presented
        in Elasticsearch

        Scenario:
            1. Check that logs are collected for all known services
               to current Elasticsearch index

        Duration 15m
        """
        known_services = {
            'CRON', 'api', 'attrd',
            'cib',
            'cinder-api', 'cinder-backup', 'cinder-scheduler', 'cinder-volume',
            'crmd',
            'dhcp-agent',
            'glare',
            'haproxy',
            'heat-api', 'heat-api-cfn', 'heat-api-cloudwatch', 'heat-engine',
            'horizon_access',
            'keystone-admin', 'keystone-public',
            'keystone-wsgi-admin', 'keystone-wsgi-main',
            'l3-agent',
            'liberasurecode',
            'lrmd',
            'metadata-agent',
            'nagios3',
            'neutron-openvswitch-agent',
            'nova-api', 'nova-compute', 'nova-conductor', 'nova-scheduler',
            'ocf-mysql-wss', 'ocf-ns_IPaddr2', 'ocf-ns_apache(apache2-nagios)',
            'ocf-ns_conntrackd', 'ocf-ns_dns', 'ocf-ns_haproxy', 'ocf-ns_ntp',
            'ocf-ns_vrouter',
            'openvswitch-agent',
            'pengine',
            'registry',
            'server',
            'su',
            'swift-account-server', 'swift-container-server',
            'swift-object-server', 'swift-proxy-server',
            'xinetd'
        }
        # NOTE(some services, available only after deploy)
        # after_deploy_services = {
        #     'dnsmasq', 'dnsmasq-dhcp',
        #     'kernel',
        #     'ntpd', 'ntpdate',
        #     'ovs-vswitchd',
        #     'rabbitmq',
        #     'sshd',
        #
        # }
        for service in known_services:
            output = self.es_kibana_api.query_elasticsearch(
                index_type="log",
                query_filter="programname:{service}".format(service=service))
            assert output['hits']['total'] != 0, (
                "Indexes don't contain {service} logs".format(service=service))
