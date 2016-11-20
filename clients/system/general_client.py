import logging
import socket

from clients.system import ssh

logger = logging.getLogger(__name__)


class GeneralActionsClient(object):
    def __init__(self, address, username,
                 password=None, private_key=None):
        self.transport = ssh.SSHTransport(address, username,
                                          password=password,
                                          private_key=private_key)

    @property
    def short_hostname(self):
        command = 'hostname --short'
        return self.transport.exec_command(command)

    @property
    def long_hostname(self):
        command = 'hostname --long'
        return self.transport.exec_command(command)

    def get_file_content(self, filename):
        command = 'cat %s' % filename
        return self.transport.exec_command(command)

    def get_date(self):
        return self.transport.exec_command("date")

    def exec_command(self, cmd):
        return self.transport.exec_command(cmd)

    def put_file(self, source_path, destination_path):
        return self.transport.put_file(source_path, destination_path)

    def get_file(self, source_path, destination_path):
        return self.transport.get_file(source_path, destination_path)

    def graceful_reboot(self):
        logger.info("Grace reboot node: {0}".format(self.hostname))
        self.transport.exec_command("/sbin/reboot > /dev/null 2>&1 &")

    def force_reboot(self):
        logger.info("Force reboot node: {0}".format(self.hostname))
        self.transport.exec_command("/sbin/reboot -f > /dev/null 2>&1 &")

    def get_pids(self, process_name):
        cmd = ("ps -ef | grep %s | grep -v 'grep' | "
               "awk {'print $2'}" % process_name)
        return self.transport.exec_command(cmd).strip().split('\n')

    def kill_process_by_pid(self, pid):
        logger.info("Killing process pid {0} on node {1}"
                    .format(pid, self.hostname))
        self.transport.exec_command("kill -9 {0}".format(pid))

    def kill_process_by_name(self, process_name):
        logger.info("Killing {0} processes on node {1}"
                    .format(process_name, self.hostname))
        for pid in self.get_pids(process_name):
            self.kill_process_by_pid(pid)

    def killall_processes(self, process_name):
        logger.info("Kill all processes {0} on node {1}"
                    .format(process_name, self.hostname))
        self.transport.exec_command("killall -9 {0}".format(process_name))

    def check_process(self, name):
        ret_code, _, _ = self.transport.exec_command(
            "ps ax | grep {0} | grep -v grep".format(name))
        if ret_code == 0:
            logger.info("Found {0} process on nodes {1}"
                        .format(name, self.hostname))
            return True
        logger.info("Not found {0} process on nodes {1}"
                    .format(name, self.hostname))
        return False

    def tcp_ping(self, port=22):
        try:
            logger.info("Opening {0} 22".format(self.transport.address))
            s = socket.socket()
            s.connect((self.transport.address, port))
            s.close()
        except socket.error:
            logger.info("Socket error")
            return False
        logger.info("Socket ok")
        return True

    def get_all_bridged_interfaces_for_node(self, excluded_criteria=None):
        """Return all network bridges for a node.

        :param excluded_criteria: regular expression to filter out items
        :type excluded_criteria: str
        :returns: list of interfaces
        :rtype: list
        """
        # TODO(rpromyshlennikov): do filtration on python side
        excluded_criteria_cmd = (
            " | grep -v '%s'" % excluded_criteria
            if excluded_criteria else "")
        cmd = "brctl show | awk '/br-/{{print $1}}'{excluded}".format(
            excluded=excluded_criteria_cmd)
        interfaces = self.exec_command(cmd)
        return [iface.strip() for iface in interfaces]

    def switch_interface(self, interface, up=True):
        """Turn a network interface up or down.

        :param interface: interface name.
        :type interface: str
        :param up: whether the interface should be turned up (default: True).
        :type up: boolean
        """
        method = 'up' if up else 'down'
        cmd = "if{method} {interface}".format(method=method,
                                              interface=interface)
        self.exec_command(cmd)

    def simulate_network_interrupt_on_node(self, interval=30):
        """Simulate a network outage on a node.

        :param interval: outage duration in seconds (default: 30).
        :type interval: int
        """
        cmd = (
            "(/sbin/iptables -I INPUT -j DROP && "
            "sleep {interval} && "
            "/sbin/iptables -D INPUT -j DROP) 2>&1>/dev/null &".format(
                interval=interval))
        self.exec_command(cmd)

    def get_pids_of_process(self, cmd_pattern):
        """Get PIDS of process by its pattern.

            :param cmd_pattern: command.
            :type cmd_pattern: str
            :returns: list of PIDS.
            :rtype: list
            """

        cmd = "pgrep -f '{}'".format(cmd_pattern)
        result = self.exec_command(cmd)
        if result['exit_code'] != 0:
            return []
        return result['stdout'][0].strip().split()

    def ban_resource(self, resource, wait=None):
        """Ban a resource from the current node.

            :param resource: resource name.
            :type resource: str
            :param wait: number of seconds to wait for the operation to complete.
            :type wait: int
        """
        cmd = "pcs resource ban {}".format(resource)
        if wait is not None:
            cmd = "{} --wait={}".format(cmd, wait)
        self.exec_command(cmd)

    def clear_resource(self, resource, wait=None):
        """Clear a resource.

            :param resource: resource name.
            :type resource: str
            :param wait: number of seconds to wait for the operation to complete.
            :type wait: int
        """
        cmd = "pcs resource clear {}".format(resource)
        if wait is not None:
            cmd = "{} --wait={}".format(cmd, wait)
        self.exec_command(cmd)

    def manage_pacemaker_service(self, name, operation="restart"):
        """Operate HA service on remote node.

            :param name: service name.
            :type name: str
            :param operation: type of operation, usually start, stop or restart.
            :type operation: str
        """
        self.exec_command("crm resource {operation} {service}".format(
            operation=operation, service=name))

    def manage_service(self, name, operation="restart"):
        """Operate service on remote node.

            :param name: service name.
            :type name: str
            :param operation: type of operation, usually start, stop or restart.
            :type operation: str
        """
        exit_code, _, = self.transport.exec_sync(
            "ls /etc/init/{}.conf".format(name))

        if exit_code == 0:
            service_cmd = 'initctl {operation} {service}'
        else:
            service_cmd = 'service {service} {operation}'

        self.exec_command(service_cmd.format(service=name,
                                             operation=operation))

    def clear_local_mail(self):
        """Clean local mail

        """
        self.exec_command("rm -f $MAIL")

    def fill_up_filesystem(self, fs, percent, file_name):
        """Fill filesystem on node.

            :param fs: name of the filesystem to fill up
            :type fs: str
            :param percent: amount of space to be filled in percent.
            :type percent: int
            :param file_name: name of the created file
            :type file_name: str

        """
        logger.info("Filling up {} filesystem to {} percent".format(fs, percent))
        cmd = (
            "fallocate -l $(df | grep {} | awk '{{ printf(\"%.0f\\n\", "
            "1024 * ((($3 + $4) * {} / 100) - $3))}}') {}".format(
                fs, percent, file_name))
        self.exec_command(cmd)

    def clean_filesystem(self, filename):
        """Clean space filled by fill_up_filesystem function

            :param filename: name of the file to delete
            :type filename: str
        """
        logger.info("Removing {} file".format(filename))
        self.exec_command("rm -f {}".format(filename))
