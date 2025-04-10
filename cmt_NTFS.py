import re
from enum import Flag, auto
from datetime import datetime

class NTFSAttribute(Flag):
    """Lớp định nghĩa các thuộc tính file/thư mục NTFS dưới dạng bit flag"""
    read_only = 0x0001   # File chỉ đọc
    hidden = 0x0002      # File ẩn
    system = 0x0004      # File hệ thống
    directory = 0x0010   # Thư mục
    archieve = 0x0020    # File đã được archive 
    device = 0x0040      # Thiết bị

def as_datetime(timestamp):
    """Chuyển đổi timestamp NTFS (100-ns intervals từ 1601-01-01) sang datetime"""
    return datetime.fromtimestamp((timestamp - 116444736000000000) // 10000000)

class Record:
    """Lớp đại diện cho một bản ghi MFT (Master File Table)"""
    
    def __init__(self, data) -> None:
        # Phân tích cấu trúc bản ghi MFT
        self.raw_data = data
        # Lấy ID file từ offset 0x2C-0x30
        self.file_id = int.from_bytes(self.raw_data[0x2C:0x30], byteorder='little')
        
        # Kiểm tra trạng thái bản ghi
        if self.flag in (0, 2):  # Bản ghi đã xóa
            raise Exception("Skip this record")
        
        # Phân tích các phần của bản ghi
        self.__parse_standard_info()  # Thông tin chuẩn
        self.__parse_file_name()      # Tên file
        self.__parse_data()           # Dữ liệu file

    def is_directory(self):
        """Kiểm tra có phải thư mục không"""
        return NTFSAttribute.directory in self.standard_info['flags']

    def __parse_data(self, start):
        """Phân tích thuộc tính dữ liệu (DATA attribute)"""
        # Xử lý dữ liệu resident (lưu trực tiếp trong MFT)
        if attr_type == b'\x80\x00\x00\x00':
            if self.data['resident']:
                # Lấy dữ liệu trực tiếp từ MFT
                self.data['content'] = self.raw_data[start + offset:start + offset + self.data['size']]
            else:
                # Xử lý dữ liệu non-resident (lưu trong cluster)
                self.__parse_cluster_chain()

class DirectoryTree:
    """Lớp quản lý cấu trúc cây thư mục NTFS"""
    
    def __build_parent_child_links(self):
        """Xây dựng quan hệ parent-child giữa các bản ghi"""
        for node in self.nodes_dict.values():
            parent_id = node.file_name['parent_id']
            if parent_id in self.nodes_dict:
                self.nodes_dict[parent_id].childs.append(node)

class NTFS:
    """Lớp chính thao tác với hệ thống file NTFS"""
    
    def __init__(self, name: str) -> None:
        """Khởi tạo và đọc thông tin volume NTFS"""
        # Mở volume ở chế độ đọc binary
        # Đọc boot sector (512 byte đầu tiên)
        # Kiểm tra OEM_ID để xác định đúng NTFS
        # Trích xuất các thông số quan trọng từ boot sector
    
    def __extract_boot_sector(self):
        """Trích xuất thông tin từ boot sector NTFS"""
        # Bytes per sector (thường 512)
        # Sectors per cluster (thường 8)
        # Vị trí bảng MFT
    
    def visit_dir(self, path) -> Record:
        """Di chuyển đến thư mục chỉ định và trả về bản ghi thư mục"""
        # Xử lý đường dẫn dạng C:\Folder\Subfolder
        # Tìm kiếm từng thành phần trong đường dẫn
    
    def get_dir(self, path = ""):
        """Lấy danh sách các entry trong thư mục"""
        # Trả về danh sách các bản ghi hợp lệ
        # Bao gồm: tên, kích thước, thuộc tính...
    
    def change_dir(self, path=""):
        """Thay đổi thư mục làm việc hiện tại"""
        # Cập nhật biến current_dir và đường dẫn hiện tại (cwd)
    
    def get_text_file(self, path: str) -> str:
        """Đọc nội dung file văn bản"""
        # Xử lý cả file resident và non-resident
        # Tự động decode từ binary sang UTF-8