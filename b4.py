import csv
import sys

# CRC Polynomial for CAN: 0x4599
CRC_POLYNOMIAL = 0x4599
CRC_WIDTH = 15  # CRC-15
def parse_can_frame(row):
    """
    Parse a CAN frame from CSV row

    Args:
        row: Dictionary containing timestamp, id, ide, rtr, dlc, data, crc, errors

    Returns:
        Dictionary with parsed frame data
    """
    result = {}

    result['timestamp'] = row['timestamp']

    # Parse ID
    frame_id = int(row['id'], 16)
    result['id_value'] = frame_id

    # Check if ID is valid (11-bit max = 0x7FF = 2047)
    if frame_id > 0x7FF:
        result['id_valid'] = False
        result['id_bits'] = None
    else:
        result['id_valid'] = True
        result['id_bits'] = [(frame_id >> (10 - i)) & 1 for i in range(11)]

    # Parse IDE and RTR
    result['ide'] = int(row['ide'])
    result['rtr_bits'] = [int(row['rtr'])]

    # Parse DLC
    dlc = int(row['dlc'])
    result['dlc_valid'] = (0 <= dlc <= 8)
    result['dlc_bits'] = [(dlc >> (3 - i)) & 1 for i in range(4)]

    # Parse Data bytes
    data_str = row['data'].strip()
    if data_str:
        data_bytes = [int(x, 16) for x in data_str.split()]
        result['data_bits'] = []
        for byte in data_bytes:
            for i in range(8):
                result['data_bits'].append((byte >> (7 - i)) & 1)

        # Check if data length matches DLC
        result['data_length_match'] = (len(data_bytes) == dlc)
    else:
        result['data_bits'] = []
        result['data_length_match'] = (dlc == 0)

    # Parse expected CRC
    result['expected_crc'] = int(row['crc'], 16)

    # Parse errors
    result['errors'] = row['errors']

    return result
def calculate_crc(data_bits):
    """
    Calculate CRC-15 using polynomial 0x4599 via modulo-2 division

    Args:
        data_bits: List of bits (0 or 1) representing the data

    Returns:
        15-bit CRC value as integer
    """
    # Append 15 zeros for CRC calculation
    extended_bits = data_bits.copy() + [0] * CRC_WIDTH

    # Convert polynomial to binary representation
    # 0x4599 = 0b100010110011001 (15 bits)
    poly_value = CRC_POLYNOMIAL
    poly_bits = []
    for i in range(CRC_WIDTH + 1):
        poly_bits.append((poly_value >> (CRC_WIDTH - i)) & 1)

    # Perform modulo-2 division (XOR-based)
    for i in range(len(data_bits)):
        if extended_bits[i] == 1:
            # XOR with polynomial
            for j in range(len(poly_bits)):
                extended_bits[i + j] ^= poly_bits[j]

    # Extract the remainder (last 15 bits)
    crc_value = 0
    for i in range(CRC_WIDTH):
        crc_value = (crc_value << 1) | extended_bits[len(data_bits) + i]

    return crc_value
def validate_can_frames(csv_file):
    """
    Validate CAN frames from CSV file

    Args:
        csv_file: Path to CSV file containing CAN frames
    """
    print("=" * 90)
    print("CAN DATA FRAME CRC VALIDATOR")
    print(f"CRC Polynomial: 0x{CRC_POLYNOMIAL:04X} ")
    print("=" * 90)
    print()

    try:
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Parse the frame
                frame = parse_can_frame(row)

                # Display frame information
                print(f"{frame['timestamp']}:", end = '')


                

                # Calculate CRC if frame is structurally valid
                can_calculate = frame['id_valid'] and frame['dlc_valid']

                if can_calculate:
                    # Combine all bits for CRC calculation (exclude timestamp)
                    # Order: ID (11 bits) + RTR (1 bit) + IDE (1 bit) + 0 (1 bit, reserved=0) + DLC (4 bits) + Data
                    all_bits = frame['id_bits'] + frame['rtr_bits'] + [frame['ide']] + [0] + frame['dlc_bits'] + frame['data_bits']

                    # Calculate CRC
                    calculated_crc = calculate_crc(all_bits)

                    # Validate
                    crc_match = (calculated_crc == frame['expected_crc'])

                    # Determine error type
                    
                    if not frame['data_length_match']:
                        error_type = "mismatch_of_dlc_and_data_frame"
                    elif not crc_match:
                        error_type = "bad_crc"
                    else:
                        error_type = "none"
                else:    
                    if not frame['id_valid']:
                        error_type = "bad_id"
                    elif not frame['dlc_valid']:
                        error_type = "bad_dlc"
                # Print result (single clean print)
                print(f"THE CAN FRAME CHECK IS SUCCESS. (error: {error_type}). The given error is {frame['errors']}")
                    


            


    except FileNotFoundError:
        print(f"Error: File '{csv_file}' not found!")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python b4.py <csv_file>")
        print("\nExample: python b4.py can_frames.csv")
        sys.exit(1)

    csv_file = sys.argv[1]
    validate_can_frames(csv_file)

