#/usr/bin/python

#
# Written for PyUSB 1.0 (w/libusb 1.0.3)
#


import usb, sys # 1.0 not 0.4
from usbdevice import ArduinoUsbDevice


if __name__ == "__main__":
    try:
        theDevice = ArduinoUsbDevice(idVendor=0x16c0, idProduct=0x05df)
    except:
        print("Error: No DigiUSB Device Found")
        sys.exit(1)



    try:
        user_input = sys.argv[1]
    except:
        print("Error: No data to send")
        exit(1)

    try: 
        bin = hex(int(user_input,16)) 
    except:
        print('error: format: 0xFF22EE77EE')
        exit(1)

    if len(user_input) % 2 != 0:
        print('Error: there must be an even number of Hex digits, odd number received')
        exit(1)

    for i in range(0, len(user_input), 2):
        try:
            val = user_input[i]+user_input[i+1]
        except:
            print('Error: could not send all data')
            exit(1)
        if val != "0x":
            #print(i, '-', val, int(val,16))
            theDevice.write(int(val, 16))
