#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include <AHT20.h>
#include <Adafruit_BMP280.h>
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
#include <BLE2902.h>


// 创建传感器对象（使用默认 I2C 地址 0x29）
// Adafruit_TCS34725 tcs = Adafruit_TCS34725(TCS34725_INTEGRATIONTIME_499MS, TCS34725_GAIN_4X);颜色传感器已删

bool deviceConnected = false;
bool oldDeviceConnected = false;

//蓝牙
// BLE 对象
BLEServer* pServer = NULL;
BLECharacteristic* pCharacteristic = NULL;
// 1. 添加回调类
class MyServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer* pServer) {
    Serial.println("📡 Client connected.");
  }

  void onDisconnect(BLEServer* pServer) {
    Serial.println("❌ Client disconnected. Restarting advertising...");
    BLEDevice::getAdvertising()->start();  // 断开后重新广播
  }
};

// define led according to pin diagramint
int led = 3;

// I2C 地址
#define AHT20_ADDRESS 0x38
#define BMP280_ADDRESS 0x77

// 创建两个ADS1115对象
Adafruit_ADS1115 ads1; // 默认构造
Adafruit_ADS1115 ads2; // 默认构造

// 实例化传感器对象
AHT20 aht20;
Adafruit_BMP280 bmp;
Adafruit_ADS1115 ads;

void setup() {
  Serial.begin(115200);
  pinMode(led, OUTPUT);//小绿灯
  
  Wire.begin();  // 初始化I2C


  
  // 初始化AHT20
  if (!aht20.begin()) {
    Serial.println("无法找到AHT20传感器，请检查连接！");
    while (1);
  }

  // 初始化BMP280
  if (!bmp.begin(BMP280_ADDRESS)) {  // 如果BMP280的地址是0x76
    Serial.println("无法找到BMP280传感器，请检查连接！");
    while (1);
  }

  // 初始化 ADS1115  
  if (!ads1.begin(0x48)) {
    Serial.println("ADS1115(0x48) 初始化失败！");
    while (1);
  }
  Serial.println("ADS1115(0x48) 初始化成功！");

 // 初始化 ADS1115_1 另一个  
  if (!ads2.begin(0x49)) {
    Serial.println("ADS1115(0x49) 初始化失败！");
    while (1);
  }
  Serial.println("ADS1115(0x49) 初始化成功！"); 

 // 设置增益（根据需要调整，±6.144V, ±4.096V, ±2.048V, ±1.024V, ±0.512V, ±0.256V）
  ads1.setGain(GAIN_ONE); //  GAIN_ONE（±4.096V）
  ads2.setGain(GAIN_ONE); //  GAIN_ONE（±4.096V）

  // 初始化 BLE
  BLEDevice::init("ESP32-C3-BLE");
  pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());  // <- 加上这行

  // BLE 连接状态回调
  class MyServerCallbacks : public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
      deviceConnected = true;
  }

    void onDisconnect(BLEServer* pServer) {
      deviceConnected = false;
  }
};

  BLEService *pService = pServer->createService("12345678-1234-5678-1234-56789abcdef0");
  pCharacteristic = pService->createCharacteristic(
                      "0000abcd-0000-1000-8000-00805f9b34fb",
                      BLECharacteristic::PROPERTY_READ |
                      BLECharacteristic::PROPERTY_NOTIFY
                    );
  pCharacteristic->addDescriptor(new BLE2902());                  

  pCharacteristic->setValue("Hello from ESP32-C3!");
  pService->start();

  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID("12345678-1234-5678-1234-56789abcdef0");
  pAdvertising->start();
  Serial.println("BLE Advertising started...");  
}

unsigned long lastTime = 0;
const unsigned long interval = 500; // 500 ms = 0.5秒

void loop() {
  unsigned long now = millis();
  if (now - lastTime >= interval) {
    lastTime = now;

    // ========== 采样部分 ==========
    int16_t adc0_0 = ads1.readADC_SingleEnded(0);
    int16_t adc0_1 = ads1.readADC_SingleEnded(1);
    int16_t adc0_2 = ads1.readADC_SingleEnded(2);
    int16_t adc0_3 = ads1.readADC_SingleEnded(3);
    int16_t adc1_0 = ads2.readADC_SingleEnded(0);
    int16_t adc1_1 = ads2.readADC_SingleEnded(1);
    int16_t adc1_2 = ads2.readADC_SingleEnded(2);
    int16_t adc1_3 = ads2.readADC_SingleEnded(3);

    float voltage0 = adc0_0 * 0.125 / 1000.0;
    float voltage1 = adc0_1 * 0.125 / 1000.0;
    float voltage2 = adc0_2 * 0.125 / 1000.0;
    float voltage3 = adc0_3 * 0.125 / 1000.0;
    float voltage4 = adc1_0 * 0.125 / 1000.0;
    float voltage5 = adc1_1 * 0.125 / 1000.0;
    float voltage6 = adc1_2 * 0.125 / 1000.0;
    float voltage7 = adc1_3 * 0.125 / 1000.0;

    float humidity = aht20.getHumidity();
    float temperature = aht20.getTemperature();
    float pressure = bmp.readPressure() / 1000.0F;

    Serial.printf("%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.2f,%.2f,%.2f\n",
      voltage0,voltage1,voltage2,voltage3,voltage4,voltage5,voltage6,voltage7,
      humidity,temperature,pressure);

    // BLE 发送
    if (pCharacteristic) {
      String bleData = String(voltage0, 4) + "," + String(voltage1, 4) + "," + String(voltage2, 4) + "," +
                       String(voltage3, 4) + "," + String(voltage4, 4) + "," + String(voltage5, 4) + "," +
                       String(voltage6, 4) + "," + String(voltage7, 4) + "," +
                       String(humidity) + "," + String(temperature) + "," + String(pressure);
      pCharacteristic->setValue(bleData.c_str());
      pCharacteristic->notify();
    }

    // LED闪烁提示
    digitalWrite(led, !digitalRead(led));
  }

  // BLE 连接状态监测
  if (!deviceConnected && oldDeviceConnected) {
    delay(500);
    pServer->startAdvertising();
    Serial.println("Client disconnected, restarting advertising...");
    oldDeviceConnected = deviceConnected;
  }

  if (deviceConnected && !oldDeviceConnected) {
    Serial.println("Client reconnected");
    oldDeviceConnected = deviceConnected;
  }
}

