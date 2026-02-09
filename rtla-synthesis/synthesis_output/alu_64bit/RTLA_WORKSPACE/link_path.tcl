setConf REF_LIBS [list \
  saed32hvt_c.ndm \
  saed32hvt_dlvl_v.ndm \
  saed32hvt_ulvl_v.ndm \
  saed32io_wb_5v.ndm \
  saed32lvt_c.ndm \
  saed32lvt_dlvl_v.ndm \
  saed32lvt_ulvl_v.ndm \
  saed32pll_5v.ndm \
  saed32rvt_c.ndm \
  saed32rvt_dlvl_v.ndm \
  saed32rvt_ulvl_v.ndm \
  /home/net/jo045021/sp26/rtl-opt-proj/yosys-internal/rtla-synthesis/synthesis_output/alu_64bit/data/ndm/SRAM_LIB_WORKSPACE_macros.ndm \
]

lappend ::search_path .
lappend ::search_path /home/net/jo045021/sp26/rtl-opt-proj/yosys-internal/rtla-synthesis/synthesis_output/alu_64bit/data/ndm/SRAM_LIB_WORKSPACE_macros.ndm
lappend ::search_path /home/net/jo045021/sp26/rtl-opt-proj/yosys-internal/rtla-synthesis/synthesis_output/alu_64bit/data/ndm

set ::link_library *
lappend ::link_library *
lappend ::link_library saed32hvt_ss0p95v125c
lappend ::link_library saed32hvt_dlvl_ss0p75v125c_i0p95v
lappend ::link_library saed32hvt_dlvl_ss0p7v125c_i0p95v
lappend ::link_library saed32hvt_dlvl_ss0p95v125c_i0p95v
lappend ::link_library saed32hvt_ulvl_ss0p95v125c_i0p75v
lappend ::link_library saed32hvt_ulvl_ss0p95v125c_i0p7v
lappend ::link_library saed32hvt_ulvl_ss0p95v125c_i0p95v
lappend ::link_library saed32io_wb_ss0p95v125c_2p25v
lappend ::link_library saed32lvt_ss0p95v125c
lappend ::link_library saed32lvt_dlvl_ss0p75v125c_i0p95v
lappend ::link_library saed32lvt_dlvl_ss0p7v125c_i0p95v
lappend ::link_library saed32lvt_dlvl_ss0p95v125c_i0p95v
lappend ::link_library saed32lvt_ulvl_ss0p95v125c_i0p75v
lappend ::link_library saed32lvt_ulvl_ss0p95v125c_i0p7v
lappend ::link_library saed32lvt_ulvl_ss0p95v125c_i0p95v
lappend ::link_library saed32pll_ss0p95v125c_2p25v
lappend ::link_library saed32rvt_ss0p95v125c
lappend ::link_library saed32rvt_dlvl_ss0p75v125c_i0p95v
lappend ::link_library saed32rvt_dlvl_ss0p7v125c_i0p95v
lappend ::link_library saed32rvt_dlvl_ss0p95v125c_i0p95v
lappend ::link_library saed32rvt_ulvl_ss0p95v125c_i0p75v
lappend ::link_library saed32rvt_ulvl_ss0p95v125c_i0p7v
lappend ::link_library saed32rvt_ulvl_ss0p95v125c_i0p95v
lappend ::link_library RAM_1RW_128x20_max_0d95_125_ccs
lappend ::link_library RAM_1RW_128x8_max_0d95_125_ccs
lappend ::link_library RAM_1RW_64x12_max_0d95_125_ccs
lappend ::link_library RAM_1RW_64x14_max_0d95_125_ccs
# process_label : ss
# process : 0.99
# voltage : 0.9500
# temperature : 125.0000

setConf MODE "func"
setConf CORNER "ss0p95v125c"
