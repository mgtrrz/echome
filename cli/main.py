import sys
import argparse
import logging
import json
sys.path.insert(0, '../python_sdk/')
from echome import Session

vm_client = Session().client("Vm")

class CmdVm:

    @staticmethod
    def describe_all():
        vms = vm_client.describe_all()
        print(json.dumps(vms, indent=4))


def main():

    top_level_commands = ["vm"]

    parser = argparse.ArgumentParser(description='ecHome cli', prog="echome")
    parser.add_argument('command', metavar='command', type=str,
                    help='Command to run to the ecHome api.', choices=top_level_commands)
    parser.add_argument('subcommand', metavar='subcommand', type=str, nargs="+",
                    help='Command to run for the namespaced ecHome api.')

    args = parser.parse_args()
    #print(args)

    if args.command == "vm":
        if args.subcommand[0] == "describe-all-vms":
            CmdVm.describe_all()


if __name__ == "__main__":
    main()