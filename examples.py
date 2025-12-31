"""
Example usage script for Nibe 360P communication

This demonstrates various use cases for the heat pump interface.
"""

import time
import sys
from main import NibeHeatPump
from registers_360p import NIBE_360P_REGISTERS, IMPORTANT_REGISTERS

# Try to import config, fall back to defaults
try:
    import config

    SERIAL_PORT = config.SERIAL_PORT
    READ_INTERVAL = config.READ_INTERVAL
except ImportError:
    print("Warning: config.py not found. Using defaults.")
    SERIAL_PORT = "COM3"  # Change this to your serial port
    READ_INTERVAL = 1.0


def example_basic_reading():
    """Example: Basic register reading"""
    print("\n=== Basic Register Reading ===")

    pump = NibeHeatPump(SERIAL_PORT, registers=NIBE_360P_REGISTERS)

    if not pump.connect():
        print("Failed to connect!")
        return

    try:
        time.sleep(2)  # Wait for connection

        # Read outdoor temperature
        outdoor_temp = pump.read_register(IMPORTANT_REGISTERS["outdoor_temp"])
        if outdoor_temp is not None:
            print(f"Outdoor Temperature: {outdoor_temp}°C")

        # Read supply temperature
        supply_temp = pump.read_register(IMPORTANT_REGISTERS["supply_temp"])
        if supply_temp is not None:
            print(f"Supply Temperature: {supply_temp}°C")

        # Read hot water temperature
        hw_temp = pump.read_register(IMPORTANT_REGISTERS["hot_water_temp"])
        if hw_temp is not None:
            print(f"Hot Water Temperature: {hw_temp}°C")

    finally:
        pump.disconnect()


def example_continuous_monitoring():
    """Example: Continuously monitor specific registers"""
    print("\n=== Continuous Monitoring ===")
    print("Press Ctrl+C to stop\n")

    pump = NibeHeatPump(SERIAL_PORT, registers=NIBE_360P_REGISTERS)

    # Add callback for data updates
    def on_update(register: int, name: str, value: float, unit: str):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {name}: {value} {unit}")

    pump.add_callback(on_update)

    if not pump.connect():
        print("Failed to connect!")
        return

    try:
        time.sleep(2)

        # Poll important registers every 10 seconds
        while True:
            for name, address in IMPORTANT_REGISTERS.items():
                pump.read_register(address)
                time.sleep(0.5)  # Small delay between registers

            time.sleep(10)  # Wait before next poll cycle

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        pump.disconnect()


def example_write_register():
    """Example: Write to a register (change setting)"""
    print("\n=== Write Register Example ===")

    pump = NibeHeatPump(SERIAL_PORT, registers=NIBE_360P_REGISTERS)

    if not pump.connect():
        print("Failed to connect!")
        return

    try:
        time.sleep(2)

        # Read current priority
        current_priority = pump.read_register(IMPORTANT_REGISTERS["priority"])
        print(f"Current Priority: {current_priority}")

        # Write new priority (example: set to hot water priority = 10)
        # WARNING: Only do this if you understand what it does!
        # print("Setting priority to 10 (Hot Water)...")
        # pump.write_register(IMPORTANT_REGISTERS['priority'], 10)
        # time.sleep(1)

        # Read back to confirm
        # new_priority = pump.read_register(IMPORTANT_REGISTERS['priority'])
        # print(f"New Priority: {new_priority}")

    finally:
        pump.disconnect()


