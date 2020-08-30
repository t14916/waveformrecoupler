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


def extract_hierarchy_information(vars):
    scoped_vars = []
    for var in vars:
        scoped_vars.append(var.split('.'))

    vars_dict = []
    for sv in scoped_vars:
        if len(sv) > 1:
            vars_dict.append((sv[-1], sv[:-1]))
        else:
            vars_dict.append(([sv[0]], ()))

    return vars_dict#, var_list


def check_scopes(scope_list, var_scope):
    exact_scoping = True
    if len(var_scope) == 0:
        exact_scoping = False
        var_scope = ['target']

    index = 0
    for s in scope_list:
        if index > len(var_scope):
            return exact_scoping
        if s == var_scope[index]:
            index += 1
        elif index > 0:
            return False
    return True


def extract_relevant_ids(definitions, vars):
    """
    :param definitions: String representing the variable descripotions in .vcd
    :param var_names: list of variables to extract in formation scope.subscope.var_name (can give more scope info)
    :return: dictionary of
    """

    # Just a list of tuples, not actual dictionary to support multiple items with the same dictionary
    vars_dict = extract_hierarchy_information(vars)
    vars_dict_keys = [e[0] for e in vars_dict]
    vars_dict_items = [e[1] for e in vars_dict]
    split_def = definitions.split("$end")
    scope_list = ['emul']
    id_dict = dict()
    for i in range(len(split_def)):
        s = split_def[i]
        parsed_def = [st for st in s.split() if st]
        if '$upscope' in s:
            #print(scope_list)
            scope_list.pop()
        elif '$scope' in s:
            curr_scope = parsed_def[-1]
            #print(curr_scope)
            scope_list.append(curr_scope)
        elif '$var' in s:
            var = parsed_def[4]
            if var not in vars_dict_keys:
                pass
            else:
                indices = []
                for i in range(len(vars_dict_keys)):
                    if var == vars_dict_keys[i]:
                        indices.append(i)
                for index in indices:
                    if check_scopes(scope_list, vars_dict_items[index]):
                        var = ".".join(scope_list[:] + [var])
                        if var not in id_dict.keys():
                            id_dict[var] = parsed_def[3]

    if len(vars) != len(id_dict.keys()):
        return None
    return id_dict


def all_same_id(id_dict):
    ids = [a[1] for a in id_dict.items()]
    for i in range(len(ids)):
        for j in range(len(ids)):
            if ids[i] != ids[j]:
                return False
    return True


def operate_on_value_dump(id_dict, input_file, operator, time_range=None):
    id_list = [item[1] for item in id_dict.items()]
    value_dict = dict()
    accumulated_value_dict = dict()
    line = input_file.readline()
    prev_time = '0'
    time_lock = False
    while line:
        line = line[:-1] # gets rid of newline character
        if line[0] == "#":
            time = line[1:]
            if time_range:
                if time_range[0] <= int(prev_time) <= time_range[1]:
                    time_lock = False
                    accumulated_value_dict[prev_time] = accumulate_values(value_dict, operator)
                if int(prev_time) < time_range[0]:
                    time_lock = True
                elif int(prev_time) > time_range[1]:
                    return accumulated_value_dict
            else:
                accumulated_value_dict[prev_time] = accumulate_values(value_dict, operator)
            prev_time = time
        elif time_lock:
            pass
        elif line[0] == "b":
            var_data, var_id = line.split()
            if var_id[:len(var_id)] in id_list:
                value_dict[var_id] = "'0{}'".format(var_data)
        else:
            var_id = line[1:]
            var_data = line[0]
            if var_id in id_list:
                value_dict[var_id] = "'{}'".format(var_data)
        line = input_file.readline()

    return accumulated_value_dict


def accumulate_values(value_dict, operator):
    acc_value = None
    value_list = [item[1] for item in value_dict.items()]
    #print(value_list[0])
    i = 0
    while i < len(value_list):
        #print(i)
        if 'x' in value_list[i]:
            return None  # invalid value in simulation
        if i == 0:
            if 'x' in value_list[1]:
                return None  # invalid value in simulation
            if operator[:7] == '(lambda':
                acc_value = eval(operator + '(int({}, 2), int({}, 2))'.format(value_list[0], value_list[1]))
            else:
                acc_value = eval('int({}, 2)'.format(str(value_list[0])) + operator + 'int({}, 2)'.format(str(value_list[1])))
            i += 2
        else:
            if operator[:7] == '(lambda':
                acc_value = eval(operator + '(int({}, 2), int({}, 2))'.format(acc_value, value_list[i]))
            else:
                acc_value = eval(str(acc_value) + operator + 'int({}, 2)'.format(str(value_list[i])))
            i += 1
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


def remove_host_definitions(definitions, target='target'):
    """
    :param definitions: String representing the first part of .vcd file describing waveform definitions
    :return: String representation of definitions only with only target and sim clock
    """
    # If target = None, provide definitions of all target modules

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
    #narrows down target scope
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


