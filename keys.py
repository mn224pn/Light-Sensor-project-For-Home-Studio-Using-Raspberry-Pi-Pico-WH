import ubinascii              # Conversions between binary data and various encodings
import machine                # To Generate a unique id from processor

# Wireless network
WIFI_SSID =  "YOUR_WIFI_NAME" # put your wifi name
WIFI_PASS = "TOUR_WIFI_PASSWORD" # No this is not our regular password. :)

# Adafruit IO (AIO) configuration
AIO_SERVER = "io.adafruit.com"
AIO_PORT = 1883
AIO_USER = "YOUR ADAFRUIT USERNAME" # place your your adafruit username here
AIO_KEY = "YOUR ADAFRUIT KEY" # Place your key here
AIO_CLIENT_ID = ubinascii.hexlify(machine.unique_id())  # Can be anything
AIO_LDR_FEED = "MQTT_by_Key" # place your key for LDR feed
AIO_POT_FEED = "MQTT_by_Key" # place your key for Potentiometer feed
AIO_BUTTON_FEED = "MQTT_by_Key" # place your key for button feed
AIO_RESET_BUTTON_FEED = "MQTT_by_Key" # place your key for reset/switch button feed
AIO_LED_STATUS = "MQTT_by_Key" # place your key for LED status feed
