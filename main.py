import time
from mqtt import MQTTClient
from machine import Pin, ADC, PWM
import keys
import wifiConnection

# ----- CONFIGURATION -----
SENSOR_INTERVAL = 12000  # Each 12 seconds pico will send data to adafruit
last_sensor_sent_ticks = 0 # To track when the last sensor data was sent
auto_mode = True # Default mode at startup
manual_led_state = False  # Used only in manual mode
led_pwm = PWM(Pin(0)) # External LED for light
led_pwm.freq(1000)  # PWM frequency = 1kHz
onboard_led = Pin("LED", Pin.OUT)  # Internal onboard LED on Pico
ldr = ADC(28) # Photoresistor pin
pot = ADC(27) # Potentiometer pin
button1 = Pin(16, Pin.IN, Pin.PULL_UP) # LED button for manual mode
button2 = Pin(17, Pin.IN, Pin.PULL_UP) # Button to switch modes Auto/Manual 
last_button1 = False # Default state of LED button
last_button2 = True  # Default state of mode button
remote_brightness = 65535  # Default brightness from Adafruit (max)
use_remote_brightness = True  # True means use Adafruit brightness, False means physical pot controls
last_pot_value = None # Last pot value
POT_TOLERANCE = 500  # Adjust sensitivity to avoid jitter
last_remote_reset_state = None # last remote mode state (Auto/Manual)
led_is_on = False  # Track real-time LED on/off state

# ----- FUNCTIONS -----
def set_led_brightness(level):
    """Set LED brightness (0-65535)"""
    global led_is_on
    led_pwm.duty_u16(level)
    led_is_on = level > 0


def update_led():
    """Update LED state/brightness immediately based on mode and inputs"""
    global last_pot_value, use_remote_brightness, remote_brightness
    local_brightness = pot.read_u16()

    # Check if pot value changed significantly
    pot_changed = False
    if last_pot_value is None or abs(local_brightness - last_pot_value) > POT_TOLERANCE:
        pot_changed = True
        last_pot_value = local_brightness

    if pot_changed:
        # Pot moved - switch control to physical pot
        use_remote_brightness = False
        remote_brightness = local_brightness  # Sync remote_brightness internally for LED
    brightness = remote_brightness if use_remote_brightness else local_brightness

    if auto_mode:
        ldr_val = ldr.read_u16()
        if ldr_val < 20000:
            set_led_brightness(brightness)
        else:
            set_led_brightness(0)
    else:
        if manual_led_state:
            set_led_brightness(brightness)
        else:
            set_led_brightness(0)


def update_onboard_led():
    """Turn ON internal Pico LED if auto mode, OFF if manual"""
    onboard_led.value(1 if auto_mode else 0)


def check_mode_switch():
    """Handles mode button presses and toggling modes"""
    global auto_mode, manual_led_state, last_button1, last_button2

    current_btn1 = button1.value()
    current_btn2 = button2.value()

    # Button 1: Manual toggle, only in manual mode
    if current_btn1 and not last_button1 and not auto_mode:
        manual_led_state = not manual_led_state
        print("Manual LED toggled:", "ON" if manual_led_state else "OFF")

    # Button 2: Toggle mode (auto/manual)
    if current_btn2 and not last_button2:
        auto_mode = not auto_mode
        mode = "AUTO" if auto_mode else "MANUAL"
        print("Mode changed to:", mode)
        if auto_mode:
            manual_led_state = False  # reset manual LED state on auto mode
        update_onboard_led()  # Update internal LED on mode change

    last_button1 = current_btn1
    last_button2 = current_btn2


