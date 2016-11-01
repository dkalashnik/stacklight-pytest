import abc

import six


@six.add_metaclass(abc.ABCMeta)
class Transport(object):
    @abc.abstractmethod
    def exec_sync(self, commands):
        """Execute shell command synchronously
        Command execution is bind to shell session.
        :return: ret_code, stdout, stderr
        """

    # TODO(dkalashnik): Add method for asynchronous command execution
    # @abc.abstractmethod
    # def exec_async(self, commands):
    #     """ Execute shell command asynchronously
    #     :return: Callable for result
    #     """

    def exec_command(self, commands):
        """Execute shell command on node
        :return: stdout
        """
        _, stdout, _ = self.exec_sync(commands)

        return stdout
