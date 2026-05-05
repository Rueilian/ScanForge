#pragma once
// ScanForge — seq_graph.h
// Sequential FF graph: cycle breaking (FVS heuristic) and depth reduction.

#include "scan_chain.h"
#include <string>
#include <utility>
#include <vector>

namespace ScanForge {

struct SeqGraphSelection {
    // Flip-flops chosen to break all detected elementary cycles (heuristic FVS).
    std::vector<int> cycle_break_ffs;
    // Additional FFs chosen to shorten long sequential paths (after cycle pass).
    std::vector<int> depth_reduction_ffs;
    // Union of the above, sorted ascending (circuit indices).
    std::vector<int> all_selected_ffs;

    int         cycle_count_raw      = 0;  // elementary cycles before minimal pruning
    int         cycle_count_minimal  = 0;  // after removing embedded supersets
    int         paths_long_recorded  = 0;  // long paths in last enumeration (≤ cap)
    std::size_t path_enum_cap_used   = 0;
    bool        edges_missing        = false;
};

// Requires ScanData::seq_edges from mergeSequentialEdgesFromVerilog() (combinational Q→D
// reachability; one edge per source FF that can reach a destination FF's D without traversing
// another FF's Q). Cycle and depth analysis use this graph as before.
// depth_threshold: maximum allowed path length in edges between FFs; paths with
// length strictly greater than this trigger the depth-reduction greedy loop.
// path_enum_cap: safety limit on how many long paths are scored per run.
SeqGraphSelection selectSequentialGraphFFs(const ScanData &data,
                                           int depth_threshold,
                                           std::size_t path_enum_cap = 500000);

void printSeqGraphReport(const ScanData &data, const SeqGraphSelection &sel);

} // namespace ScanForge
