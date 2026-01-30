import os

# Centralized Path Manager
class PathManager:
    '''Centralized Path Manager'''

    def __init__(self) -> None:
        root_path = os.path.abspath(os.path.join(os.getcwd(), '..', '..'))
        data_folder = os.path.join(root_path, "data")
        extracted_data_folder = os.path.join(root_path, "extracted_data")
        metadata_folder = os.path.join(root_path, "metadata")
    
        self.dir_dict = {
            "root": root_path,
            "data": data_folder,
            "extracted_data": extracted_data_folder,
            "metadata": metadata_folder
        }

    def get_dir(self, key: str) -> str:
        return self.dir_dict[key]
