import cStringIO
import logging
import select

import paramiko


logger = logging.getLogger(__name__)

# Suppress paramiko logging
logging.getLogger("paramiko").setLevel(logging.WARNING)


class SSHTransport(object):
    def __init__(self, address, username, password=None,
                 private_key=None, look_for_keys=False, *args, **kwargs):

        self.address = address
        self.username = username
        self.password = password
        if private_key is not None:
            self.private_key = paramiko.RSAKey.\
                from_private_key(cStringIO.StringIO(private_key))
        else:
            self.private_key = None

        self.look_for_keys = look_for_keys
        self.buf_size = 1024
        self.channel_timeout = 10.0

    def _get_ssh_connection(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(
            paramiko.AutoAddPolicy())
        ssh.connect(self.address, username=self.username,
                    password=self.password, pkey=self.private_key,
                    timeout=self.channel_timeout)
        logger.debug("Successfuly connected to: {0}".format(self.address))
        return ssh

    def _get_sftp_connection(self):
        transport = paramiko.Transport((self.address, 22))
        transport.connect(username=self.username,
                          password=self.password,
                          pkey=self.private_key)

        return paramiko.SFTPClient.from_transport(transport)

    def exec_sync(self, cmd):
        logger.debug("Executing {0} on host {1}".format(cmd, self.address))
        ssh = self._get_ssh_connection()
        transport = ssh.get_transport()
        channel = transport.open_session()
        channel.fileno()
        channel.exec_command(cmd)
        channel.shutdown_write()
        out_data = []
        err_data = []
        poll = select.poll()
        poll.register(channel, select.POLLIN)

        while True:
            ready = poll.poll(self.channel_timeout)
            if not any(ready):
                continue
            if not ready[0]:
                continue
            out_chunk = err_chunk = None
            if channel.recv_ready():
                out_chunk = channel.recv(self.buf_size)
                out_data += out_chunk,
            if channel.recv_stderr_ready():
                err_chunk = channel.recv_stderr(self.buf_size)
                err_data += err_chunk,
            if channel.closed and not err_chunk and not out_chunk:
                break
        exit_status = channel.recv_exit_status()
        logger.debug("Command {0} executed with status: {1}"
                     .format(cmd, exit_status))
        return exit_status, ''.join(out_data).strip(), ''.join(err_data).strip()

    def exec_command(self, cmd):
        exit_status, stdout, stderr = self.exec_sync(cmd)
        return stdout

    def put_file(self, source_path, destination_path):
        sftp = self._get_sftp_connection()
        sftp.put(source_path, destination_path)
        sftp.close()

    def get_file(self, source_path, destination_path):
        sftp = self._get_sftp_connection()
        sftp.get(source_path, destination_path)
        sftp.close()
