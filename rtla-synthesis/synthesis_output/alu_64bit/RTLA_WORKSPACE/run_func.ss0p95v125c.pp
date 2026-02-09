set_app_var sh_continue_on_error true
set_app_var power_enable_rtl_analysis true
source RTLA_WORKSPACE/conf_func.ss0p95v125c.tcl
::pprtl::read_design_data
::pprtl::read_name_mapping
::pprtl::read_activity_files
::pprtl::compute_metrics
quit
