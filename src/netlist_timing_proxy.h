#pragma once

#include "timing_exclusion.h"

#include <string>

namespace ScanForge {

// Build a timing-criticality proxy from a gate-level netlist by measuring the
// combinational logic depth feeding each scan FF's D pin. Higher depth implies
// higher timing criticality.
bool buildTimingProxyFromNetlist(const std::string &netlist_path,
                                 const ScanData &data,
                                 TimingRanking &out);

} // namespace ScanForge
