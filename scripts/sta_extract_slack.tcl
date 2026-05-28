# sta_extract_slack.tcl
# OpenSTA TCL template for per-FF minimum slack extraction.
# Variables must be set by the calling wrapper before sourcing this file:
#   $liberty_file  — path to NanGate45 Liberty .lib
#   $netlist_file  — path to synthesized gate-level Verilog
#   $top_module    — top module name
#   $clock_port    — clock port name in the netlist (e.g. clock, CLOCK)
#   $output_file   — output CSV path (ff_instance,min_slack)

read_liberty $liberty_file
read_verilog  $netlist_file
link_design   $top_module

# ITC'99 circuits have no SDC constraints — create a virtual clock
create_clock -name clk -period 1.0 [get_ports $clock_port]
set_input_delay  0.1 -clock clk [all_inputs]
set_output_delay 0.1 -clock clk [all_outputs]

# Collect all SDFF_X1 instances
set ff_instances {}
foreach cell [get_cells -hierarchical *] {
    set rn [get_property $cell ref_name]
    # Match all NanGate45 DFF variants: DFF_X1, DFFR_X1, DFFS_X1, DFFRS_X1,
    # SDFF_X1, SDFFR_X1, SDFFS_X1, SDFFRS_X1 (and X2 variants)
    if {[regexp {^S?DFFR?S?_X[12]$} $rn]} {
        lappend ff_instances [get_property $cell full_name]
    }
}

if {[llength $ff_instances] == 0} {
    puts "ERROR: no SDFF_X1 cells found in $top_module"
    exit 1
}

# Initialize slack dict with large value
set ff_slack [dict create]
foreach inst $ff_instances {
    dict set ff_slack $inst 9999.0
}

# Report all setup paths (max timing) — these give meaningful slack for criticality ranking
set paths [find_timing_paths -path_delay max -group_path_count 999999 -sort_by_slack]

foreach path $paths {
    set slack [get_property $path slack]
    # Walk path points; match FF instance names
    foreach pt [get_property $path points] {
        set pin_name [get_property $pt pin]
        # pin_name format: "inst_name/pin" — extract instance
        set parts [split $pin_name /]
        if {[llength $parts] < 2} continue
        set inst [join [lrange $parts 0 end-1] /]
        if {[dict exists $ff_slack $inst]} {
            set cur [dict get $ff_slack $inst]
            if {$slack < $cur} {
                dict set ff_slack $inst $slack
            }
        }
    }
}

# Write CSV
set f [open $output_file w]
puts $f "ff_instance,min_slack"
dict for {inst slack} $ff_slack {
    puts $f "$inst,$slack"
}
close $f

puts "Wrote [llength $ff_instances] FF slack entries to $output_file"
exit
