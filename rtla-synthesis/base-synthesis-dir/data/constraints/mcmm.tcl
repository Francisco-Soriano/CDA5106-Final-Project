##########################################################################################
# Copyright (c) 2024 Synopsys, Inc. All rights reserved.
##########################################################################################

remove_scenarios -all
remove_modes -all
remove_corners -all

set mode_constraints(func) "m_func.tcl"

set corner_constraints(ss0p95v125c) "c_ss0p95v125c.tcl"
# set corner_constraints(ss0p95vn40c) "c_ss0p95vn40c.tcl"
# set corner_constraints(ff1p16v125c) "c_ff1p16v125c.tcl"
# set corner_constraints(ff1p16vn40c) "c_ff1p16vn40c.tcl"
# set corner_constraints(tt1p05v60c) "c_tt1p05v60c.tcl"
set scenario_constraints(func.ss0p95v125c) "s_func.ss0p95v125c.tcl"
# set scenario_constraints(func.ss0p95vn40c) "s_func.ss0p95vn40c.tcl"
# set scenario_constraints(func.ff1p16v125c) "s_func.ff1p16v125c.tcl"
# set scenario_constraints(func.ff1p16vn40c) "s_func.ff1p16vn40c.tcl"
# set scenario_constraints(func.tt1p05v60c) "s_func.tt1p05v60c.tcl"

foreach mode [array names mode_constraints] { 
    create_mode ${mode}
}

foreach corner [array names corner_constraints] {
    create_corner ${corner}
}

foreach scenario [array names scenario_constraints] {
    lassign [split ${scenario} "."] mode corner
    create_scenario -name ${scenario} -mode ${mode} -corner ${corner}
}

foreach mode [array names mode_constraints] { 
    current_mode ${mode}
    source -echo $mode_constraints(${mode})
}

foreach corner [array names corner_constraints] {
    current_corner ${corner}
    source -echo $corner_constraints(${corner})
}

foreach scenario [array names scenario_constraints] {
    current_scenario ${scenario}
    source -echo $scenario_constraints(${scenario})
}

set_scenario_status {func.ss0p95v125c} \
    -setup true -hold false \
    -leakage_power true -dynamic_power true \
    -max_transition true -max_capacitance true -min_capacitance false

# set_scenario_status {func.ss0p95vn40c} \
#     -setup true -hold false \
#     -leakage_power true -dynamic_power true \
#     -max_transition true -max_capacitance true -min_capacitance false

# set_scenario_status {func.ff1p16v125c func.ff1p16vn40c} \
#     -active false \
#     -setup false -hold true \
#     -leakage_power true -dynamic_power false \
#     -max_transition false -max_capacitance false -min_capacitance true  \
#     -active false

# set_scenario_status {func.tt1p05v60c} \
#     -active false \
#     -setup false -hold false \
#     -leakage_power true -dynamic_power true \
#     -max_transition false -max_capacitance false -min_capacitance false

set_ignored_layers -min_routing_layer M2 -max_routing_layer M4


