import argparse
def main():
    parser = argparse.ArgumentParser(
        description="MyGit - My git clone"
    )
    subparsers = parser.add_subparsers(
        dest = "command",
        help = "Available commands"
    )

    # initalizing init command
    init_parser = subparsers.add_parser("init", help = "Initalize the repo")
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return
    
    
main()