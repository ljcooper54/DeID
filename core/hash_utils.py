import hashlib
import os

def content_hash(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

def path_hash(path: str) -> str:
    abspath = os.path.abspath(path)
    return hashlib.sha256(abspath.encode("utf-8")).hexdigest()
