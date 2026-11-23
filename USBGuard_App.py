import tkinter as tk
from tkinter import ttk, messagebox
import json
import time
import threading
import ctypes
import sys
import os
import subprocess
from pathlib import Path
from datetime import datetime
from usbguard.service import run_service
import wmi
import pythoncom
import requests

try:
    from PIL import Image, ImageTk, ImageOps
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

class USBGuardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("💀 USB Port Monitor : The Forensic Tool 💀")
        self.root.geometry("1200x850")
        self.root.minsize(700, 450)
        self.root.configure(bg="#0a0a0a")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # --- ICON SETUP (PIL Use Karke) ---
        try:
            icon_path = Path(__file__).parent / "hacker_new.ico"
            if icon_path.exists() and HAS_PIL:
                icon_img = Image.open(icon_path)
                self.icon_photo = ImageTk.PhotoImage(icon_img)
                self.root.iconphoto(True, self.icon_photo)
            elif icon_path.exists():
                self.root.iconbitmap(str(icon_path))
            else:
                print(f"Warning: hacker.ico not found at {icon_path}")
        except Exception as e:
            print(f"Icon load error: {e}")
        # ----------------------------------

        # --- MAIN FRAME ---
        self.main_frame = tk.Frame(root, bg="#0a0a0a")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_file = Path.home() / "USBGuard_Logs" / "usb_events.jsonl"
        
        self.device_history = {}  
        self.storage_files = {}   
        self.device_names = {}    
        self.processed_events = set() 
        
        self.failed_attempts = 0
        self.lockout_time = 0

        self.phone_models = {
            "SM-A156E": "Samsung Galaxy A15 5G", "SM-A155F": "Samsung Galaxy A15",
            "SM-S928B": "Samsung Galaxy S24 Ultra", "SM-S918B": "Samsung Galaxy S23 Ultra",
            "iPhone": "Apple iPhone", "Redmi": "Xiaomi Redmi", "CPH": "Oppo / OnePlus"
        }

        # --- TOP BAR WITH IMAGE BANNER (resizable) ---
        self.header = tk.Canvas(self.main_frame, height=140, highlightthickness=0, bg="#0a0a0a")
        self.header.pack(fill=tk.X)

        self.header_src = None
        img_path = Path(__file__).parent / "background.jpg"
        if HAS_PIL and img_path.exists():
            try:
                self.header_src = Image.open(img_path)
            except Exception:
                self.header_src = None

        self.header_img = None
        self.header_img_id = self.header.create_image(0, 0, anchor="nw")
        self.title_id = self.header.create_text(20, 70, text="💀 USB Port Monitor : The Forensic Tool 💀",
                                                font=("Segoe UI", 18, "bold"), fill="#00ff00", anchor="w")

        self.min_btn = tk.Button(self.header, text="— Minimize to Background", command=self.root.withdraw,
                                 bg="#222", fg="#00ffff", font=("Segoe UI", 10))
        self.refresh_btn = tk.Button(self.header, text="🔄 Refresh Data", command=self.refresh_data,
                                     bg="#222", fg="#00ffff", font=("Segoe UI", 10, "bold"))
        self.min_win = self.header.create_window(0, 70, window=self.min_btn, anchor="e")
        self.refresh_win = self.header.create_window(0, 70, window=self.refresh_btn, anchor="e")

        self.header.bind("<Configure>", self.resize_header)

        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Tab 1: All Devices
        self.tab_live = tk.Frame(self.notebook, bg="#111")
        self.notebook.add(self.tab_live, text="🔌 All Devices")
        top_frame = tk.Frame(self.tab_live, bg="#111")
        top_frame.pack(fill=tk.BOTH, expand=True)
        self.tree_live = self.create_tree(top_frame, ("Device Name", "Current Status", "Action"))
        self.tree_live.bind("<<TreeviewSelect>>", self.on_device_select)

        self.history_frame = tk.Frame(self.tab_live, bg="#0a0a0a", height=150)
        self.history_frame.pack(fill=tk.X, padx=10, pady=5)
        self.history_label = tk.Label(self.history_frame, text="Select a device to view its connection history.", fg="#00ff00", bg="#0a0a0a", font=("Segoe UI", 10, "bold"))
        self.history_label.pack(anchor="w")
        self.tree_inline_history = self.create_tree(self.history_frame, ("Connection Time", "Disconnection Time", "Duration"))

        # Tab 2: Phones
        self.tab_phone = tk.Frame(self.notebook, bg="#111")
        self.notebook.add(self.tab_phone, text="📱 Phones")
        self.tree_phone = self.create_tree(self.tab_phone, ("Time", "Phone Name", "Battery Status", "Status"))
        self.tree_phone.bind("<Double-1>", self.show_phone_details)

        # Tab 3: Bluetooth & WiFi
        self.tab_bluetooth = tk.Frame(self.notebook, bg="#111")
        self.notebook.add(self.tab_bluetooth, text="📶 Bluetooth / WiFi")
        self.tree_bluetooth = self.create_tree(self.tab_bluetooth, ("Time", "Device Name", "MAC Address", "Status"))
        self.tree_bluetooth.bind("<<TreeviewSelect>>", self.on_bluetooth_select)

        self.bt_history_frame = tk.Frame(self.tab_bluetooth, bg="#0a0a0a", height=150)
        self.bt_history_frame.pack(fill=tk.X, padx=10, pady=5)
        self.bt_history_label = tk.Label(self.bt_history_frame, text="Select a Bluetooth device to view its history.", fg="#00ff00", bg="#0a0a0a", font=("Segoe UI", 10, "bold"))
        self.bt_history_label.pack(anchor="w")
        self.tree_bt_inline_history = self.create_tree(self.bt_history_frame, ("Connection Time", "Disconnection Time", "Duration"))

        # Tab 4: Storage
        self.tab_storage = tk.Frame(self.notebook, bg="#111")
        self.notebook.add(self.tab_storage, text="💾 Storage (Pendrive)")
        
        storage_top = tk.Frame(self.tab_storage, bg="#111")
        storage_top.pack(fill=tk.BOTH, expand=True)
        self.tree_storage = self.create_tree(storage_top, ("Time", "Drive Name", "Total Files", "Threats", "Status"))
        self.tree_storage.bind("<<TreeviewSelect>>", self.on_storage_select) 

        self.storage_history_frame = tk.Frame(self.tab_storage, bg="#0a0a0a", height=200)
        self.storage_history_frame.pack(fill=tk.X, padx=10, pady=5)
        self.storage_history_label = tk.Label(self.storage_history_frame, text="Select a drive to inspect its file hierarchy.", fg="#00ff00", bg="#0a0a0a", font=("Segoe UI", 10, "bold"))
        self.storage_history_label.pack(anchor="w")
        self.tree_storage_inline = self.create_tree(self.storage_history_frame, ("File Name", "File Type", "Size", "Status"))

        # Tab 5: Network
        self.tab_network = tk.Frame(self.notebook, bg="#111")
        self.notebook.add(self.tab_network, text="🌐 Internet Info")
        self.lbl_network = tk.Label(self.tab_network, text="Loading Network Details...", fg="#00ff00", bg="#111", font=("Segoe UI", 12), justify="left")
        self.lbl_network.pack(pady=20)

        self.status_var = tk.StringVar(value="🟢 Monitoring Active | Engine Running...")
        status_label = tk.Label(self.main_frame, textvariable=self.status_var, font=("Segoe UI", 10), fg="#00ff00", bg="#0a0a0a")
        status_label.pack(side=tk.BOTTOM, pady=5, before=self.notebook)

        self.stop_event = threading.Event()
        threading.Thread(target=run_service, args=(self.stop_event,), daemon=True).start()
        threading.Thread(target=self.read_logs_live, daemon=True).start()
        threading.Thread(target=self.get_network_info, daemon=True).start()
        threading.Thread(target=self.load_storage_system_logs, daemon=True).start()

    def resize_header(self, event):
        w, h = max(event.width, 1), max(event.height, 1)

        if self.header_src is not None and HAS_PIL:
            img = ImageOps.fit(self.header_src, (w, h), Image.Resampling.BILINEAR)
            self.header_img = ImageTk.PhotoImage(img)
            self.header.itemconfig(self.header_img_id, image=self.header_img)

        if w >= 1000:
            size, min_txt, ref_txt = 18, "— Minimize to Background", "🔄 Refresh Data"
        elif w >= 800:
            size, min_txt, ref_txt = 14, "— Minimize", "🔄 Refresh"
        else:
            size, min_txt, ref_txt = 11, "—", "🔄"
        self.header.itemconfig(self.title_id, font=("Segoe UI", size, "bold"))
        self.min_btn.config(text=min_txt)
        self.refresh_btn.config(text=ref_txt)

        self.header.coords(self.refresh_win, w - 15, h // 2)
        self.header.coords(self.min_win, w - 25 - self.refresh_btn.winfo_reqwidth(), h // 2)

    def load_storage_system_logs(self):
        try:
            cmd = "Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Kernel-PnP/Configuration'; ID=400,410} -MaxEvents 30 | Select-Object TimeCreated, Message | ConvertTo-Json"
            output = subprocess.check_output(["powershell", "-Command", cmd], text=True, creationflags=0x08000000)
            
            if output.strip():
                data = json.loads(output)
                if not isinstance(data, list): data = [data]
                
                for log in reversed(data):
                    time_str = log.get("TimeCreated", "")
                    msg = log.get("Message", "")
                    
                    if "/Date(" in time_str:
                        import re
                        match = re.search(r'/Date\((\d+)\)/', time_str)
                        if match:
                            time_str = datetime.fromtimestamp(int(match.group(1))/1000).strftime("%Y-%m-%d %H:%M:%S")
                            
                    if "USBSTOR" in msg or "Disk" in msg:
                        action = "Connected" if "Started" in msg else "Disconnected"
                        tag = "green" if action == "Connected" else "gray"
                        self.root.after(0, lambda t=time_str, a=action, tg=tag: self.tree_storage.insert("", 0, values=(t, "Storage Drive", "-", "-", a), tags=(tg,)))
        except Exception:
            pass

    def refresh_data(self):
        self.status_var.set("🔄 Refreshing... Verifying device connections.")
        def check_new_devices():
            time.sleep(1) 
            self.get_network_info()
            self.root.after(0, lambda: self.status_var.set("🟢 Monitoring Active | Engine Running..."))
        threading.Thread(target=check_new_devices, daemon=True).start()

    def on_bluetooth_select(self, event):
        selected = self.tree_bluetooth.selection()
        if not selected: return
        
        bt_name = self.tree_bluetooth.item(selected[0])['values'][1]
        mac = self.tree_bluetooth.item(selected[0])['values'][2]
        self.bt_history_label.config(text=f"📜 Connection History: {bt_name} ({mac})")
        
        for item in self.tree_bt_inline_history.get_children():
            self.tree_bt_inline_history.delete(item)
            
        if mac in self.device_history:
            for h in self.device_history[mac]:
                self.tree_bt_inline_history.insert("", tk.END, values=(h['insert'], h.get('remove', 'Active'), h.get('duration', '-')))

    def on_storage_select(self, event):
        selected = self.tree_storage.selection()
        if not selected: return
        values = self.tree_storage.item(selected[0])['values']
        if len(values) < 2: return
        
        drive_name = str(values[1]).split('(')[1].replace(')', '').strip()
        self.storage_history_label.config(text=f"📁 File Hierarchy: {drive_name}")
        
        for item in self.tree_storage_inline.get_children():
            self.tree_storage_inline.delete(item)
            
        files = self.storage_files.get(drive_name, [])
        if not files:
            files = self.read_drive_data_from_file(drive_name)
            self.storage_files[drive_name] = files
            
        if files:
            for f in files:
                size_mb = round(f['size_bytes'] / (1024 * 1024), 2)
                size_text = f"{size_mb} MB" if size_mb > 0 else f"{f['size_bytes']} Bytes"
                simple_type = self.get_simple_file_type(f['data_type'])
                
                if f.get("status") == "SUSPICIOUS":
                    status = "🚨 MALICIOUS"
                    tag = "red"
                elif f.get("status") == "WARNING":
                    status = "⚠️ WARNING"
                    tag = "yellow"
                else:
                    status = "✅ SECURE"
                    tag = "green"
                    
                self.tree_storage_inline.insert("", tk.END, values=(f['path'], simple_type, size_text, status), tags=(tag,))
            
            self.tree_storage_inline.tag_configure("green", foreground="#00ff00")
            self.tree_storage_inline.tag_configure("red", foreground="#ff0000")
            self.tree_storage_inline.tag_configure("yellow", foreground="#f1c40f")
        else:
            self.tree_storage_inline.insert("", tk.END, values=("No scan data found.", "-", "-", "-"))

    def get_phone_battery(self):
        try:
            result = subprocess.check_output(["adb", "shell", "dumpsys", "battery"], text=True, timeout=2)
            for line in result.split('\n'):
                if "level:" in line: return f"🔋 {line.split(':')[1].strip()}%"
        except: pass
        return "🔋 Battery N/A"

    def get_friendly_name(self, tech_name):
        tech_name_lower = tech_name.lower()
        for code, model in self.phone_models.items():
            if code.lower() in tech_name_lower: return f"📱 {model}"
        if "mouse" in tech_name_lower: return "🖱️ Mouse"
        if "keyboard" in tech_name_lower: return "⌨️ Keyboard"
        if "headset" in tech_name_lower or "headphone" in tech_name_lower or "airpod" in tech_name_lower or "buds" in tech_name_lower: return "🎧 Headphones"
        if "watch" in tech_name_lower: return "⌚ Smartwatch"
        if "phone" in tech_name_lower: return "📱 Smartphone"
        return tech_name

    def create_tree(self, parent, columns):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#111", foreground="#00ff00", fieldbackground="#111", rowheight=25, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background="#222", foreground="#00ffff", font=("Segoe UI", 10, "bold"))
        
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=6)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120, minwidth=70, stretch=True, anchor="center")
        
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        return tree

    def on_device_select(self, event):
        selected = self.tree_live.selection()
        if not selected: return
        
        device_name = self.tree_live.item(selected[0])['values'][0]
        self.history_label.config(text=f"📜 Connection History: {device_name}")
        
        for item in self.tree_inline_history.get_children():
            self.tree_inline_history.delete(item)
            
        serial = None
        for s, n in self.device_names.items():
            if n == device_name:
                serial = s
                break
                
        if serial and serial in self.device_history:
            for h in self.device_history[serial]:
                self.tree_inline_history.insert("", tk.END, values=(h['insert'], h.get('remove', 'Active'), h.get('duration', '-')))

    def show_phone_details(self, event):
        selected = self.tree_phone.selection()
        if not selected: return
        popup = tk.Toplevel(self.root)
        popup.title("Phone Data Explorer")
        popup.geometry("500x300")
        popup.configure(bg="#1e1e1e")
        popup.transient(self.root)
        popup.grab_set()
        lbl = tk.Label(popup, text="Phone Data Explorer:\n\n1. Connect phone in 'File Transfer' mode.\n2. Open Windows File Explorer.\n3. Locate your device under 'This PC'.\n\n(Note: Direct MTP access is restricted by OS Security).", fg="#00ff00", bg="#1e1e1e", font=("Segoe UI", 11), justify="left")
        lbl.pack(padx=20, pady=20)

    def read_drive_data_from_file(self, drive_name):
        files = []
        if not self.log_file.exists(): return files
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if data.get("event") == "USB_INSERTED" and drive_name in str(data.get("drive", "")):
                            hierarchy = data.get("hierarchy_snapshot", [])
                            if hierarchy: files = hierarchy
                    except: pass
        except: pass
        return files

    def get_simple_file_type(self, mime_type):
        if "image" in mime_type: return "🖼️ Image"
        if "video" in mime_type: return "🎥 Video"
        if "audio" in mime_type: return "🎵 Audio"
        if "pdf" in mime_type: return "📄 PDF Document"
        if "text" in mime_type: return "📝 Text Document"
        if "zip" in mime_type or "rar" in mime_type: return "🗜️ Compressed Archive"
        if "dosexec" in mime_type or "executable" in mime_type: return "🚨 Executable / Malware"
        return "📁 File"

    def get_network_info(self):
        pythoncom.CoInitialize()
        try:
            c = wmi.WMI()
            info = "--- NETWORK & WIFI DETAILS ---\n\n"
            
            try:
                wifi_output = subprocess.check_output(["netsh", "wlan", "show", "interfaces"], text=True)
                wifi_name = "Disconnected"
                for line in wifi_output.split('\n'):
                    if "SSID" in line and "BSSID" not in line:
                        wifi_name = line.split(":")[1].strip()
                        break
            except:
                wifi_name = "Disconnected"

            info += f"Connected Router: {wifi_name}\n\n"
            
            for ip in c.Win32_NetworkAdapterConfiguration(IPEnabled=True):
                info += f"Adapter: {ip.Description}\nMAC Address: {ip.MACAddress}\nLocal IP: {ip.IPAddress}\n"
            try:
                public_ip = requests.get('https://api.ipify.org', timeout=5).text
                info += f"\n🌐 Public IP: {public_ip}\n"
            except:
                info += f"\n🌐 Public IP: Unavailable\n"
            
            self.root.after(0, lambda: self.show_network_details(info))
        except: pass
        finally: pythoncom.CoUninitialize()

    def show_network_details(self, info_text):
        for widget in self.tab_network.winfo_children():
            widget.destroy()
            
        lbl = tk.Label(self.tab_network, text=info_text, fg="#00ff00", bg="#111", font=("Segoe UI", 12), justify="left")
        lbl.pack(pady=10)
        
        btn = tk.Button(self.tab_network, text="🔒 View WiFi Password", command=self.ask_admin_password, bg="#222", fg="#00ffff")
        btn.pack(pady=10)
        
    def ask_admin_password(self):
        current_time = time.time()
        
        if self.failed_attempts >= 5:
            remaining_time = int(self.lockout_time - current_time)
            if remaining_time > 0:
                mins = remaining_time // 60
                secs = remaining_time % 60
                messagebox.showerror("System Locked", f"Too many failed attempts.\nPlease try again after {mins}m {secs}s.")
                return
            else:
                self.failed_attempts = 0

        popup = tk.Toplevel(self.root)
        popup.title("Security Clearance Required")
        popup.geometry("350x200")
        popup.configure(bg="#1e1e1e")
        
        popup.transient(self.root)
        popup.grab_set() 

        tk.Label(popup, text="Enter Administrator Password:", fg="#00ff00", bg="#1e1e1e", font=("Segoe UI", 10, "bold")).pack(pady=15)
        pwd_entry = tk.Entry(popup, show="*", font=("Segoe UI", 12), width=25)
        pwd_entry.pack(pady=5)
        pwd_entry.focus_set() 

        def verify():
            if pwd_entry.get() == "admin": 
                messagebox.showinfo("Access Granted", "Authorization Successful.")
                popup.destroy()
                messagebox.showinfo("Security Restriction", "Direct password extraction is restricted by Windows OS Policies.")
            else:
                self.failed_attempts += 1
                
                if self.failed_attempts >= 5:
                    self.lockout_time = time.time() + 3600 
                    messagebox.showerror("System Locked", "Maximum 5 attempts reached.\nSystem locked for 1 hour.")
                    popup.destroy()
                else:
                    remaining = 5 - self.failed_attempts
                    messagebox.showerror("Access Denied", f"Invalid Credentials.\nAttempts remaining: {remaining}")
                    pwd_entry.delete(0, tk.END)
        
        popup.bind('<Return>', lambda event: verify())
        
        tk.Button(popup, text="Verify", command=verify, bg="#333", fg="#00ff00", font=("Segoe UI", 10, "bold"), width=10).pack(pady=15)

    def on_closing(self):
        self.root.withdraw() 
        print("GUI Minimized to Background. Monitoring is still active.")

    def read_logs_live(self):
        while not self.log_file.exists(): time.sleep(1)
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f: self.process_line(line)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                self.process_line(line)

    def process_line(self, line):
        try:
            data = json.loads(line)
            event = data.get("event")
            time_str = data.get("timestamp", "")
            serial = data.get("serial", data.get("device_id", data.get("drive", "")))
            raw_name = data.get("device_name", "Unknown")
            mac_addr = data.get("mac_address", serial if "BTHENUM" in str(serial) else "-")
            bt_status = data.get("status", "🟢 Connected")
            
            event_id = f"{event}_{serial}_{time_str}"
            if event_id in self.processed_events: return
            self.processed_events.add(event_id)

            if event in ["BT_CONNECTED", "BT_DISCONNECTED"]:
                friendly_bt = self.get_friendly_name(raw_name)
                duration = data.get("duration_seconds", "-")
                
                if serial not in self.device_names:
                    self.device_names[serial] = friendly_bt
                    self.device_history[serial] = []

                if event == "BT_CONNECTED":
                    status_text = bt_status 
                    self.device_history[serial].append({"insert": time_str, "duration": "-"})
                else:
                    status_text = "-"
                    for h in reversed(self.device_history[serial]):
                        if 'remove' not in h:
                            h['remove'] = time_str
                            h['duration'] = f"{duration}s"
                            break

                existing_bt_items = [self.tree_bluetooth.item(i)['values'][1] for i in self.tree_bluetooth.get_children()]
                if friendly_bt not in existing_bt_items:
                    self.root.after(0, lambda: self.tree_bluetooth.insert("", 0, values=(time_str, friendly_bt, mac_addr, status_text)))
                else:
                    for item in self.tree_bluetooth.get_children():
                        if friendly_bt == self.tree_bluetooth.item(item)['values'][1]:
                            self.root.after(0, lambda i=item: self.tree_bluetooth.item(i, values=(time_str, friendly_bt, mac_addr, status_text)))
                
                existing_live = [self.tree_live.item(i)['values'][0] for i in self.tree_live.get_children()]
                live_status = "Active" if "Connected" in status_text else "Paired"
                if friendly_bt not in existing_live:
                    self.root.after(0, lambda: self.tree_live.insert("", 0, values=(friendly_bt, live_status, "View Details")))
                else:
                    for item in self.tree_live.get_children():
                        if friendly_bt == self.tree_live.item(item)['values'][0]:
                            self.root.after(0, lambda i=item: self.tree_live.item(i, values=(friendly_bt, live_status, "View Details")))

            block_list = ["amd", "nvidia", "realtek", "intel", "audio", "system", "bios", "controller", "direct memory", "provisioning", "pci", "hub", "enumerator", "root", "host", "xbox", "armoury", "integrated", "internal", "camera", "video"]
            if any(x in raw_name.lower() for x in block_list): return

            if event in ["PORT_CONNECTED", "PORT_DISCONNECTED"]:
                friendly_name = self.get_friendly_name(raw_name)
                if friendly_name == "Ignore": return
                
                duration = data.get("duration_seconds", "-")
                
                if serial not in self.device_names:
                    self.device_names[serial] = friendly_name
                    self.device_history[serial] = []

                existing_items = [self.tree_live.item(i)['values'][0] for i in self.tree_live.get_children()]
                
                if event == "PORT_CONNECTED":
                    if friendly_name not in existing_items:
                        self.root.after(0, lambda: self.tree_live.insert("", 0, values=(friendly_name, "Active", "View Details")))
                    else:
                        for item in self.tree_live.get_children():
                            if friendly_name == self.tree_live.item(item)['values'][0]:
                                self.root.after(0, lambda i=item: self.tree_live.item(i, values=(friendly_name, "Active", "View Details")))
                    
                    self.device_history[serial].append({"insert": time_str, "duration": "-"})
                    
                    if "📱" in friendly_name or "Phone" in raw_name:
                        battery = self.get_phone_battery()
                        self.root.after(0, lambda: self.tree_phone.insert("", 0, values=(time_str, friendly_name, battery, "Connected")))

                elif event == "PORT_DISCONNECTED":
                    for item in self.tree_live.get_children():
                        if friendly_name == self.tree_live.item(item)['values'][0]:
                            self.root.after(0, lambda i=item: self.tree_live.item(i, values=(friendly_name, "Offline", "View Details")))
                    
                    if serial in self.device_history:
                        for h in reversed(self.device_history[serial]):
                            if 'remove' not in h:
                                h['remove'] = time_str
                                h['duration'] = f"{duration}s"
                                break

            elif event == "USB_INSERTED":
                drive = data.get("drive", "") 
                hierarchy = data.get("hierarchy_snapshot", [])
                self.storage_files[drive] = hierarchy 
                friendly_name = f"💾 Drive ({drive})"
                
                if serial not in self.device_names:
                    self.device_names[serial] = friendly_name
                    self.device_history[serial] = []

                self.device_history[serial].append({"insert": time_str, "duration": "-"})
                
                existing_items = [self.tree_live.item(i)['values'][0] for i in self.tree_live.get_children()]
                if friendly_name not in existing_items:
                    self.root.after(0, lambda: self.tree_live.insert("", 0, values=(friendly_name, "Active", "View Details")))
                else:
                    for item in self.tree_live.get_children():
                        if friendly_name == self.tree_live.item(item)['values'][0]:
                            self.root.after(0, lambda i=item: self.tree_live.item(i, values=(friendly_name, "Active", "View Details")))

                threats = sum(1 for f in hierarchy if f.get("status") == "SUSPICIOUS")
                status = f"🚨 {threats} THREATS" if threats > 0 else "✅ SECURE"
                tag = "red" if threats > 0 else "green"

                self.root.after(0, lambda: self.tree_storage.insert("", 0, values=(time_str, friendly_name, len(hierarchy), threats, status), tags=(tag,)))
                self.tree_storage.tag_configure("green", foreground="#00ff00")
                self.tree_storage.tag_configure("red", foreground="#ff0000")

            elif event == "USB_REMOVED":
                drive = data.get("drive", "")
                duration = data.get("duration_seconds", "-")
                friendly_name = f"💾 Drive ({drive})"
                
                for item in self.tree_live.get_children():
                    if friendly_name == self.tree_live.item(item)['values'][0]:
                        self.root.after(0, lambda i=item: self.tree_live.item(i, values=(friendly_name, "Offline", "View Details")))
                
                if serial in self.device_history:
                    for h in reversed(self.device_history[serial]):
                        if 'remove' not in h:
                            h['remove'] = time_str
                            h['duration'] = f"{duration}s"
                            break

        except Exception:
            pass

if __name__ == "__main__":
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 0)
    else:
        # --- TASKBAR ICON FIX ---
        try:
            myappid = 'usbguard.forensics.tool.1'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass
        # ------------------------
        
        root = tk.Tk()
        app = USBGuardApp(root)
        root.mainloop()