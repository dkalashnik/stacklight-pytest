#!/bin/bash -x

# Verify that Salt master is correctly bootstrapped
salt-key
reclass-salt --top

# Verify that Salt minions are responding and the same version as master
salt-call --version
salt '*' test.version

# Check the VIPs
salt -C 'I@keepalived:cluster' cmd.run "ip a | grep 172.16.10.2"

# Check the gluster status
salt -C 'I@glusterfs:server' cmd.run "gluster peer status; gluster volume status" -b 1

# Check the rabbitmq status
salt -C 'I@rabbitmq:server' cmd.run "rabbitmqctl cluster_status"

# Check galera status
salt -C 'I@galera:master' mysql.status | grep -A1 wsrep_cluster_size
salt -C 'I@galera:slave' mysql.status | grep -A1 wsrep_cluster_size

# Check keystone
salt -C 'I@keystone:server' cmd.run ". /root/keystonerc; keystone service-list"

# Check glance
salt -C 'I@keystone:server' cmd.run ". /root/keystonerc; glance image-list"

# Check nova
salt -C 'I@keystone:server' cmd.run ". /root/keystonerc; nova service-list"

# Check cinder
salt -C 'I@keystone:server' cmd.run ". /root/keystonerc; cinder list"

# Check neutron
salt -C 'I@keystone:server' cmd.run ". /root/keystonerc; neutron agent-list"

# Check heat
salt -C 'I@keystone:server' cmd.run ". /root/keystonerc; heat resource-type-list"

