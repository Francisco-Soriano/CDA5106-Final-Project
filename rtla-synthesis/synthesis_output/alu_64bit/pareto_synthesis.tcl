# Directory Variables
set scripts_dir "./scripts/"

# set DESIGN_NAME	  <top module name>
set DESIGN_LIBRARY	  ${DESIGN_NAME}.dlib

# Pareto Synthesis Variables
set low_bound 0.01
set high_bound 5.00
set epsilon 0.01
set max_iterations 20
set num_pareto_points 15

# Analytics variables
set analytics_file "pareto_synthesis_analytics.csv"
set analytics_data {}

proc log_analytics {phase duration {extra ""}} {
    global analytics_data
    lappend analytics_data [list $phase $duration $extra]
    puts "Analytics: $phase took $duration seconds. $extra"
}

proc write_analytics_csv {} {
    global analytics_file analytics_data
    set fp [open $analytics_file w]
    puts $fp "Phase,Duration (seconds),Details"
    foreach entry $analytics_data {
        puts $fp [join $entry ","]
    }
    close $fp
    puts "Analytics written to $analytics_file"
}

proc timing_met {report_file} {
    set fp [open $report_file r]
    set content [read $fp]
    close $fp
    # Check for no "VIOLATED" or slack > 0 (adjust regex)
    if {[regexp {slack.*MET} $content]} {
        return 1
    } else {
        return 0
    }
}

# Return the combinational area from an area report
proc get_combinational_area {filename} {
    set fp [open $filename r]
    set area 0
    while {[gets $fp line] >= 0} {
        if {[regexp {^Combinational area:\s+([0-9.]+)} $line match value]} {
            set area $value
            break
        }
    }
    close $fp
    return $area
}

# Report design metrics
proc report_synthesis_results {clock_target report_dir} {
    if {![file exists "${report_dir}/${clock_target}"]} {
        file mkdir "${report_dir}/${clock_target}"
    }

    report_timing > "${report_dir}/${clock_target}/timing.rpt"
    report_qor > "${report_dir}/${clock_target}/qor.rpt"
    report_area > "${report_dir}/${clock_target}/area.rpt"
    report_resources > "${report_dir}/${clock_target}/resources.rpt"
    report_power > "${report_dir}/${clock_target}/power.rpt"
}

# After finding timing constraints for min delay and min area, determine intermediate timing constraints
proc compute_delay_targets {min_area_timing_constraint min_delay_timing_constraint} {
    global num_pareto_points
    set delay_targets {}
    set delay_increment [expr {($min_area_timing_constraint - $min_delay_timing_constraint) / ($num_pareto_points - 1)}]
    for {set i 0} {$i < $num_pareto_points} {incr i} {
        lappend delay_targets [expr {$min_delay_timing_constraint + $i * $delay_increment}]
    }
    return $delay_targets
}

################################################################################
# SCRIPT BODY
################################################################################
source -echo "$scripts_dir/setup.tcl"

set MIN_AREA_DIR "${REPORTS_DIR}/min_area_endpoint"
if [file exists ${MIN_AREA_DIR}]  {
  file delete -force ${MIN_AREA_DIR}
}
file mkdir $MIN_AREA_DIR

set MIN_DELAY_DIR "${REPORTS_DIR}/min_delay_endpoint"
if [file exists ${MIN_DELAY_DIR}]  {
  file delete -force ${MIN_DELAY_DIR}
}
file mkdir $MIN_DELAY_DIR

################################################################################
# Find minimum achievable area timing constraint
################################################################################
puts "Determining minimimum achievable area of the design..."
set start_time [clock seconds]

set tightest $high_bound
set high $high_bound
set low $low_bound

set CLK_PERIOD $high_bound
source "${scripts_dir}/run_synthesis.tcl"
report_synthesis_results $CLK_PERIOD $MIN_AREA_DIR
set min_area [get_combinational_area "$MIN_AREA_DIR/$CLK_PERIOD/area.rpt"]

reset_design
remove_block
remove_design -all

for {set i 0} {$i < $max_iterations} {incr i} {
    set mid [expr {($low + $high) / 2.0}]
    puts "Testing area at $mid ns..."
    set CLK_PERIOD $mid

    source "${scripts_dir}/run_synthesis.tcl"
    report_synthesis_results $CLK_PERIOD $MIN_AREA_DIR
    set design_area [get_combinational_area "$MIN_AREA_DIR/$CLK_PERIOD/area.rpt"]

    if {$design_area <= [expr {$min_area + $epsilon}]} {
        set tightest $mid
        set high $mid
    } else {
        set low $mid
    }

    reset_design
    remove_block
    remove_design -all

    if {abs($high - $low) < $epsilon} break
}
set min_area_timing_constraint $tightest
set end_time [clock seconds]
set duration [expr {$end_time - $start_time}]
log_analytics "Min Area Search" $duration "Min area: $min_area um^2 at $min_area_timing_constraint ns"
puts "Minimum area of $min_area um^2 found at clock period $min_area_timing_constraint ns."

################################################################################
# Find minimum achievable delay timing constraint
################################################################################
puts "Determining minimum achievable delay of design..."
set start_time [clock seconds]
set min_delay_timing_constraint $min_area_timing_constraint
set high $min_area_timing_constraint
set low $low_bound

for {set i 0} {$i < $max_iterations} {incr i} {
    set mid [expr ($low + $high) / 2.0]
    puts "Testing delay at $mid ns..."
    set CLK_PERIOD $mid
    source "${scripts_dir}/run_synthesis.tcl"

    report_synthesis_results $CLK_PERIOD $MIN_DELAY_DIR
    set timing_met [timing_met "$MIN_DELAY_DIR/$CLK_PERIOD/timing.rpt"]

    if {$timing_met} {
        set min_delay_timing_constraint $mid
        set high $mid
    } else {
        set low $mid
    }

    reset_design
    remove_block
    remove_design -all

    if {abs($high - $low) < 0.005} break
}

set end_time [clock seconds]
set duration [expr {$end_time - $start_time}]
log_analytics "Min Delay Search" $duration "Min delay constraint: $min_delay_timing_constraint ns"
    
################################################################################
# Evaluate intermediate delay constraints
################################################################################
puts "Determining ${num_pareto_points} Pareto points between $min_delay_timing_constraint ns and $min_area_timing_constraint ns."
set delay_targets [compute_delay_targets $min_area_timing_constraint $min_delay_timing_constraint]

puts "Evaluating delay targets: $delay_targets"
set point_index 1
foreach clock_period_target $delay_targets {
    set start_time [clock seconds]
    set CLK_PERIOD $clock_period_target
    puts "Synthesizing for target clock period: $CLK_PERIOD ps"

    source "${scripts_dir}/run_synthesis.tcl"

    report_synthesis_results $CLK_PERIOD $REPORTS_DIR

    set end_time [clock seconds]
    set duration [expr {$end_time - $start_time}]
    log_analytics "Pareto Point $point_index" $duration "Clock period: $CLK_PERIOD ns"

    reset_design
    remove_block
    remove_design -all
    incr point_index
}

write_analytics_csv
