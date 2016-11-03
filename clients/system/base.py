import abc

import six


@six.add_metaclass(abc.ABCMeta)
class Transport(object):
    @abc.abstractmethod
    def exec_sync(self, cmd):
        """

        :param cmd:
        :return:
        """

    @abc.abstractmethod
    def put_file(self, source_path, destination_path):
        """

        :param source_path:
        :param destination_path:
        :return:
        """

    @abc.abstractmethod
    def get_file(self, source_path, destination_path):
        """

        :param source_path:
        :param destination_path:
        :return:
        """

    def exec_command(self, cmd):
        """

        :param cmd:
        :return:
        """

        exit_status, stdout, stderr = self.exec_sync(" ".join(cmd))

        return exit_status, stdout, stderr
