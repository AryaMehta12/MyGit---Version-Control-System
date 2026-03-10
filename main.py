import argparse
from pathlib import Path
import sys
import json

# repository class
class Repo:
    def __init__(self,path ='.'):
        self.path = Path(path).resolve()
        self.mygit_dir = self.path/".mygit"

        #objects -> commits/trees/tags etc.
        self.objects_dir = self.mygit_dir/"objects"

        #refs -> points to previous commits
        self.ref_dir = self.mygit_dir/"refs"
        self.heads_dir = self.ref_dir/"heads"

        #HEAD -> stores current branch
        self.head_file = self.mygit_dir/"HEAD"

        #index -> staging area(stores the list of files for next commit.)
        self.head_file = self.mygit_dir/"index"

    def init(self) -> bool:
        if self.mygit_dir.exists():
            return False
        
        # creating necessary direcetories 
        self.mygit_dir.mkdir()
        self.objects_dir.mkdir()
        self.ref_dir.mkdir()
        self.heads_dir.mkdir()

        #HEAD pointer
        self.head_file.write_text("ref: refs/heads/COOLEST\n")
        self.index_file.write_text(json.dumps({},indent = 2))
        print(f"Mygit Repository Initialized, in {self.mygit_dir}")
        return True

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
    init_parser = subparsers.add_parser("add", help = "Initalize the repo")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return
    try:
        if args.command == "init":
            repo = Repo()
            if not repo.init():
                print("Already Initialized!")
                return 
    except Exception as e:
        print(f"Error:{e}")

main()