import time
from bme690 import BME690

sensor = BME690()

try:
    while True:
        if sensor.get_sensor_data():
            print(f"Temp:     {sensor.data.temperature:.2f} °C")
            print(f"Humidity: {sensor.data.humidity:.2f} %")
            print(f"Pressure: {sensor.data.pressure:.2f} hPa")
            print(f"Gas:      {sensor.data.gas_resistance:.0f} ohms")
            print("-" * 35)
        time.sleep(3)

except KeyboardInterrupt:
    print("\nMonitoring Stopped, oh nooooo :( ")
