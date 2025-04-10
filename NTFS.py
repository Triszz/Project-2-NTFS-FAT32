import re
from enum import Flag, auto
from datetime import datetime
class NTFSAttribute(Flag):
    read_only = 0x0001  # File chỉ đọc
    hidden = 0x0002     # File ẩn
    system = 0x0004     # File hệ thống
    directory = 0x0010  # Thư mục
    archieve = 0x0020   # File đã được archive 
    device = 0x0040     # Thiết bị
    
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
    self.flag = self.raw_data[0x16]
    # Kiểm tra trạng thái bản ghi
    if self.flag == 0 or self.flag == 2:
      # Bản ghi đã xóa
      raise Exception("Skip this record")
    standard_info_start = int.from_bytes(self.raw_data[0x14:0x16], byteorder='little')
    standard_info_size = int.from_bytes(self.raw_data[standard_info_start + 4:standard_info_start + 8], byteorder='little')
    self.standard_info = {}
    self.__parse_standard_info(standard_info_start)  # Phân tích thông tin chuẩn của bản ghi
    file_name_start = standard_info_start + standard_info_size
    file_name_size = int.from_bytes(self.raw_data[file_name_start + 4:file_name_start + 8], byteorder='little')
    self.file_name = {}
    self.__parse_file_name(file_name_start) # Phân tích tên file của bản ghi
    data_start = file_name_start + file_name_size
    data_sig = self.raw_data[data_start:data_start + 4]
    if data_sig[0] == 64:
      data_start += int.from_bytes(self.raw_data[data_start + 4:data_start + 8], byteorder='little')
    
    data_sig = self.raw_data[data_start:data_start + 4]
    self.data = {}
    if data_sig[0] == 128:
      self.__parse_data(data_start) # Phân tích dữ liệu file của bản ghi
    elif data_sig[0] == 144:
      self.standard_info['flags'] |= NTFSAttribute.directory
      self.data['size'] = 0
      self.data['resident'] = True
    self.childs: list[Record] = []

    del self.raw_data

  def get_attributes(self):
    # Lấy tất cả các thuộc tính từ flags
    return [attr.name for attr in NTFSAttribute if attr in self.standard_info['flags']]

  def is_directory(self):
    """Kiểm tra có phải thư mục không"""
    return NTFSAttribute.directory in self.standard_info['flags']
  
  def is_leaf(self):
    return not len(self.childs)

  def is_active_record(self):
    flags = self.standard_info['flags']
    if NTFSAttribute.system in flags or NTFSAttribute.hidden in flags:
      return False
    return True
  
  def find_record(self, name: str):
    for record in self.childs:
      if record.file_name['long_name'] == name:
        return record
    return None
  
  def get_active_records(self) -> 'list[Record]':
    record_list: list[Record] = []
    for record in self.childs:
      if record.is_active_record():
        record_list.append(record)
    return record_list
  
  def __parse_data(self, start):
    """Phân tích thuộc tính dữ liệu (DATA attribute)"""
    self.data = {'resident': False, 'size': 0}  # <-- Thêm dòng này
    
    # Kiểm tra loại thuộc tính (DATA: 0x80, Directory: 0x90)
    attr_type = self.raw_data[start:start + 4]
    
    # Xử lý thuộc tính DATA (0x80)
    if attr_type == b'\x80\x00\x00\x00':
        self.data['resident'] = not bool(self.raw_data[start + 0x8])  # 0x8 = Resident flag
        
        # Resident Data
        if self.data['resident']:
            offset = int.from_bytes(self.raw_data[start + 0x14:start + 0x16], byteorder='little')
            self.data['size'] = int.from_bytes(self.raw_data[start + 0x10:start + 0x14], byteorder='little')
            self.data['content'] = self.raw_data[start + offset:start + offset + self.data['size']] # Lấy dữ liệu trực tiếp từ MFT
        
        # Non-Resident Data
        else:
            cluster_chain = self.raw_data[start + 0x40]
            offset_bits = (cluster_chain & 0xF0) >> 4
            size_bits = cluster_chain & 0x0F
            
            self.data['size'] = int.from_bytes(self.raw_data[start + 0x30:start + 0x38], byteorder='little')
            self.data['cluster_size'] = int.from_bytes(self.raw_data[start + 0x41:start + 0x41 + size_bits], byteorder='little')
            self.data['cluster_offset'] = int.from_bytes(self.raw_data[start + 0x41 + size_bits:start + 0x41 + size_bits + offset_bits], byteorder='little')
    
    # Xử lý thư mục (Directory, 0x90)
    elif attr_type == b'\x90\x00\x00\x00':
        self.standard_info['flags'] |= NTFSAttribute.directory
        self.data.update({'resident': True, 'size': 0})  # <-- Cập nhật
    
    # Các trường hợp khác (nếu cần)
    else:
        pass  # Hoặc xử lý tùy theo logic


  def __parse_file_name(self, start):
    sig = int.from_bytes(self.raw_data[start:start + 4], byteorder='little')
    if sig != 0x30:
      raise Exception("Skip this record")
    
    # header = self.raw_data[start:start + 0x10]
    size = int.from_bytes(self.raw_data[start + 0x10:start + 0x14], byteorder='little')
    offset = int.from_bytes(self.raw_data[start + 0x14: start + 0x16], byteorder='little')
    body = self.raw_data[start + offset: start + offset + size]
    
    self.file_name["parent_id"] = int.from_bytes(body[:6], byteorder='little')
    name_length = body[64]
    self.file_name["long_name"] = self.__decode_filename(body[66:66 + name_length * 2])  # unicode

  def __decode_filename(self, raw_bytes):
    return raw_bytes.decode('utf-16le', errors='replace')  # Thêm xử lý lỗi

  def __parse_standard_info(self, start):
    sig = int.from_bytes(self.raw_data[start:start + 4], byteorder='little')
    if sig != 0x10:
      raise Exception("Something Wrong!")
    offset = int.from_bytes(self.raw_data[start + 20:start + 21], byteorder='little')
    begin = start + offset
    self.standard_info["created_time"] = as_datetime(int.from_bytes(self.raw_data[begin:begin + 8], byteorder='little'))
    self.standard_info["last_modified_time"] = as_datetime(int.from_bytes(self.raw_data[begin + 8:begin + 16], byteorder='little'))
    self.standard_info["flags"] = NTFSAttribute(int.from_bytes(self.raw_data[begin + 32:begin + 36], byteorder='little'))
    self.standard_info["created_time"] = as_datetime(int.from_bytes(self.raw_data[begin:begin+8], byteorder='little'))
    
    self.__parse_flags(begin + 32)

  def __parse_flags(self, offset):
      flags_value = int.from_bytes(self.raw_data[offset:offset+4], byteorder='little')
      self.standard_info["flags"] = NTFSAttribute(flags_value)
      # Xử lý riêng cờ DEVICE
      if NTFSAttribute.device in self.standard_info["flags"]:
          self.standard_info["flags"] &= ~NTFSAttribute.device


