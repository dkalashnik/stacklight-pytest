Tests to check stacklight

Prerequisites:
==============

Code requirements:
------------------
Install requirements with 'pip install -r requirements.txt'

Prepared environment:
---------------------
Tests requires 'deploy_toolchain' in https://github.com/openstack/stacklight-integration-tests:

.. code:: bash

    export PYTHONPATH="$PYTHONPATH:/home/some_user/fuel-qa"
    export UPDATE_MASTER=true
    export UPDATE_FUEL_MIRROR='http://mirror.seed-cz1.fuel-infra.org/mos-repos/centos/mos9.0-centos7/snapshots/os-2016-06-23-135731/x86_64 http://mirror.seed-cz1.fuel-infra.org/mos-repos/centos/mos9.0-centos7/snapshots/proposed-2016-09-22-152322/x86_64 http://mirror.seed-cz1.fuel-infra.org/mos-repos/centos/mos9.0-centos7/snapshots/updates-2016-06-23-135916/x86_64 http://mirror.seed-cz1.fuel-infra.org/mos-repos/centos/mos9.0-centos7/snapshots/holdback-2016-06-23-140047/x86_64 http://mirror.seed-cz1.fuel-infra.org/mos-repos/centos/mos9.0-centos7/snapshots/security-2016-06-23-140002/x86_64'
    export EXTRA_DEB_REPOS='mos-proposed,deb http://mirror.seed-cz1.fuel-infra.org/mos-repos/ubuntu/snapshots/9.0-2016-09-22-142322 mos9.0-proposed main restricted|mos-updates,deb http://mirror.seed-cz1.fuel-infra.org/mos-repos/ubuntu/snapshots/9.0-2016-09-22-142322 mos9.0-updates main restricted|mos-holdback,deb http://mirror.seed-cz1.fuel-infra.org/mos-repos/ubuntu/snapshots/9.0-2016-09-22-142322 mos9.0-holdback main restricted|mos-security,deb http://mirror.seed-cz1.fuel-infra.org/mos-repos/ubuntu/snapshots/9.0-2016-09-22-142322 mos9.0-security main restricted'
    export ENV_NAME=stacklight
    export VENV_PATH=../fuel-devops-venv
    export ISO_PATH=/home/some_user/fuel-9.0-mos-495-2016-06-16_18-18-00.iso
    export NODES_COUNT=4

    # You can download plugins from some srvX server (requires access to server)
    scp srvX-bud.infra.mirantis.net:/home/jenkins/workspace/plugins/fuel-plugin-elasticsearch-kibana/elasticsearch_kibana-1.0-1.0.0-1.noarch.rpm /home/some_user/lma
    scp srvX-bud.infra.mirantis.net:/home/jenkins/workspace/plugins/fuel-plugin-influxdb-grafana/.build/rpm/RPMS/noarch/influxdb_grafana-1.0-1.0.0-1.noarch.rpm /home/some_user/lma
    scp srvX-bud.infra.mirantis.net:/home/jenkins/workspace/plugins/fuel-plugin-lma-collector/lma_collector-1.0-1.0.0-1.noarch.rpm /home/some_user/lma
    scp srvX-bud.infra.mirantis.net:/home/jenkins/workspace/plugins/fuel-plugin-lma-infrastructure-alerting/lma_infrastructure_alerting-1.0-1.0.0-1.noarch.rpm /home/some_user/lma

    export ELASTICSEARCH_KIBANA_PLUGIN_PATH=/home/some_user/lma/elasticsearch_kibana-1.0-1.0.0-1.noarch.rpm
    export INFLUXDB_GRAFANA_PLUGIN_PATH=/home/some_user/lma/influxdb_grafana-1.0-1.0.0-1.noarch.rpm
    export LMA_COLLECTOR_PLUGIN_PATH=/home/some_user/lma/lma_collector-1.0-1.0.0-1.noarch.rpm
    export LMA_INFRA_ALERTING_PLUGIN_PATH=/home/some_user/lma/lma_infrastructure_alerting-1.0-1.0.0-1.noarch.rpm
    ./utils/jenkins/system_tests.sh -t test -w $(pwd) -j fuelweb_test -i $ISO_PATH -kK -o --group=deploy_toolchain


Build and install as python package
===================================
Build dist with next command:

Run install on target machine:
   pip install dist/stacklight_tests-0.0.1.dev58.tar.gz --process-dependency-links

where "--process-dependency-links" flag is necessary.

Run tests
=========
You need to generate config from fuel to run tests now:
   PYTHONPATH=".:$PYTHONPATH" python config/fuel_config.py

In case of using MK2x it worth generating config from mk env to run tests:
   PYTHONPATH=".:$PYTHONPATH" python config/mk_config.py

After file 'fixtures/config.yaml' is generated it is worth adding
OpenStack clients endpoing hostname to /etc/hosts:
   sudo python host_utils.py

After adding endpoint hostname to hosts file you can run tests.

To view initial tests in test_alerts.py just type 'pytest'. They are using
default settings from deployment. Later it is going to be configured.
