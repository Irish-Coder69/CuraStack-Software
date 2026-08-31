"""CLI helper to bump or set CuraStack Software version."""

import argparse
import version_manager as vm


def main():
    parser = argparse.ArgumentParser(description="CuraStack Software version manager")
    parser.add_argument(
        "action",
        nargs="?",
        default="show",
        choices=["show", "build", "patch", "minor", "major", "set"],
        help="Version action",
    )
    parser.add_argument("--major", type=int, default=None)
    parser.add_argument("--minor", type=int, default=None)
    parser.add_argument("--patch", type=int, default=None)
    parser.add_argument("--build", type=int, default=None)
    args = parser.parse_args()

    if args.action == "show":
        print(vm.get_version_string())
        return

    if args.action == "build":
        print(vm.bump_build())
        return

    if args.action == "patch":
        print(vm.bump_patch())
        return

    if args.action == "minor":
        print(vm.bump_minor())
        return

    if args.action == "major":
        print(vm.bump_major())
        return

    if args.action == "set":
        current = vm.get_version_data()
        major = args.major if args.major is not None else current["major"]
        minor = args.minor if args.minor is not None else current["minor"]
        patch = args.patch if args.patch is not None else current["patch"]
        build = args.build if args.build is not None else current["build"]
        print(vm.set_version(major, minor, patch, build))


if __name__ == "__main__":
    main()
