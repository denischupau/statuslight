# USB StatusLight
USB status light with 10 LEDs, to indicate status on a PC or server by blinking/fading/ON/Off colors.

I wrote it for my own use, and publish it as-is, use at your own risks.

## What is it?

The status light is based on:
- the Digispark Digistump USB board with an ATTiny85 @16.5MHz
- with the bootloader Micronucleus (2KB) to enable flashing the firmware through USB
- 10 APA102 LEDS which are the "DotStar" RGB addressable LEDs with Clock/Data lines: they don't need precise timing, so we can have USB
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
- the blinking or fading, ON or OFF states happen between those 2 colors, with a very simple algorithm that increments/decrements RGB by a user-defined amount)
- the speed is the increment/decrement amount passed by the user (0-15) for each LED (each LED can blink/fade with a different speed and colors)

## Usage

### Presentation

This "sketch" is written for Digispark's ATTINY85 USB dev board with "Micronucleus" flashed.
It's the 16.5MHz flavour.

The LEDs are APA102 (originaly 10 of them) because they don't need precise timings (so we DO have precise timing for USB).

It takes commands from a computer via its USB port.

Commands may be sent via the Python script "sendUSB.py" based on Digispark's API, or the statusLight daemon through MQTT.

### Example commands:

Command example (hexadecimal value):
sendUSB.py 0x02F7660000

What it does:
- 02   is 0x00 (foreground colour) + 0x02 (LED 2)
- F7   is 0xF0 (4bits speed, 15 = lowest speed, big delay) + 0x07 (3bits: LEDON + BLINK + FADER)
- 66 00 00   R G B color

sendUSB.py 0x42F7000066
- 42 is 0x40 (update the background colour) + 0x02 (LED 2)

sendUSB.py 0x1233
- blink LED 2 more rapidly without fadder and without changing colours

#### Explanation, First byte: LED mode + LED number

LED modes: (4 lower bits are the LED number)
- 0x10   GET the properties of the LED
- 0x20   updates the properties of the specific LEDs, without the colours
- 0x40   updates the "background" colour (when it blinks/fades) or otherwise "foreground" colour
- 0x80   reset all states, vars, etc.
- 0x0F   LED number to address: 0 to 9 (10 LEDs, but you can add or remove some, max 15)

#### Explanation, Second byte: LADE/Blink speed + blink mode

Control fading/blinking and speed:
- 0xF0   speed from 0x0 to 0xF (0 - 15), 15 = lowest speed, big delay:
LED properties:
- 0x01   mode ON : this pixel is ON/OFF
- 0x02   mode blink : this pixel is blinking
- 0x04   mode fader : the blinking or color change is smooth
- 0x08   fading/blinking up or down (internal, not settable via USB = ignored when set via USB)

#### Watchdog mode

The status light has a "watchdog mode" ACTIVE BY DEFAULT AT BOOT:
when enabled, it uses LED0 as a slowly fading green indicator (color can be changed).
- It waits for an actualization of LED 0 within 2min max.
- To deactivate it, just set BOTH the Blink & Fader bits to 1 (mutualy exclusive modes): 0x60.

#### Batch command

The light allows for multiple LEDs or multiple properties of a single LED to be sent with 1 command.

Here is an example (use it WITHOUT the double-quotes and Plus signs, which are there for the readability):

sendUSB.py "0x40F3006600"+"01F5000099"+"0337880000"+"4393880033"+"05F1005533"+"06F7EE0044"+"0777334455"+"4737000066"+"0893998877"+"09F3660066"

#### Reset

You can prefix everything with 0x80 + 40F3... to reset before enetering other parameters (without the + sign)

#### Remarks

This version is clearing the WDTRIGG with the global states (init_app()) when receiving a packet after watchdog triggered

Also: the watchdog is used to restart the device when the PC is rebooted and the device hangs, waiting for I don't know what...
