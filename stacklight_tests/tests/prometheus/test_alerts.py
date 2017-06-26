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

    def test_predict_linear_disk_inodes_free_alert(
            self, cluster, prometheus_alerting):
        """Check that operation system alerts can be fired.
         Scenario:
            1. Check that alert is not fired
            3. Create files 400000 /dev/shm
            4. Wait until and check that alert was fired
            5. Remove all files from /dev/shm
            6. Wait until and check that alert was ended

        Duration 15m
        """
        cmp = cluster.filter_by_role("compute")[0]
        criteria = {
            "name": "PredictLinearDiskInodesFree",
            "service": "system",
        }
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=10 * 60)
        cmp.exec_command("cd /dev/shm; for i in {1..4} ;do touch {$i}a{000001..100000}.c; done")
        prometheus_alerting.check_alert_status(
            criteria, is_fired=True, timeout=10 * 60)
        remove_files = "cd /dev/shm; find . -name '*.c' -print0 | xargs -0 rm"
        cmp.exec_command(remove_files)
        prometheus_alerting.check_alert_status(
            criteria, is_fired=False, timeout=15 * 60)


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