class DirectoryTree:
  """Lớp quản lý cấu trúc cây thư mục NTFS"""
  def __init__(self, nodes: 'list[Record]') -> None:
    self.root = None
    self.nodes_dict: dict[int, Record] = {}
    for node in nodes:
      self.nodes_dict[node.file_id] = node

    self.__build_parent_child_links()
    self.__find_root_node()

  def __build_parent_child_links(self):
    """Xây dựng quan hệ parent-child giữa các bản ghi"""
    for node in self.nodes_dict.values():
        parent_id = node.file_name['parent_id']
        if parent_id in self.nodes_dict:
            self.nodes_dict[parent_id].childs.append(node)

  def __find_root_node(self):
    for node in self.nodes_dict.values():
        if node.file_name['parent_id'] == node.file_id:
            self.root = node
            break
    
    self.current_dir = self.root

  def find_record(self, name: str):
    # Chuẩn hóa tên file (bỏ ký tự đặc biệt và phân biệt hoa thường)
        normalized_name = name.strip().lower()
        for record in self.current_dir.childs:
            if record.file_name['long_name'].strip().lower() == normalized_name:
                return record
        return None
  
  def get_parent_record(self, record: Record):
    return self.nodes_dict[record.file_name['parent_id']]

  def get_active_records(self) -> 'list[Record]':
    return self.current_dir.get_active_records()

class File:
  def __init__(self, data: bytes) -> None:
    self.raw_data = data
    self.info_offset = int.from_bytes(self.raw_data[0x14:0x16], byteorder='little')
    self.info_len = int.from_bytes(self.raw_data[0x3C:0x40], byteorder='little')
    self.file_name_offset = self.info_offset + self.info_len
    self.file_name_len = int.from_bytes(self.raw_data[0x9C:0xA0], byteorder='little')
    self.data_offset = self.file_name_offset + self.file_name_len
    self.data_len = int.from_bytes(self.raw_data[0x104:0x108], byteorder='little')
    self.num_sector = (int.from_bytes(self.raw_data[0x118:0x120], byteorder='little') + 1) * 8
    del self.raw_data

