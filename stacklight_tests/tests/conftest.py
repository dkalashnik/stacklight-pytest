import logging

import pytest

from stacklight_tests.clients.fixtures import *  # noqa


logger = logging.getLogger(__name__)


@pytest.fixture
def destructive(request):
    """Does some recovering and cleaning actions provided
    by test in case of fail only.
    """
    recovery_actions = []
    yield recovery_actions
    if request.node.rep_call.failed:
        for recovery_method in recovery_actions:
            try:
                recovery_method()
            except Exception as e:
                logger.error(
                    "Recovery failed: {} with exception: {}".format(
                        recovery_method, e))
