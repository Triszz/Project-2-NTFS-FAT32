from enum import Flag, auto
from itertools import chain
import re

class FAT32DateTime:
    """Lưu trữ và định dạng các thành phần thời gian"""
    def __init__(self, year, month, day, hour=0, minute=0, second=0, microsecond=0):
        """Khởi tạo đối tượng thời gian với các thành phần"""
        self.year = year
        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second
        self.microsecond = microsecond

    def strftime(self, format_str):
        """"Định dạng thời gian thành chuỗi theo mã format"""
        return format_str \
            .replace("%Y", f"{self.year:04}") \
            .replace("%m", f"{self.month:02}") \
            .replace("%d", f"{self.day:02}") \
            .replace("%H", f"{self.hour:02}") \
            .replace("%M", f"{self.minute:02}") \
            .replace("%S", f"{self.second:02}") \
            .replace("%f", f"{self.microsecond:06}")
    
    def date(self):
        return self
    
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
        for i in range(0, len(self.raw_data), 4):
            self.elements.append(int.from_bytes(self.raw_data[i:i + 4], byteorder='little'))
    
    def get_cluster_chain(self, index: int) -> 'list[int]':
        # Trả về chuỗi cluster liên tiếp của file/thư mục
        index_list = []
        while True:
            index_list.append(index)
            index = self.elements[index]
            if index == 0x0FFFFFFF or index == 0x0FFFFFF7:
                break
        return index_list 

