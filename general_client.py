#import ConfigParser
import cStringIO
import logging
import socket
import ssh_transport

logger = logging.getLogger(__name__)


class GeneralActionsClient(object):
    def __init__(self, address, username,
                 password=None,
                 private_key=None):
        self.transport = ssh_transport.SSHTransport(address,
                                                    username,
                                                    password=password,
                                                    private_key=private_key)

    @property
    def hostname(self):
        command = 'hostname'
        return self.transport.exec_command(command).strip()

    def get_file_content(self, filename):
        command = 'cat %s' % filename
        ret_code, output, stderr = self.transport.exec_sync(command)
        #if ret_code is not 0:
        # raise exceptions.SSHCommandFailed(command=command,
        #                                   host=self.hostname,
        #                                   stderr=stderr)
        return output

    def get_date(self):
        return self.transport.exec_command("date")

    def execute(self, cmd):
        return self.transport.exec_command(cmd)

    def get_ini_config(self, filename):
        data = self.get_file_content(filename)
        configfile = cStringIO.StringIO(data)
        #config = ConfigParser.ConfigParser()
        #c#onfig.readfp(configfile)
        return {}

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
        ret_code, _, _ = self.transport.exec_sync(
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
