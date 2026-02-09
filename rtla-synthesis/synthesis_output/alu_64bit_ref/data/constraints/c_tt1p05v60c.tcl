##########################################################################################
# Copyright (c) 2024 Synopsys, Inc. All rights reserved.
##########################################################################################

set_parasitic_parameters -library ${PARASITIC_LIB} -early_spec typTLU -late_spec typTLU

set_process_number 1.00
set_process_label tt

set_temperature 60
set_voltage 1.05 -object_list VDD
set_voltage 0.00 -object_list [get_supply_nets VSS*]

set_load 5 [all_outputs]


