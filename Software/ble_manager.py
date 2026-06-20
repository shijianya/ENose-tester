# ble_manager.py

import asyncio
import threading
from bleak import BleakScanner, BleakClient
from tkinter import messagebox

ble_client = None
ble_loop = asyncio.new_event_loop()

# 启动 BLE 后台事件循环
ble_thread = threading.Thread(target=ble_loop.run_forever, daemon=True)
ble_thread.start()

# 工具：将协程提交到 ble_loop 中执行
def run_in_ble_loop(coro):
    return asyncio.run_coroutine_threadsafe(coro, ble_loop)

# 扫描 BLE 设备，并通过回调函数返回设备名称和地址列表
def scan_ble_devices(callback):
    async def scan():
        try:
            devices = await BleakScanner.discover()
            result = [(d.name or "未知设备", d.address) for d in devices if d.name]
            callback(result)
        except Exception as e:
            messagebox.showerror("扫描失败", str(e))

    run_in_ble_loop(scan())

# 连接 BLE 设备
def connect_ble_device(address, on_connected_callback=None):
    global ble_client

    async def connect():
        global ble_client
        try:
            ble_client = BleakClient(address)
            await ble_client.connect()
            if ble_client.is_connected:
                messagebox.showinfo("连接成功", f"已连接到 {address}")
                if on_connected_callback:
                    on_connected_callback()
        except Exception as e:
            messagebox.showerror("连接失败", str(e))

    run_in_ble_loop(connect())

# 启动 notify（传入 UUID 和数据处理函数）
def start_notify(characteristic_uuid, handle_ble_data):
    global ble_client

    if ble_client and ble_client.is_connected:
        run_in_ble_loop(
            ble_client.start_notify(characteristic_uuid, handle_ble_data)
        )
    else:
        messagebox.showerror("错误", "蓝牙未连接")

# 断开连接
def disconnect_ble_device():
    global ble_client

    if not ble_client or not ble_client.is_connected:
        messagebox.showinfo("信息", "设备未连接")
        return

    async def disconnect():
        global ble_client
        try:
            await ble_client.disconnect()
            messagebox.showinfo("已断开", "蓝牙连接已断开")
        except Exception as e:
            messagebox.showerror("断开失败", str(e))
        finally:
            ble_client = None

    run_in_ble_loop(disconnect())

# 暴露 ble_client 供外部判断连接状态
def get_ble_client():
    return ble_client
