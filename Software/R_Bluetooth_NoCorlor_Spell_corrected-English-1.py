import threading
import serial
import serial.tools.list_ports
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation
import matplotlib
from datetime import datetime
from matplotlib.ticker import FormatStrFormatter
import matplotlib.cm as cm
import numpy as np
import csv
from ble_manager import connect_ble_device, disconnect_ble_device, scan_ble_devices, get_ble_client
from ble_receiver import start_ble_read, set_running

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial']
plt.rcParams['font.size'] = 15  # 基础字体大小
matplotlib.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

# 全局变量
ser = None  # 串口对象
running = False  # 数据采集状态
x_data = []  # x数据列表
channel_count = 8
voltage_lists = [[] for _ in range(channel_count)]
index = 0  # 数据点计数
all_data = []  # 用于保存所有采集的数据
max_len = 600
current_rgb = [0, 0, 0,0]  # 初始化 RGB 值

#################参考电阻####################
import json
import os
import locale

def open_resistor_dialog():
    resistor_window = tk.Toplevel(root)
    resistor_window.title("Set reference resistance")

    entry_vars = {}

    # 遍历 resistor_values 字典
    for i, (key, value) in enumerate(resistor_values.items()):
        # 标签
        tk.Label(resistor_window, text=key, font=("Arial", 15)).grid(row=i, column=0, padx=10, pady=5)

        # 输入框
        var = tk.StringVar(value=format_with_separator(value))
        def make_trace_callback(var):
            def callback(*args):  # args 是 trace_add 自动传入的三个参数
                update_display(var)
            return callback
        
        var.trace_add("write", make_trace_callback(var))
        entry = tk.Entry(resistor_window, textvariable=var, font=("Arial", 15), width=15)
        entry.grid(row=i, column=1, padx=10, pady=5)
        entry_vars[key] = var

        # 设置按钮
        def make_set_function(k, v):
            return lambda: update_resistor_value(k, v)
        tk.Button(resistor_window, text="Input", font=("Arial", 15), command=make_set_function(key, var)).grid(row=i, column=2, padx=5)

def format_with_separator(value):
    """Format a number as a string with a mille separator"""
    return locale.format_string("%.0f", value, grouping=True)


def update_display(var):
    """Update display format"""
    value = var.get()
    try:
        num = float(value.replace(',', ''))  # 先去掉旧的千分位
        formatted_value = format_with_separator(num)
        var.set(formatted_value)
    except ValueError:
        pass  # 忽略无效输入

# 设置 locale 以支持千分位分隔符
locale.setlocale(locale.LC_ALL, '')

# 配置文件路径
CONFIG_FILE = "config.json"

# 从文件加载电阻值配置（如果存在）
def load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Loading configuration failed: {e}")
    # 返回默认值
    return {
        "R1": 1000000,
        "R2": 1000000,
        "R3": 1000000,
        "R4": 1000000,
        "R5": 1000000,
        "R6": 1000000,
        "R7": 1000000
    }

