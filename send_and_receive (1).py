import serial
import numpy as np
import threading
import time

# Simulation of virtual serial ports

# Mac: First install socat using, brew install socat
# Run the following command in the terminal and keep it running on the execution of code
# socat -d -d pty,raw,echo=0 pty,raw,echo=0
# You can find the port names in the terminal where you ran the socat command. 

# Windows: In this application, we are going to use com0com
# There will a zip file attched to the resouces of the application. Run setup.exe
# Open your installed folder, run setupc.exe
# Type: install PortName=COM30 PortName=COM31 to create your virtual ports

# Replace "your_port" with the port name of the sender and receiver

# To install dependencies, 
# pip install pyserial
# pip install numpy

# Now to run your code, 
# python3 send_and_receive.py

port_sender = "COM30"  # CHANGE THIS to your sender port (e.g., COM30 or /dev/pts/1)
port_receiver = "COM31"  # CHANGE THIS to your receiver port (e.g., COM31 or /dev/pts/2)

BYTE_RESET_PROBABLITY = 0.005

# ==================== PROTOCOL CONSTANTS ====================
START_BYTE = 0xAA      # Packet start marker
END_BYTE = 0x55        # Packet end marker
ACK_BYTE = 0x06        # Acknowledgment (success)
NACK_BYTE = 0x15       # Negative acknowledgment (failure)

# PWM Validation Constants
MAX_PWM = 255
MIN_PWM = 0
MAX_PWM_CHANGE = 50    # Maximum allowed change between consecutive values

# ==================== CRC CALCULATION ====================
def calculate_crc(data):
    """
    Calculate CRC-8 checksum for error detection
    Uses polynomial 0x07 (x^8 + x^2 + x + 1)
    """
    #used 0x07 because it is the smallest one among most commonly used polynomials 
    crc = 0
    for byte in data:
        crc ^= byte #done to accumulate the next element of a data packets data
        for _ in range(8):
            if crc & 0x80: #checks if the MSB is 1
                crc = (crc << 1) ^ 0x07
            else:
                crc <<= 1
            crc &= 0xFF #chops the MSB off to 8 bits
    return crc

# ==================== SENDER FUNCTION ====================
def send_data(ser: serial.Serial, data: np.ndarray) -> None:
    """
    Send PWM data with robust error detection
    
    Packet Structure:
    [START_BYTE] [DATA_LENGTH] [PWM_1] [PWM_2] ... [PWM_N] [CRC8] [END_BYTE]
    
    - START_BYTE (0xAA): Marks beginning of packet
    - DATA_LENGTH: Number of PWM values (1 byte)
    - PWM_VALUES: Array of PWM values (1 byte each)
    - CRC8: Error detection checksum
    - END_BYTE (0x55): Marks end of packet
    """
    
    data_to_send = []
    
    # Step 1: Add START byte
    data_to_send.append(START_BYTE)
    
    # Step 2: Add data length
    data_length = len(data)
    data_to_send.append(data_length)
    
    # Step 3: Add PWM values with range validation
    pwm_values = []
    for pwm in data:
        # Convert to integer and validate range
        pwm_value = int(pwm)
        if pwm_value < MIN_PWM:
            pwm_value = MIN_PWM
        elif pwm_value > MAX_PWM:
            pwm_value = MAX_PWM
        pwm_values.append(pwm_value)
        data_to_send.append(pwm_value)
    
    # Step 4: Calculate CRC over length + PWM data
    crc_data = bytes([data_length] + pwm_values)
    crc = calculate_crc(crc_data)
    data_to_send.append(crc)
    
    # Step 5: Add END byte
    data_to_send.append(END_BYTE)
    
    # For challenge question - simulate random bit corruption
    '''for i in range(len(data_to_send)):
        if np.random.random() < BYTE_RESET_PROBABLITY:
            data_to_send[i] = 0x00'''
    
    # Step 6: Send data one byte at a time (as required)
    for byte in data_to_send:
        ser.write(bytes([byte]))

