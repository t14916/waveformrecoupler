import argparse
from vcd_utils import *
import timeit


def main():
    recouple_parser = argparse.ArgumentParser(description="Provide file names of input to recouple at output"
                                                 " in format 'input output'")

    recouple_parser.set_defaults(mode="recouple")
    recouple_parser.add_argument('input_filename', help='Provides input filename of decoupled '
                                                        'waveform from firesim execution')
    recouple_parser.add_argument('output_filename', default='recoupled.vcd', help='Provides output filename to be '
                                                                                  'created at the end of execution')

    args = recouple_parser.parse_args()
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
            # print(repr(s))
            s_list = [c for c in s.split() if c]
            if curr_scope is not None and "clockBridge_clocks" in curr_scope:
                if s_list[-1] == "O":
                    target_clock_ids.append(s_list[3])
            if s_list[3] != clock_id:
                id_set.add(s_list[3])  # id
            else:
                invalid_defs.append(s)

    # print(target_clock_ids)
    # print(invalid_defs)
    # print(repr(sim_header_string.splitlines()[10]))
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
    throughput = (input_wave_file.tell() / 10 ** 6) / time_elapsed
    print("Time Elapsed: ", time_elapsed, " seconds")
    print(time_elapsed_vd)
    print("Throughput: ", throughput, "MB/s")
    print("Time for 1 GB file", 1000 / throughput)

    input_wave_file.close()
    output_wave_file.close()


if __name__ == "__main__":
    main()
