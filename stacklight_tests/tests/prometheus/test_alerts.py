import logging
import pytest

from stacklight_tests import utils

logger = logging.getLogger(__name__)

service_down_entities = {
    # format: {id_for_test: (service_to_stop, [filter(s)_for_nodes],
    # count_of_nodes_to_stop_on, alertname, service_name_in_alert)}
    "cinder_api_down":
        ("cinder-api", ["service.cinder.control.cluster_control"], 3,
         "CinderAPIDown", "cinder-api"),
    "glance_api_down":
        ("glance-api", ["service.glance.control.cluster"], 3,
         "GlanceAPIDown", "glance-api"),
    "neutron_api_down":
        ("neutron-server", ["service.neutron.control.cluster"], 3,
         "NeutronAPIDown", ""),
    "nova_api_down": ("nova-api", ["system.nova.control.cluster"], 3,
                      "NovaAPIDown", "nova-api"),
    "apache_down": ("apache2", ["service.apache.server.single"], 3,
                    "ApacheDown", "apache"),
    "glusterfs_down": ("glusterfs-server", ["service.glusterfs.server"], 1,
                       "GlusterFSDown", "glusterfs"),
    "heat_api_down": ("heat-api", ["service.heat.server.cluster"], 3,
                      "HeatAPIDown", "heat-api"),
    "keystone_api_down": ("apache2", ["service.keystone.server.cluster"], 3,
                          "KeystoneAPIDown", "keystone-public-api"),
    "rabbitmq_down": ("rabbitmq-server", ["service.rabbitmq.server.cluster"],
                      1, "RabbitMQDown", "rabbitmq"),
    "nginx_down": ("nginx", ["service.nginx.server.single"], 1, "NginxDown",
                   "nginx"),
    "procstat_influxdb": ("influxdb", ["influxdb"], 1,
                          "ProcstatRunningInfluxdb", "influxdb"),
    "procstat_memcached": ("memcached", ["memcached"], 1,
                           "ProcstatRunningMemcached", "memcached"),
    "procstat_keepalived": ("keepalived", ["keepalived"], 1,
                            "ProcstatRunningKeepalived", "keepalived"),
    "procstat_kibana": ("kibana", ["kibana"], 1, "ProcstatRunningKibana",
                        "kibana"),
    "procstat_docker": ("docker", ["docker"], 1, "ProcstatRunningDockerd",
                        "docker"),
    "procstat_kube_proxy": ("kube-proxy", ["k8s_controller"], 1,
                            "ProcstatRunningKubernetes", "kubernetes"),
    "procstat_kube_apiserver": ("kube-apiserver", ["k8s_controller"], 1,
                                "ProcstatRunningKubernetes", "kubernetes"),
    "procstat_kube_controller_manager":
        ("kube-controller-manager", ["k8s_controller"], 1,
         "ProcstatRunningKubernetes", "kubernetes"),
    "procstat_kubelet": ("kubelet", ["k8s_controller"], 1,
                         "ProcstatRunningKubernetes", "kubernetes"),
    "procstat_kube_scheduler": ("kube-scheduler", ["k8s_controller"], 1,
                                "ProcstatRunningKubernetes", "kubernetes"),
    "procstat_calico": ("calico-node", ["k8s_controller"], 1,
                        "ProcstatRunningCalico", "calico"),
    "etcd_cluster_small": ("etcd", ["k8s_controller"], 1, "EtcdClusterSmall",
                           "etcd"),
    "neutron_all_agents_down":
        ("neutron-l3-agent",
         ["system.neutron.compute.cluster", "service.neutron.gateway.single"],
         3, "NeutronAllAgentsDown", "neutron-l3-agent"),
    "neutron_only_one_agent_up":
        ("neutron-metadata-agent",
         ["system.neutron.compute.cluster", "service.neutron.gateway.single"],
         2, "NeutronOnlyOneAgentUp", "neutron-metadata-agent"),
    "neutron_some_agents_down":
        ("neutron-openvswitch-agent",
         ["system.neutron.compute.cluster", "service.neutron.gateway.single"],
         1, "NeutronSomeAgentsDown", "neutron-openvswitch-agent"),
    "nova_only_one_service_up": ("nova-cert", ["system.nova.control.cluster"],
                                 2, "NovaOnlyOneServiceUp", "nova-cert"),
    "nova_some_services_down":
        ("nova-conductor", ["system.nova.control.cluster"], 1,
         "NovaSomeServicesDown", "nova-conductor"),
    "nova_all_services_down":
        ("nova-scheduler", ["system.nova.control.cluster"], 3,
         "NovaAllServicesDown", "nova-scheduler"),
    "nova_all_computes_down": ("nova-compute", ["service.nova.compute.kvm"], 2,
                               "NovaAllComputesDown", "nova-compute"),
    "nova_some_computes_down": ("nova-compute", ["service.nova.compute.kvm"],
                                1, "NovaSomeComputesDown", "nova-compute"),
    "nova_libvirt_down": ("libvirt-bin", ["service.nova.compute.kvm"], 1,
                          "NovaLibvirtDown", "libvirt"),
}


