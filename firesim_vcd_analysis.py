import argparse
import timeit


operations_dict = {'and': ' & ',
                   'or': ' | ',
                   'xor': ' ^ '}


def in_file_split(input_file, delimiter):
    line = input_file.readline()
    split_list = []
    while delimiter not in line:
        split_list.append(line)
        line = input_file.readline()

    return "".join(split_list)


def parse_operator(op_string):
    if op_string in operations_dict.keys():
        operator = operations_dict[op_string]
        return operator
    elif op_string[:6] == 'lambda':
        split_op_string = op_string.split()
        for i in range(len(split_op_string)):
            s = split_op_string[i]
            if s in operations_dict.keys():
                split_op_string[i] = operations_dict[s]
        return '(' + op_string + ')'
    else:
        return None


def extract_relevant_ids(definitions, var_names):
    """
    :param definitions: String representing the variable descripotions in .vcd
    :param var_names: list of variables to extract
    :return: dictionary of
    """
    split_def = definitions.split("$end")
    id_dict = dict()
    for i in range(len(split_def)):
        s = split_def[i]
        parsed_def = [st for st in s.split() if st]
        if 'var' in s:
            if parsed_def[-1] in var_names:
                id_dict[parsed_def[-1]] = parsed_def[-2]
    return id_dict


def operate_on_value_dump(id_dict, input_file, operator, time_range=None):
    id_list = [item[1] for item in id_dict.items()]
    value_dict = dict()
    accumulated_value_dict = dict()
    line = input_file.readline()

    while line:
        line = line[:-1] # gets rid of newline character
        if line[0] == "#":
            time = line[1:]
            if time_range:
                if time_range[0] <= int(time) <= time_range[1]:
                    accumulated_value_dict[time] = accumulate_values(value_dict, operator)
                if int(time) > time_range[1]:
                    return accumulated_value_dict
            else:
                accumulated_value_dict[time] = accumulate_values(value_dict, operator)
        elif line[0] == "b":
            var_data, var_id = line.split()
            if var_id[:len(var_id)] in id_list:
                value_dict[var_id] = var_data
        else:
            var_id = line[1:]
            var_data = line[0]
            if var_id in id_list:
                value_dict[var_id] = var_data
        line = input_file.readline()

    return accumulated_value_dict


def accumulate_values(value_dict, operator):
    acc_value = None
    value_list = [item[1] for item in value_dict.items()]
    for i in range(1, len(value_list)):
        if i == 1:
            if operator[:7] == '(lambda':
                acc_value = eval(operator + '({}, {})'.format(value_list[0], value_list[1]))
            else:
                acc_value = eval(str(value_list[0]) + operator + str(value_list[1]))
        else:
            if operator[:7] == '(lambda':
                acc_value = eval(operator + '({}, {})'.format(acc_value, value_list[i]))
            else:
                acc_value = eval(str(acc_value) + operator + str(value_list[i]))
    return acc_value

def basic_assertion_analysis(assertion_data):
    first_assert = None
    last_assert = None
    num_assertions = 0

    for e in assertion_data.items():
        if e[1]:
            if first_assert is None:
                first_assert = e[0]
            last_assert = e[0]
            num_assertions += 1

    return first_assert, last_assert, num_assertions


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
    _, target_defs = definitions.split("$scope module {} $end".format(target))
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

    target_defs_split = target_defs_split[:index]

    time_variable_definition = "$var wire      64 {}  time $end\n".format(main_clock_id)
    target_defs = "$scope module {} $end\n".format(target) + time_variable_definition + "$end".join(target_defs_split[:index]) + "$end\n"

    return timescale_def + target_defs, target_defs_split, main_clock_id


def trim_and_write_value_dump(id_set, input_file, output_file, real_timing_id, target_clock_id):
    current_time_values = []
    recoupled_time = 0
    original_time = 0

    line = input_file.readline()
    while line:
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
                    if current_time_values:
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


