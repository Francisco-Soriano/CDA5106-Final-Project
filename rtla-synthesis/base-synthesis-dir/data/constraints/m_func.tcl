##########################################################################################
# Copyright (c) 2024 Synopsys, Inc. All rights reserved.
##########################################################################################

# create_clock -name clk -period $CLK_PERIOD [get_ports clk]
# create_clock -name clk2 -period [expr 2*$CLK_PERIOD] [get_ports clk2]
# create_clock -name clk -period 1 [get_ports clk]
# create_clock -name clk2 -period 2 [get_ports clk2]

# set_clock_groups -group clk -group clk2 -asynchronous

# create_clock -name clk -period $CLK_PERIOD [get_ports clk]

# TODO: conduct study to compare results of virtual clock + i/p and o/p delay versus register-wrapped module
create_clock -name clk -period $CLK_PERIOD

set clock_ports [filter_collection [get_attribute [get_clocks] sources] object_class==port]
set input_ports [remove_from_collection [all_inputs] ${clock_ports}]

set output_ports [all_outputs]

group_path -name REGOUT -to ${output_ports}
group_path -name REGIN -from ${input_ports}
group_path -name FEEDTHROUGH -from ${input_ports} -to ${output_ports}

