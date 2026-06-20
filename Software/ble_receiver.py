# ble_receiver.py

from ble_manager import start_notify
from tkinter import messagebox

# 替换为你的 BLE 设备传输数据的特征 UUID
CHAR_UUID = "0000abcd-0000-1000-8000-00805f9b34fb"

running = False  # 和主程序同步

# ble_receiver.py 文件中加在顶部
_root = None  # 存储主程序传进来的 root

def set_root(r):
    global _root
    _root = r
        
def start_ble_read(update_plot_func):
    """
    启动 BLE 数据接收
    :param update_plot_func: 用于处理数据的回调函数，比如 update_plot
    """
    def handle_ble_data(sender, data):
        if not running:
            return
        try:
            text = data.decode(errors="ignore").strip()
            parts = text.split(',')
            if len(parts) == 11:                
                values = list(map(float, parts))
                #print(values)
                # ✅ 改成在主线程中调用
                if _root:
                    _root.after(0, update_plot_func, values)
                else:
                    print("Warning: root is not set, cannot update GUI safely.")
            else:
                print("not 11")
        except Exception as e:
            print("蓝牙数据处理错误：", e)

    try:
        start_notify(CHAR_UUID, handle_ble_data)
    except Exception as e:
        messagebox.showerror("启动监听失败", str(e))

def set_running(state: bool):
    global running
    running = state
