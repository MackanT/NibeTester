"""
Test sending a read request to the pump (master/slave model)
The pump might be a slave that only responds when queried
"""

import serial
import time

SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE = 57600


def create_read_request(register: int) -> bytes:
    """Create a Nibe read request: C0 69 02 <addr_low> <addr_high> <checksum>"""
    data = bytearray(
        [
            0xC0,  # Start byte
            0x69,  # Read command
            0x02,  # Length: 2 bytes (address)
            register & 0xFF,  # Address low
            (register >> 8) & 0xFF,  # Address high
        ]
    )

    # Calculate XOR checksum
    checksum = 0
    for b in data:
        checksum ^= b
    data.append(checksum)

    return bytes(data)


print("=" * 70)
print("MASTER/SLAVE TEST: Send query, wait for response")
print("=" * 70)
print("Testing if pump is a slave device that only responds to queries\n")

ser = serial.Serial(
    port=SERIAL_PORT,
    baudrate=BAUDRATE,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=0.5,
)

# Flush any existing data
ser.reset_input_buffer()
ser.reset_output_buffer()
time.sleep(0.5)

# Send read request for register 40004 (outdoor temp)
request = create_read_request(40004)
print(f"Sending read request for register 40004:")
print(f"  Hex: {request.hex(' ').upper()}")
print(f"  Bytes: {list(request)}\n")

ser.write(request)
ser.flush()

print("Waiting for response (3 seconds)...\n")
time.sleep(3.0)

# Read response
response = ser.read(100)

ser.close()

if response:
    print(f"✓ Received {len(response)} bytes:")

    # Show hex dump
    for i in range(0, len(response), 16):
        chunk = response[i : i + 16]
        hex_str = " ".join([f"{b:02X}" for b in chunk])
        ascii_str = "".join([chr(b) if 32 <= b < 127 else "." for b in chunk])
        print(f"  {i:04X}:  {hex_str:<48}  {ascii_str}")

    # Check for 0xC0 start byte
    if 0xC0 in response:
        idx = response.index(0xC0)
        print(f"\n✓ Found 0xC0 at position {idx}")

        if idx + 3 < len(response):
            cmd = response[idx + 1]
            length = response[idx + 2]
            print(f"  Command: 0x{cmd:02X}, Length: {length}")

            expected_len = 3 + length + 1
            if len(response) >= idx + expected_len:
                msg = response[idx : idx + expected_len]

                # Checksum
                calc_cs = 0
                for b in msg[:-1]:
                    calc_cs ^= b
                actual_cs = msg[-1]

                print(
                    f"  Checksum: 0x{actual_cs:02X}, Calculated: 0x{calc_cs:02X} {'✓' if calc_cs == actual_cs else '✗'}"
                )

                if calc_cs == actual_cs:
                    print(f"\n  ✓✓✓ VALID RESPONSE!")
                    print(f"  The pump IS a slave device - send queries to get data!")
    else:
        print("\n✗ No 0xC0 start byte in response")
        print("  Response might be ACK/NACK or error")
else:
    print("✗ No response received")
    print("\nPossible issues:")
    print("1. Wrong baud rate or parity")
    print("2. Pump not in correct mode")
    print("3. Need to send different init sequence first")
    print("4. A/B wires swapped")

print("\n" + "=" * 70)
