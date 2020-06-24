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
            'name': 'AVR read fuses and lock bits',
            'version': '1.0.0',
            'description': 'Module to write the value of fuses and lock bits\n'
                           'Fuse settings can be calculated here: \nhttps://www.engbedded.com/fusecalc',
            'author': 'Jordan Ovrè / Ghecko <jovre@immunit.ch>, Paul Duncan / Eresse <pduncan@immunit.ch>'
        })
        self.options = {
            "spi_bus": {"Value": "", "Required": True, "Type": "int",
                        "Description": "The octowire SPI bus (0=SPI0 or 1=SPI1)", "Default": 0},
            "reset_line": {"Value": "", "Required": True, "Type": "int",
                           "Description": "The octowire GPIO used as the Reset line", "Default": 0},
            "spi_baudrate": {"Value": "", "Required": True, "Type": "int",
                             "Description": "set SPI baudrate (1000000 = 1MHz) maximum = 50MHz", "Default": 1000000},
            "low_fuse": {"Value": "", "Required": False, "Type": "hex",
                         "Description": "Low fuse hexadecimal value (Format: 0xXX)", "Default": ""},
            "high_fuse": {"Value": "", "Required": False, "Type": "hex",
                          "Description": "High fuse hexadecimal value (Format: 0xXX)", "Default": ""},
            "extended_fuse": {"Value": "", "Required": False, "Type": "hex",
                              "Description": "Extended fuse hexadecimal value (Format: 0xXX)", "Default": ""},
            "lock_bits": {"Value": "", "Required": False, "Type": "hex",
                          "Description": "Lock bits hexadecimal value (Format: 0xXX)", "Default": ""},
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

    def write_fuses(self, spi_interface, device):
        read_low_fuse = b'\x50\x00\x00'
        read_high_fuse = b'\x58\x08\x00'
        read_extended_fuse = b'\x50\x08\x00'

        if len(device["fuse_low"]) > 0:
            spi_interface.transmit(read_low_fuse)
            low_fuse = spi_interface.receive(1)[0]
            self.logger.handle("Low fuse settings (Byte value: {})".format(hex(low_fuse)), self.logger.RESULT)
            self.print_table(self.parse_fuse(device["fuse_low"], low_fuse), ["Fuse name", "Status", "Value", "Mask"])

        if len(device["fuse_high"]) > 0:
            spi_interface.transmit(read_high_fuse)
            high_fuse = spi_interface.receive(1)[0]
            self.logger.handle("High fuse settings (Byte value: {})".format(hex(high_fuse)), self.logger.RESULT)
            self.print_table(self.parse_fuse(device["fuse_high"], high_fuse), ["Fuse name", "Status", "Value", "Mask"])

        if len(device["fuse_extended"]) > 0:
            spi_interface.transmit(read_extended_fuse)
            extended_fuse = spi_interface.receive(1)[0]
            self.logger.handle("Extended fuse settings (Byte value: {})".format(hex(extended_fuse)), self.logger.RESULT)
            self.print_table(self.parse_fuse(device["fuse_extended"], extended_fuse),
                             ["Fuse name", "Status", "Value", "Mask"])

    def write_lockbits(self, spi_interface, device):
        read_lockbits = b'\x58\x00\x00'

        if len(device["lock_bits"]) > 0:
            spi_interface.transmit(read_lockbits)
            lock_bits = spi_interface.receive(1)[0]
            self.logger.handle("Lock bits settings (Byte value: {})".format(hex(lock_bits)), self.logger.RESULT)
            self.print_table(self.parse_fuse(device["lock_bits"], lock_bits),
                             ["Lock bit name", "Status", "Value", "Mask"])

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

            # Active Reset is low
            reset.status = 1

            # Configure SPI with default phase and polarity
            spi_interface.configure(baudrate=spi_baudrate)

            self.logger.handle("Enable Memory Access...", self.logger.INFO)
            # Drive reset low
            reset.status = 0
            # Enable Memory Access
            spi_interface.transmit(enable_mem_access_cmd)
            time.sleep(0.5)

            # Write fuses
            self.write_fuses(spi_interface, device)

            # Write lock bits
            self.write_lockbits(spi_interface, device)

            # Drive reset high
            reset.status = 1

    def run(self):
        """
        Main function.
        get fuses and lock bits value.
        :return: Nothing.
        """
        # If detect_octowire is True then Detect and connect to the Octowire hardware. Else, connect to the Octowire
        # using the parameters that were configured. It sets the self.owf_serial variable if the hardware is found.
        self.connect()
        if not self.owf_serial:
            return
        try:
            self.process()
        except ValueError as err:
            self.logger.handle(err, self.logger.ERROR)
        except Exception as err:
            self.logger.handle("{}: {}".format(type(err).__name__, err), self.logger.ERROR)
