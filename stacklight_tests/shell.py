import argparse

from stacklight_tests.config import fuel_config
from stacklight_tests.config import mk_config
from stacklight_tests import host_utils

fn_mapping = {
    "gen-config-mk": mk_config.main,
    "gen-config-fuel": fuel_config.main,
    "setup-hosts": host_utils.main,
}


def main():
    parser = argparse.ArgumentParser(prog="stl-tests")
    parser.add_argument(
        "cmd",
        choices=(fn_mapping.keys()),
        help="Command to do",
    )
    args = parser.parse_args()
    fn_mapping[args.cmd]()


if __name__ == "__main__":
    main()
