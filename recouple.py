import argparse
import timeit


def in_file_split(input_file, delimiter):
    line = input_file.readline()
    split_list = []
    while delimiter not in line:
        split_list.append(line)
        line = input_file.readline()

    return "".join(split_list)


def remove_host_definitions(definitions, target):
    """
    :param definitions: String representing the first part of .vcd file describing waveform definitions
    :return: String representation of definitions only with only target and sim clock
    """
    split_def = definitions.split("$end")
    timescale_def = None
    for s in split_def:
        if s[:10] == "$timescale":
            timescale_def = s + "$end\n"
            break

    _, definitions = definitions.split("$scope module FPGATop $end")
    main_clock_id = definitions.split("$end")[0].split()[-2] #NOTE: requires the line directly after FPGATop to be the
                                                             #the host clock. This needs to be changed when firesim
                                                             #updates
    _, target_defs = definitions.split("$scope module {} $end".format(target)) #start from target or defs?
    target_defs_split = target_defs.split("$end")
    scope_num = 1
    upscope_num = 0
    index = -1
    clock_id_index = []
    for i in range(len(target_defs_split)):
        s = target_defs_split[i]
        if "$scope" in s:
            scope_num += 1
        elif "$upscope" in s:
            upscope_num += 1
        if scope_num == upscope_num:
            index = i
            break
        """
        if not main_clock_id:
            parsed_def = [st for st in s.split() if st]
            if parsed_def[-1] == "clock":
                main_clock_id = parsed_def[-2]
            clock_id_index.append(i)
        elif main_clock_id in s:
            clock_id_index.append(i)"""

    target_defs_split = target_defs_split[:index]

    """"
    clock_id_index.sort(reverse=True)
    for i in clock_id_index:
        target_defs_split.pop(i)
    """
    time_variable_definition = "$var wire      64 {}  time $end\n".format(main_clock_id)
    target_defs = "$scope module {} $end\n".format(target) + time_variable_definition + "$end".join(target_defs_split[:index]) + "$end\n"

    return timescale_def + target_defs, target_defs_split, main_clock_id


def trim_and_write_value_dump(id_set, input_file, output_file, real_timing_id, target_clock_id):
    current_time_values = []
    recoupled_time = 0
    original_time = 0
    #TODO: change this to take lines directly from the file instead
    """
    for line in value_dump.splitlines():
        if line:
            if line[0] == "#":
                if current_time_values:
                    output_file.write("#{}\n".format(recoupled_time))
                    output_file.write("\n".join(current_time_values) + "\n")
                    recoupled_time += 1
                    current_time_values = []
                else:
                    current_time_values = []
            elif line[0] == "b":
                _, var_id = line.split()
                if var_id in id_set:
                    current_time_values.append(line)
            else:
                var_id = line[1:]
                if var_id in id_set:
                    current_time_values.append(line)
    """
    """
    for line in value_dump.splitlines():
        if line:
            if line[0] == "#":
                original_time = line[1:]
            elif line[0] == "b":
                _, var_id = line.split()
                if var_id in id_set:
                    current_time_values.append(line)
            else:
                var_id = line[1:]
                if var_id == target_clock_id:
                    if current_time_values:
                        output_file.write("#{}\n".format(recoupled_time))
                        output_file.write("\n".join(current_time_values) + "\n")
                        output_file.write(convert_to_binary_string(original_time, 64) + " {}\n".format(real_timing_id))
                        recoupled_time += 1
                        current_time_values = []
                if var_id in id_set:
                    current_time_values.append(line)
    """
    #print(target_clock_id)
    #print(real_timing_id)
    line = input_file.readline()
    while line:
        #print(current_time_values)
        #print(repr(line))
        if line:
            if line[0] == "#":
                original_time = line[1:]
            elif line[0] == "b":
                _, var_id = line.split()
                if var_id in id_set:
                    current_time_values.append(line)
            else:
                var_id = line[1:-1]
                if var_id == target_clock_id:
                    #print("yay")
                    if current_time_values:
                        #print(current_time_values)
                        output_file.write("#{}\n".format(recoupled_time))
                        #output_file.write("\n".join(current_time_values) + "\n")
                        output_file.write("".join(current_time_values) + "\n")
                        output_file.write(convert_to_binary_string(original_time, 64) + " {}\n".format(real_timing_id))
                        recoupled_time += 1
                        current_time_values = []
                if var_id in id_set:
                    current_time_values.append(line)
            line = input_file.readline()

    return 0


