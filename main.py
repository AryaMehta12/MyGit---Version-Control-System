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

class Tree(GitObject):
    def __init__(self, entries: list[tuple[str, str, str]]):
        self.entries = entries or []
        content = self._serialize_entries()
        super().__init__('tree',content)
        pass

    def _serialize_entries(self) -> bytes:
        # <mode> <name>\0<hash>
        content = b""
        for mode,name,obj_hash in sorted(self.entries): 
            #we sort as in sha-1 hashing order of entries changing produces diff obj hash for each obj, as byte sequence changed.
            content += f"{mode} {name}\0".encode()
            content += bytes.fromhex(obj_hash) # fromhex as our stored hashes are in hexa for index storage and readability, while actual content needs to be purely the bytes version
        return content 

    def add_entry(self, mode: str, name:str, obj_hash:str):
        self.entries.append((mode,name,obj_hash))
        self.content = self._serialize_entries() 

    @classmethod
    def from_content(cls, content: bytes) -> "Tree":
        tree = cls()
        i = 0
        while i<len(content):
            null_idx = content.find(b"\0", i)
            #100644 README.md\0[20 bytesh hash]100644 sumnelse.py\0[50bytes]
            #basically if we keep finding from start always well only get the same 0, so the tracker i
            if null_idx == -1:
                break
            mode_name = content[i:null_idx].decode()
            mode,name = mode_name.split(" ",1) # only splits 1 space, and .i.e., the first one, so even if name has spaces its ok!
            obj_hash = content[null_idx+1: null_idx+21].decode() #sha1 hash always give 20 byte hashes
            i = null_idx+21
        return tree
    
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

    def add_dir(self,path : str):
        full_path = self.path/path
        if not full_path.exists():
            raise FileNotFoundError(f"Path {path} does not exist!")
        if not full_path.is_dir():
            raise ValueError(f"{path} is not a directory!")
        added_count = 0
        for fpath in full_path.rglob('*'):
            if ".mygit" in fpath.parts:
                    continue
            fpath_rel = str(fpath.relative_to(self.path))
            if fpath.is_file():
                self.add_file(fpath_rel)
                added_count +=1
    
        if added_count>0 :
            print(f"Added {added_count} files from director {path}")
        else :
            print(f"no new files in directory {path}")
        
    def add_path(self, path: str) -> None:
        full_path = self.path / path 
        if not full_path.exists():
            raise FileNotFoundError(f"Path {path} not found")
        if full_path.is_file():
            self.add_file(path)
        elif full_path.is_dir():
            self.add_dir(path)
        else:
            raise ValueError(f"{path} is neither a file nor a directory!")

    def create_tree_from_index(self):
        index = self.load_index()
        if not index:
            tree = Tree()
            return self.store_object(tree)
        
        dirs = {},files = {}

        for file_path, blob_hash in index.items():
            parts = file_path.split("/")
            if len(parts) == 1:
                #file is in root
                files[parts[0]] = blob_hash
            else:
                dir_name = parts[0]
                if dir_name not in dirs:
                    dirs[dir_name] = {}
                
                #works as DAG
                current  = dirs[dir_name] #creating our curr dic pointer
                for part in parts[1:-1]: #all except last, cuz last is the file not folder
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[-1] = blob_hash

        def create_trees_recursively(entries_dict: dict):
            tree = Tree()
            for name, val in entries_dict.items():
                if isinstance(val,str): #type is a file
                    tree.add_entry("100644",name,blob_hash)
                if isinstance(blob_hash,dict): #its a nested dir
                    subtree_hash = create_trees_recursively(val)
                    tree.add_entry("40000",name,subtree_hash)
            return self.store_object(tree)

        root_entries = {**files} # **decomposes dictionary item, basically its used for multiple dictionary combining only
        for dir_name, dir_content in dir.items():
            root_entries[dir_name] = dir_content

        return create_trees_recursively(root_entries)

    # commiting -> from staging area(obj) to local repository, commit here will take a snapshot of the index file(our current staging area)
    # and store it into the local repo, i.e essentially creating a saved version of our current work incase we need to go back to it.
    # the issue right now with index file is that there is no heirarchial structure everything is stored in the form 
    # "rel_dir": "obj_hash", i.e everything is rel to current directory, so it would be like 
    # "folder1/hi.txt" = "..",
    # "folder1/hello.txt" = "..", etc.
    # but we would want to store it as 
    # "folder1":{
    #       "hello.txt":"..",
    #       "hi.txt": "..",
    # }
    # i.e., giving it a heirarchial strucutre, this is where we use trees.

    def commit(self, message: str, author: str = "MyGit User <MyGit@gmail.com> "):
        # create a tre from the index
        tree_hash = self.create_tree_from_index()
        pass



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

    # add command
    add_parser = subparsers.add_parser("add", help = "Add files to staging area")
    add_parser.add_argument("paths",nargs='+', help = "Files and directories to add")

    #commit command
    commit_parser = subparsers.add_parser("commit", help = "Create a new commit")
    # -/ -- makes an argument flagged, i.e., in the above like paths is positional I can just work with add file.ext 
    # but to call a flagged argument I need to specify the flag -m , also -/-- makes it optional by default and hence the required = True part. 
    commit_parser.add_argument("-m","--message", help = "write the commit message",required = True)  
    commit_parser.add_argument("--author", help  ="credentials")

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

        elif args.command == "commit":
            if not repo.mygit_dir.exists():
                print("MyGit uninitiallized")
                return
            author = args.author or "MyGit user <Mygit@gmail.com>"
            repo.commit(args.message,author)
            
    except Exception as e:
        print(f"Error:{e}")
        sys.exit(1)

main()