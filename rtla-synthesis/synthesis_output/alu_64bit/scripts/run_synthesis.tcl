# if {[file exists $DESIGN_LIBRARY]} {
#   file delete -force $DESIGN_LIBRARY
# }

# create_lib \
#   -use_technology_lib $TECH_LIB \
#   -ref_libs $REFERENCE_LIBRARY \
#   $DESIGN_LIBRARY

# #Enable DMM
# set_current_mismatch_config auto_fix
# get_current_mismatch_config

################################################################################
# Read in the RTL Design
#################################################################################

analyze -format sverilog [glob ./data/rtl/*.sv]

################################################################################
# Elaborate and link the design
#################################################################################
elaborate ${DESIGN_NAME}
set_top_module ${DESIGN_NAME}

report_design_mismatch -verbose

#################################################################################
# Apply Logical Design Constraints
#################################################################################
source data/constraints/mcmm.tcl

#Report the autofloorplanning defaults
report_auto_floorplan_constraints

#Set the target utilization for rtl_opt to 0.75
set_auto_floorplan_constraints -core_utilization 0.75

#Have rtl_opt place the pins on the top edge of the design
set_block_pin_constraints -side 2 -self -allowed_layers M4

#################################################################################
# Run the rtl_opt command
#################################################################################
rtl_opt

compute_metrics -timing -congestion -power

save_lib -all