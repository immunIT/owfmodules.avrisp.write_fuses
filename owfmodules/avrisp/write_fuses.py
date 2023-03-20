# -*- coding: utf-8 -*-

# Octowire Framework
# Copyright (c) ImmunIT - Jordan Ovrè / Paul Duncan
# License: Apache 2.0
# Paul Duncan / Eresse <pduncan@immunit.ch>
# Jordan Ovrè / Ghecko <jovre@immunit.ch>

import time

from octowire_framework.module.AModule import AModule
from octowire.gpio import GPIO
from octowire.spi import SPI
from owfmodules.avrisp.device_id import DeviceID


class WriteFuses(AModule):
    def __init__(self, owf_config):
        super(WriteFuses, self).__init__(owf_config)
        self.meta.update({
            'name': 'AVR write fuses and lock bits',
            'version': '1.0.3',
            'description': 'Write the fuses and lock bits of AVR microcontrollers\n'
                           'Fuse settings can be calculated here: \nhttps://www.engbedded.com/fusecalc',
            'author': 'Jordan Ovrè / Ghecko <jovre@immunit.ch>, Paul Duncan / Eresse <pduncan@immunit.ch>'
        })
        self.options = {
            "spi_bus": {"Value": "", "Required": True, "Type": "int",
                        "Description": "SPI bus (0=SPI0 or 1=SPI1)", "Default": 0},
            "reset_line": {"Value": "", "Required": True, "Type": "int",
                           "Description": "GPIO used as the Reset line", "Default": 0},
            "spi_baudrate": {"Value": "", "Required": True, "Type": "int",
                             "Description": "SPI frequency (1000000 = 1MHz) maximum = 50MHz", "Default": 1000000},
            "low_fuse": {"Value": "", "Required": False, "Type": "hex",
                         "Description": "Low fuse hexadecimal value (Format: 0xCA)", "Default": ""},
            "high_fuse": {"Value": "", "Required": False, "Type": "hex",
                          "Description": "High fuse hexadecimal value (Format: 0xFE)", "Default": ""},
            "extended_fuse": {"Value": "", "Required": False, "Type": "hex",
                              "Description": "Extended fuse hexadecimal value (Format: 0xBE)", "Default": ""},
            "lock_bits": {"Value": "", "Required": False, "Type": "hex",
                          "Description": "Lock bits hexadecimal value (Format: 0xEF)", "Default": ""},
        }
        self.dependencies.append("owfmodules.avrisp.device_id>=1.0.0")

    def get_device_id(self, spi_bus, reset_line, spi_baudrate):
        device_id_module = DeviceID(owf_config=self.config)
        # Set DeviceID module options
        device_id_module.options["spi_bus"]["Value"] = spi_bus
        device_id_module.options["reset_line"]["Value"] = reset_line
        device_id_module.options["spi_baudrate"]["Value"] = spi_baudrate
        device_id_module.owf_serial = self.owf_serial
        device_id = device_id_module.run(return_value=True)
        return device_id

    def write_fuses(self, spi_interface, device, reset):
        write_low_fuse = b'\xAC\xA0\x00'
        write_high_fuse = b'\xAC\xA8\x00'
        write_extended_fuse = b'\xAC\xA4\x00'

        if len(device["fuse_low"]) > 0:
            if self.options["low_fuse"]["Value"] != "":
                # Drive reset low
                reset.status = 0

                spi_interface.transmit(write_low_fuse + bytes([self.options["low_fuse"]["Value"]]))
                self.logger.handle(f"Low fuse value written ({hex(self.options['low_fuse']['Value'])}).",
                                   self.logger.RESULT)
                # Drive reset high
                reset.status = 1
                time.sleep(0.1)
            else:
                self.logger.handle("Low fuse left unchanged", self.logger.INFO)

        if len(device["fuse_high"]) > 0:
            if self.options["high_fuse"]["Value"] != "":
                # Drive reset low
                reset.status = 0

                spi_interface.transmit(write_high_fuse + bytes([self.options["high_fuse"]["Value"]]))
                self.logger.handle(f"High fuse value written ({hex(self.options['high_fuse']['Value'])}).",
                                   self.logger.RESULT)
                
                # Drive reset high
                reset.status = 1
                time.sleep(0.1)
            else:
                self.logger.handle("High fuse left unchanged", self.logger.INFO)

        if len(device["fuse_extended"]) > 0:
            if self.options["extended_fuse"]["Value"] != "":
                # Drive reset low
                reset.status = 0
                spi_interface.transmit(write_extended_fuse + bytes([self.options["extended_fuse"]["Value"]]))
                self.logger.handle(f"Extended fuse value written ({hex(self.options['extended_fuse']['Value'])}).",
                                   self.logger.RESULT)
                # Drive reset high
                reset.status = 1
                time.sleep(0.1)
            else:
                self.logger.handle("Extended fuse left unchanged", self.logger.INFO)

    def write_lockbits(self, spi_interface, device):
        write_lockbits = b'\xAC\xE0\x00'

        if len(device["lock_bits"]) > 0:
            if self.options["lock_bits"]["Value"] != "":
                spi_interface.transmit(write_lockbits + bytes([self.options["lock_bits"]["Value"]]))
                self.logger.handle(f"Lock bits written ({hex(self.options['lock_bits']['Value'])}).",
                                   self.logger.RESULT)
            else:
                self.logger.handle("Lock bits left unchanged", self.logger.INFO)

    def process(self):
        enable_mem_access_cmd = b'\xac\x53\x00\x00'
        spi_bus = self.options["spi_bus"]["Value"]
        reset_line = self.options["reset_line"]["Value"]
        spi_baudrate = self.options["spi_baudrate"]["Value"]

        device = self.get_device_id(spi_bus, reset_line, spi_baudrate)

        if device is not None:
            spi_interface = SPI(serial_instance=self.owf_serial, bus_id=spi_bus)
            reset = GPIO(serial_instance=self.owf_serial, gpio_pin=reset_line)
            reset.direction = GPIO.OUTPUT

            # Reset is active-low
            reset.status = 1

            # Configure SPI with default phase and polarity
            spi_interface.configure(baudrate=spi_baudrate)
            self.logger.handle("Enabling Memory Access...", self.logger.INFO)

            # Drive reset low
            reset.status = 0

            # Enable Memory Access
            spi_interface.transmit(enable_mem_access_cmd)
            time.sleep(0.5)

            # Drive reset high
            reset.status = 1

            # Write fuses - This function manage the reset line (a reset cycle is needed for each fuse group)
            self.write_fuses(spi_interface, device, reset)

            # Drive reset low
            reset.status = 0

            # Write lock bits
            self.write_lockbits(spi_interface, device)

            # Drive reset high
            reset.status = 1

    def run(self):
        """
        Main function.
        Write fuses and lock bits.
        :return: Nothing.
        """
        # If detect_octowire is True then detect and connect to the Octowire hardware. Else, connect to the Octowire
        # using the parameters that were configured. This sets the self.owf_serial variable if the hardware is found.
        self.connect()
        if not self.owf_serial:
            return
        try:
            self.process()
        except ValueError as err:
            self.logger.handle(err, self.logger.ERROR)
        except Exception as err:
            self.logger.handle("{}: {}".format(type(err).__name__, err), self.logger.ERROR)