def example_data_logging():
    """Example: Log data to CSV file"""
    print("\n=== Data Logging to CSV ===")
    print("Logging data to nibe_log.csv")
    print("Press Ctrl+C to stop\n")

    import csv
    from datetime import datetime

    pump = NibeHeatPump(SERIAL_PORT, registers=NIBE_360P_REGISTERS)

    if not pump.connect():
        print("Failed to connect!")
        return

    # Open CSV file
    with open("nibe_log.csv", "w", newline="") as csvfile:
        fieldnames = ["timestamp", "register", "name", "value", "unit"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        def on_update(register: int, name: str, value: float, unit: str):
            row = {
                "timestamp": datetime.now().isoformat(),
                "register": register,
                "name": name,
                "value": value,
                "unit": unit,
            }
            writer.writerow(row)
            csvfile.flush()  # Ensure data is written
            print(f"Logged: {name} = {value} {unit}")

        pump.add_callback(on_update)

        try:
            time.sleep(2)

            # Poll registers continuously
            while True:
                for address in [40004, 40008, 40012, 40013, 43005]:
                    pump.read_register(address)
                    time.sleep(0.5)

                time.sleep(30)  # Log every 30 seconds

        except KeyboardInterrupt:
            print("\nStopping logging...")
        finally:
            pump.disconnect()


def example_alarm_monitoring():
    """Example: Monitor for alarms"""
    print("\n=== Alarm Monitoring ===")
    print("Monitoring for alarms... Press Ctrl+C to stop\n")

    pump = NibeHeatPump(SERIAL_PORT, registers=NIBE_360P_REGISTERS)

    if not pump.connect():
        print("Failed to connect!")
        return

    try:
        time.sleep(2)

        last_alarm = None

        while True:
            # Read alarm register
            alarm = pump.read_register(IMPORTANT_REGISTERS["alarm"])

            if alarm is not None and alarm != 0:
                if alarm != last_alarm:
                    print(f"⚠️  ALARM DETECTED! Code: {int(alarm)}")
                    last_alarm = alarm
                    # Here you could send notification, email, etc.
            else:
                if last_alarm is not None:
                    print("✓ Alarm cleared")
                last_alarm = alarm

            time.sleep(5)  # Check every 5 seconds

    except KeyboardInterrupt:
        print("\nStopping alarm monitoring...")
    finally:
        pump.disconnect()


def example_temperature_dashboard():
    """Example: Simple console dashboard"""
    print("\n=== Temperature Dashboard ===")
    print("Press Ctrl+C to stop\n")

    pump = NibeHeatPump(SERIAL_PORT, registers=NIBE_360P_REGISTERS)

    if not pump.connect():
        print("Failed to connect!")
        return

    try:
        time.sleep(2)

        while True:
            # Clear screen (works on most terminals)
            print("\033[2J\033[H", end="")

            print("═" * 60)
            print("            NIBE 360P TEMPERATURE DASHBOARD")
            print("═" * 60)
            print()

            # Read and display temperatures
            outdoor = pump.read_register(40004)
            supply = pump.read_register(40008)
            return_temp = pump.read_register(40012)
            hot_water = pump.read_register(40013)
            degree_min = pump.read_register(43005)
            comp_freq = pump.read_register(43136)

            print(
                f"  Outdoor Temperature:     {outdoor:6.1f} °C"
                if outdoor
                else "  Outdoor Temperature:     N/A"
            )
            print(
                f"  Supply Temperature:      {supply:6.1f} °C"
                if supply
                else "  Supply Temperature:      N/A"
            )
            print(
                f"  Return Temperature:      {return_temp:6.1f} °C"
                if return_temp
                else "  Return Temperature:      N/A"
            )
            print(
                f"  Hot Water Temperature:   {hot_water:6.1f} °C"
                if hot_water
                else "  Hot Water Temperature:   N/A"
            )
            print()
            print(
                f"  Degree Minutes:          {degree_min:6.1f} DM"
                if degree_min
                else "  Degree Minutes:          N/A"
            )
            print(
                f"  Compressor Frequency:    {comp_freq:6.0f} Hz"
                if comp_freq
                else "  Compressor Frequency:    N/A"
            )
            print()
            print("─" * 60)
            print(f"  Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print("  Press Ctrl+C to exit")
            print("═" * 60)

            time.sleep(5)  # Update every 5 seconds

    except KeyboardInterrupt:
        print("\n\nExiting dashboard...")
    finally:
        pump.disconnect()


def main():
    """Main menu"""
    print("=" * 60)
    print("        Nibe 360P Heat Pump Examples")
    print("=" * 60)
    print()
    print("Select an example to run:")
    print()
    print("  1. Basic Register Reading")
    print("  2. Continuous Monitoring")
    print("  3. Write Register (Advanced)")
    print("  4. Data Logging to CSV")
    print("  5. Alarm Monitoring")
    print("  6. Temperature Dashboard")
    print("  7. Read All Registers Once")
    print()
    print("  0. Exit")
    print()

    try:
        choice = input("Enter your choice (0-7): ").strip()

        if choice == "1":
            example_basic_reading()
        elif choice == "2":
            example_continuous_monitoring()
        elif choice == "3":
            example_write_register()
        elif choice == "4":
            example_data_logging()
        elif choice == "5":
            example_alarm_monitoring()
        elif choice == "6":
            example_temperature_dashboard()
        elif choice == "7":
            pump = NibeHeatPump(SERIAL_PORT, registers=NIBE_360P_REGISTERS)
            if pump.connect():
                time.sleep(2)
                pump.read_all_registers(interval=0.5)
                pump.disconnect()
        elif choice == "0":
            print("Goodbye!")
            sys.exit(0)
        else:
            print("Invalid choice!")

    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