class RDET_entry:
    """Lớp biểu diễn 1 entry trong thư mục (32 bytes)"""
    def __init__(self, data):
        # Phân tích entry thư mục từ dữ liệu 32 bytes
        self.raw_data = data
        self.flag = data[0xB:0xC]
        self.is_subentry = False
        self.is_deleted = False
        self.is_empty = False
        self.is_label = False
        self.attr = Attribute(0)
        self.size = 0
        self.date_created = None
        self.last_accessed = None
        self.date_updated = None
        self.ext = b""
        self.long_name = ""
        self.name = b""
        self.start_cluster = 0
        
        self._determine_entry_type()
        if self.is_subentry:
            self._process_long_name()
        else:
            self._read_attributes()
            self._process_short_name()
            if not self.is_empty and not self.is_label:
                self._parse_dates()
                self._read_cluster_and_size()

    def _determine_entry_type(self):
        # Xác định loại entry (subentry/long name)
        self.is_subentry = self.flag == b'\x0f'

    def _read_attributes(self):
        # Đọc các thuộc tính từ byte attribute
        attr_value = int.from_bytes(self.flag, byteorder='little')
        self.attr = Attribute(attr_value)

    def _process_short_name(self):
        # Xử lý tên file ngắn (8.3 format)
        self.name = self.raw_data[:0x8]
        self.ext = self.raw_data[0x8:0xB]
        
        if self.name.startswith(b'\xe5'):
            self.is_deleted = True
        elif self.name.startswith(b'\x00'):
            self.is_empty = True
            self.name = b""
        
        if Attribute.vollable in self.attr:
            self.is_label = True

    def _process_long_name(self):
        # Ghép các subentry để tạo tên file dài
        self.index = self.raw_data[0]
        self.name = b""
        for i in chain(range(0x1, 0xB), range(0xE, 0x1A), range(0x1C, 0x20)):
            self.name += int.to_bytes(self.raw_data[i], 1, byteorder='little')
            if self.name.endswith(b"\xff\xff"):
                self.name = self.name[:-2]
                break
        self.name = self.name.decode('utf-16le').strip('\x00')

    def _parse_dates(self):
        # Phân tích các thông tin ngày tháng
        self._parse_date_created()
        self._parse_last_accessed()
        self._parse_date_updated()

    def _parse_date_created(self):
        # Đọc 4 byte thời gian tạo (3 byte time + 1 byte ms)
        self.time_created_raw = int.from_bytes(self.raw_data[0xD:0x10], byteorder='little')
        self.date_created_raw = int.from_bytes(self.raw_data[0x10:0x12], byteorder='little')
    
        h = (self.time_created_raw & 0b111110000000000000000000) >> 19
        m = (self.time_created_raw & 0b000001111110000000000000) >> 13
        s = (self.time_created_raw & 0b000000000001111110000000) >> 7
        ms = (self.time_created_raw & 0b000000000000000001111111)
        
        year = 1980 + ((self.date_created_raw & 0b1111111000000000) >> 9)
        mon = (self.date_created_raw & 0b0000000111100000) >> 5
        day = self.date_created_raw & 0b0000000000011111

        # self.date_created = datetime(year, mon, day, h, m, s, ms*10)
        self.date_created = FAT32DateTime(
            year=year,
            month=mon,
            day=day,
            hour=h,
            minute=m,
            second=s,
            microsecond=ms*10 
        )

    def _parse_last_accessed(self):
        self.last_accessed_raw = int.from_bytes(self.raw_data[0x12:0x14], 'little')
        date = self._parse_fat_date(self.last_accessed_raw)
       # self.last_accessed = datetime(date['year'], date['month'], date['day'])
        self.last_accessed = FAT32DateTime(
            year=date['year'],   
            month=date['month'],
            day=date['day']
        )

    def _parse_date_updated(self):
        self.time_updated_raw = int.from_bytes(self.raw_data[0x16:0x18], 'little')
        self.date_updated_raw = int.from_bytes(self.raw_data[0x18:0x1A], 'little')

        h = (self.time_updated_raw & 0b1111100000000000) >> 11
        m = (self.time_updated_raw & 0b0000011111100000) >> 5
        s = (self.time_updated_raw & 0b0000000000011111) * 2
        
        year = 1980 + ((self.date_updated_raw & 0b1111111000000000) >> 9)
        mon = (self.date_updated_raw & 0b0000000111100000) >> 5
        day = self.date_updated_raw & 0b0000000000011111

        #self.date_updated = datetime(year, mon, day, h, m, s)
        self.date_updated = FAT32DateTime(
            year=year,
            month=mon,
            day=day,
            hour=h,
            minute=m,
            second=s
        )

    def _parse_fat_time(self, raw_time, include_ms=False):
        if include_ms:
            h = (raw_time & 0xF8000000) >> 27
            m = (raw_time & 0x07E00000) >> 21
            s = (raw_time & 0x001F0000) >> 16
            ms = (raw_time & 0x0000FFFF)
            return {'hour': h, 'minute': m, 'second': s, 'ms': ms*10}
        else:
            h = (raw_time & 0xF800) >> 11
            m = (raw_time & 0x07E0) >> 5
            s = (raw_time & 0x001F) * 2
            return {'hour': h, 'minute': m, 'second': s, 'ms': 0}

    def _parse_fat_date(self, raw_date):
        year = 1980 + ((raw_date & 0xFE00) >> 9)
        month = (raw_date & 0x01E0) >> 5
        day = raw_date & 0x001F
        return {'year': year, 'month': month, 'day': day}

    def _read_cluster_and_size(self):
        self.start_cluster = int.from_bytes(self.raw_data[0x14:0x16][::-1] + self.raw_data[0x1A:0x1C][::-1], byteorder='big')
        self.size = int.from_bytes(self.raw_data[0x1C:0x20], byteorder='little')

    def is_active_entry(self) -> bool:
        return not (self.is_empty or self.is_subentry or self.is_deleted or self.is_label or Attribute.system in self.attr)
    
    def is_directory(self) -> bool:
        # Kiểm tra có phải thư mục không
        # (bao gồm cả thư mục đặc biệt '.' và '..')
        if self.long_name in (".", ".."):
            return True
        return Attribute.directory in self.attr

    def is_archive(self) -> bool:
        return Attribute.archive in self.attr

    def get_attributes(self):
        if self.is_subentry or self.is_empty or self.is_label:
            return []
        return [attr.name for attr in Attribute if attr in self.attr]

class RDET:
    """Lớp quản lý Root Directory Entry Table"""
    def __init__(self, data: bytes) -> None:
        # Khởi tạo và phân tích toàn bộ RDET
        self.raw_data: bytes = data
        self.entries: list[RDET_entry] = []
        long_name = ""
        for i in range(0, len(data), 32):
            entry = RDET_entry(data[i:i+32])
            self.entries.append(entry)
            if entry.is_empty or entry.is_deleted:
                long_name = ""
                continue
            if entry.is_subentry:
                long_name = entry.name + long_name
                continue

            if long_name != "":
                entry.long_name = long_name
            else:
                entry.long_name = self._construct_short_name(entry)
            long_name = ""

    def _construct_short_name(self, entry):
        # Tạo tên file đầy đủ từ tên ngắn và phần mở rộng
        ext = entry.ext.strip().decode(errors='replace')
        name = entry.name.strip().decode(errors='replace')
    
        if name == "." or name == "..":
            return name
        
        return f"{name}.{ext}" if ext else name

    def get_active_entries(self) -> 'list[RDET_entry]':
        # Lọc các entry hợp lệ (không bị xóa, không ẩn...)
        return [
            entry for entry in self.entries 
            if entry.is_active_entry() 
            and entry.long_name not in (".", "..")  # Thêm điều kiện lọc
        ]

    def find_entry(self, name) -> RDET_entry:
        # Tìm entry theo tên trong thư mục
        lower_name = name.lower()
        for entry in self.get_active_entries():
            if entry.long_name.lower() == lower_name:
                return entry
        return None

