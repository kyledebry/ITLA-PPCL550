"""
Adapted from https://www.pure-photonics.com/s/ITLA_v3-CUSTOMER.PY

@author: PurePhotonics, Kyle DeBry
"""

from serial import Serial, SerialException
import time
import struct
import threading
import logging


class ITLA:
    """ Base class for Pure-Photonics ITLA lasers
        Adapted from https://www.pure-photonics.com/s/ITLA_v3-CUSTOMER.PY
    """
    NOERROR = 0x00  # No error
    EXERROR = 0x01  # Execution error, read NOP register for reason
    AEERROR = 0x02
    CPERROR = 0x03  # Command pending error
    NRERROR = 0x04  # Error: laser not responding, check baud rate
    CSERROR = 0x05  # Checksum error
    ERROR_SERPORT = 0x01  # Error: unable to connect to port, check port number. Should be 'COM#', e.g. 'COM2'.
    ERROR_SERBAUD = 0x02  # Error: incorrect baud rate

    REG_Nop = 0x00  # Read a pending response or interrupted response. Often used to check communication. R/W
    REG_Mfgr = 0x02  # Manufacturer (AEA mode) R
    REG_Model = 0x03  # Model (AEA mode) R
    REG_Serial = 0x04  # Serial number (AEA mode) R
    REG_Release = 0x06  # Firmware release (AEA mode) R
    REG_Gencfg = 0x08  # General module configuration R/W
    REG_AeaEar = 0x0B  # Location accessed through AEA-EA and AEA-EAC R/W
    REG_Iocap = 0x0D  # Physical interface information (data rate, etc.) R/W
    REG_Ear = 0x10  # Location accessed through EA and EAC R/W
    REG_Dlconfig = 0x14  # Download configuration register R/W
    REG_Dlstatus = 0x15  # Download status register R
    REG_Channel = 0x30  # Setting valid channel causes tuning operation to occur R/W
    REG_Power = 0x31  # Sets optical power, encoded as dBm * 100 R/W
    REG_ResetEnable = 0x32  # Reset/Enable: enable output, hard and soft reset R/W
    REG_Grid = 0x34  # Allows setting the grid spacing for channel numbering R/W
    REG_FreqTHz = 0x35  # Frequency, THz part. Sets the frequency in THz to the left of the decimal point. R/W
    REG_FreqGHz = 0x36  # Frequency, GHz*10 part. Sets the frequency to the right of the decimal point in units of 0.1
    # GHz. R/W
    REG_GetFreqTHz = 0x40  # Returns the frequency the laser thinks it is at in THz
    REG_GETFreqGHz = 0x41  # Returns the frequency the laser thinks it is at in GHz
    REG_Oop = 0x42  # Returns optical power in dBm * 100. R
    REG_Opsl = 0x50  # Returns min possible optical power. R
    REG_Opsh = 0x51  # Returns max possible optical power. R
    REG_Lfl1 = 0x52  # Returns laser's first frequency, THz part. R
    REG_Lfl2 = 0x53  # Returns laser's first frequency, 0.1 * GHz part. R
    REG_Lfh1 = 0x54  # Returns laser's last frequency, THz part. R
    REG_Lfh2 = 0x55  # Returns laser's last frequency, 0.1 * GHz part. R
    REG_Currents = 0x57  # Returns module specific currents. R
    REG_Temps = 0x58  # Return module specific temperatures. R
    REG_Ftf = 0x62  # Fine tune frequency adjustment of laser output. R/W
    REG_Mode = 0x90  # Select between dither (0), no-dither (1), and whisper mode (2). R/W
    REG_PW = 0xE0  # Password to enable laser. See documentation. R/W
    REG_Csweepsena = 0xE5  # Start (1) or stop (0) clean sweep. R/W
    REG_Csweepamp = 0xE4  # Set range for clean sweep. R/W
    REG_Cscanamp = 0xE4
    REG_Cscanon = 0xE5
    REG_Csweepon = 0xE5
    REG_Csweepoffset = 0xE6  # Returns offset of clean sweep in units of 0.1 GHz with offset of 200 GHz. Offset is
    # (read-out - 2000) * 0.1 GHz. R
    REG_Cscanoffset = 0xE6
    REG_Csweepstop = 0xE7  # Set frequency in GHz to stop the clean sweep
    REG_Cscansled = 0xF0  # Set sled temp for clean scan. R/W ?
    REG_Csweepspeed = 0xF1  # Set clean sweep speed in MHz/sec. R/W
    REG_Cscanf1 = 0xF1  # Set filter 1 temperature for clean scan. R/W ?
    REG_Cscanf2 = 0xF2  # Set filter 2 temperature for clean scan. R/W ?
    REG_CjumpTHz = 0xEA  # Set clean jump target frequency (THz). R/W
    REG_CjumpGHz = 0xEB  # Set clean jump target frequency (0.1 * GHz). R/W
    REG_CjumpSled = 0xEC  # Set clean jump target temperature for the laser (0.01 C). R/W
    REG_Cjumpon = 0xED  # Execute clean jump. 1 = start. W
    REG_Cjumpoffset = 0xE6  # Returns the difference between desired frequency and current frequency. R
    REG_SledSlope = 0xE8  # Returns the sled slope in units of 0.0001 C/GHz. R
    REG_CjumpCurrent = 0xE9  # Set clean jump current (0.1 * mA). R/W

    READ = 0
    WRITE = 1

    SET_ON = 8  # When enabling laser with REG_ResetEnable, this turns on laser
    SET_OFF = 0  # When disabling laser with REG_ResetEnable, this turns off laser

    def __init__(self, port, baud, log_level):
        self.latest_register = 0
        self.tempport = 0
        self.raybin = 0
        self.queue = []
        self.maxrowticket = 0

        self._error = ITLA.NOERROR
        self.serial_lock = 0

        self.port = port
        self.baudrate = baud

        logging.basicConfig(format='%(levelname)s: %(message)s', level=log_level)

        self.sercon = self.itla_connect(self.port, self.baudrate)
        logging.debug(self.sercon)

        logging.debug('ITLA initialized')

    @staticmethod
    def strip_string(input_str):
        outp = ''
        input_str = str(input_str)
        teller = 0
        while teller < len(input_str) and ord(input_str[teller]) > 47:
            outp = outp + input_str[teller]
            teller = teller + 1
        return outp

    def itla_last_error(self):
        """Gives the most recent error that has occurred

        :return: the error code
        """
        return self._error

    def serial_lock(self):
        return self.serial_lock

    def serial_lock_set(self):
        self.serial_lock = 1

    def serial_lock_unset(self):
        self.serial_lock = 0
        self.queue.pop(0)

    @staticmethod
    def checksum(byte0, byte1, byte2, byte3):
        bip8 = (byte0 & 0x0f) ^ byte1 ^ byte2 ^ byte3
        bip4 = ((bip8 & 0xf0) >> 4) ^ (bip8 & 0x0f)
        return bip4

    def send_command(self, byte0, byte1, byte2, byte3):
        """ Writes four bytes to the device.

        :param byte0: first byte
        :param byte1: second byte
        :param byte2: third byte
        :param byte3: fourth byte
        """
        self.sercon.write(chr(byte0).encode())
        self.sercon.write(chr(byte1).encode())
        self.sercon.write(chr(byte2).encode())
        self.sercon.write(chr(byte3).encode())

    def receive_response(self):
        ref_time = time.perf_counter()
        while self.sercon.inWaiting() < 4:
            if time.perf_counter() > ref_time + 0.25:
                self._error = ITLA.NRERROR
                logging.error('No response')
                return 0xFF, 0xFF, 0xFF, 0xFF
            time.sleep(0.0001)
        try:
            byte0 = ord(self.sercon.read(1))
            byte1 = ord(self.sercon.read(1))
            byte2 = ord(self.sercon.read(1))
            byte3 = ord(self.sercon.read(1))
        except SerialException as s_e:
            logging.error('Problem with serial communication. self.queue[0] =', self.queue)
            logging.error('Exception: %s' % str(s_e))
            byte0 = 0xFF
            byte1 = 0xFF
            byte2 = 0xFF
            byte3 = 0xFF
        if ITLA.checksum(byte0, byte1, byte2, byte3) == byte0 >> 4:
            self._error = byte0 & 0x03
            return byte0, byte1, byte2, byte3
        else:
            self._error = ITLA.CSERROR
            logging.error('CS error')
            return byte0, byte1, byte2, byte3

    def receive_simple_response(self):
        ref_time = time.clock()
        while self.sercon.inWaiting() < 4:
            if time.clock() > ref_time + 0.25:
                self._error = self.NRERROR
                return 0xFF, 0xFF, 0xFF, 0xFF
            time.sleep(0.0001)
        byte0 = ord(self.sercon.read(1))
        byte1 = ord(self.sercon.read(1))
        byte2 = ord(self.sercon.read(1))
        byte3 = ord(self.sercon.read(1))

        return byte0, byte1, byte2, byte3

    def itla_connect(self, port, baud_rate=9600):

        try:
            self.sercon = Serial(port, baud_rate, timeout=1)
        except SerialException as s_e:
            logging.error(s_e)
            return ITLA.ERROR_SERPORT
        baudrate2 = 4800
        logging.debug('Trying baud rate %d' % baud_rate)
        while baudrate2 <= 115200:
            self.itla_communicate(ITLA.REG_Nop, 0, 0)
            if self.itla_last_error() != ITLA.NOERROR:
                logging.debug('Last error: %s' % self.itla_last_error())
                # go to next baudrate
                if baudrate2 == 4800:
                    baudrate2 = 9600
                elif baudrate2 == 9600:
                    baudrate2 = 19200
                elif baudrate2 == 19200:
                    baudrate2 = 38400
                elif baudrate2 == 38400:
                    baudrate2 = 57600
                elif baudrate2 == 57600:
                    baudrate2 = 115200
                elif baudrate2 == 115200:
                    baudrate2 = 10000000
                self.sercon.close()
                logging.debug('Trying baud rate %d' % baudrate2)
                self.sercon = Serial(port, baudrate2, timeout=1)
            else:
                logging.info('Detected baud rate %d' % self.sercon.baudrate)
                logging.debug('ITLA last error: %s' % self.itla_last_error())
                return self.sercon
        self.sercon.close()
        return ITLA.ERROR_SERBAUD

    def itla_disconnect(self):
        logging.debug('Disconnecting ITLA...')
        self.sercon.close()

    def itla_communicate(self, register, data, rw, resend=False):
        """ Sends data and returns the response from the device

        :param resend: set to True to prompt the device to resend the last packet (if there was a CS error)
        :param register: the ITLA register to send data to
        :param data: an integer to send to the device
        :param rw: 0 = read, 1 = write
        :return: the device's response
        """
        lock = threading.Lock()
        lock.acquire()
        rowticket = self.maxrowticket + 1
        self.maxrowticket = self.maxrowticket + 1
        self.queue.append(rowticket)
        lock.release()
        while self.queue[0] != rowticket:
            rowticket = rowticket

        # logging.debug('Sending ' + str(data) + ' to register ' + str(hex(register)) + ', rw = ' + str(rw))

        if rw == 0:
            byte2 = int(data / 256)
            byte3 = int(data - byte2 * 256)
            self.latest_register = register
            byte1 = int(ITLA.checksum(0, register, byte2, byte3)) * 16
            if resend:
                byte1 += 8
            self.send_command(byte1, register, byte2, byte3)
            test = self.receive_response()

            b0 = test[0]
            # b1 = test[1]    # Value not used
            b2 = test[2]
            b3 = test[3]
            """
            print(hex(b0))
            print(hex(b1))
            print(hex(b2))
            print(hex(b3))
            """

            # logging.debug('Response = {0} {1} {2} {3}'.format(hex(b0), hex(b1), hex(b2), hex(b3)))

            if (b0 & 0x03) == 0x02:
                test = self.aea(b2 * 256 + b3)
                lock.acquire()
                self.queue.pop(0)
                lock.release()
                return test
            lock.acquire()
            self.queue.pop(0)
            lock.release()

            # if self._error != ITLA.NOERROR:
            #     logging.error('Device error: %s' % hex(self._error))
            #     time.sleep(0.1)
            #     nop_response = self.itla_communicate(ITLA.REG_Nop, 0, ITLA.READ)
            #     logging.error('NOP register reads %s' % hex(nop_response))

            return b2 * 256 + b3
        else:
            byte2 = int(data / 256)
            byte3 = int(data - byte2 * 256)
            self.send_command(int(ITLA.checksum(1, register, byte2, byte3)) * 16 + 1, register, byte2, byte3)
            test = self.receive_response()
            lock.acquire()
            self.queue.pop(0)
            lock.release()

            """
            print(hex(test[0]))
            print(hex(test[1]))
            print(hex(test[2]))
            print(hex(test[3]))
            """
            # logging.debug('Response = {0} {1} {2} {3}'.format(hex(test[0]), hex(test[1]), hex(test[2]), hex(test[3])))

            # if self._error != ITLA.NOERROR:
            #     logging.error('Device error: %s' % hex(self._error))
            #     time.sleep(0.1)
            #     nop_response = self.itla_communicate(ITLA.REG_Nop, 0, ITLA.READ)
            #     logging.error('NOP register reads %s' % hex(nop_response))

            return test[2] * 256 + test[3]

    def itla_signed_communicate(self, register, data, rw):
        """Treats the response of the communication as a signed 2-bit integer"""

        # Get raw response, treated as unsigned int
        resp_unsigned = int(self.itla_communicate(register, data, rw))

        # Max signed int is 2^(N-1) - 1
        max_2byte_int = 2 ** 15 - 1

        resp = resp_unsigned

        # If larger than max signed int, it is negative
        if resp_unsigned > max_2byte_int:
            resp = -1 * (2 ** 16 - resp_unsigned)

        return resp

    def itla_send_only(self, register, data, rw):
        rowticket = self.maxrowticket + 1
        self.maxrowticket = self.maxrowticket + 1
        self.queue.append(rowticket)
        while self.queue[0] != rowticket:
            time.sleep(.1)
        self.serial_lock_set()
        if rw == 0:
            self.latest_register = register
            self.send_command(int(ITLA.checksum(0, register, 0, 0)) * 16, register, 0, 0)
            self.receive_simple_response()
            self.serial_lock_unset()
        else:
            byte2 = int(data / 256)
            byte3 = int(data - byte2 * 256)
            self.send_command(int(ITLA.checksum(1, register, byte2, byte3)) * 16 + 1, register, byte2, byte3)
            self.receive_simple_response()
            self.serial_lock_unset()

    def aea(self, bytes_to_write):
        outp = ''
        while bytes_to_write > 0:
            self.send_command(int(ITLA.checksum(0, ITLA.REG_AeaEar, 0, 0)) * 16, ITLA.REG_AeaEar, 0, 0)
            test = self.receive_response()
            outp = outp + chr(test[2])
            outp = outp + chr(test[3])
            bytes_to_write = bytes_to_write - 2
        return outp

    def itla_firmware_upgrade_start(self, raydata, salvage=0):
        # set the baudrate to maximum and reconfigure the serial connection
        if salvage == 0:
            ref = ITLA.strip_string(self.itla_communicate(ITLA.REG_Serial, 0, 0))
            if len(ref) < 5:
                print('problems with communication before start FW upgrade')
                return self.sercon, 'problems with communication before start FW upgrade'
            self.itla_communicate(ITLA.REG_ResetEnable, 0, 1)
        else:
            ref = None
        self.itla_communicate(ITLA.REG_Iocap, 64, 1)  # bits 4-7 are 0x04 for 115200 baudrate
        # validate communication with the laser
        self.tempport = self.sercon.portstr
        self.sercon.close()
        self.sercon = Serial(self.tempport, 115200, timeout=1)
        if ITLA.strip_string(self.itla_communicate(ITLA.REG_Serial, 0, 0)) != ref:
            return self.sercon, 'After change baudrate: serial discrepancy found. Aborting. ' + str(
                ITLA.strip_string(self.itla_communicate(ITLA.REG_Serial, 0, 0)))
        # load the ray file
        self.raybin = raydata
        if len(self.raybin) & 0x01:
            self.raybin.append('\x00')
        self.itla_communicate(ITLA.REG_Dlconfig, 2, 1)  # first do abort to make sure everything is ok
        # print ITLALastError()
        if self.itla_last_error() != ITLA.NOERROR:
            return self.sercon, 'After dlconfig abort: error found. Aborting. ' + str(self.itla_last_error())
        # initiate the transfer; INIT_WRITE=0x0001; TYPE=0x1000; RUNV=0x0000
        # temp=ITLACommunicate(sercon,REG_Dlconfig,0x0001 ^ 0x1000 ^ 0x0000,1)
        # check temp for the correct feedback
        self.itla_communicate(ITLA.REG_Dlconfig, 3 * 16 * 256 + 1, 1)  # initwrite=1; type =3 in bits 12:15
        # print ITLALastError()
        if self.itla_last_error() != ITLA.NOERROR:
            return self.sercon, 'After dlconfig init_write: error found. Aborting. ' + str(self.itla_last_error())
        return self.sercon, ''

    def itla_upgrade_write(self, count):
        # start writing bits
        teller = 0
        while teller < count:
            self.itla_send_only(ITLA.REG_Ear, struct.unpack('>H', self.raybin[teller:teller + 2])[0], 1)
            teller = teller + 2
        self.raybin = self.raybin[count:]
        # write done. clean up
        return ''

    def itla_firmware_upgrade_complete(self):
        time.sleep(0.5)
        self.sercon.flushInput()
        self.sercon.flushOutput()
        self.itla_communicate(ITLA.REG_Dlconfig, 4, 1)  # done (bit 2)
        if self.itla_last_error() != ITLA.NOERROR:
            return self.sercon, 'After dlconfig done: error found. Aborting. ' + str(self.itla_last_error())
        # init check
        self.itla_communicate(ITLA.REG_Dlconfig, 16, 1)  # init check bit 4
        if self.itla_last_error() == ITLA.CPERROR:
            while (self.itla_communicate(ITLA.REG_Nop, 0, 0) & 0xff00) > 0:
                time.sleep(0.5)
        elif self.itla_last_error() != ITLA.NOERROR:
            return self.sercon, 'After dlconfig done: error found. Aborting. ' + str(self.itla_last_error())
        # check for valid=1
        temp = self.itla_communicate(ITLA.REG_Dlstatus, 0, 0)
        if temp & 0x01 == 0x00:
            return self.sercon, 'Dlstatus not good. Aborting. '
        # write concluding dlconfig
        self.itla_communicate(ITLA.REG_Dlconfig, 3 * 256 + 32, 1)  # init run (bit 5) + runv (bit 8:11) =3
        if self.itla_last_error() != ITLA.NOERROR:
            return self.sercon, 'After dlconfig init run and runv: error found. Aborting. ' + str(
                self.itla_last_error())
        time.sleep(1)
        # set the baudrate to 9600 and reconfigure the serial connection
        self.itla_communicate(ITLA.REG_Iocap, 0, 1)  # bits 4-7 are 0x0 for 9600 baudrate
        self.sercon.close()
        # validate communication with the laser
        self.sercon = Serial(self.tempport, 9600, timeout=1)
        ref = ITLA.strip_string(self.itla_communicate(ITLA.REG_Serial, 0, 0))
        if len(ref) < 5:
            return self.sercon, 'After change back to 9600 baudrate: serial discrepancy found. Aborting. ' + str(
                ITLA.strip_string(self.itla_communicate(ITLA.REG_Serial, 0, 0)))
        return self.sercon, ''

    @staticmethod
    def itla_split_dual(input_list, rank):
        teller = rank * 2
        return ord(input_list[teller]) * 256 + ord(input_list[teller + 1])