def trim_and_write_value_dump(id_set, input_file, output_file, real_timing_id, target_clock_ids):
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
                if var_id in target_clock_ids:
                    if current_time_values:
                        output_file.write("#{}\n".format(recoupled_time))
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
    parser = argparse.ArgumentParser(description="Provide file names of input to recouple at output"
                                                 " in format 'input output'")
    subparsers = parser.add_subparsers(help="Provides the mode of execution: either 'query' or 'recouple'")
    query_parser = subparsers.add_parser("query")
    recouple_parser = subparsers.add_parser("recouple")

    query_parser.set_defaults(mode="query")
    query_parser.add_argument('input_filename', help='Provides input filename of decoupled '
                                                     'waveform from firesim execution')
    query_parser.add_argument('var_names', nargs='+', action='extend',
                              help='Provides names of variables to be queried from VCD.\n'
                              'Can provide hierarchy information as follows:\n'
                              'target.clockBridge_clocks_0_buffer.O\n'
                              'If no information provided, variables will be chosen as first variables with\n'
                              'matching variable name in scope target')
    #query_parser.add_argument('-tm', '--target_module', default=None, help='Specify target module in firesim hierarchy')
    query_parser.add_argument('-o', '--operator', default='and',
                              help="Provides operator to be mapped across the variables "
                              "provided by var_names. Currently must be an "
                              "infix operator from the following supported list.\n"
                              "Supported Operations: and : bitwise and,"
                              "or : bitwise or, xor : bitwise xor.\n"
                              "example usage: '-o xor' signifies bitwise xor usage")
    query_parser.add_argument('-l', '--lambda-operator', default=None, action='extend', nargs='*',
                              help="Alternative operator definition using lambdas instead of infix which allows more "
                              "complex accumulation. Ex: 'lambda x,y: x and y'. Operators converted to bitwise as in -o"
                              "usage. Also overrides -o.")
    # Cares about when signals are asserted
    # how fire function works -> let's you exclude and include signals -> can define all signals which have to be high
    # decoupled helper in rocketchip
    query_parser.add_argument('-t', '--time_range', nargs=2, default=None,
                              help='Provides time range operated on, inclusive'
                              'of both bounds')
    recouple_parser.set_defaults(mode="recouple")
    recouple_parser.add_argument('input_filename', help='Provides input filename of decoupled '
                                                        'waveform from firesim execution')
    recouple_parser.add_argument('output_filename', default='recoupled.vcd', help='Provides output filename to be '
                                                                                  'created at the end of execution')

    args = parser.parse_args()
    input_filename = args.input_filename
    if args.mode == 'recouple':
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

        definitions = in_file_split(input_wave_file, "$enddefinitions")
        sim_header_string, sim_definitions_list, clock_id = remove_host_definitions(definitions)
        sim_header_string = sim_header_string + "$enddefinitions\n$end\n$dumpvars\n"

        invalid_defs = []
        target_clock_ids = []
        curr_scope = None
        id_set = set()
        for s in sim_definitions_list:
            if "$scope" in s:
                curr_scope = [c for c in s.split() if c][2]
            if "$var" in s:
                #print(repr(s))
                s_list = [c for c in s.split() if c]
                if curr_scope is not None and "clockBridge_clocks" in curr_scope:
                    if s_list[-1] == "O":
                        target_clock_ids.append(s_list[3])
                if s_list[3] != clock_id:
                    id_set.add(s_list[3])# id
                else:
                    invalid_defs.append(s)

        #print(target_clock_ids)
        #print(invalid_defs)
        #print(repr(sim_header_string.splitlines()[10]))
        if clock_id in id_set:
            id_set.remove(clock_id)

        adjusted_header_string_list = sim_header_string.splitlines()
        for inv in invalid_defs:
            def_start = inv.find("$var")
            adjusted_header_string_list.remove(inv[def_start:] + "$end")
        sim_header_string = "\n".join(adjusted_header_string_list)
        output_wave_file.write(sim_header_string)

        line = input_wave_file.readline()
        while "$dumpvars" not in line:
            line = input_wave_file.readline()

        initial_time_vd = timeit.default_timer()

        trim_and_write_value_dump(id_set, input_wave_file, output_wave_file, clock_id, target_clock_ids)

        time_elapsed, time_elapsed_vd = timeit.default_timer() - initial_time, timeit.default_timer() - initial_time_vd
        input_wave_file.seek(0, 2)
        throughput = (input_wave_file.tell()/10**6)/time_elapsed
        print("Time Elapsed: ", time_elapsed, " seconds")
        print(time_elapsed_vd)
        print("Throughput: ", throughput, "MB/s")
        print("Time for 1 GB file", 1000 / throughput)

        input_wave_file.close()
        output_wave_file.close()

    elif args.mode == 'query':

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

        #if args.target_module is not None:
        #    _, definitions, _ = remove_host_definitions(definitions, args.target_module)
        #    definitions = "$end".join(definitions)
        _, definitions = definitions.split('$scope module FPGATop $end')
        definitions = '$scope module FPGATop $end\n' + definitions
        id_dict = extract_relevant_ids(definitions, args.var_names)
        if id_dict is None:
            print(vars)
            print(id_dict.keys())
            print("Could not find all variables. Make sure that the hierarchy information is correct.")
            return
        if all_same_id(id_dict):
            print("All provided variables have the same id!!")
            return
        line = input_wave_file.readline()
        while "$dumpvars" not in line:
            line = input_wave_file.readline()

        assertion_dict = operate_on_value_dump(id_dict, input_wave_file, operator, time_range)
        assertion_data = basic_assertion_analysis(assertion_dict)

        print(assertion_dict)
        print(id_dict)
        print("Following data shows time of first/last assertion, not cycles!")
        print("Earliest Assertion:   {}".format(assertion_data[0]))
        print("Latest Assertion:     {}".format(assertion_data[1]))
        print("Number of Assertions: {}".format(assertion_data[2]))

        input_wave_file.close()

# Priority
#Throughput: 30 MB/s" ~30 - 40 seconds for 1 GB file
# Bonus
# TODO: look into possible optimizations (running online/ mapreduce methodologies)
# TODO: Try and figure out what is stalling the system -> look at the golden gate paper and keep track of queues

if __name__ == "__main__":
    main()

