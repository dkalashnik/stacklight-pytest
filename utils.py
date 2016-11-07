import os

import exceptions


def get_fixture(name, check_existance=True):
    test_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(test_dir, "fixtures", name)
    if check_existance and not os.path.isfile(path):
        raise exceptions.NotFound("File {} not found".format(path))
    return path
