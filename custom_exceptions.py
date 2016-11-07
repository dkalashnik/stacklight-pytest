class BaseCustomException(Exception):
    msg_fmt = "%(message)s"

    def __init__(self, message=None, **kwargs):
        self.kwargs = kwargs

        if "%(message)s" in self.msg_fmt:
            kwargs.update({"message": message})

        super(BaseCustomException, self).__init__(self.msg_fmt % kwargs)


class NotFound(BaseCustomException):
    pass


class NoValidHost(BaseCustomException):
    msg_fmt = "No host with condition '%(condition)' in cluster"


class EmptyCluster(BaseCustomException):
    msg_fmt = "No hosts in cluster"


class TimeoutException(BaseCustomException):
    msg_fmt = "Request timed out."


class SSHTimeout(BaseCustomException):
    msg_fmt = ("Connection to the %(host)s via SSH timed out.\n"
               "User: %(user)s, Password: %(password)s")


class SSHCommandFailed(BaseCustomException):
    msg_fmt = ("Execution of %(command)s on host %(host)s failed:\n"
               "%(stderr)s")


class TimeoutError(BaseCustomException):
    pass
