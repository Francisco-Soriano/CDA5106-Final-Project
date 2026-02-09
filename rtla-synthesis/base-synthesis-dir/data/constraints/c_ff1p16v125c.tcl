##########################################################################################
# Copyright (c) 2024 Synopsys, Inc. All rights reserved.
##########################################################################################

set_parasitic_parameters -library ${PARASITIC_LIB} -early_spec minTLU -late_spec minTLU

set_process_number 1.01
set_process_label ff

set_temperature 125
set_voltage 1.16 -object_list VDD
set_voltage 0.00 -object_list [get_supply_nets VSS*]

set_timing_derate -late 1.05 -cell_delay -net_delay

set_load 5 [all_outputs]
