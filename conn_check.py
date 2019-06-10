import serial

conn = serial.Serial('COM2', 115200, timeout=4)

print(conn)

conn.write(bytearray([0] * 4))

for i in range(4):
    byte = ord(conn.read(1))
    print(byte)

conn.close()
