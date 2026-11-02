/*
 * Arduino project file for the Digispark Digistump USB Status Light circle:
 * Light/flashes individual LEDs on a 10 LEDs ring via USB commands sent from a computer.
 * 
 * This "sketch" is written for Digispark's ATTINY85 USB dev board with "Micronucleus" flashed.
 * It's the 16.5MHz flavour.
 * 
 * The LEDs are APA102 (originaly 10 of them) because they don't need precise timings.
 * 
 * It takes commands from a computer via USB port.
 * 
 * Commands may be sent via the Python script "sendUSB.py" based on Digispark's API.
 * 
 * Commands are formed as follow :
 * 
 * sendUSB.py 0x02F7660000
 * 
 * 02 is 0x00 (foreground colour) + 0x02 (LED 2)
 * F7 is 0xF0 (speed 16 = lowest speed, big delay) + 0x07 (LEDON + BLINK + FADER)
 * 66 00 00 = RGB color
 * 
 * sendUSB.py 0x42F7000066
 * 42 is 0x40 (update the background colour) + 0x02 (LED 2)
 *
 * sendUSB.py 0x1233
 * => blink LED 2 more rapidly without fadder and without changing colours
 * 
 * First octet: LED mode + LED number
 * LED modes: (4 lower bits are the LED number)
 *   0x20  // updates the properties of the specific LEDs, without the colours
 *   0x40  // updates the "background" colour (when it blinks) or otherwise "foreground" colour
 *   0x80  // reset all states, vars, etc.
 * LED properties:
 *   0x01  // mode ON : this pixel is ON/OFF
 *   0x02  // mode blink : this pixel is blinking
 *   0x04  // mode fader : the blinking or color change is smooth
 *   0x08  // fading/blinking up or down (not settable via USB = ignored when set via USB)
 *   0xF0  // blink/fade speed mask (the higher the slower)
 * 
 * Watchdog: ACTIVE BY DEFAULT AT BOOT, when enabled, uses LED0 as a slowly fading green indicator (the second color can be changed).
 *              It waits for an actualization of LED 0 every 2min max.
 *              To activate/deactivate it, just set BOTH the Blink & Fader bits to 1 (mutualy exclusive modes): 0x60.
 * 
 * Or for multiple LEDs or multiple properties of a single LED (without the " y +) :
 * 
 * sendUSB.py "0x40F3006600"+"01F5000099"+"0337880000"+"4393880033"+"05F1005533"+"06F7EE0044"+"0777334455"+"4737000066"+"0893998877"+"09F3660066"
 * 
 * Or prefix everything with 0x80 + 40F3... to reset before enetering other parameters
 * 
 *
 *
 * This version is clearing the WDTRIGG with the global states (init_app()) when receiving a packet after watchdog triggered
 *   Also new: the watchdog is used to restart the device when the PC is rebooted and the device hangs, waiting for I don't know what...
 */

#include <util/delay.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include <avr/wdt.h>

#define HARDRESET_ENABLED // this will enable a hard reset when receiving the "reset" instruction to reinitiate the LEDs state.
                          // It also enables reflashing of the firmware, if your Micronucelus flashing mode is configured to activate after a hard reset.
                          // If the module can be reflashed after receiving a reset order:
                                // is it a security problem for you? Who can send this instruction? who can access the USB port?
//#define EXTPROP_SEND      // If defined, sends properties and colors of each LED after the App flags (1byte + NBPIXEL x (1 + 3 + 3))
                            //    Sending data is time consuming and the refresh function MUST be called every 50ms MAXIMUM (otherwise the USB host disconnects).

#include <DigiUSB.h>
#define USB_CFG_DEVICE_NAME     'S','t','a','t','u','s','B','l','i','n','k'
#define USB_CFG_DEVICE_NAME_LEN 11

//======================= LEDs control =======================
#define apa102_port B     // Data and clk port 
#define apa102_data 0    // Data out pin
#define apa102_clk  2    // Clk out pin

struct cRGB { uint8_t b; uint8_t g; uint8_t r; };   // BGR (APA102 Standard)
//struct cRGB { uint8_t g; uint8_t b; uint8_t r; };   // GBR 

