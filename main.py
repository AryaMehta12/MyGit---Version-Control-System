import argparse
from pathlib import Path
import sys
import json
import hashlib,zlib

#contains all subclasses like blob, tree, commit
class GitObject:
    def __init__(self,obj_type: str, content: bytes):
        self.type = obj_type
        self.content = content

    def hash(self) -> str:
        # f(<type> <size>\0<content>)
        # sha1 hashing
        # convert hash to readable(hexa) format, for storage in objs
        header = f"{self.type} {len(self.content)}\0".encode()
        return hashlib.sha1(header +self.content).hexdigest()
    
    def serialize(self) -> bytes:
        header = f"{self.type}{len(self.content)}\0".encode()
        return zlib.compress(header + self.content)
    
    @classmethod
    def deserialize(cls,data: bytes) -> "GitObject":
        decompressed = zlib.decompress(data)
        null_idx = decompressed.find(b"\0")
        header = decompressed[:null_idx]
        content = decompressed[null_idx:]
        
        obj_type, _  = header.split(" ")
        return cls(obj_type, content)
    
class Blob(GitObject): #Blob -> binary large object (stores file content)
    def __init__(self,content):
        super().__init__('blob',content)
    def get_content(self)->bytes:
        return self.content

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
        self.index_file = self.mygit_dir/"index"

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
        self.save_index({})
        print(f"Mygit Repository Initialized, in {self.mygit_dir}")
        return True
    
    def store_object(self,obj:GitObject):
        obj_hash = obj.hash()
        obj_dir = self.objects_dir / obj_hash[:2]
        obj_file = obj_dir/ obj_hash[2:]

        if not obj_file.exists():
            obj_dir.mkdir(exist_ok = True) #do nothing if it already exists(as multiple hash files can be under the same dir)
            obj_file.write_bytes(obj.serialize())

        return obj_hash
    
    def load_index(self) -> dict[str,str]:
        if not self.index_file.exists(): ##incase user deleted the file on accident
            return {} 
        try:
            return json.loads(self.index_file.read_text())
        except:
            return {}
    

    def save_index(self, index):
        self.index_file.write_text(json.dumps(index,indent = 2))
    
    def add_dir(self):
        pass
    # 4 types of objects -> BLOB, COMMIT, TREES, TAGS
    def add_file(self,path: str):
        full_path = self.path/path
        if not full_path.exists():
            raise FileNotFoundError(f"Path {path} not found!")
            
        # Read the file content
        content = full_path.read_bytes()
        # Create BLOB (binary large obj)
        blob = Blob(content)
        # store the blob obj in .mygit/objects
        blob_hash = self.store_object(blob)
        #update index to include the files
        index = self.load_index()
        index[path] = blob_hash
        self.save_index(index)

        print(f"Added {path}")

    def add_dir(self):
        pass
    def add_path(self,path:str) -> None:
        full_path = self.path/path 
        if not full_path.exists():
            raise FileNotFoundError(f"Path {path} not found")
        if full_path.is_file():
            self.add_file(path)
        elif full_path.is_dir():
            self.add_dir(path)
        else:
            raise ValueError(f"{path} is neither a file nor a directory!")


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
    add_parser = subparsers.add_parser("add", help = "Add files to staging area")
    add_parser.add_argument("paths",nargs='+')
    args = parser.parse_args()


    repo = Repo()
    if not args.command:
        parser.print_help()
        return
    try:
        if args.command == "init":
            if not repo.init():
                print("Already Initialized!")
                return 
            
        elif args.command == "add":
            if not repo.mygit_dir.exists():
                print("MyGit Uninitialized!")
                return
            for path in args.paths:
                repo.add_path(path)
            
    except Exception as e:
        print(f"Error:{e}")
        sys.exit(1)

main()