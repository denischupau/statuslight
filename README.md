# USB StatusLight
USB status light with 10 LEDs, to indicate status on a PC or server by blinking/fading colors.

I wrote it for my own use, and publish it as-is, use at your own risks.

## What is it?

The status light is based on:
- the Digispark Digistump USB board with an ATTiny85 @16.5MHz
- with the bootloader Micronucleus (2KB) to enable flashing the firmware through USB
- 10 APA102 LEDS which are the "DotStar" RGB addressable LEDs
- the firmware written in the Arduino IDE (I know, not ideal, but it's an old project I wanted finished quickly)

The Python software consists in 3 programs:
- sendUSB, which is the basic Digispark software to send commands to the Digistump board (based on the "usbdevice.py" providing the "ArduinoUsbDevice" class)
- StatusLight daemon which connects to the USB Digistump and to an MQTT broker (like Mosquitto) thus enabling to check on the light's state and send commands to it via MQTT,
- StatusLight GUI helper: a TK GUI to easily try and test commands to send to the light via MQTT.

I integrated this to my Home Assistant setup to have some very visible status on the server about things like failed backups, disk problem, etc.

## What it can do

- of the 10 LEDs (you can add or remove some, be careful about the VERY limited RAM), 9 are usable by default (can be disabled),
- by default the 1st LED (LED 0) is used as a server's watchdog indicator: it fades slowly between light green and black (colors can be changed, but without receiving any USB command for LED0 in 2min, the whole light blinks full BLUE/RED (server overloaded or dead)
- receive command from MQTT to make any of the addressable LEDs blink or fade with specified colors and speed
- the status light has 2 colors for each LED: a background and a foreground (24bits each)
- the blinking or fading happens between those 2 colors, with a very simple algorithm that increments/decrements RGB by a user-defined amount)
- the speed is the increment/decrement amount passed by the user (0-15) for each LED (each LED can blink/fade with a different speed and colors)