#define CONCAT(a, b)            a ## b
#define CONCAT_EXP(a, b)   CONCAT(a, b)

#define apa102_PORTREG  CONCAT_EXP(PORT,apa102_port)
#define apa102_DDRREG   CONCAT_EXP(DDR,apa102_port)

#define nop() asm volatile(" nop \n\t")


inline void SPI_init(void) {
  apa102_DDRREG  |=  _BV(apa102_data);
  apa102_DDRREG  |=  _BV(apa102_clk);
  apa102_PORTREG &= ~_BV(apa102_clk);  // initial state of clk is low
}

// Assumed state before call: SCK- Low, MOSI- High
void SPI_write(uint8_t c) {
  uint8_t i;
  for (i=0; i<8 ;i++)
  {
    if (!(c&0x80)) {
      apa102_PORTREG &= ~_BV(apa102_data); // set data low
    } else {
      apa102_PORTREG |=  _BV(apa102_data); // set data high
    }     
  
  apa102_PORTREG |= (1<< apa102_clk); // SCK hi , data sampled here

  c<<=1;
  
  nop();  // Stretch clock
  nop();
  
  apa102_PORTREG &= ~_BV(apa102_clk); // clk low
  }
// State after call: SCK Low, Dat high
}
 
void inline apa102_setleds(struct cRGB *ledarray, uint8_t leds)
{
  uint16_t i;
  uint8_t *rawarray=(uint8_t*)ledarray;
  SPI_init();
  
  SPI_write(0x00);  // Start Frame
  SPI_write(0x00);
  SPI_write(0x00);
  SPI_write(0x00);
 
  for (i=0; i<(leds+leds+leds); i+=3)
  {
    SPI_write(0xff);  // Maximum global brightness
    SPI_write(rawarray[i+0]);
    SPI_write(rawarray[i+1]);
    SPI_write(rawarray[i+2]);
  }
  
  // End frame: 8+8*(leds >> 4) clock cycles    
  for (i=0; i<leds; i+=16)
  {
    SPI_write(0xff);  // 8 more clock cycles
  }
}

//====================================================

#define NBPIXEL 10
struct cRGB strip[NBPIXEL]; // strip current state
struct cRGB strip_frgrnd[NBPIXEL];  // LEDs foreground color (when LED is "On")
struct cRGB strip_bckgnd[NBPIXEL];  // strip background color (when LED is "Off")
uint8_t strip_prop[NBPIXEL]; // each led's properties (delay/blink/smooth/on/up)
uint8_t strip_time[NBPIXEL]; // timers for fading/blinking

// Modes of operation (THEY ARE ALSO APP FLAGS)
#define GETFLGS  0x10  // get the content of the flags variable
#define UPDTPRP  0x20  // Udates only the properties of the LED, without color
#define BKGRNDC  0x40  // updates the "Background" color, otherwise the Front color
#define RSETALL  0x80  // reset all states, vars, etc.

// LEDs properties:
#define BLSPD  0xF0  // blink/fade speed mask
#define ONPIX  0x01  // mode ON : this pixel is ON/OFF
#define BLINK  0x02  // mode blink : this pixel is blinking
#define FADER  0x04  // mode fader : the blinking or color change is smooth
#define FADUP  0x08  // is the pixel fading/blinking up or down (not settable via USB)


byte in = 0;
uint8_t USBstate = 0; // state of USB values retrieving
uint8_t USBpixel = 0, Props=0, Red=0, Green=0, Blue=0; // to retrieve USB values
uint8_t pixel = 0; // current pixel

// App flags: WARNING, use only the lower bits (see Modes of operation that use upper bits)
volatile byte flags = 0; // application general flags (USBBUSY, WTCHDOG, WDTRIGG, BKGRNDC, UPDTPRP)
#define USBBUSY  0x01  // USB is receiving data
#define WTCHDOG  0x02  // watchdog ON/OFF
#define WDTRIGG  0x04  // Watchdog triggered
//      UPDTPRP  0x20
//      BKGRNDC  0x40

