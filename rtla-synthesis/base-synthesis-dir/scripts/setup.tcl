##########################################################################################
# Tool: RTL Architect
# Copyright (C) 2019-2022 Synopsys, Inc. All rights reserved.
##########################################################################################
set RTL_SOURCE_FILES		[glob -directory ./data/rtl *.v *.sv]
set TCL_MCMM_SETUP_FILE         data/constraints/mcmm.tcl

set TECH_LIB			saed32nm_1p9m_tech.ndm
set REFERENCE_LIBRARY		[glob -tails -nocomplain -directory ./data/ndm *.ndm]
set PARASITIC_LIB		saed32nm_1p9m_tech

lappend search_path {*}[list . data data/rtl data/ndm scripts data/constraints]

set REPORTS_DIR reports
if [file exists ${REPORTS_DIR}]  {
  file delete -force ${REPORTS_DIR}
}
file mkdir $REPORTS_DIR

set_host_options -max_cores 8

# Added to test
if {[file exists $DESIGN_LIBRARY]} {
  file delete -force $DESIGN_LIBRARY
}

create_lib \
  -use_technology_lib $TECH_LIB \
  -ref_libs $REFERENCE_LIBRARY \
  $DESIGN_LIBRARY

#Enable DMM
set_current_mismatch_config auto_fix
get_current_mismatch_config

# ################################################################################
# # Read in the RTL Design
# #################################################################################

# analyze -format sverilog [glob ./data/rtl/*.sv]

# ################################################################################
# # Elaborate and link the design
# #################################################################################
# elaborate ${DESIGN_NAME}
# set_top_module ${DESIGN_NAME}

# report_design_mismatch -verbose