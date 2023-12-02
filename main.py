import codecs
import datetime

file = open("uchiage hanabi.mid", "rb")  # Change file name here
clear = open("output.txt", "w")
clear.write("")
clear.close()
output = open("output.txt", "a")

current_time = 0
bpm = 120
tpqn = 0
note_history = []
count = 0


def read_hex(hexadecimal, start, end):
    return hexadecimal[start * 2: (end + 1) * 2]


def read_header():
    global tpqn
    header = codecs.encode(file.read(14), "hex")

    if read_hex(header, 0, 3).decode() != "4d546864":  # header is not MThd
        print("Not a MIDI file")

    if read_hex(header, 7, 7).decode() != "06":  # header chunk size is not 6
        print("Not a MIDI file")

    print(f"Format Type: {read_hex(header, 9, 9).decode()}")
    if read_hex(header, 9, 9).decode() != "00":  # format type can only be 0
        print("Format Type not supported")

    print(f"Number of tracks = {int(read_hex(header, 10, 11).decode(), 16)}")

    time_division = format(int(read_hex(header, 12, 13).decode(), 16), 'b')
    tpqn = int(read_hex(header, 12, 13), 16)
    if len(time_division) < 16:
        print(f"Clock Ticks = {tpqn} ticks / quarter note")
    else:
        frame = int(time_division[1:7], 16)
        ticks_per_frame = int(time_division[8:15], 16)
        print(f"{frame} FPS, {ticks_per_frame} ticks per frame")


def read_track_chunk():
    track_chunk = codecs.encode(file.read(8), "hex")

    if read_hex(track_chunk, 0, 3).decode() != "4d54726b":  # header is not MThd
        print("Error: Not a MIDI track chunk")

    print(f"Track Size: {int(read_hex(track_chunk, 4, 7).decode(), 16)} bytes")


def read_meta_event():
    global bpm

    meta = codecs.encode(file.read(2), "hex").decode()
    if meta == "00ff":
        event_type = codecs.encode(file.read(1), "hex").decode()

        if event_type == "58":
            print("Time Signature Meta Event detected")
            file.read(1)  # skip byte size
            values = codecs.encode(file.read(4), "hex")
            print(f"Time Signature: {int(read_hex(values, 0, 0), 16)} / {2 ** int(read_hex(values, 1, 1), 16)}")
            print(f"Metronome: {96 / int(read_hex(values, 2, 2), 16)} clicks per bar")
            if read_hex(values, 3, 3).decode() == "08":
                print("Expected 32nds value")
            else:
                print("Unexpected 32nds value. The track may be converted wrongly")

        elif event_type == "51":
            print("Set Tempo Meta Event detected")
            file.read(1)  # skip byte size
            values = codecs.encode(file.read(3), "hex")
            bpm = 60000000 / int(read_hex(values, 0, 2), 16)
            print(f"BPM: {bpm}")  # microsecond_per_minute / microseconds_per_quarter_note

        elif event_type == "03":
            print("Sequence/Track Name Meta Event detected")
            file.read(1)  # skip byte size
            string_hex = ""
            while True:
                next_hex = codecs.encode(file.read(1), "hex").decode()
                if next_hex == "00":
                    file.seek(-1, 1)
                    break
                string_hex += next_hex
            print(f"Sequence/Track Name = {bytes.fromhex(string_hex).decode()}")

        elif event_type == "2f":
            print("End of Track Meta Event detected")
        else:
            print("Meta Event not coded")
        return True
    else:
        file.seek(-2, 1)
        return False


def calculate_time(ticks):
    global bpm, tpqn
    return round(ticks / tpqn * (60 / bpm), 5)


def read_chunk_event(time_delay_size=1):
    global current_time, note_history, count

    if time_delay_size == 10:
        print(codecs.encode(file.read(time_delay_size), "hex").decode())
        print("Limit Exceeded")
        return False

    hex_vlq = ""

    for _ in range(time_delay_size):
        hex_vlq += codecs.encode(file.read(1), 'hex').decode()

    time_delay = convert_vlq_to_number(hex_vlq)

    event_type = codecs.encode(file.read(1), "hex").decode()
    if event_type == "c0":
        print(f"Instrument = {codecs.encode(file.read(1), 'hex').decode()}")
        return True

    elif event_type == "90":
        current_time += time_delay
        midi_note = int(codecs.encode(file.read(1), 'hex'), 16) + 12
        note_history.append((midi_note, current_time))
        file.read(1)
        # print(f"Note On: Delay = {time_delay}, Note = {midi_note}, Velocity = {codecs.encode(file.read(1), 'hex').decode()}")
        return True

    elif event_type == "80":
        current_time += time_delay
        midi_note = int(codecs.encode(file.read(1), 'hex'), 16) + 12
        for a, b in note_history:
            if a == midi_note:
                note_history.remove((a, b))
                # print(f"Note: {midi_note}, DelayB: {b}, Length: {current_time - b}")
                output.write(
                    f"const sound{count} = consecutively(list(silence_sound({calculate_time(b)}), custom({midi_note}, {calculate_time(current_time - b)})));\n")
                count += 1
        file.read(1)
        # print(f"Note Off: Delay = {time_delay}, Note = {midi_note}, Velocity = {codecs.encode(file.read(1), 'hex').decode()}")
        return True

    elif event_type == "ff":
        file.seek(-2, 1)
        read_meta_event()
        return False
    else:
        file.seek(-2, 1)
        return read_chunk_event(time_delay_size + 1)


def print_simultaneously(times):
    string = "return simultaneously(list("
    for _ in range(times):
        string += f"sound{_}, "
    string = string.removesuffix(", ")
    string += "));"
    return string


def convert_vlq_to_number(hex):
    binary_number = ""
    count = 0
    while True:
        binary_decoded = format(int(read_hex(hex, count, count), 16), "08b")
        if binary_decoded[0] == "0":
            binary_number += binary_decoded[1:]
            return int(binary_number, 2)
        else:
            if (count + 1) * 2 == len(hex):
                return -1
            binary_number += binary_decoded[1:]
            count += 1


def main():
    read_header()
    read_track_chunk()
    while True:
        print("###################################")
        if not read_meta_event():
            break

    while True:
        if not read_chunk_event():
            break

    total_time = current_time / tpqn * (60 / bpm)
    print("Duration: " + str(datetime.timedelta(seconds=total_time)))
    print(note_history)  # making sure note history is clear
    output.write(print_simultaneously(count))
    output.close()


main()