#define WDLEDP 0xF7   // app watchdog properties by default (F = slowest speed, 7 = fading blink)
#define WDLEDG 0x44   // app Watchdog foreground Green intensity
unsigned long usbRcvTimeOut = 0;  // timeout for receiving new data when expecting some more (also by watchdog)

void init_app() {
  // init memory
  memset((void *)strip, 0x00, NBPIXEL*3);
  memset((void *)strip_frgrnd, 0x00, NBPIXEL*3);
  memset((void *)strip_bckgnd, 0x00, NBPIXEL*3);
  memset((void *)strip_prop, 0x00, NBPIXEL);
  memset((void *)strip_time, 0x00, NBPIXEL);
  flags = WTCHDOG; // by default all flags cleared but Watchdog
  strip_prop[0] = WDLEDP;  // LED 0 default Watchdog properties
  in = 0;
  USBstate = 0;
  USBpixel = 0;
  pixel = 0;
}

void setup() {
  wdt_enable(WDTO_8S);  // Watchdog at 8s
  DigiUSB.begin();
  DigiUSB.write(0xFF);  // starting message
  init_app();
  rainbowCycle(100);
  wdt_reset();
  rainbowCycle(100);
  wdt_reset();
  colorFade({0,0,0}, 5);
}

void loop() {
  wdt_reset();    // reset the WD timer
  USBhandle();

  if (!(flags & USBBUSY)) {
    if((flags & WTCHDOG) && !(flags & WDTRIGG)) { // watchdog ON and not triggered, impose FG color for LED 0 (properties in USBhandle())
      strip_frgrnd[0].r = 0;
      strip_frgrnd[0].g = WDLEDG; // LED 0 (watchdog) green default
      strip_frgrnd[0].b = 0;
    }
    if (flags & WDTRIGG) {  // if Watchdog triggered, alternate colors FG=RED, BG=BLUE
      if (++strip_time[0] >= 0xFE) { // here we use only 1 timer: when timer of Pixel 0 (pixel used for WD) has finished, alternate colors Red/Blue
        strip_time[0] = 0;    // reset timer
        if (strip[0].r != 128) {  // pixel red value is not red?
          for(char i=0; i < NBPIXEL; i++) {
            strip[i].r = 128;  // all red
            strip[i].g = 0; 
            strip[i].b = 0;
          }
        } else {
          for(char i=0; i < NBPIXEL; i++) {
            strip[i].r = 0;
            strip[i].g = 0;
            strip[i].b = 6;  // all blue
          }
        }
        apa102_setleds(strip, NBPIXEL);
      }
      delay(2);
    } else {    // normal loop
      if (strip_prop[pixel] & ONPIX) {  // pixel ON
        if (strip_prop[pixel] & BLINK) { // pixel blink
          if (strip_prop[pixel] & FADER) { // pixel fade
            if (strip_time[pixel] == 0) {  // time is up
              if (strip_prop[pixel] & FADUP) { // pixel fade "up"
                if (!fading(strip_frgrnd)) {   // when fading up finished
                  strip_prop[pixel] &= ~FADUP; // set fade down
                }
              } else if (!fading(strip_bckgnd)) { // when fade down finished
                strip_prop[pixel] |= FADUP;       // set fade up
              }
            }
            if (++strip_time[pixel] >= (strip_prop[pixel] >> 4)) { // when timer has finished 
              strip_time[pixel] = 0;    // reset
            }
          } else {  // pixel blinks without smoothing
            if (strip_time[pixel] == 0) { // only do it when time is up
              if (strip_prop[pixel] & FADUP) { // pixel blink "up"
                strip[pixel] = strip_frgrnd[pixel];
                strip_prop[pixel] &= ~FADUP;
              } else {
                strip[pixel] = strip_bckgnd[pixel];
                strip_prop[pixel] |= FADUP;
              }
            }
            if (++strip_time[pixel] >= (strip_prop[pixel] & 0xF0)) { // timer (this time do not shift so we have a longer timer, as blink is immediate)
              strip_time[pixel] = 0;    // reset the timer
            }
          }
        } else { // pixel is fixed (not blinking)
          if (strip_prop[pixel] & FADER) {
            fading(strip_frgrnd);
          } else {
            strip[pixel] = strip_frgrnd[pixel];
          }
        }
      } else { // pixel OFF
        strip[pixel]={0,0,0};
      }
      apa102_setleds(strip, NBPIXEL);
      if (++pixel >= NBPIXEL) {  // next pixel
        pixel = 0;
      }
    }
  }
}

