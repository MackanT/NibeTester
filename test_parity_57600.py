"""
Test 57600 baud with all parity settings
"""
import serial
import time

SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE = 57600

parity_modes = {
    'NONE': serial.PARITY_NONE,
    'EVEN': serial.PARITY_EVEN,
    'ODD': serial.PARITY_ODD,
}

print("Testing 57600 baud with different parity settings")
print("="*70)

for parity_name, parity_value in parity_modes.items():
    print(f"\nTesting PARITY_{parity_name}...")
    
    try:
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUDRATE,
            bytesize=serial.EIGHTBITS,
            parity=parity_value,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1
        )
        
        # Collect data for 3 seconds
        start = time.time()
        buffer = bytearray()
        
        while (time.time() - start) < 3.0:
            data = ser.read(100)
            if data:
                buffer.extend(data)
        
        ser.close()
        
        # Analysis
        c0_count = buffer.count(0xC0)
        
        print(f"  Total bytes: {len(buffer)}")
        print(f"  0xC0 start bytes: {c0_count}")
        
        if buffer:
            # Show first 32 bytes
            sample = ' '.join([f'{b:02X}' for b in buffer[:32]])
            print(f"  First 32 bytes: {sample}")
            
            # Look for patterns around 0xC0
            if 0xC0 in buffer:
                idx = buffer.index(0xC0)
                context_start = max(0, idx - 5)
                context_end = min(len(buffer), idx + 15)
                context = buffer[context_start:context_end]
                context_hex = ' '.join([f'{b:02X}' for b in context])
                print(f"  Context around 0xC0: {context_hex}")
            
            if c0_count >= 3:
                print(f"  ✓✓✓ EXCELLENT! This looks correct!")
            elif c0_count > 0:
                print(f"  ✓ Found some 0xC0 bytes")
        else:
            print(f"  No data received")
            
    except Exception as e:
        print(f"  ERROR: {e}")

print("\n" + "="*70)
print("Use the parity setting with the most 0xC0 bytes")
