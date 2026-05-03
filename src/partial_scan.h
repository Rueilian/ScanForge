#pragma once
// ScanForge — partial_scan.h
// Partial scan FF selection strategies based on SCOAP testability metrics.

#include "scan_chain.h"
#include <vector>

namespace ScanForge {

// Selection strategy for choosing which FFs to include.
enum class SelectionMode {
    SCOAP_CO,          // rank by observability (CO) — harder to observe → scan it
    SCOAP_COMBINED,    // rank by CC0+CC1+2*CO (overall hardness)
    RANDOM,            // random selection (for baseline comparison)
    SCOAP_CO_WEAR,     // normalized CO minus λ × normalized full-scan stress
    SCOAP_COMBINED_WEAR, // normalized (CC0+CC1+2*CO) minus λ × normalized stress
};

// Select `k` FF indices from data.ffs using the given strategy.
// Returns sorted list of selected indices (circuit order).
// Wear modes require stressByFF with size data.numFF (full-scan per-FF stress scores).
std::vector<int> selectFFs(const ScanData &data, int k,
                            SelectionMode mode = SelectionMode::SCOAP_CO,
                            unsigned seed = 42,
                            const std::vector<double> *stressByFF = nullptr,
                            double lambda = 0.5);

// Sweep partial scan ratios and print a comparison table.
// Ratios: list of fractions in (0,1], e.g. {0.25, 0.5, 0.75, 1.0}
void sweepPartialScan(const ScanData &data,
                      const std::vector<double> &ratios,
                      SelectionMode mode = SelectionMode::SCOAP_CO,
                      double lambda = 0.5);

// Sweep coverage estimation across ratios, comparing all three modes.
// Prints a table: ratio | K | CO coverage | Combined coverage | Random coverage
void sweepCoverage(const ScanData &data,
                   const std::vector<double> &ratios,
                   bool csv = false,
                   unsigned seed = 42);

} // namespace ScanForge
