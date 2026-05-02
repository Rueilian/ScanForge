#pragma once
// ScanForge — partial_scan.h
// Partial scan FF selection strategies based on SCOAP testability metrics.

#include "scan_chain.h"
#include <vector>

namespace ScanForge {

// Selection strategy for choosing which FFs to include.
enum class SelectionMode {
    SCOAP_CO,        // rank by observability (CO) — harder to observe → scan it
    SCOAP_COMBINED,  // rank by CC0+CC1+2*CO (overall hardness)
    RANDOM,          // random selection (for baseline comparison)
};

// Select `k` FF indices from data.ffs using the given strategy.
// Returns sorted list of selected indices (circuit order).
std::vector<int> selectFFs(const ScanData &data, int k,
                            SelectionMode mode = SelectionMode::SCOAP_CO,
                            unsigned seed = 42);

// Sweep partial scan ratios and print a comparison table.
// Ratios: list of fractions in (0,1], e.g. {0.25, 0.5, 0.75, 1.0}
void sweepPartialScan(const ScanData &data,
                      const std::vector<double> &ratios,
                      SelectionMode mode = SelectionMode::SCOAP_CO);

} // namespace ScanForge