// handles USB input
void USBhandle() {
  DigiUSB.refresh();
  if (DigiUSB.available()) {
    usbRcvTimeOut = millis();  // reset the USB receive timeOut
    if (flags & WDTRIGG){   // data received: reset app WD
      flags = WTCHDOG; // by default all flags cleared but Watchdog
      USBstate = 0;
      USBpixel = 0;
    }
    in = DigiUSB.read();
    // 5 states machine
    switch(USBstate) {
      case 0: // state 0: mode of operation (first byte of a new sequence)
        flags &= ~(BKGRNDC | UPDTPRP);
        if (in & RSETALL){  // Reset via Watchdog or soft reinit
#ifdef HARDRESET_ENABLED
            wdt_enable(WDTO_15MS);
            delay(20);
#else
            init_app();
#endif
        } else if (in & GETFLGS) {
          DigiUSB.write(flags);
#ifdef EXTPROP_SEND
          for (char i = 0; i < NBPIXEL; i++) {
            DigiUSB.write(strip_prop[i]);
            DigiUSB.write(strip_frgrnd[i].r);
            DigiUSB.write(strip_frgrnd[i].g);
            DigiUSB.write(strip_frgrnd[i].b);
            DigiUSB.write(strip_bckgnd[i].r);
            DigiUSB.write(strip_bckgnd[i].g);
            DigiUSB.write(strip_bckgnd[i].b);
          }
#endif
        } else if ((in & (UPDTPRP | BKGRNDC)) == (UPDTPRP | BKGRNDC)) {  // Watchdog activate/deactivate
          flags ^= WTCHDOG;  // toggle ON/OFF
          if (flags & WTCHDOG) {  // watchdog enabled
            strip_prop[0] = WDLEDP; // LED 0 watchdog default properties
          } else {
            strip_prop[0] = 0x00;   // LED Off+NoBlink+NoFade when shuting down watchdog
          }
        } else {
          flags |= USBBUSY;         // USB is now busy (receiving sequence)
          USBstate = 1;
          USBpixel = (in & 0x0F); // get the pixel address
          if (USBpixel >= NBPIXEL) USBpixel = 0;
          if (in & UPDTPRP) flags |= UPDTPRP;
          if (in & BKGRNDC) flags |= BKGRNDC;
        }
        break;
      case 1: // state 1: led properties
        if (flags & WTCHDOG && USBpixel == 0) {strip_prop[USBpixel] = (in | (ONPIX | BLINK));} // protect "Blink" and "On" for LED 0 if Watchdog ON
        else {strip_prop[USBpixel] = in;}
        if (flags & UPDTPRP) {
          USBstate = 0;
          flags &= ~USBBUSY;
        } else {
          USBstate = 2;
        }
        break;
      case 2:  // state 2: Red color
        if (flags & BKGRNDC) {
          strip_bckgnd[USBpixel].r = in;
        } else {
          strip_frgrnd[USBpixel].r = in;
        }
        USBstate = 3;
        break;
      case 3:  // state 3: Green color
        if (flags & BKGRNDC) {
          strip_bckgnd[USBpixel].g = in;
        } else {
          strip_frgrnd[USBpixel].g = in;
        }
        USBstate = 4;
        break;
      case 4:  // state 4: Blue color
        if (flags & BKGRNDC) {
          strip_bckgnd[USBpixel].b = in;
        } else {
          strip_frgrnd[USBpixel].b = in;
        }
        USBstate = 0;
        flags &= ~USBBUSY;
        break;
      default:
        if ((millis() - usbRcvTimeOut > 250) && (flags & USBBUSY)) { // something wrong happened: reset the state machine
          USBstate = 0;
          flags &= ~USBBUSY;
        }
        break;
    }
  } else {
    if ((millis() - usbRcvTimeOut > 10000) && ((flags & (WTCHDOG | WDTRIGG)) == WTCHDOG)) {  // if Watchdog ON and we didn't receive anything for 10seconds
      flags |= WDTRIGG;
      DigiUSB.write(flags);
    }
  }
}

