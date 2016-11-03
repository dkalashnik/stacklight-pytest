name = 'influxdb_grafana'
role_name = ['influxdb_grafana']
failover_vip = 'influxdb'
plugin_path = '/tmp/tmp' # INFLUXDB_GRAFANA_PLUGIN_PATH
version = '1' # get_plugin_version(plugin_path)

influxdb_db_name = "lma"
influxdb_user = 'influxdb'
influxdb_pass = 'influxdbpass'
influxdb_rootuser = 'root'
influxdb_rootpass = 'r00tme'

grafana_user = 'grafana'
grafana_pass = 'grafanapass'

mysql_mode = 'local'
mysql_dbname = 'grafanalma'
mysql_user = 'grafanalma'
mysql_pass = 'mysqlpass'

default_options = {
    'influxdb_rootpass/value': influxdb_rootpass,
    'influxdb_username/value': influxdb_user,
    'influxdb_userpass/value': influxdb_pass,
    'grafana_username/value': grafana_user,
    'grafana_userpass/value': grafana_pass,
    'mysql_mode/value': mysql_mode,
    'mysql_dbname/value': mysql_dbname,
    'mysql_username/value': mysql_user,
    'mysql_password/value': mysql_pass,
}

toolchain_options = default_options