def convert_to_binary_string(num, bitsize):
    """
    :param num:
    :param bitsize:
    :return: binary number in "b00...." notation, in string format
    """
    num = int(num)
    binary_num_array = [str(0) for _ in range(bitsize)]
    index = 0
    while num >= 1 and index <= bitsize:
        index += 1
        binary_num_array[-index] = str(int(num % 2))
        num = num / 2

    return "b{}".format("".join(binary_num_array))

def generate_unused_id(id_set):
    return None

def main():
    # use a library for arg parsing (arg parse) instead of basic python library
    # a lot easier to use
    parser = argparse.ArgumentParser(description="Provide file names of input, output, and target hardware to recouple"
                                                 " in format 'input target_hardware output'")
    parser.add_argument('input_filename', help='Provides input filename of decoupled waveform from firesim execution')
    parser.add_argument('target_hardware', help='Provides target hardware to be recoupled')
    parser.add_argument('output_filename', default='recoupled.vcd', help='Provides output filename to be '
                                                                         'created at the end of execution')
    args = parser.parse_args()

    if args.input_filename[-4:] != ".vcd":
        input_filename = args.input_filename + ".vcd"
    else:
        input_filename = args.input_filename
    if args.output_filename[-4:] != ".vcd":
        output_filename = args.output_filename + ".vcd"
    else:
        output_filename = args.output_filename

    input_wave_file = open(input_filename, "r")
    output_wave_file = open(output_filename, "w")
    initial_time = timeit.default_timer()

    #definitions, value_dump = input_wave_file.read().split("$enddefinitions")
    definitions = in_file_split(input_wave_file, "$enddefinitions")
    sim_header_string, sim_definitions_list, clock_id = remove_host_definitions(definitions, args.target_hardware)
    #sim_header_string, sim_definitions_list = remove_host_definitions(definitions, args.target_hardware)
    sim_header_string = sim_header_string + "$enddefinitions\n$end\n$dumpvars\n"
    output_wave_file.write(sim_header_string)
    id_set = set()
    target_clock_id = None
    for s in sim_definitions_list:
        if "$var" in s:
            s_list = [c for c in s.split() if c]
            #TODO: Remember to change this code when moving to multiclock setting
            #print(s_list[-1] == "clock")
            if s_list[-1] == "clock" and target_clock_id is None:
                target_clock_id = s_list[3]
            if s_list[3]:
                id_set.add(s_list[3])# id
    """
    if clock_id in id_set:
        id_set.remove(clock_id)
    """
    #print(id_set)
    #_, value_dump = value_dump.split("$dumpvars")
    line = input_wave_file.readline()
    while "$dumpvars" not in line:
        line = input_wave_file.readline()
    initial_time_vd = timeit.default_timer()
    trim_and_write_value_dump(id_set, input_wave_file, output_wave_file, clock_id, target_clock_id)
    time_elapsed, time_elapsed_vd = timeit.default_timer() - initial_time, timeit.default_timer() - initial_time_vd
    input_wave_file.seek(0, 2)
    throughput = (input_wave_file.tell()/10**6)/time_elapsed
    print("Time Elapsed: ", time_elapsed, " seconds")
    print(time_elapsed_vd)
    print("Throughput: ", throughput, "Mb/s")
    print("Time for 1 Gb file", 1000 / throughput)
    input_wave_file.close()
    output_wave_file.close()

# Priority
# TODO: text based method to interact with VCD -> query vcd
# TODO: Measure throughput (run with rocketchip vcd) WORK ON THIS
# Bonus
# TODO: look into possible optimizations (running online/ mapreduce methodologies)
# TODO: Try and figure out what is stalling the system -> look at the golden gate paper and keep track of queues

if __name__ == "__main__":
    main()

