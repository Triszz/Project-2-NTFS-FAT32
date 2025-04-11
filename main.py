import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import win32api
from FAT32 import FAT32, Attribute
from NTFS import NTFS, NTFSAttribute  

class DiskAnalyzerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Disk Partition Analyzer")
        self.current_fs = None
        self.current_partition = None
        
        # Configure styles
        self.style = ttk.Style()
        self.style.configure("Treeview", font=('Arial', 10), rowheight=25)
        
        # Create GUI components
        self.create_widgets()
        self.populate_drives()
        
    def create_widgets(self):
        # Top frame for drive selection
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(top_frame, text="Select Partition:").pack(side=tk.LEFT)
        self.drive_combobox = ttk.Combobox(top_frame, width=5, state='readonly')
        self.drive_combobox.pack(side=tk.LEFT, padx=10)
        self.drive_combobox.bind('<<ComboboxSelected>>', self.on_drive_select)

        # Main container using PanedWindow
        main_pane = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        main_pane.pack(fill=tk.BOTH, expand=True)

        # Left pane: Tree view
        left_frame = ttk.Frame(main_pane, width=300)
        main_pane.add(left_frame)

        # Tree view for directory structure
        self.tree = ttk.Treeview(left_frame, columns=('size'), show='tree')
        self.tree.heading('#0', text='Directory Structure', anchor=tk.W)
        self.tree.column('#0', width=280, anchor=tk.W)
        self.tree.column('size', width=100, anchor=tk.E)

        vsb = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(left_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        # Right pane: Metadata and content
        right_pane = tk.PanedWindow(main_pane, orient=tk.VERTICAL, sashrelief=tk.RAISED)
        main_pane.add(right_pane)

        # Metadata panel (top 30%)
        info_frame = ttk.LabelFrame(right_pane, text="Properties")
        right_pane.add(info_frame, height=200, sticky='nsew') # Tự động co giãn theo tỷ lệ khi resize cửa sổ

        self.info_text = tk.Text(info_frame, wrap=tk.WORD, font=('Consolas', 10))
        self.info_text.pack(fill=tk.BOTH, expand=True)

        # Content panel (bottom 70%)
        content_frame = ttk.LabelFrame(right_pane, text="Content")
        right_pane.add(content_frame, height=400, sticky='nsew')  # Chiều cao lớn hơn

        self.content_text = tk.Text(content_frame, wrap=tk.WORD, font=('Consolas', 10))
        self.content_text.pack(fill=tk.BOTH, expand=True)

        # Bind tree events
        self.tree.bind('<<TreeviewOpen>>', self.on_tree_open)
        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)

    def populate_drives(self):
        drives = [f"{d}:\\" for d in win32api.GetLogicalDriveStrings().split('\x00') if d]
        self.drive_combobox['values'] = drives
        if drives:
            self.drive_combobox.current(0)
            self.on_drive_select()

    def on_drive_select(self, event=None):
        selected = self.drive_combobox.get()
        self.current_partition = selected[:2]  # Lấy 'C:' từ 'C:\\'
        self.initialize_filesystem()
        self.populate_tree()

    def initialize_filesystem(self):
        try:
            if not self.current_partition:
                return
                
            # Thêm log để kiểm tra giá trị
            print(f"Trying to access: \\\\.\\{self.current_partition}")
                
            if FAT32.check_fat32(self.current_partition):
                self.current_fs = FAT32(self.current_partition)
            elif NTFS.check_ntfs(self.current_partition):
                self.current_fs = NTFS(self.current_partition)
            else:
                messagebox.showerror("Error", "Unsupported filesystem")
                
        except Exception as e:
            messagebox.showerror("Critical Error", 
                f"Cannot access partition {self.current_partition}:\n{str(e)}\n"
                "Please run as Administrator and check drive letter!")
            self.current_fs = None

    def populate_tree(self, path=''):
        self.tree.delete(*self.tree.get_children())
        try:
            entries = self.current_fs.get_dir(path)
            for entry in entries:
                name = entry['Name']
                if entry.get('Size', 0) == 0:  # Directory
                    node = self.tree.insert('', 'end', text=name, values=('DIR'), open=False)
                    self.tree.insert(node, 'end')  # Dummy node for expand
                else:  # File
                    self.tree.insert('', 'end', text=name, values=(f"{entry['Size']} bytes"))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_tree_open(self, event):
        node = self.tree.focus()
        children = self.tree.get_children(node)
        if children and len(children) == 1 and self.tree.item(children[0])['text'] == '':
            self.tree.delete(children[0])
            parent_path = self.get_full_path(node)
            try:
                entries = self.current_fs.get_dir(parent_path)
                for entry in entries:
                    name = entry['Name']
                    if entry.get('Size', 0) == 0:
                        child_node = self.tree.insert(node, 'end', text=name, values=('DIR'), open=False)
                        self.tree.insert(child_node, 'end')  # Dummy node
                    else:
                        self.tree.insert(node, 'end', text=name, values=(f"{entry['Size']} bytes"))
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def get_full_path(self, node):
        path = []
        while node:
            current_node = self.tree.item(node)
            node_text = current_node['text']
            # Bỏ qua node root (nếu có)
            if node_text != self.current_partition:
                path.append(node_text)
            node = self.tree.parent(node)
        return '\\'.join(reversed(path))

    def on_tree_select(self, event):
        node = self.tree.focus()
        if not node:
            return
        
        path = self.get_full_path(node)
        try:
            self.info_text.delete(1.0, tk.END)
            self.content_text.delete(1.0, tk.END)
            
            is_directory = self.tree.item(node)['values'][0] == 'DIR'
            name = os.path.basename(path)
            info = f"Name: {name}\n"
            
            # Truy vấn metadata từ hệ thống file
            if isinstance(self.current_fs, FAT32):
                # Truy vấn entry từ đường dẫn đầy đủ
                entry = self.current_fs.RDET.find_entry(name)
                if not entry:
                    # Nếu không tìm thấy, thử truy vấn trong thư mục con
                    parent_dir = os.path.dirname(path)
                    cdet = self.current_fs.visit_dir(parent_dir)
                    entry = cdet.find_entry(name)
                
                if entry:
                    attributes = []
                    for attr in Attribute:
                        if attr in entry.attr:
                            attributes.append(attr.name)
                    info += f"Attributes: {', '.join(attributes) if attributes else 'N/A'}\n"
                    
                    # Ngày và giờ tạo
                    if hasattr(entry, 'date_created'):
                        info += f"Date created: {entry.date_created.strftime('%Y-%m-%d')}\n"
                        info += f"Time created: {entry.date_created.strftime('%H:%M:%S')}\n"
                    
                    # Kích thước (chỉ file)
                    if not is_directory:
                        info += f"Total Size: {entry.size} bytes\n"

            elif isinstance(self.current_fs, NTFS):
                # Truy vấn record từ đường dẫn đầy đủ
                record = self.current_fs.dir_tree.current_dir.find_record(name)
                if not record:
                    parent_dir = os.path.dirname(path)
                    next_dir = self.current_fs.visit_dir(parent_dir)
                    record = next_dir.find_record(name)
                
                if record:
                    # Lọc bỏ thuộc tính DEVICE
                    attributes = [attr.name for attr in NTFSAttribute 
                          if attr in record.standard_info['flags'] 
                          and attr != NTFSAttribute.device]  # <-- Thêm điều kiện này
                    info += f"Attributes: {', '.join(attributes) if attributes else 'N/A'}\n"
                    
                    # Ngày và giờ tạo
                    created = record.standard_info.get('created_time', None)
                    if created:
                        info += f"Date created: {created.strftime('%Y-%m-%d')}\n"
                        info += f"Time created: {created.strftime('%H:%M:%S')}\n"
                    
                    # Kích thước (chỉ file)
                    if not is_directory:
                        info += f"Total Size: {record.data.get('size', 'N/A')} bytes\n"

            self.info_text.insert(tk.END, info)

            # Hiển thị nội dung file (nếu không phải thư mục)
            if not is_directory:
                try:
                    content = self.current_fs.get_text_file(path)
                    self.content_text.insert(tk.END, content)
                except Exception as e:
                    self.content_text.insert(tk.END, f"Cannot display content: {str(e)}")

        except Exception as e:
            messagebox.showerror("Error", str(e))

if __name__ == '__main__':
    root = tk.Tk()
    app = DiskAnalyzerApp(root)
    root.geometry("900x600")
    root.mainloop()