# 保存电阻值配置到文件
def save_config():
    """Save resistance value to json file"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(resistor_values, f, indent=4)

# 加载初始配置
resistor_values = load_config()

def update_resistor_value(key, var):
    try:
        new_value = float(var.get().replace(',', ''))
        resistor_values[key] = new_value
        save_config()  # 直接调用保存
        print(f"{key} Update to {new_value}")
    except ValueError:
        messagebox.showerror("Error", f"{key} is invalid. Please enter a number.")

def toggle():
    global running, ser, all_data, x_data, channel_count
    if running:
        stop_acquisition()
        start_btn.config(text="Start")           
    else:
        all_data.clear()
        channel_count = int(channel_cb.get()) + 1
        source = source_var.get()
        running = True
        start_btn.config(text="Stop")
        init_plot()
        
        if source == "serial":
            port = port_cb.get()
            baud = baud_cb.get()
            try:
                ser = serial.Serial(port, int(baud), timeout=1)
                thread = threading.Thread(target=read_serial, daemon=True)
                thread.start()
            except Exception as e:
                messagebox.showerror("Error", str(e))
                running = False
                start_btn.config(text="Start")

        elif source == "ble":
            try:
                set_running(True)  # 告诉 ble_receiver 可以接收了              
                start_ble_read(update_plot_safe)  # 你在 ble_receiver 里写的函数
            except Exception as e:
                messagebox.showerror("BLE Error", str(e))
                running = False
                start_btn.config(text="Start")

def read_serial():    
    while running and ser:
        try:
            data = ser.readline().decode().strip()
            parts = data.split(',')            
            if len(parts) == 11:
                values = list(map(float, parts))                
                update_plot_safe(values)                
                                                  
        except Exception as e:
            print("Read Error：", e)

#计算电阻
def calculate_resistance(v0, v1, channel):
    resistor_key = f"R{channel}"  # 如 channel=1 → "R1"
    resistance = (v0 - v1) / (v1 / resistor_values[resistor_key]) if v1 > 0 else 0
    return resistance
'''
def standard_color(r,g,b):
    d = max(r,g,b)
    return int(r/d*255), int(g/d*255), int(b/d*255)
'''
# 更新图形（每次更新数据点）
def update_plot(values):
    global running, index, resistor_values, all_data,x_data, lines, voltage_lists, axes
    if running:
        try:            
            # 依次提取电压值
            voltage0 = round(values[0], 3)
            voltage_list = [round(v, 3) for v in values[1:channel_count]]  # voltage1 到 channel_count            
            humidity, temperature, pressure = values[8], values[9], values[10]

            # 从 data_list 中提取 r, g, b（最后三项）
            #r,g,b,c = values[11], values[12], values[13], values[14]
            #r = int(r)
            #g = int(g)
            #b = int(b)
            #c = int(c)
            #current_rgb[0], current_rgb[1], current_rgb[2], current_rgb[3] = r, g, b, c  

            # 更新图形数据
            x_data.append(index / 2)
                        
            for i in range(channel_count):
                voltage_lists[i].append(round(values[i],3))
            
            # 保持数据长度
            if len(voltage_lists[i]) > max_len:
                x_data = x_data[-max_len:]
                for i in range(channel_count):
                    voltage_lists[i] = voltage_lists[i][-max_len:]
            
            # 计算每个电阻值（单位 kΩ）
            resistances = []
            for i, v in enumerate(voltage_list):
                res = calculate_resistance(voltage0, v, i + 1)
                resistances.append(round(res / 1000, 3))  # 转千欧

            # 更新实时数据显示
            pressure_label.config(text=f"Pressure: {pressure:.1f}kPa")
            humidity_label.config(text=f"Humidity: {humidity:.1f}%")                
            temperature_label.config(text=f"Temperature: {temperature:.1f}°C")
            Voltage_C.config(text=f"Voltage0: {voltage0:.3f}V")
            Time_value.config(text=f"Time: {index/2:.1f}S")
        
            
            #r_cal, g_cal, b_cal = standard_color(r, g, b)
                
            #tk_color = f"#{r_cal:02x}{g_cal:02x}{b_cal:02x}"

             #更新色块
            #color_canvas.itemconfig(color_rect, fill=tk_color)
       
            # 更新 line 数据
            for i in range(channel_count):
                lines[i].set_data(x_data, voltage_lists[i])
                axes[i].relim()
                axes[i].autoscale_view()


                # 获取数据的最小和最大值
                data_min = min(voltage_lists[i])
                data_max = max(voltage_lists[i])
    
                # 计算中间值
                mid_value = (data_min + data_max) / 2
                
                # 设置 y 轴刻度为 [最小值, 中间值, 最大值]
                axes[i].set_yticks([data_min, mid_value, data_max])
                
            canvas.draw_idle()
            
            # 记录数据
            all_data.append([voltage0] + resistances + [humidity, temperature, pressure])
            index += 1
                
        except Exception as e:
            print(f"解析或绘图时出错: {e}")



def update_plot_safe(values):
    root.after(0, update_plot, values)

# 保存数据
def save_data():
    # 获取当前日期时间
    current_time = datetime.now().strftime("%Y%m%d%H%M%S")    
    
    # 创建文件名
    file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
    
    if file_path:
        with open(file_path, 'w', newline='',encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            # 日期
            f.write(f"Date: {current_time}\n")
            f.write("Resistance Unit: KΩ \n")
            for key, value in resistor_values.items():
                writer.writerow([key, value])
            #f.write("\n")  # 空行
            
            # 数据列标题
            f.write("voltage0,")
            for i in range(channel_count-1):
                f.write(f"Resistance{i+1},")               
            f.write("humidity,temperature,pressure\n")
            
            # 数据写入
            for i in range(len(all_data)):
                for j in range(len(all_data[i])):
                    f.write(f"{all_data[i][j]}")
                    if j < len(all_data[i])-1:
                            f.write(",")   
                f.write("\n")

        messagebox.showinfo("Note", f"data saved {file_path}")

# 停止采集
def stop_acquisition():
    global running, ser, x_data, index,voltage_lists
    running = False
    if ser:
        ser.close()
        ser = None
            
    set_running(False)  # 停止 BLE 接收（如果启用了）
    # 清空数据和重置index
    x_data.clear()
    for lst in voltage_lists:
            lst.clear()    
    
    index = 0  # 重置 index 为 0
    
    #messagebox.showinfo("提示", "数据采集已停止！")

#结束按钮程序
def end_pgm():
    stop_acquisition()
    save_data()

#######################################################################################################

######################################################################################################################

# 退出程序
def exit_program():
    stop_acquisition()
    root.destroy()

# 刷新串口列表
def refresh_ports():
    ports = serial.tools.list_ports.comports()
    port_cb['values'] = [port.device for port in ports]
    
# 回调函数：扫描完成后填入下拉框
def update_ble_device_list(device_list):
    ble_device_cb['values'] = [f"{name} ({addr})" for name, addr in device_list]
    if device_list:
        ble_device_cb.current(0)

# 点击连接按钮后触发：取出地址并连接
def connect_selected_ble():
    selection = ble_device_cb.get()
    if not selection or '(' not in selection:
        messagebox.showerror("Error", "请选择有效的 BLE 设备")
        return
    address = selection.split('(')[-1].strip(')')
    connect_ble_device(address)

# GUI 初始化 ##################################################################################################################
root = tk.Tk()

from ble_receiver import set_root
set_root(root)  # ✅ 传入主线程中的 root 对象

root.title("USST E-nose tester")
root.geometry("1000x720")

# 初始化配置部分
config_frame = ttk.LabelFrame(root, text="Set Up")
config_frame.pack(fill="x", padx=10, pady=5)

serial_frame = ttk.Frame(config_frame)
ble_frame = ttk.Frame(config_frame)

# 新增一个 Frame 用于 RGB 色块显示
#color_frame = ttk.LabelFrame(root, text="当前颜色")
#color_frame.pack(side="left", padx=10, pady=10)

# 创建 canvas 色块区域
#color_canvas = tk.Canvas(color_frame, width=60, height=1000, bg="white", highlightthickness=1, highlightbackground="black")
#color_canvas.pack(padx=5, pady=5)

# 创建矩形色块（初始为黑色）
#color_rect = color_canvas.create_rectangle(0, 0, 60, 980, fill="#000000")

# ===== 选择数据源类型 =====
ttk.Label(config_frame, text="Data source:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
source_var = tk.StringVar(value="serial")  # 默认使用串口
source_cb = ttk.Combobox(config_frame, textvariable=source_var, values=["serial", "ble"], width=10, state="readonly")
source_cb.grid(row=0, column=1, padx=5, sticky="w")
source_cb.bind("<<ComboboxSelected>>", lambda e: update_connection_ui())

# ===== 串口设置 =====
# 串口设置
ttk.Label(serial_frame, text="Serial port:").grid(row=0, column=0, padx=5, pady=5)
port_var = tk.StringVar(value="COM3")
port_cb = ttk.Combobox(serial_frame, textvariable=port_var, width=10)
port_cb.grid(row=0, column=1, sticky="w")

ttk.Label(serial_frame, text="Baud rate:").grid(row=0, column=2, padx=5, pady=5)
baud_var = tk.StringVar(value="115200")
baud_cb = ttk.Combobox(serial_frame, textvariable=baud_var, values=["9600", "19200", "38400", "57600", "115200"], width=10)
baud_cb.grid(row=0, column=3, sticky="w")

# 初始添加到设置区
serial_frame.grid(row=1, column=0, columnspan=4, sticky="w", padx=5)


# ===== 蓝牙设置 =====
# 蓝牙设置
ble_device_var = tk.StringVar()
ble_device_cb = ttk.Combobox(ble_frame, textvariable=ble_device_var, width=30, state="readonly")
ble_device_cb.grid(row=0, column=0, padx=5, pady=5, sticky="w")

scan_button = ttk.Button(ble_frame, text="Scanning")
scan_button.grid(row=0, column=1, padx=5, pady=5, sticky="w")
scan_button.config(command=lambda: scan_ble_devices(update_ble_device_list))

connect_button = ttk.Button(ble_frame, text="Connect")
connect_button.grid(row=0, column=2, padx=5, pady=5, sticky="w")
connect_button.config(command=connect_selected_ble)

disconnect_button = ttk.Button(ble_frame, text="Disconnect")
disconnect_button.grid(row=0, column=3, padx=5, pady=5, sticky="w")
disconnect_button.config(command=disconnect_ble_device)

# 默认不显示
ble_frame.grid_forget()

def on_source_change(event=None):
    source = source_var.get()
    if source == "serial":
        serial_frame.grid(row=1, column=0, columnspan=4, sticky="w", padx=5)
        ble_frame.grid_forget()
    elif source == "ble":
        serial_frame.grid_forget()
        ble_frame.grid(row=1, column=0, columnspan=4, sticky="w", padx=5)


source_cb.bind("<<ComboboxSelected>>", on_source_change)

#通道数
ttk.Label(config_frame, text="Channel number:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
channel_cb = ttk.Combobox(config_frame, width=3, state="readonly", values=[str(i) for i in range(8)])
channel_cb.current(7)
channel_cb.grid(row=0, column=3, sticky="w")

# 按钮部分
ttk.Button(config_frame, text="Set reference resistance", command=open_resistor_dialog).grid(row=0, column=4, padx=5, pady=5, sticky="w")
start_btn = ttk.Button(config_frame, text="Start", command=toggle)
start_btn.grid(row=0, column=5, padx=5, pady=5, sticky="w")
ttk.Button(config_frame, text="Save", command=save_data).grid(row=0, column=6, padx=5, pady=5, sticky="w")

# 实时数据显示
data_frame = ttk.LabelFrame(root, text="Real-time data")
data_frame.pack(fill="x", padx=10, pady=5)

pressure_label = tk.Label(data_frame, text="Pressure: --kPa", font=("Arial", 14))
pressure_label.grid(row=0, column=0, padx=10, pady=10)

humidity_label = tk.Label(data_frame, text="Humidity: --%", font=("Arial", 14))
humidity_label.grid(row=0, column=1, padx=10, pady=10)

temperature_label = tk.Label(data_frame, text="Temperature: --°C", font=("Arial", 14))
temperature_label.grid(row=0, column=2, padx=10, pady=10)

Voltage_C = tk.Label(data_frame, text="Voltage0：--V", font=("Arial", 14))
Voltage_C.grid(row=0, column=5, padx=10, pady=10)

Time_value = tk.Label(data_frame, text="Time：--s", font=("Arial", 14))
Time_value.grid(row=0, column=9, padx=10, pady=10)

#图形区
fig, axes, lines = plt.figure(figsize=(10, 7)), [], []
canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)


# 初始化子图和线
def init_plot():
    global fig, canvas, axes, lines
    cmap = cm.get_cmap('tab10')  # 或 'tab10','viridis', 'plasma', 'rainbow', 'cool', etc.
    fig.clf()
    axes.clear()
    lines.clear()
    labels = [f"V_{i}" for i in range(channel_count)]
    for i in range(channel_count):
        
        # 取颜色：cmap(i / channel_count) 会返回 RGBA 值
        color = cmap(i / channel_count)
        
        ax = fig.add_subplot(channel_count, 1, i + 1)
        ax.set_ylabel(labels[i], rotation=0, labelpad=15, fontsize=15, va='center',color=color)
        ax.grid(True)
        
        # 限制 Y 轴坐标为 3 位小数
        ax.yaxis.set_major_formatter(FormatStrFormatter('%.3f'))
        
        line, = ax.plot([], [],color=color, label=f"V_{i}")        
        axes.append(ax)
        lines.append(line)
    for ax in axes[:-1]:
        ax.label_outer()  # 隐藏非底部子图的 x 轴标签
        
    axes[-1].set_xlabel("Time (s)")
    fig.tight_layout(pad=1.0)
    canvas.draw_idle()
    
init_plot()

# 主循环
root.protocol("WM_DELETE_WINDOW", exit_program)
root.mainloop()
