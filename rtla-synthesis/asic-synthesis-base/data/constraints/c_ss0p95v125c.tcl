##########################################################################################
# Copyright (c) 2024 Synopsys, Inc. All rights reserved.
##########################################################################################
set_parasitic_parameters -library ${PARASITIC_LIB} -early_spec maxTLU -late_spec maxTLU

set_process_number 0.99
set_process_label ss

set_temperature 125
set_voltage 0.95 -object_list VDD
set_voltage 0.00 -object_list [get_supply_nets VSS*]

set_timing_derate -early 0.95 -cell_delay -net_delay

set_load 5 [all_outputs]
 
