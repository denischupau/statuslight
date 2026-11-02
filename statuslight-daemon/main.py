#!/usr/bin/env python3
# -*- coding: utf-8 -*-                                                                                  
                                                    
# apt install python3-paho-mqtt  o  pip3 install paho-mqtt
# apt install python3-usb           
# HomeAssistant device classes: https://www.home-assistant.io/integrations/sensor/                       
# HomeAssistant device customization: https://www.home-assistant.io/docs/configuration/customizing-devices/
# HomeAssistant MQTT syntax and abreviations: https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery
                                                                                                         
import time                                
import json, re                                     
import paho.mqtt.client as mqtt                                                                          
from time import sleep                
from datetime import datetime                                                                            
                                                    
#                                                                                                        
# Written for PyUSB 1.0 (w/libusb 1.0.3)                                                                 
#                                                                                                        
                                                                                                         
                                                                                                         
import usb, sys # 1.0 not 0.4                       
from usbdevice import ArduinoUsbDevice                                                                   
                                                    
                                                    
class Application():
    def __init__(self):                             
        # variables           
        self.bLoop = True # Loop?
        self.usb_states = []        # memorizes the states received from the USB status light            
        self.seconds_elapsed = 0    # seconds elapsed since the last USB ping (read)                                                                                                                               
        self.print_time = False     # print messages with time stamp?                                                                                                                                              
        self.print_prefix = True    # print messages with the script prefix?                             
        self.mqtt_srv_ip = '192.168.229.2'          
        self.mqtt_srv_port = 1883                                                                                                                                                                                  
        self.mqtt_topic_cmd = "rpialeks/usbledstatus01/cmd"
        self.mqtt_topic_state = 'rpialeks/usbledstatus01/state'                                          
        self.mqtt_data_received = ''                                                                     
        self.mqtt_client = mqtt.Client(callback_api_version = mqtt.CallbackAPIVersion.VERSION2, client_id = "usbstatus")
        self.mqtt_client.on_publish = self.on_publish
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_disconnect = self.on_disconnect
        self.mqtt_client.on_subscribe = self.on_subscribe
        
        ### Define the autoconf payloads ###
        autoconf_switch = json.loads('''{
            "unique_id": "rpialeks_usbledstatus01",
            "name": "RPi Aleks USB LED status",
            "state_topic": "rpialeks/light/usbledstatus01/state",
            "command_topic": "rpialeks/usbledstatus01/cmd",
            "availability_topic":"rpialeks/light/usbledstatus01/status"
        }''')

    def loop_start(self):
        # main loop (just ping the device, and starts the MQTT thread)
        self.mqtt_connect()
        self.mqtt_client.loop_start()
        self.update_light('0x10')   # "ping" the device by asking the current state
        self.read_device()
        self.analyse_states()
        self.mqtt_publish_states()
        while self.bLoop:
            sleep(1)
            self.seconds_elapsed += 1
            if self.seconds_elapsed > 8:
                self.seconds_elapsed = 0
                self.update_light('0x10')   # "ping" the device by asking the current state
                self.read_device()
                self.analyse_states()
                self.mqtt_publish_states()
            sys.stdout.flush()      # flushes the output in real time
        self.mqtt_client.loop_stop()

        
    def mqtt_connect(self):
        try:
            self.mqtt_client.connect(self.mqtt_srv_ip, self.mqtt_srv_port, 60)
        except:
            sys.exit('* ERROR: could not connect to MQTT: ' + self.mqtt_srv_ip + ':' + str(self.mqtt_srv_port))
            
    
    def mqtt_publish_states(self):
        for state in self.usb_states:
            self.mqtt_client.publish(self.mqtt_topic_state, '{:08b}'.format(state))

    def on_publish(self, client, userdata, mid, reason_code, properties):
        #self.print_with_time("sent a message")
        pass

    def on_connect(self, client, userdata, flags, rc, properties):
        self.print_with_time("Connected to MQTT broker with result code "+str(rc))
        self.print_with_time("Subscribe to: " + self.mqtt_topic_cmd)
        client.subscribe(self.mqtt_topic_cmd)

    def on_disconnect(self, client, userdata, flags, rc, properties):
        #self.update_light('0x80')    # clear status 
        self.read_device()
        self.mqtt_publish_states()
        if rc != 0:
            self.print_with_time(f"Unexpected disconnection with code {rc}.")
            FIRST_RECONNECT_DELAY = 1
            MAX_RECONNECT_COUNT = 12
            MAX_RECONNECT_DELAY = 60
            RECONNECT_RATE = 2
            reconnect_count, reconnect_delay = 0, FIRST_RECONNECT_DELAY
            while reconnect_count < MAX_RECONNECT_COUNT:
                self.print_with_time(f"Reconnecting in {reconnect_delay} seconds...")
                time.sleep(reconnect_delay)

                try:
                    client.reconnect()
                    self.print_with_time("Reconnected successfully!")
                    return
                except Exception as err:
                    self.print_with_time(f"{err}. Reconnect failed. Retrying...")

                reconnect_delay *= RECONNECT_RATE
                reconnect_delay = min(reconnect_delay, MAX_RECONNECT_DELAY)
                reconnect_count += 1
            self.print_with_time(f"Reconnect failed after {reconnect_count} attempts. Exiting...")
            self.bLoop = False
            return False
        else:
            self.print_with_time('Disconnected')
            self.bLoop = False
            return 1

    def on_subscribe(self, client, userdata, mid, granted_qos, properties):
        self.print_with_time('Subscribed')

    def on_message(self, client, userdata, msg):
        self.print_with_time("Received message '" + str(msg.payload) + "' on topic '" + msg.topic + "' with QoS " + str(msg.qos))
        data = msg.payload.decode()
        if data == 'disconnect':
            client.disconnect()
        else:
            self.mqtt_data_received = data
            self.sanitize_mqtt_message()
            if self.mqtt_data_received != '':
                self.update_light(self.mqtt_data_received)
                self.print_with_time('MQTT received command ' + self.mqtt_data_received)
            self.read_device()
            self.mqtt_publish_states()

    def analyse_states(self):
        for state in self.usb_states:
            if state == 0xFF:
                self.print_with_time('* USB device started')
            elif (state & 0x04) > 0:
                self.print_with_time('* USB device Watchdog TRIGGERED')

    # init the USB device in our app
    def init_device(self):
        try:
            theDevice = ArduinoUsbDevice(idVendor=0x16c0, idProduct=0x05df)
            return theDevice
        except:
            self.print_with_time("No DigiUSB Device Found")
            return False

    def sanitize_mqtt_message(self):
        try:
            self.mqtt_data_received = re.match('^0x[0-9A-F]*', self.mqtt_data_received).group(0)
        except:
            self.mqtt_data_received = ''

    def update_light(self, data = ''):
        theDevice = self.init_device()
        if theDevice == False:
            return False
        if data == '':
            self.print_with_time('Received invalid data from MQTT: no LED update done')
            return False
        if len(data) % 2 != 0:
            self.print_with_time('Error: there must be an even number of Hex digits, odd number received')
            return False

        #self.print_with_time("Update light: " + data)
        for i in range(0, len(data), 2):
            val = data[i] + data[i+1]
            if val != "0x":
#                self.print_with_time('* try to write "0x' + val + '"', ending = "... ")
                try:
                    theDevice.write(int(val, 16))
#                    print('done.')
                except Exception as error:
                    self.print_with_time(f"* USB write: {type(error).__name__} – {error}")
        return True

    # read all the received states from USB, in self.usb_states
    def read_device(self):
        doloop = True
        received = []
        theDevice = self.init_device()
        if theDevice == False:
            self.usb_states = received
        while doloop:
            try:
                stat = theDevice.read()
                received.append(stat)
            except:
                doloop = False
        self.usb_states = received
    
    def print_with_time(self, data, ending = ''):
        prefix = ''
        if self.print_time == True:
            prefix += datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        if self.print_prefix == True:
            prefix += ' USBstatusLight'
        if ending == '':
            print(prefix + ': ' + data)
        else:
            print(prefix + ': ' + data, end = ending)
            


def main():
    my_app = Application()
    my_app.loop_start()
    return 0

if __name__ == '__main__':
    main()
