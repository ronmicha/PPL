import os
import sys
import re

# https://penandpants.com/2012/03/09/reading-text-tables-with-python/

delimiters = r":|::"


def union(*args):
    args = args[0]  # Extract arguments list from *args tuple
    input_validation(args, is_union=True)
    tables_structure_validation(args[0], args[1])
    with open(args[2], "w") as output_file:
        for input_file_path in [args[0], args[1]]:
            file_name = os.path.basename(input_file_path)
            with open(input_file_path, "r") as input_file:
                for line in input_file:
                    line = line.strip()
                    output_file.write("{0}:{1}\n".format(line, file_name))


def separate(*args):
    args = args[0]  # Extract arguments list from *args tuple
    input_validation(args, is_union=False)
    with open(args[1], "w") as output_file_1:
        with open(args[2], "w") as output_file_2:
            with open(args[0], "r") as input_file:
                for line in input_file:
                    split_line = re.split(delimiters, line)
                    # TODO: write to output_file_1 or output_file_2 based on last column


def distinct(*args):
    input_file_path = args[0]
    column_index = args[1]
    output_file_path = args[2]


def like(*args):
    input_file_path = args[0]
    column_index = args[1]
    regex = args[2]


def input_validation(args, is_union):
    if len(args) != 3:
        raise Exception("Wrong number of arguments. This operation requires 3 arguments")

    if not os.path.isfile(args[0]) or (is_union and not os.path.isfile(args[1])):
        raise Exception("Input arguments don't exist")

    arg_1_extension = os.path.splitext(args[0])[1]
    arg_2_extension = os.path.splitext(args[1])[1]
    arg_3_extension = os.path.splitext(args[2])[1]

    if arg_1_extension not in (".txt", ".csv") or \
                    arg_2_extension not in (".txt", ".csv") or \
                    arg_3_extension not in (".txt", ".csv"):
        raise Exception("All arguments must be txt or csv files")

    if arg_1_extension != arg_2_extension != arg_3_extension:
        raise Exception("All arguments must be of same type")


def tables_structure_validation(file_1_path, file_2_path):
    import numpy as np
    from string import digits

    file_1_structure = np.genfromtxt(file_1_path, delimiter=':', dtype=None).dtype  # TODO: delimiters?
    file_2_structure = np.genfromtxt(file_2_path, delimiter=':', dtype=None).dtype
    error_message = "The tables' format does not match"

    if len(file_1_structure) != len(file_2_structure):
        raise Exception(error_message)

    for i in range(len(file_1_structure.fields)):
        # Extract dtype name of column i and remove digits from it (so that 'string6144' == 'string8325')
        file_1_col_i_type = file_1_structure.fields.values()[i][0].name.translate(None, digits)
        file_2_col_i_type = file_2_structure.fields.values()[i][0].name.translate(None, digits)
        if file_1_col_i_type != file_2_col_i_type:
            raise Exception(error_message)


if __name__ == "__main__":
    try:
        functions_dict = \
            {
                "UNION": union,
                "SEPARATE": separate,
                "DISTINCT": distinct,
                "LIKE": like
            }

        if len(sys.argv) < 2:
            raise Exception("Missing operation. Available operations: {0}".format(", ".join(functions_dict.keys())))

        action = sys.argv[1].upper()

        if action not in functions_dict:
            raise Exception("Invalid operation {0}. Valid operations: {1}".format(action, ", ".join(functions_dict.keys())))

        functions_dict[action](sys.argv[2:])

    except Exception as ex:
        print "ERROR:", ex.message
