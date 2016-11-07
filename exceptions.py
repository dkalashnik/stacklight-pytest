class BaseException(Exception):
    msg_fmt = _("%(message)s")

    def __init__(self, message=None, **kwargs):
        self.kwargs = kwargs

        if "%(message)s" in self.msg_fmt:
            kwargs.update({"message": message})

        super(BaseException, self).__init__(self.msg_fmt % kwargs)


class NotFound(BaseException):
    pass


class NoValidHost(BaseException):
    msg_fmt = _("No host with condition '%(condition)' in cluster")


class EmptyCluster(BaseException):
    msg_fmt = _("No hosts in cluster")


class TimeoutException(BaseException):
    msg_fmt = _("Request timed out.")


class SSHTimeout(BaseException):
    msg_fmt = _("Connection to the %(host)s via SSH timed out.\n"
                "User: %(user)s, Password: %(password)s")


class SSHCommandFailed(BaseException):
    msg_fmt = _("Execution of %(command)s on host %(host)s failed:\n"
                "%(stderr)s")