class NTFS:
  """Lớp chính thao tác với hệ thống file NTFS"""
  info = [
    "OEM_ID",
    "serial_number",
    "bytes_per_sector",
    "sectors_per_cluster", 
    "reserved_sectors",
    "volume_size",
    "first_cluster_of_MFT",
    "first_cluster_of_MFTMirr",
    "record_size",
  ]
  def __init__(self, name: str) -> None:
    """Khởi tạo và đọc thông tin volume NTFS"""
    self.name = name
    self.cwd = [self.name]
    try:
      self.fd = open(r'\\.\%s' % self.name, 'rb') # Mở volume ở chế độ đọc binary
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
      self.boot_sector_raw = self.fd.read(0x200)  # Đọc boot sector (512 byte đầu tiên)
      self.boot_sector = {}
      self.__extract_boot_sector()
      # Kiểm tra OEM_ID để xác định đúng NTFS
      if self.boot_sector["OEM_ID"] != b'NTFS    ':
        raise Exception("Not NTFS")
      # Trích xuất các thông số quan trọng từ boot sector
      self.boot_sector["OEM_ID"] = self.boot_sector["OEM_ID"].decode()
      self.boot_sector['serial_number'] = hex(self.boot_sector['serial_number'] & 0xFFFFFFFF)[2:].upper()
      self.boot_sector['serial_number'] = self.boot_sector['serial_number'][:4] + "-" + self.boot_sector['serial_number'][4:]
      self.SC = self.boot_sector["sectors_per_cluster"]
      self.BS = self.boot_sector["bytes_per_sector"]

      self.record_size = self.boot_sector["record_size"]
      self.mft_offset = self.boot_sector['first_cluster_of_MFT']
      self.fd.seek(self.mft_offset * self.SC * self.BS)
      self.mft_file = File(self.fd.read(self.record_size))
      mft_record: list[Record] = []
      for _ in range(2, self.mft_file.num_sector, 2):
        dat = self.fd.read(self.record_size)
        if dat[:4] == b"FILE":
          try:
            mft_record.append(Record(dat))
          except Exception as e:
            pass
  
      self.dir_tree = DirectoryTree(mft_record)
    except Exception as e:
      print(f"[ERROR] {e}")
      exit()

  @staticmethod
  def check_ntfs(name: str):
    try:
      with open(r'\\.\%s' % name, 'rb') as fd:
        oem_id = fd.read(0xB)[3:]
        if oem_id == b'NTFS    ':
          return True
        return False
    except Exception as e:
      print(f"[ERROR] {e}")
      exit()

  def __extract_boot_sector(self):
    """Trích xuất thông tin từ boot sector NTFS"""
    self.boot_sector.update(self.__read_boot_values())

  def __read_boot_values(self):
    clusters_per_record = int.from_bytes(
        self.boot_sector_raw[0x40:0x41], 
        'little', 
        signed=True
    )
    return {
        'OEM_ID': self.boot_sector_raw[3:0xB],
        'bytes_per_sector': self.__read_uint16(0xB),
        'sectors_per_cluster': int.from_bytes(self.boot_sector_raw[0xD:0xE], 'little'),
        'reserved_sectors': int.from_bytes(self.boot_sector_raw[0xE:0x10], 'little'),
        'volume_size': int.from_bytes(self.boot_sector_raw[0x28:0x30], 'little'),
        'first_cluster_of_MFT': int.from_bytes(self.boot_sector_raw[0x30:0x38], 'little'),
        'first_cluster_of_MFTMirr': int.from_bytes(self.boot_sector_raw[0x38:0x40], 'little'),
        # 'Clusters Per File Record Segment': clusters_per_record,
        'record_size': 2 ** abs(clusters_per_record),  # Tính trực tiếp từ biến cục bộ
        'serial_number': int.from_bytes(self.boot_sector_raw[0x48:0x50], 'little'),
        # 'Signature': self.boot_sector_raw[0x1FE:0x200],
    }
  def __read_uint16(self, offset):
    return int.from_bytes(self.boot_sector_raw[offset:offset+2], 'little')


  def __parse_path(self, path):
    dirs = re.sub(r"[/\\]+", r"\\", path).strip("\\").split("\\")
    return dirs
  
  def visit_dir(self, path) -> Record:
    """Di chuyển đến thư mục chỉ định và trả về bản ghi thư mục"""
    # Xử lý đường dẫn dạng C:\Folder\Subfolder
    dirs = self.__parse_path(path)
    cur_dir = self.dir_tree.current_dir
    # Tìm kiếm từng thành phần trong đường dẫn
    for d in dirs:
        record = cur_dir.find_record(d)
        if record and record.is_directory():
          cur_dir = record
        else:
          # Xử lý khi không tìm thấy thư mục
          raise Exception(f"Directory '{d}' not found")
    return cur_dir

  def get_dir(self, path = ""):
    """Lấy danh sách các entry trong thư mục"""
    try:
      if path != "":
        next_dir = self.visit_dir(path)
        if next_dir is None:
            return []  # Trả về danh sách rỗng nếu không tìm thấy
        record_list = next_dir.get_active_records()
      else:
        record_list = self.dir_tree.get_active_records()   # Trả về danh sách các bản ghi hợp lệ
      ret = []
      # Bao gồm: tên, kích thước, thuộc tính...
      for record in record_list:
        obj = {}
        obj["Flags"] = record.standard_info['flags'].value
        obj["Date Modified"] = record.standard_info['last_modified_time']
        obj["Size"] = record.data.get('size', 0)
        obj["Name"] = record.file_name['long_name']
        obj["Sector"] = (
                self.mft_offset * self.SC + record.file_id
                if record.data.get('resident', False)
                else record.data.get('cluster_offset', 0) * self.SC
            )
        ret.append(obj)
      return ret
    except Exception as e:
      raise (e)

  def change_dir(self, path=""):
    """Thay đổi thư mục làm việc hiện tại"""
    if path == "":
      raise Exception("Path to directory is required!")
    try:
      # Cập nhật biến current_dir và đường dẫn hiện tại (cwd)
      next_dir = self.visit_dir(path)
      self.dir_tree.current_dir = next_dir

      dirs = self.__parse_path(path)
      if dirs[0] == self.name:
        self.cwd.clear()
        self.cwd.append(self.name)
        dirs.pop(0)
      for d in dirs:
        if d == "..":
          if len(self.cwd) > 1: self.cwd.pop()
        elif d != ".":
          self.cwd.append(d)
    except Exception as e:
      raise (e)

  def get_cwd(self):
    if len(self.cwd) == 1:
      return self.cwd[0] + "\\"
    return "\\".join(self.cwd)
  
  # def get_file_content(self, path: str):
  #   path = self.__parse_path(path)
  #   if len(path) > 1:
  #     name = path[-1]
  #     path = "\\".join(path[:-1])
  #     next_dir = self.visit_dir(path)
  #     record = next_dir.find_record(name)
  #   else:
  #     record = self.dir_tree.find_record(path[0])

  #   if record is None:
  #     raise Exception("File doesn't exist")
  #   if record.is_directory():
  #     raise Exception("Is a directory")

  #   if 'resident' not in record.data:
  #     return b''
  #   if record.data['resident']:
  #     return record.data['content']
  #   else:
  #     real_size = record.data['size']
  #     offset = record.data['cluster_offset'] * self.SC * self.BS
  #     size = record.data['cluster_size'] * self.SC * self.BS
  #     self.fd.seek(offset)
  #     data = self.fd.read(min(size, real_size))
  #     return data

  def get_text_file(self, path: str) -> str:
    """Đọc nội dung file văn bản"""
    path = self.__parse_path(path)
    try:
        if len(path) > 1:
            name = path[-1]
            path = "\\".join(path[:-1])
            next_dir = self.visit_dir(path)
            record = next_dir.find_record(name)
        else:
            record = self.dir_tree.find_record(path[0])

        if record is None:
            return "[Error] File not found"
        if record.is_directory():
            return "[Error] This is a directory"
        
        if 'resident' not in record.data or 'size' not in record.data:
          return "[Error] Invalid file attributes"

        # Xử lý file resident
        if record.data['resident']:
            content = record.data.get('content', b'')
            try:
                return content.decode('utf-8', errors='replace')   # Tự động decode từ binary sang UTF-8 và thay thế ký tự bị lỗi 
            except Exception as e:
                return f"[Error] Cannot decode content: {str(e)}"
        
        # Xử lý file non-resident
        else:
            data = ""
            size_left = record.data.get('size', 0)
            offset = record.data.get('cluster_offset', 0) * self.SC * self.BS
            cluster_size = record.data.get('cluster_size', 0)
            
            self.fd.seek(offset)
            for _ in range(cluster_size):
                if size_left <= 0:
                    break
                chunk_size = min(self.SC * self.BS, size_left)
                raw_data = self.fd.read(chunk_size)
                size_left -= chunk_size
                try:
                    decoded_chunk = raw_data.decode('utf-8', errors='replace')
                    data += decoded_chunk
                except Exception as e:
                    data += f"[Decode error at chunk {_}: {str(e)}]"
            return data

    except Exception as e:
        return f"[System Error] {str(e)}"
  
  def __str__(self) -> str:
    s = "Volume name: " + self.name
    s += "\nVolume information:\n"
    for key in NTFS.info:
      s += f"{key}: {self.boot_sector[key]}\n"
    return s
  
  def __del__(self):
    if getattr(self, "fd", None):
      print("Closing Volume...")
      self.fd.close()