def send_sensor_data():
    """Publish sensor data every SENSOR_INTERVAL milliseconds"""
    global last_sensor_sent_ticks, use_remote_brightness, led_is_on

    if (time.ticks_ms() - last_sensor_sent_ticks) < SENSOR_INTERVAL:
        return

    light_val = ldr.read_u16()
    pot_val = pot.read_u16()

    # Send brightness percentage based on remote_brightness (the one controlling LED)
    brightness_percent = int((remote_brightness - 384) * 100 / (65535 - 384))
    brightness_percent = max(1, min(100, brightness_percent))
    print(f"LDR: {light_val}, BRIGHTNESS: {brightness_percent}%, Mode: {'AUTO' if auto_mode else 'MANUAL'}")

    try: # Always send LDR data
        client.publish(topic=keys.AIO_LDR_FEED, msg=str(light_val))
    except Exception as e:
        print("FAILED to publish LDR:", e)

    try: # Send brightness only if physical pot took control
        if not use_remote_brightness:
            client.publish(topic=keys.AIO_POT_FEED, msg=str(brightness_percent))

        # Publish LED status, manual toggle, and mode
        client.publish(topic=keys.AIO_LED_STATUS, msg="1" if led_is_on else "0")
        client.publish(topic=keys.AIO_BUTTON_FEED, msg="ON" if manual_led_state else "OFF")
        client.publish(topic=keys.AIO_RESET_BUTTON_FEED, msg="1" if auto_mode else "0")

        print("Published sensor data.")
    except Exception as e:
        print("FAILED to publish other sensor data:", e)

    last_sensor_sent_ticks = time.ticks_ms()


def sub_cb(topic, msg):
    """ Callback function"""
    global auto_mode, manual_led_state, last_remote_reset_state, remote_brightness, use_remote_brightness

    if topic == keys.AIO_BUTTON_FEED.encode():
        print((topic, msg))
        if msg == b'ON' and not auto_mode:
            manual_led_state = True
            print("Manual LED set to: ON (via Adafruit)")
        elif msg == b'OFF' and not auto_mode:
            manual_led_state = False
            print("Manual LED set to: OFF (via Adafruit)")

    elif topic == keys.AIO_POT_FEED.encode():
        print((topic, msg))
        try:
            percent = int(msg)
            percent = max(0, min(100, percent))
            # Convert percent to PWM range 384-65535
            remote_brightness = int((percent / 100) * (65535 - 384) + 384)
            use_remote_brightness = True  # Adafruit now controls brightness
            print(f"Remote brightness set to {percent}% → PWM: {remote_brightness}")
        except ValueError:
            print("Invalid brightness value from Adafruit")

    elif topic == keys.AIO_RESET_BUTTON_FEED.encode():
        print((topic, msg))
        if msg == b'1':
            auto_mode = True
            manual_led_state = False
            print("Mode set to: AUTO (via Adafruit)\n")
        elif msg == b'0':
            auto_mode = False
            print("Mode set to: MANUAL (via Adafruit)\n")
        last_remote_reset_state = msg

# ----- CONNECTION SETUP -----

try:
    ip = wifiConnection.connect()
except KeyboardInterrupt:
    print("Keyboard interrupt")

client = MQTTClient(keys.AIO_CLIENT_ID, keys.AIO_SERVER, keys.AIO_PORT, keys.AIO_USER, keys.AIO_KEY)
client.set_callback(sub_cb)
client.connect()
# Subscribe to all relevant feeds
client.subscribe(keys.AIO_BUTTON_FEED)
client.subscribe(keys.AIO_RESET_BUTTON_FEED)
client.subscribe(keys.AIO_POT_FEED)
print("\nConnected and subscribed to Adafruit IO feeds.\n")

update_onboard_led() # Set initial onboard LED state

# ----- MAIN LOOP -----

try:
    while True:
        client.check_msg()       # Handle incoming MQTT messages (non-blocking)
        check_mode_switch()      # Check buttons for mode or manual toggles
        update_onboard_led()     # Keep onboard LED synced with mode
        update_led()             # Update LED brightness/state immediately
        send_sensor_data()       # Publish sensor data every SENSOR_INTERVAL
        time.sleep_ms(50)        # Small delay to reduce CPU load, smooth updates
finally:
    client.disconnect()
    wifiConnection.disconnect()
    print("Disconnected from Adafruit IO.")