class FAT32:
    """Lớp chính thao tác với hệ thống file FAT32"""
    info = [
        "bytes_per_sector",
        "sectors_per_cluster", 
        "sectors_before_FAT", 
        "sectors_per_FAT",
        "number_of_FAT",
        "volume_size",
        "start_cluster_RDET",
        "start_sector_Data",
        "FAT_type"
    ]
    def __init__(self, name: str) -> None:
        # Khởi tạo và đọc thông tin boot sector
        self.name = name
        self.cwd = [self.name]
        try:
            self.fd = open(r'\\.\%s' % self.name, 'rb')
        except FileNotFoundError:
            print(f"[ERROR] No volume named {name}")
            exit()
        except PermissionError:
            print("[ERROR] Permission denied, try again as admin/root")
            exit()
        except Exception as e:
            print(e)
            print("[ERROR] Unknown error occurred")
            exit() 
        
        try:
            self.boot_sector_raw = self.fd.read(0x200)
            self.boot_sector = {}
            self.__extract_boot_sector()
            if self.boot_sector["FAT_type"] != b"FAT32   ":
                raise Exception("Not FAT32")
            self.boot_sector["FAT_type"] = self.boot_sector["FAT_type"].decode()
            self.SB = self.boot_sector['sectors_before_FAT']
            self.SF = self.boot_sector["sectors_per_FAT"]
            self.NF = self.boot_sector["number_of_FAT"]
            self.SC = self.boot_sector["sectors_per_cluster"]
            self.BS = self.boot_sector["bytes_per_sector"]
            self.boot_sector_reserved_raw = self.fd.read(self.BS * (self.SB - 1))
            
            FAT_size = self.BS * self.SF
            self.FAT: list[FAT] = []
            for _ in range(self.NF):
                self.FAT.append(FAT(self.fd.read(FAT_size)))

            self.DET = {}
            
            start = self.boot_sector["start_cluster_RDET"]
            self.DET[start] = RDET(self.get_all_cluster_data(start))
            self.RDET = self.DET[start]

        except Exception as e:
            print(f"[ERROR] {e}")
            exit()
  
    @staticmethod
    def check_fat32(name: str):
        try:
            with open(r'\\.\%s' % name, 'rb') as fd:
                fd.read(1)
                fd.seek(0x52)
                fat_name = fd.read(8)
                return fat_name == b"FAT32   "
        except Exception as e:
            print(f"[ERROR] {e}")
            exit()

    def __extract_boot_sector(self):
        # Trích xuất thông tin từ boot sector
        self.boot_sector['bytes_per_sector'] = self._read_boot_sector_field(0xB, 2)
        self.boot_sector['sectors_per_cluster'] = self._read_boot_sector_field(0xD, 1)
        self.boot_sector['sectors_before_FAT'] = self._read_boot_sector_field(0xE, 2)
        self.boot_sector['number_of_FAT'] = self._read_boot_sector_field(0x10, 1)
        self.boot_sector['volume_size'] = self._read_boot_sector_field(0x20, 4)
        self.boot_sector['sectors_per_FAT'] = self._read_boot_sector_field(0x24, 4)
        self.boot_sector['start_cluster_RDET'] = self._read_boot_sector_field(0x2C, 4)
        self.boot_sector['FAT_type'] = self.boot_sector_raw[0x52:0x5A]
        self.boot_sector['start_sector_Data'] = (
            self.boot_sector['sectors_before_FAT'] + 
            self.boot_sector['number_of_FAT'] * self.boot_sector['sectors_per_FAT']
        )

    def _read_boot_sector_field(self, offset, length):
        return int.from_bytes(
            self.boot_sector_raw[offset:offset+length], 
            byteorder='little'
        )

    def __offset_from_cluster(self, index):
        return self.SB + self.SF * self.NF + (index - 2) * self.SC
  
    def __parse_path(self, path):
        return re.sub(r"[/\\]+", r"\\", path).strip("\\").split("\\")

    def get_cwd(self):
        return "\\".join(self.cwd) + ("\\" if len(self.cwd) == 1 else "")

    def visit_dir(self, dir) -> RDET:
        # Di chuyển đến thư mục chỉ định và trả về RDET của nó
        if dir == "":
            return self.RDET
        dirs = self.__parse_path(dir)
        cdet = self.RDET
        for d in dirs:
            entry = cdet.find_entry(d)
            if entry and entry.is_directory():
                # Thêm kiểm tra cluster hợp lệ
                if entry.start_cluster == 0:
                    continue  # Bỏ qua thư mục gốc ảo
                if entry.start_cluster not in self.DET:
                    self.DET[entry.start_cluster] = RDET(self.get_all_cluster_data(entry.start_cluster))
                cdet = self.DET[entry.start_cluster]
            else:
                raise NotADirectoryError(f"'{d}' is not a directory")
        return cdet
  
    def get_dir(self, dir=""):
        # Lấy danh sách các entry trong thư mục hiện tại
        try:
            cdet = self.visit_dir(dir)
            entry_list = cdet.get_active_entries()
            return [{
                "Flags": entry.attr.value,
                "Date Modified": entry.date_updated,
                "Size": entry.size,
                "Name": entry.long_name,
                "Sector": (entry.start_cluster + 2) * self.SC if entry.start_cluster == 0 else entry.start_cluster * self.SC
            } for entry in entry_list]
        except Exception as e:
            raise e
      
    def change_dir(self, path=""):
        # Thay đổi thư mục làm việc hiện tại
        if not path:
            raise ValueError("Path required")
        cdet = self.visit_dir(path)
        self.RDET = cdet
        dirs = self.__parse_path(path)
        if dirs[0] == self.name:
            self.cwd = [self.name]
            dirs = dirs[1:]
        for d in dirs:
            self.cwd.append(d) if d != ".." else self.cwd.pop()

    def get_all_cluster_data(self, cluster_index):
        # Đọc toàn bộ dữ liệu từ chuỗi cluster
        index_list = self.FAT[0].get_cluster_chain(cluster_index)
        data = b""
        for i in index_list:
            self.fd.seek(self.__offset_from_cluster(i) * self.BS)
            data += self.fd.read(self.SC * self.BS)
        return data
  
    def get_text_file(self, path: str) -> str:
        # Đọc nội dung file văn bản
        path_parts = self.__parse_path(path)
        entry = self._find_entry(path_parts)
        if not entry:
            raise FileNotFoundError("File not found")
        if entry.is_directory():
            raise IsADirectoryError("Is a directory")
        return self._read_file_content(entry)

    # def get_file_content(self, path: str) -> bytes:
    #     path_parts = self.__parse_path(path)
    #     entry = self._find_entry(path_parts)
    #     if not entry:
    #         raise FileNotFoundError("File not found")
    #     if entry.is_directory():
    #         raise IsADirectoryError("Is a directory")
    #     return self.get_all_cluster_data(entry.start_cluster)[:entry.size]

    def _find_entry(self, path_parts):
        # Tìm entry theo đường dẫn
        if len(path_parts) > 1:
            cdet = self.visit_dir("\\".join(path_parts[:-1]))
            return cdet.find_entry(path_parts[-1])
        return self.RDET.find_entry(path_parts[0])

    def _read_file_content(self, entry):
        data = bytearray()
        remaining = entry.size
        for cluster in self.FAT[0].get_cluster_chain(entry.start_cluster):
            if remaining <= 0:
                break
            self.fd.seek(self.__offset_from_cluster(cluster) * self.BS)
            read_size = min(self.SC * self.BS, remaining)
            data.extend(self.fd.read(read_size))
            remaining -= read_size
        return data.decode(errors='replace')

    def __str__(self) -> str:
        info = "\n".join(f"{k}: {v}" for k, v in self.boot_sector.items() if k in self.info)
        return f"Volume name: {self.name}\nVolume information:\n{info}"

    def __del__(self):
        if hasattr(self, 'fd') and self.fd:
            self.fd.close()