# ==================== RECEIVER FUNCTION ====================
def receive_data(ser: serial.Serial) -> tuple[np.ndarray, bool]:
    """
    Receive PWM data and validate using CRC
    
    Returns:
        - received_pwm_data: numpy array of PWM values (empty if error)
        - acknowledgement: True if valid, False if corrupted
    """
    
    received_pwm_data = []
    acknowledgement = False
    
    try:
        # Step 1: Wait for START byte
        while True:
            byte = ser.read(1)
            if len(byte) == 0:  # Timeout
                return np.array([]), False
            if byte[0] == START_BYTE:
                break
        
        # Step 2: Read data length
        length_byte = ser.read(1)
        if len(length_byte) == 0:
            return np.array([]), False
        data_length = length_byte[0]
        
        # Sanity check: reasonable data length
        if data_length == 0 or data_length > 200:
            return np.array([]), False
        
        # Step 3: Read PWM values
        pwm_values = []
        for _ in range(data_length):
            pwm_byte = ser.read(1)
            if len(pwm_byte) == 0:
                return np.array([]), False
            pwm_values.append(pwm_byte[0])
        
        # Step 4: Read CRC
        crc_byte = ser.read(1)
        if len(crc_byte) == 0:
            return np.array([]), False
        received_crc = crc_byte[0]
        
        # Step 5: Read END byte
        end_byte = ser.read(1)
        if len(end_byte) == 0 or end_byte[0] != END_BYTE:
            return np.array([]), False
        
        # Step 6: Validate CRC
        crc_data = bytes([data_length] + pwm_values)
        calculated_crc = calculate_crc(crc_data)
        
        if calculated_crc != received_crc:
            # CRC mismatch - data corrupted
            print("CRC Error")
            return np.array(pwm_values), False  # Return data but mark as failed
        
        # Step 7: Range validation on all PWM values
        valid = True
        for pwm in pwm_values:
            if pwm < MIN_PWM or pwm > MAX_PWM:
                print("Range Error")
                valid = False
                break
        
        if not valid:
            return np.array(pwm_values), False
        
        # Step 8: All checks passed!
        received_pwm_data = pwm_values
        acknowledgement = True
        print("CRC Valid")
        
    except Exception as e:
        print(f"    ⚠️  Receive Error: {e}")
        return np.array([]), False
    
    return np.array(received_pwm_data), acknowledgement

# ==================== THREADING FUNCTIONS ====================
def receive_thread_task(received_data: list, no_of_success: int):
    no_of_tries = 0
    try:
        with serial.Serial(port_receiver, 9600, timeout=0.2) as ser:
            while len(received_data) < 100 and no_of_tries < 150:
                print(f"[RECEIVER] [{no_of_tries}] Trying to Receive Data")

                received_arr, acknowledgement = receive_data(ser)
                
                if np.any(received_arr) or acknowledgement:
                    received_data.append(received_arr)
                    if acknowledgement:
                        print(f"[RECEIVER] [{len(received_data)}] SUCCESS")
                        no_of_success[0] += 1
                    else: 
                        print(f"[RECEIVER] [{len(received_data)}] FAILED")
                no_of_tries += 1
                time.sleep(0.01) 
            else: 
                print(f"[RECEIVER] Time Out")
    except Exception as e:
        print(f"Receiver Thread Error: {e}")

def send_thread_task(all_data):
    try: 
        with serial.Serial(port_sender, 9600) as ser:
            for i, data in enumerate(all_data):
                send_data(ser, data)
                print(f"[SENDER]   [{i+1}] Packet Sent")
                time.sleep(0.15) 
    except Exception as e:
        print(f"Sender Thread Error: {e}")

def generate_pwm():
    pwm = np.random.randint(0, 255, size=(100,))
    return pwm

# ==================== MAIN FUNCTION ====================
def main():
    print("=" * 60)
    print("PWM DATA TRANSMISSION WITH CRC AND VALIDATION")
    print("=" * 60)
    print(f"Sender Port:   {port_sender}")
    print(f"Receiver Port: {port_receiver}")
    print(f"Corruption Probability: {BYTE_RESET_PROBABLITY * 100}%")
    print("=" * 60)
    print()

    pwm_data = [generate_pwm() for i in range(100)]
    received_data = []
    no_of_success = [0]

    receiver_thread = threading.Thread(target=receive_thread_task, args=(received_data, no_of_success))
    receiver_thread.daemon = True
    receiver_thread.start()

    time.sleep(1)

    sender_thread = threading.Thread(target=send_thread_task, args=(pwm_data,))
    sender_thread.daemon = True
    sender_thread.start()

    time.sleep(1)

    sender_thread.join(timeout=30)
    receiver_thread.join(timeout=30)

    print()
    print("=" * 60)
    print(f"FINAL RESULTS: {no_of_success[0]}/100 Successful")
    print(f"Success Rate: {no_of_success[0]}%")
    print("=" * 60)

if __name__ == "__main__":
    main()