class TestPrometheusAlerts(object):
    def test_system_load_alerts(self, cluster, prometheus_alerting):
        def check_status(is_fired=True):
            alert_names = ["SystemLoad5", "AvgCPUUsageIdle"]
            for alert_name in alert_names:
                criteria = {
                    "name": alert_name,
                    "host": compute.hostname,
                }
                prometheus_alerting.check_alert_status(
                    criteria, is_fired=is_fired, timeout=6 * 60)

        load_processes_count = 20

        # TODO(rpromyshlennikov): use ".get_random_compute" method
        # instead of current filter after roles config of hosts will be fixed
        compute = [host for host in cluster.hosts
                   if host.fqdn.startswith("cmp")][0]

        check_status(is_fired=False)
        with compute.os.make_temporary_load(load_processes_count):
            check_status()
        check_status(is_fired=False)

    def test_system_mem_alert(self, cluster, prometheus_alerting):
        cmp = cluster.filter_by_role("compute")[0]
        criteria = {
            "name": "AvgMemAvailablePercent",
            "service": "system",
        }
        cmp.os.apt_get_install_package("stress")
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=10 * 60)
        memory = cmp.exec_command("grep MemFree /proc/meminfo")
        _, memory, _ = memory.split()
        memory = str(int(memory) * 0.99)
        command = "nohup stress --vm-bytes " + memory + "k --vm-keep -m 1" \
                  " --timeout 600 &"
        cmp.exec_command(command)
        prometheus_alerting.check_alert_status(
            criteria, is_fired=True, timeout=10 * 60)
        cmp.os.apt_get_remove_package("stress")
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=10 * 60)

    def test_predict_linear_disk_inodes_free_alert(
            self, cluster, prometheus_alerting):
        cmp = cluster.filter_by_role("compute")[0]
        criteria = {
            "name": "PredictLinearDiskInodesFree",
            "service": "system",
        }
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=10 * 60)
        cmp.exec_command("cd /dev/shm; for i in {1..4}; "
                         "do touch {$i}a{000001..100000}.c; done")
        prometheus_alerting.check_alert_status(
            criteria, is_fired=True, timeout=10 * 60)
        remove_files = "cd /dev/shm; find . -name '*.c' -print0 | xargs -0 rm"
        cmp.exec_command(remove_files)
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=15 * 60)

    def test_system_predict_linear_disk_free_alert(self, cluster,
                                                   prometheus_alerting):
        cmp = cluster.filter_by_role("compute")[0]
        criteria = {
            "name": "PredictLinearDiskFree",
            "service": "system",
        }
        cmp.os.apt_get_install_package("stress")
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=10 * 60)
        command = "cd /dev/shm; nohup stress -d 2 --timeout 480s &"
        cmp.exec_command(command)
        prometheus_alerting.check_alert_status(
            criteria, is_fired=True, timeout=10 * 60)
        cmp.os.apt_get_remove_package("stress")
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=15 * 60)

    def test_influxdb_httpclient_error_alert(
            self, cluster, prometheus_alerting):
        infl_node = cluster.filter_by_role("influxdb")[0]
        criteria = {
            "name": "InfluxdbHTTPClientError",
            "service": "influxdb",
        }
        prometheus_alerting.check_alert_status(criteria, is_fired=False)
        command = (
            "for i in {1..6000}; do influx -host " + str(infl_node.address) +
            " -port 8086 -database lma -username lma -password lmapass "
            "execute 'show tables' &>/dev/null; done"
        )
        infl_node.exec_command(command)
        prometheus_alerting.check_alert_status(
            criteria, is_fired=True, timeout=6 * 60)
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=6 * 60)

    @pytest.mark.parametrize(
        "entities", service_down_entities.values(),
        ids=service_down_entities.keys())
    def test_service_down_alerts(self, cluster, destructive,
                                 prometheus_alerting, entities):
        service = entities[0]
        roles = entities[1]
        target_nodes = []
        for role in roles:
            target_nodes.extend(cluster.filter_by_role(role))
        if not target_nodes:
            pytest.skip("No nodes with {} role(s) found".format(
                ', '.join([role for role in roles])))
        target_nodes = target_nodes[:entities[2]]
        criteria = {
            "name": entities[3],
            "service": entities[4],
        }
        prometheus_alerting.check_alert_status(criteria, is_fired=False)
        logger.info("Stop {} service on {} node(s)".format(
            service, ', '.join([str(n.hostname) for n in target_nodes])))
        for node in target_nodes:
            destructive.append(
                lambda: node.os.manage_service(service, "start"))
            node.os.manage_service(service, "stop")
        prometheus_alerting.check_alert_status(
            criteria, is_fired=True, timeout=10 * 60)
        logger.info("Start {} service on {} node(s)".format(
            service, ', '.join([str(n.hostname) for n in target_nodes])))
        for node in target_nodes:
            node.os.manage_service(service, "start")
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=10 * 60)

    def test_nova_aggregates_memory(self, prometheus_api, prometheus_alerting,
                                    os_clients, os_actions, destructive):
        def get_agg_free_ram(a_n, a_id):
            def _get_current_value(q):
                try:
                    v = prometheus_api.get_query(q)[0]["value"][1]
                except IndexError:
                    v = 0
                return v
            query = ('openstack_nova_aggregate_free_ram{aggregate="' + a_n +
                     '",aggregate_id="' + str(a_id) + '"}')
            utils.wait(lambda: _get_current_value(query) != 0,
                       interval=10, timeout=2 * 60)
            return _get_current_value(query)

        client = os_clients.compute
        aggr_name = "test-aggr"
        az = "test-az"
        host = "cmp01"
        aggr = client.aggregates.create(aggr_name, az)
        client.aggregates.add_host(aggr, host)
        destructive.append(lambda: client.aggregates.remove_host(
            aggr, host))
        destructive.append(lambda: client.aggregates.delete(aggr.id))
        criteria = {
            "name": "NovaAggregatesFreeMemoryLow"
        }
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=10 * 60)
        free_ram = get_agg_free_ram(aggr_name, aggr.id)
        image = os_actions.get_cirros_image()
        flavor = os_actions.create_flavor(
            name="test_flavor", ram=int(free_ram) - 100)
        destructive.append(lambda: client.flavors.delete(flavor))
        tenant_id = os_actions.get_admin_tenant().id
        net = os_actions.create_network(tenant_id)
        subnet = os_actions.create_subnet(net, tenant_id, "192.168.100.0/24")
        server = os_actions.create_basic_server(image, flavor, net,
                                                availability_zone=az)
        destructive.append(lambda: client.servers.delete(server))
        destructive.append(lambda: os_clients.network.delete_subnet(
            subnet['id']))
        destructive.append(lambda: os_clients.network.delete_network(
            net['id']))
        prometheus_alerting.check_alert_status(
            criteria, is_fired=True, timeout=10 * 60)
        client.servers.delete(server)
        utils.wait(
            lambda: (server.id not in [s.id for s in client.servers.list()])
        )
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=10 * 60)
        os_clients.network.delete_subnet(subnet['id'])
        os_clients.network.delete_network(net['id'])
        client.flavors.delete(flavor)
        client.aggregates.remove_host(aggr, host)
        client.aggregates.delete(aggr.id)
