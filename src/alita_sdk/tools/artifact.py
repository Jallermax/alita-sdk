
from langchain.tools import BaseTool
from typing import Any
from pydantic import create_model
from pydantic.fields import FieldInfo

class ListFiles(BaseTool):
    name: str = "listFiles"
    description: str = "List all files in the artifact"
    artifact: Any
    args_schema = create_model( "listBucket")
    
    def _run(self):
        return self.artifact.list()


class CreateFile(BaseTool):
    name: str = "createFile"
    description: str = "Create a file in the artifact"
    artifact: Any
    args_schema = create_model(
        "createFile", 
        filename = (str, FieldInfo(description="Filename")),
        filedata = (str, FieldInfo(description="Stringified content of the file"))
        )
    
    def _run(self, filename, filedata):
        return self.artifact.create(filename, filedata)


class ReadFile(BaseTool):
    name: str = "readFile"
    description: str = "Read a file in the artifact"
    artifact: Any
    args_schema = create_model(
        "readFile", 
        filename = (str, FieldInfo(description="Filename"))
        )
    
    def _run(self, filename):
        return self.artifact.get(filename)

class DeleteFile(BaseTool):
    name: str = "deleteFile"
    description: str = "Delete a file in the artifact"
    artifact: Any
    args_schema = create_model(
        "deleteFile", 
        filename = (str, FieldInfo(description="Filename"))
        )
    
    def _run(self, filename):
        return self.artifact.delete(filename)


class AppendData(BaseTool):
    name: str = "appendData"
    description: str = "Append data to a file in the artifact"
    artifact: Any
    args_schema = create_model(
        "appendData", 
        filename = (str, FieldInfo(description="Filename")),
        filedata = (str, FieldInfo(description="Stringified content to append"))
        )
    
    def _run(self, filename, filedata):
        return self.artifact.append(filename, filedata)

class OverwriteData(BaseTool):
    name: str = "overwriteData"
    description: str = "Overwrite data in a file in the artifact"
    artifact: Any
    args_schema = create_model(
        "overwriteData", 
        filename = (str, FieldInfo(description="Filename")),
        filedata = (str, FieldInfo(description="Stringified content to overwrite"))
    )
    
    def _run(self, filename, filedata):
        return self.artifact.overwrite(filename, filedata)
    
__all__ = [
    {
        "name": "ListFiles",
        "tool": ListFiles
    },
    {
        "name": "CreateFile",
        "tool": CreateFile
    },
    {
        "name": "ReadFile",
        "tool": ReadFile
    },
    {
        "name": "DeleteFile",
        "tool": DeleteFile
    },
    {
        "name": "AppendData",
        "tool": AppendData
    },
    {
        "name": "OverwriteData",
        "tool": OverwriteData
    }
]