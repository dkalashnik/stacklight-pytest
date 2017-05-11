import argparse

from stacklight_tests.config import mk_config

fn_mapping = {
    "gen-config-mk": mk_config.main,
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
