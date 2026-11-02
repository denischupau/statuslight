#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Application to ease the use and set of the USB Digistump status light
from tkinter import *
from tkinter import ttk, font
import tkinter as tk
from tkinter.colorchooser import askcolor
import paho.mqtt.client as mqtt
import re

class Application():
    def __init__(self):
        self.root = Tk()
        self.root.title("USB status light helper")

        # constants
        num_leds = 10
        slow_max = 15

        # control variables
        self.mode = IntVar(value = 0)
        self.ledid = IntVar(value = 0)
        self.ledprop_on = IntVar(value = False)
        self.ledprop_blink = IntVar(value = False)
        self.ledprop_fader = IntVar(value = False)
        self.blinkslow = IntVar(value = 0)
        self.mqtt_ip = StringVar(value = '192.168.xxx.xxx')
        self.mqtt_port = IntVar(value = 1883)
        self.mqtt_topic_cmd = StringVar(value = 'xxx/usbledstatus01/cmd')
        self.mqtt_topic_state = StringVar(value = '/usbledstatus01/state')
        self.cmd_result = StringVar(value = '')
        self.usbstate_follow = BooleanVar(value = True)

        self.fontBold = font.Font(weight="bold")
        self.current_color = '#000000'

        # validations
        valid_ip_wrapper = self.root.register(self.valid_ip)
        valid_port_wrapper = self.root.register(self.valid_port)
        valid_topic_wrapper = self.root.register(self.valid_topic)

        # device_img = PhotoImage(file = '') # image/Drawing of the USB status light

        # Frames
        self.frame_led = tk.Frame(self.root)
        self.frame_led['borderwidth'] = 1
        self.frame_led['relief'] = 'solid'
        self.frame_mqtt = tk.Frame(self.root)
        self.frame_mqtt['borderwidth'] = 1
        self.frame_mqtt['relief'] = 'solid'
        self.frame_states = tk.Frame(self.root)
        self.frame_states['borderwidth'] = 1
        self.frame_states['relief'] = 'solid'
        self.frame_sttext = tk.Frame(self.frame_states)
        self.frame_sttext['borderwidth'] = 1
        self.frame_sttext['relief'] = 'solid'

        # Widgets
        #self.image1 = ttk.Label(self.root, image = "device_img", anchor = "center")
        self.label_led = tk.Label(self.frame_led, text = 'LED command', font = self.fontBold)
        self.label_ledid = tk.Label(self.frame_led, text = "LED id:")
        self.spinled = tk.Spinbox(self.frame_led, from_ = 0, to = num_leds - 1, wrap = True, textvariable = self.ledid, width = 3, state = 'readonly', command = self.refresh_cmd)
        self.label_mode = tk.Label(self.frame_led, text = 'Mode:')
        self.mode0 = tk.Radiobutton(self.frame_led, text = 'Get light state', variable = self.mode, value = 1, command = self.refresh_cmd)
        self.mode1 = tk.Radiobutton(self.frame_led, text = 'Foreground color', variable = self.mode, value = 0, command = self.refresh_cmd)
        self.mode2 = tk.Radiobutton(self.frame_led, text = 'Background color', variable = self.mode, value = 4, command = self.refresh_cmd)
        self.mode3 = tk.Radiobutton(self.frame_led, text = 'Update properties only', variable = self.mode, value = 2, command = self.refresh_cmd)
        self.mode4 = tk.Radiobutton(self.frame_led, text = 'Reset the state of all LEDs', variable = self.mode, value = 8, command = self.refresh_cmd)
        self.mode5 = tk.Radiobutton(self.frame_led, text = 'Toggle watchdog', variable = self.mode, value = 6, command = self.refresh_cmd)
        self.label_prop = tk.Label(self.frame_led, text = 'Properties:')
        self.prop0 = tk.Checkbutton(self.frame_led, text = 'LED ON', variable = self.ledprop_on, onvalue = 1, offvalue = 0, command = self.refresh_cmd)
        self.prop1 = tk.Checkbutton(self.frame_led, text = 'Blinking', variable = self.ledprop_blink, onvalue = 2, offvalue = 0, command = self.refresh_cmd)
        self.prop2 = tk.Checkbutton(self.frame_led, text = 'Blinking with fading', variable = self.ledprop_fader, onvalue = 4, offvalue = 0, command = self.refresh_cmd)
        self.label_slow = tk.Label(self.frame_led, text = 'Slowness of the blinking:')
        self.slow = tk.Spinbox(self.frame_led, from_ = 0, to = slow_max, wrap = True, textvariable = self.blinkslow, width = 3, state = 'readonly', command = self.refresh_cmd)
        self.askcolor = tk.Button(self.frame_led, text = 'Pick a color', command = self.pick_color)
        self.label_color = tk.Label(self.frame_led, text = 'LED color')# command = self.pick_color)
        self.label_cmdres = tk.Label(self.frame_led, text = 'Command to send:', font = self.fontBold)
        self.cmd2send = tk.Entry(self.frame_led, textvariable = self.cmd_result, state = 'readonly', width = 13)


        self.label_mqtt = tk.Label(self.frame_mqtt, text = 'MQTT service:', font = self.fontBold)
        self.label_srvip = tk.Label(self.frame_mqtt, text = 'Server IP:')
        self.mqttip = tk.Entry(self.frame_mqtt, textvariable = self.mqtt_ip, width = 16, validate = 'all', validatecommand = (valid_ip_wrapper, '%d', '%P'))
        self.label_srvport = tk.Label(self.frame_mqtt, text = 'Server port:')
        self.mqttport = tk.Entry(self.frame_mqtt, textvariable = self.mqtt_port, width = 6, validate = 'all', validatecommand = (valid_port_wrapper, '%d', '%P'))
        self.label_topcmd = tk.Label(self.frame_mqtt, text = 'MQTT command topic:')
        self.mqttcmd = tk.Entry(self.frame_mqtt, textvariable = self.mqtt_topic_cmd, width = 40, validate = 'all', validatecommand = (valid_topic_wrapper, '%d', '%P'))
        self.label_topst = tk.Label(self.frame_mqtt, text = 'MQTT state topic:')
        self.mqttstate = tk.Entry(self.frame_mqtt, textvariable = self.mqtt_topic_state, width = 40, validate = 'all', validatecommand = (valid_topic_wrapper, '%d', '%P'))
        self.label_states = tk.Label(self.frame_states, text = 'App logs', font = self.fontBold)
        self.usbstate_sbar = tk.Scrollbar(self.frame_sttext, orient = 'vertical')
        self.usbstate = tk.Text(self.frame_sttext, yscrollcommand = self.usbstate_sbar.set, state = 'disabled', width = 90, height = 30)
        self.usbstate_sbar.config(command = self.usbstate.yview)
        self.usbstate_auto = tk.Checkbutton(self.frame_states, text = 'Auto scrolling', variable = self.usbstate_follow, onvalue = True, offvalue = False)
        self.button_erase = tk.Button(self.frame_states, text = 'Erase the logs', command = self.usbstate_erase)
        self.button_con = tk.Button(self.root, text = 'MQTT connect', command = self.mqtt_connect)
        self.button_send = tk.Button(self.root, text = 'Send command', command = self.send_mqtt_command)
        self.button_quit = tk.Button(self.root, text = 'Quit', command = quit)

        # draw widgets
        self.frame_led.grid(column = 0, row = 0, columnspan = 3) #(side = TOP, fill = BOTH, expand = True, padx = 10, pady = 10)
        self.frame_mqtt.grid(column = 0, row = 1, columnspan = 3) #(side = TOP, fill = BOTH, expand = True, padx = 10, pady = 10)
        self.frame_states.grid(column = 0, row = 2, columnspan = 3, sticky = EW) #(side = TOP, fill = BOTH, expand = True, padx = 10, pady = 10)
        #self.device_img.pack(side = TOP, fill = BOTH, expand = True, padx = 10, pady = 5)
        self.label_led.grid(column = 0, row = 0, sticky = (W))
        self.label_ledid.grid(column = 0, row = 1, sticky = (E))
        self.spinled.grid(column = 1, row = 1, sticky = (W))
        self.label_mode.grid(column = 0, row = 2, sticky = (E))
        self.mode0.grid(column = 1, row = 2, sticky = (W))
        self.mode1.grid(column = 1, row = 3, sticky = (W))
        self.mode2.grid(column = 1, row = 4, sticky = (W))
        self.mode3.grid(column = 1, row = 5, sticky = (W))
        self.mode4.grid(column = 1, row = 6, sticky = (W))
        self.mode5.grid(column = 1, row = 7, sticky = (W))
        self.label_prop.grid(column = 0, row = 8, sticky = (E))
        self.prop0.grid(column = 1, row = 8, sticky = (W))
        self.prop1.grid(column = 1, row = 9, sticky = (W))
        self.prop2.grid(column = 1, row = 10, sticky = (W))
        self.label_slow.grid(column = 0, row = 11, sticky = (E))
        self.slow.grid(column = 1, row = 11, sticky = (W))
        self.askcolor.grid(column = 0, row = 12, sticky = (E))
        self.label_color.grid(column = 1, row = 12, sticky = (W))
        self.label_cmdres.grid(column = 0, row = 13, sticky = (E))
        self.cmd2send.grid(column = 1, row = 13, sticky = (W), pady = 10)

        self.label_mqtt.grid(column = 0, row = 11, sticky = (W))
        self.label_srvip.grid(column = 0, row = 12, sticky = (E))
        self.mqttip.grid(column = 1, row = 12, sticky = (W))
        self.label_srvport.grid(column = 0, row = 13, sticky = (E))
        self.mqttport.grid(column = 1, row = 13, sticky = (W))
        self.label_topcmd.grid(column = 0, row = 14, sticky = (E))
        self.mqttcmd.grid(column = 1, row = 14, sticky = (W))
        self.label_topst.grid(column = 0, row = 15, sticky = (E))
        self.mqttstate.grid(column = 1, row = 15, sticky = (W))
        
        self.label_states.grid(column = 0, row = 0, columnspan = 2, sticky = W)
        self.frame_sttext.grid(column = 0, row = 1, columnspan = 2, sticky = E)
        self.usbstate_sbar.pack(side = RIGHT, fill = BOTH, expand = True, padx = 0, pady = 0) #grid(column = 3, row = 1, columnspan = 1, sticky = NS)
        self.usbstate.pack(side = LEFT, fill = BOTH, expand = True, padx = 0, pady = 0) #grid(column = 0, row = 1, columnspan = 4, sticky = EW)
        self.usbstate_sbar.config(command = self.usbstate.yview)
        self.usbstate_auto.grid(column = 0, row = 2)
        self.button_erase.grid(column = 1, row = 2)
        
        self.button_con.grid(column = 0, row = 3) #(side = LEFT, fill = BOTH, expand = True, padx = 10, pady = 5)
        self.button_send.grid(column = 1, row = 3) #(side = LEFT, fill = BOTH, expand = True, padx = 10, pady = 5)
        self.button_quit.grid(column = 2, row = 3) #(side = RIGHT, fill = BOTH, expand = True, padx = 10, pady = 5)

        self.mqtt_client = mqtt.Client(callback_api_version = mqtt.CallbackAPIVersion.VERSION2, client_id = "statushelper")
        self.mqtt_client.on_publish = self.on_publish
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_disconnect = self.on_disconnect
        self.mqtt_client.on_subscribe = self.on_subscribe

        

    def app_loop(self):
        # main loop
        self.refresh_cmd()
        self.root.mainloop()
        self.mqtt_client.loop_stop()
    
    def state_print(self, data):
        self.usbstate.config(state = 'normal')
        self.usbstate.insert(END, '{}'.format(data) + '\n')
        if self.usbstate_follow.get():
            self.usbstate.see(END)
        self.usbstate.config(state = 'disabled')
    
    def usbstate_erase(self):
        self.usbstate.config(state = 'normal')
        self.usbstate.delete(0.0, END)
        self.usbstate.see(END)
        self.usbstate.config(state = 'disabled')

    def valid_ip(self, why, newval):
        if re.match('^(?:[0-9]{1,3}\\.){3}[0-9]{1,3}$', newval) is None:
            return False
        return True

    def valid_port(self, why, newval):
        if re.match('^[0-9]{1,5}$', newval) is None:
            return False
        return True
        
    def valid_topic(self, why, newval):
        if re.match('^(?:[a-zA-Z0-9][a-zA-Z0-9\\_\\-]{0,20}[a-zA-Z0-9]\\/){1,20}[a-zA-Z0-9][a-zA-Z0-9\\_\\-]{1,20}[a-zA-Z0-9]$', newval) is None:
            return False
        return True
        
    def refresh_cmd(self):
        newcmd = ''
        if self.mode.get() == 8:
            newcmd = '0x80'
        elif self.mode.get() == 6:
            newcmd = '0x60'
        elif self.mode.get() == 1:
            newcmd = '0x10'
        elif self.mode.get() == 2:
            newcmd = '0x' + str(self.mode.get()) + str(self.ledid.get()) + "{:X}".format(self.blinkslow.get())
            newcmd += str(self.ledprop_on.get() + self.ledprop_blink.get() + self.ledprop_fader.get())
        else:
            newcmd = '0x' + str(self.mode.get()) + str(self.ledid.get()) + "{:X}".format(self.blinkslow.get())
            newcmd += str(self.ledprop_on.get() + self.ledprop_blink.get() + self.ledprop_fader.get())
            newcmd += self.current_color[1:7].upper()
        self.cmd_result.set(newcmd)

    def pick_color(self):
        color = askcolor(title = "Pick a color", initialcolor = self.current_color)
        if color[1] is not None:
            self.current_color = color[1]
            if color[0][0] < 128 or color[0][1] < 128 or color[0][2] < 128:
                self.label_color.config(fg = 'white', bg = color[1])
            else:
                self.label_color.config(fg = 'black', bg = color[1])
            self.refresh_cmd()

    def mqtt_connect(self):
        try:
            self.mqtt_client.connect(self.mqtt_ip.get(), self.mqtt_port.get(), 60)
        except:
            self.button_con.config(bg = 'red', activebackground = '#FF2222')
        self.mqtt_client.loop_start()

    def send_mqtt_command(self):
        if self.mqtt_client.publish(self.mqtt_topic_cmd.get(), self.cmd_result.get())[0] != 0:
            self.state_print('Could not send the MQTT message (connected?)')
        else:
            self.state_print('Sent ' + self.cmd_result.get())
        
    def get_mqtt_state(self):
        print('get MQTT state')


    def on_publish(self, client, userdata, mid, reason_code, property):
        #print("sent a message")
        pass

    def on_connect(self, client, userdata, flags, rc, property):
        self.state_print("Connected with result code "+str(rc))
        self.button_con.config(bg = 'green', activebackground = '#22FF22')
        self.state_print("Subscribe to: " + self.mqtt_topic_cmd.get())
        client.subscribe(self.mqtt_topic_cmd.get())
        self.state_print("Subscribe to: " + self.mqtt_topic_state.get())
        client.subscribe(self.mqtt_topic_state.get())
            

    def on_disconnect(self, client, userdata, rc, property):
        if rc != 0:
            self.state_print("Unexpected disconnection.")
            return False
        else:
            self.state_print('Disconnected')
            return True

    def on_subscribe(self, client, userdata, mid, granted_qos, property):
        self.state_print('Subscribed')

    def on_message(self, client, userdata, msg):
        self.state_print("Received message '" + str(msg.payload) + "' on topic '" + msg.topic + "' with QoS " + str(msg.qos))
        data = msg.payload.decode()
        if data == 'disconnect':
            client.disconnect()
        #else:
        #    print(data)


def main():
    my_app = Application()
    my_app.app_loop()
    return 0

if __name__ == '__main__':
    main()

