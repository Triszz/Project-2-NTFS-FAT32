from enum import Flag, auto
from datetime import datetime
from itertools import chain
import re

class Attribute(Flag):
    """Lớp định nghĩa các thuộc tính file/thư mục trong FAT32"""
    read_only = 0x01    # File chỉ đọc
    hidden = 0x02       # File ẩn
    system = 0x04       # File hệ thống
    vollable = 0x08     # Volume label (nhãn ổ đĩa)
    directory = 0x10    # Thư mục
    archive = 0x20      # File archive

class FAT:
    """Lớp quản lý bảng FAT (File Allocation Table)"""
    def __init__(self, data) -> None:
        # Khởi tạo bảng FAT từ dữ liệu nhị phân
        self.raw_data = data
        self.elements = []
        # Phân tích cấu trúc bảng FAT
    
    def get_cluster_chain(self, index: int) -> 'list[int]':
        # Trả về chuỗi cluster liên tiếp của file/thư mục

class RDET_entry:
    """Lớp biểu diễn 1 entry trong thư mục (32 bytes)"""
    def __init__(self, data):
        # Phân tích entry thư mục từ dữ liệu 32 bytes
    
    def _determine_entry_type(self):
        # Xác định loại entry (subentry/long name)
    
    def _read_attributes(self):
        # Đọc các thuộc tính từ byte attribute
    
    def _process_short_name(self):
        # Xử lý tên file ngắn (8.3 format)
    
    def _process_long_name(self):
        # Ghép các subentry để tạo tên file dài
    
    def _parse_dates(self):
        # Phân tích các thông tin ngày tháng
    
    def is_directory(self) -> bool:
        # Kiểm tra có phải thư mục không
        # (bao gồm cả thư mục đặc biệt '.' và '..')

class RDET:
    """Lớp quản lý Root Directory Entry Table"""
    def __init__(self, data: bytes) -> None:
        # Khởi tạo và phân tích toàn bộ RDET
    
    def _construct_short_name(self, entry):
        # Tạo tên file đầy đủ từ tên ngắn và phần mở rộng
    
    def get_active_entries(self) -> 'list[RDET_entry]':
        # Lọc các entry hợp lệ (không bị xóa, không ẩn...)
    
    def find_entry(self, name) -> RDET_entry:
        # Tìm entry theo tên trong thư mục

class FAT32:
    """Lớp chính thao tác với hệ thống file FAT32"""
    def __init__(self, name: str) -> None:
        # Khởi tạo và đọc thông tin boot sector
    
    def __extract_boot_sector(self):
        # Trích xuất thông tin từ boot sector
    
    def visit_dir(self, dir) -> RDET:
        # Di chuyển đến thư mục chỉ định và trả về RDET của nó
    
    def get_dir(self, dir=""):
        # Lấy danh sách các entry trong thư mục hiện tại
    
    def change_dir(self, path=""):
        # Thay đổi thư mục làm việc hiện tại
    
    def get_all_cluster_data(self, cluster_index):
        # Đọc toàn bộ dữ liệu từ chuỗi cluster
    
    def get_text_file(self, path: str) -> str:
        # Đọc nội dung file văn bản
    
    def _find_entry(self, path_parts):
        # Tìm entry theo đường dẫn