def main():
    # use a library for arg parsing (arg parse) instead of basic python library
    # a lot easier to use
    parser = argparse.ArgumentParser(description="Provide file names of input to recouple at output"
                                                 " in format 'input output'")
    parser.add_argument('mode', help='Provides the mode of execution: either query or recouple')
    parser.add_argument('input_filename', help='Provides input filename of decoupled waveform from firesim execution')

    args = parser.parse_known_args()[0]
    input_filename = args.input_filename
    if args.mode == 'recouple':
        parser.add_argument('-tm', '--target_module', default=None, help='Provides target module to be recoupled')
        parser.add_argument('output_filename', default='recoupled.vcd', help='Provides output filename to be '
                                                                             'created at the end of execution')
        args = parser.parse_args()

        if input_filename[-4:] != ".vcd":
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
        sim_header_string, sim_definitions_list, clock_id = remove_host_definitions(definitions, 'StriderInterconnect')
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
    elif args.mode == 'query':
        parser.add_argument('var_names', nargs='+', action='extend',
                            help='Provides names of variables to be queried from VCD')
        parser.add_argument('-tm', '--target_module', default=None, help='Specify target module in firesim hierarchy')
        parser.add_argument('-o', '--operator', default='and',
                            help="Provides operator to be mapped across the variables "
                                 "provided by var_names. Currently must be an "
                                 "infix operator from the following supported list.\n"
                                 "Supported Operations: and : bitwise and,"
                                 "or : bitwise or, xor : bitwise xor.\n"
                                 "example usage: '-o xor' signifies bitwise xor usage")
        parser.add_argument('-l', '--lambda-operator', default=None, action='extend', nargs='*',
                            help="Alternative operator definition using lambdas instead of infix which allows more complex "
                                 "accumulation. Ex: 'lambda x,y: x and y'. Operators converted to bitwise as in -o usage."
                                 "Overrides -o.")

        # Cares about when signals are asserted
        # how fire function works -> let's you exclude and include signals -> can define all signals which have to be high
        # decoupled helper in rocketchip
        parser.add_argument('-t', '--time_range', nargs=2, default=None,
                            help='Provides time range operated on, inclusive'
                                 'of both bounds')
        args = parser.parse_args()
        if input_filename[-4:] != ".vcd":
            input_filename = args.input_filename + ".vcd"
        else:
            input_filename = args.input_filename

        time_range = None
        if args.time_range:
            time_range = [int(s) for s in args.time_range]

        input_wave_file = open(input_filename, "r")
        if args.lambda_operator is None:
            operator = parse_operator(args.operator)
        else:
            operator = parse_operator(" ".join(args.lambda_operator))

        assert operator is not None, "Invalid operator, run 'python query_vcd.py -h' for more info"

        definitions = in_file_split(input_wave_file, "$enddefinitions")
        if args.target_module is not None:
            _, definitions, _ = remove_host_definitions(definitions, args.target_module)
            definitions = "$end".join(definitions)

        id_dict = extract_relevant_ids(definitions, args.var_names)
        line = input_wave_file.readline()
        while "$dumpvars" not in line:
            line = input_wave_file.readline()

        if time_range:
            assertion_data = basic_assertion_analysis(
                operate_on_value_dump(id_dict, input_wave_file, operator, time_range))
        else:
            assertion_data = basic_assertion_analysis(
                operate_on_value_dump(id_dict, input_wave_file, operator, time_range))

        print("Following data shows time of first/last assertion, not cycles!")
        print("Earliest Assertion:   {}".format(assertion_data[0]))
        print("Latest Assertion:     {}".format(assertion_data[1]))
        print("Number of Assertions: {}".format(assertion_data[2]))

        input_wave_file.close()

# Priority
# TODO: Measure throughput (run with rocketchip vcd) WORK ON THIS
# Bonus
# TODO: look into possible optimizations (running online/ mapreduce methodologies)
# TODO: Try and figure out what is stalling the system -> look at the golden gate paper and keep track of queues

if __name__ == "__main__":
    main()

