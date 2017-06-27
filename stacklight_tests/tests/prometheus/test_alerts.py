import pytest


class TestPrometheusAlerts(object):
    def test_system_load_alerts(self, cluster, prometheus_alerting):
        """Check that alert for load overage and idle on node can be fired.

        Scenario:
            1. Check that alert is not fired
            2. Make high load on compute node during 5 minutes
            3. Wait until and check that alert was fired
            4. Unload compute node
            5. Wait until and check that alert was ended

        Duration 15m
        """
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


class TestKubernetesAlerts(object):
    @pytest.mark.parametrize(
        "service", ["kube-proxy", "kube-apiserver", "kube-controller-manager",
                    "kubelet", "kube-scheduler"])
    def test_kubernetes_alert(self, cluster, prometheus_alerting, service):
        """Check that alerts for kubernetes services can be fired.

        Scenario:
            1. Check that alert is not fired
            2. Stop the corresponding kubernetes service on controller node
            3. Wait until and check that alert was fired
            4. Start the kubernetes service
            5. Wait until and check that alert was ended

        Duration 30m
        """
        ctl = [host for host in cluster.hosts
               if host.fqdn.startswith("ctl")][0]
        criteria = {
            "name": "ProcstatRunningKubernetes",
            "host": ctl.hostname,
        }
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=6 * 60)
        ctl.os.manage_service(service, "stop")
        prometheus_alerting.check_alert_status(
            criteria, is_fired=True, timeout=6 * 60)
        ctl.os.manage_service(service, "start")
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=6 * 60)


class TestCalicoAlerts(object):
    def test_calico_alert(self, cluster, prometheus_alerting):
        """Check that alerts for calico services can be fired.
         Scenario:
            1. Check that alert is not fired
            2. Stop calico-node service on controller node
            3. Wait until and check that alert was fired
            4. Start calico-node service
            5. Wait until and check that alert was ended

        Duration 10m
        """
        ctl = [host for host in cluster.hosts
               if host.fqdn.startswith("ctl")][0]
        criteria = {
            "name": "ProcstatRunningCalico",
            "host": ctl.hostname,
        }
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=6 * 60)
        ctl.os.manage_service("calico-node", "stop")
        prometheus_alerting.check_alert_status(
            criteria, is_fired=True, timeout=6 * 60)
        ctl.os.manage_service("calico-node", "start")
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=6 * 60)


class TestEtcdAlerts(object):
    def test_etcd_alert(self, cluster, prometheus_alerting):
        """Check that alerts for etcd services can be fired.
         Scenario:
            1. Check that alert is not fired
            2. Stop etcd service on controller node
            3. Wait until and check that alert was fired
            4. Start etcd service
            5. Wait until and check that alert was ended

        Duration 10m
        """
        ctl = [host for host in cluster.hosts
               if host.fqdn.startswith("ctl")][0]
        criteria = {
            "name": "EtcdClusterSmall",
            "service": "etcd",
        }
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=6 * 60)
        ctl.os.manage_service("etcd", "stop")
        prometheus_alerting.check_alert_status(
            criteria, is_fired=True, timeout=6 * 60)
        ctl.os.manage_service("etcd", "start")
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=6 * 60)


class TestElasticSearchAlerts(object):
    def test_es_health_alert(self, cluster, prometheus_alerting):
        monitoring_nodes = cluster.filter_by_role("monitoring")[:2]
        criteria = {
            "name": "elasticsearch_cluster_health",
            "service": "elasticsearch",
        }
        prometheus_alerting.check_alert_status(criteria, is_fired=False)
        criteria.update({"severity": "warning"})
        for mon_node in monitoring_nodes:
            mon_node.os.manage_service("elasticsearch", "stop")
            prometheus_alerting.check_alert_status(
                criteria, is_fired=True, timeout=6 * 60)
            criteria.update({"severity": "critical"})
        for mon_node in monitoring_nodes:
            mon_node.os.manage_service("elasticsearch", "start")
        del(criteria["severity"])
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=6 * 60)


class TestInfluxDBAlerts(object):
    def test_procstat_running_influxdb_alert(self, cluster, prometheus_alerting):
        """Check that alerts ProcstatRunningInfluxdb can be fired.
         Scenario:
            1. Check that alert is not fired
            2. Stop all influxdb services on controller node
            3. Wait until and check that alert was fired
            4. Start all influxdb services
            5. Wait until and check that alert was ended

        Duration 10m
        """
        influx_nodes = cluster.filter_by_role("influxdb")
        criteria = {
            "name": "ProcstatRunningInfluxdb",
            "service": "influxdb",
        }
        prometheus_alerting.check_alert_status(criteria, is_fired=False)
        for inf_node in influx_nodes:
            inf_node.os.manage_service("influxdb", "stop")
        prometheus_alerting.check_alert_status(
            criteria, is_fired=True, timeout=6 * 60)
        for inf_node in influx_nodes:
            inf_node.os.manage_service("influxdb", "start")
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=6 * 60)

    def test_influxdb_httpclient_error_alert(self, cluster, prometheus_alerting):
        """Check that alerts InfluxdbHTTPClientError can be fired.
         Scenario:
            1. Check that alert is not fired
            2. Create 6000 failed requests in influxdb
            3. Wait until and check that alert was fired
            4. Wait until and check that alert was ended

        Duration 10m
        """
        infl_node = cluster.filter_by_role("influxdb")[0]
        criteria = {
            "name": "InfluxdbHTTPClientError",
            "service": "influxdb",
        }
        prometheus_alerting.check_alert_status(criteria, is_fired=False)
        command = "for i in {1..6000}; do influx -host " + str(
            infl_node.address) + " -port 8086 -database lma -username lma" \
                                 " -password lmapass -execute 'show tables'" \
                                 " &>/dev/null; done"
        infl_node.exec_command(command)
        prometheus_alerting.check_alert_status(
            criteria, is_fired=True, timeout=6 * 60)
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=6 * 60)