bool USBcheck() {
  DigiUSB.refresh();
  if (DigiUSB.available()) {
    return true;
  } else {
    return false;
  }
}


//################### LEDs effects ###################

// makes the rainbow equally distributed throughout
void rainbowCycle(uint8_t wait) {
  uint16_t i, j;
  for(j=0; j<NBPIXEL; j++) { // 1 cycle of all LEDs
    for(i=0; i< NBPIXEL; i++) {
      strip[i] = Wheel((i+j) * 256 / NBPIXEL);
    }
    apa102_setleds(strip, NBPIXEL);
    //if (USBcheck()) return;
    wdt_reset();    // reset the WD timer
    USBhandle();
    delay(wait);
  }
}

// fades towards reference color, one step at a time
bool fading(cRGB * ref_tab) {
  bool changed = false; // tracks changes, when no more change : returns false
  if (strip[pixel].r < ref_tab[pixel].r) {
    strip[pixel].r++;
    changed = true; // changed
  } else {
    if (strip[pixel].r > ref_tab[pixel].r) {
      strip[pixel].r--;
      changed = true; // changed
    }
  }
  // Green
  if (strip[pixel].g < ref_tab[pixel].g) {
    strip[pixel].g++;
    changed = true; // changed
  } else {
    if (strip[pixel].g > ref_tab[pixel].g) {
      strip[pixel].g--;
      changed = true; // changed
    }
  }
  // Blue
  if (strip[pixel].b < ref_tab[pixel].b) {
    strip[pixel].b++;
    changed = true; // changed
  } else {
    if (strip[pixel].b > ref_tab[pixel].b) {
      strip[pixel].b--;
      changed = true; // changed
    }
  }
  return changed;
}

// fades to color
void colorFade(struct cRGB c, uint8_t wait) {
  byte flgs = 0x07; // tracks changes, when no more change : return
  while (flgs != 0x00) { // all setup ?
    flgs = 0;
    for (uint8_t l = 0; l < NBPIXEL; l++) {
      // Red
      if (strip[l].r < c.r) {
        strip[l].r++;
        flgs |= 0x01; // changed
      } else {
        if (strip[l].r > c.r) {
          strip[l].r--;
          flgs |= 0x01;
        }
      }
      // Green
      if (strip[l].g < c.g) {
        strip[l].g++;
        flgs |= 0x02;
      } else {
        if (strip[l].g > c.g) {
          strip[l].g--;
          flgs |= 0x02;
        }
      }
      // Blue
      if (strip[l].b < c.b) {
        strip[l].b++;
        flgs |= 0x04;
      } else {
        if (strip[l].b > c.b) {
          strip[l].b--;
          flgs |= 0x04;
        }
      }
      if (flgs & 0x07) flgs |= 0x10; // mark that there has been a change on a LED
      flgs &= ~0x07; // clear color flags
    }
    apa102_setleds(strip, NBPIXEL);
    wdt_reset();    // reset the WD timer
    USBhandle();
    delay(wait);
  }
}


//################## HELPERS ###################

// Input a value 0 to 255 to get a color value.
// The colours are a transition r - g - b - back to r.
struct cRGB Wheel(byte WheelPos) {
  struct cRGB Color;
  WheelPos = 255 - WheelPos;
  if(WheelPos < 85) {
    Color.r = 255 - WheelPos * 3;
    Color.g = 0;
    Color.b = WheelPos * 3;
    return Color;
  } else if(WheelPos < 170) {
    WheelPos -= 85;
    Color.r = 0;
    Color.g = WheelPos * 3;
    Color.b = 255 - WheelPos * 3;
    return Color;
  } else {
   WheelPos -= 170;
   Color.r = WheelPos * 3;
   Color.g = 255 - WheelPos * 3;
   Color.b = 0;
   return Color;
  }
}
