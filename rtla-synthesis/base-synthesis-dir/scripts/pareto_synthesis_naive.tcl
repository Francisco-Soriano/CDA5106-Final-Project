# Return the WNS from a timing report
proc check_violation {filename} {
    set fp [open $filename r]
    set result 0
    while {[gets $fp line] >= 0} {
        if {[regexp {VIOLATED} $line]} {
            # Split the line and find the value (assuming it's the last word)
            set words [split $line]
            set result [lindex $words end]
            close $fp
            return $result
        }
    }
    close $fp
    return 0
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

# Directory Variables
set scripts_dir "./scripts/"

# set DESIGN_NAME	  <top module name>
set DESIGN_LIBRARY	  ${DESIGN_NAME}.dlib

# Synthesis Variables
set clock_period_target 0.01
set prev_area 0
set prev_prev_area 0
set delay_targets {}

source -echo "$scripts_dir/setup.tcl"

set first_iteration 1
# Synthesize each delay point
while {1} {

    set CLK_PERIOD $clock_period_target

    puts "Synthesizing for target clock period: $CLK_PERIOD ps"

    source "${scripts_dir}/run_synthesis.tcl"

    if {![file exists "${REPORTS_DIR}/${CLK_PERIOD}"]} {
        file mkdir "${REPORTS_DIR}/${CLK_PERIOD}"
    }

    # Report Design Metrics
    report_timing > "$REPORTS_DIR/$clock_period_target/timing.rpt"
    report_qor > "$REPORTS_DIR/$clock_period_target/qor.rpt"
    report_area > "$REPORTS_DIR/$clock_period_target/area.rpt"
    report_resources > "$REPORTS_DIR/$clock_period_target/resources.rpt"
    report_power > "$REPORTS_DIR/$clock_period_target/power.rpt"

    set negative_slack [check_violation "$REPORTS_DIR/$clock_period_target/timing.rpt"]

    # If timing is violated, increase clock period target by the WNS
    if {$negative_slack != 0} {
        puts "Timing violated by $negative_slack ns, increasing target clock period."
        set clock_period_target [expr $clock_period_target - $negative_slack]

        if {$first_iteration == 1} {
            # Dynamically set delay_increment based on magnitude of negative slack
            set slack_mag [expr abs($negative_slack)]
            set delay_increment [expr $slack_mag / 200.0]
        }
        set first_iteration 0
    } else {
        puts "Timing met, increasing target clock period by $delay_increment ns."
        lappend delay_targets $clock_period_target

        set design_area [get_combinational_area "$REPORTS_DIR/$clock_period_target/area.rpt"]

        # If min area has stabilized for 3 consecutive runs, break out of loop
        if {$design_area == $prev_area && $prev_area == $prev_prev_area} {
            break
        } else {
            set prev_prev_area $prev_area
            set prev_area $design_area
        }
        set clock_period_target [expr $clock_period_target + $delay_increment]
    }

    # Clear design for next synthesis run
    reset_design
    remove_block
    remove_design -all
}

exit
