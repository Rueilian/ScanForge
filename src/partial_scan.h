#pragma once
// ScanForge — partial_scan.h
// Partial scan FF selection strategies based on SCOAP testability metrics.

#include "scan_chain.h"
#include <string>
#include <vector>

namespace ScanForge {

// Selection strategy for choosing which FFs to include.
enum class SelectionMode {
    SCOAP_CO,            // rank by observability (CO) — harder to observe → scan it
    SCOAP_COMBINED,      // rank by CC0+CC1+2*CO (overall hardness)
    RANDOM,              // random selection (for baseline comparison)
    SCOAP_CO_WEAR,       // normalized CO minus λ × normalized full-scan stress
    SCOAP_COMBINED_WEAR, // normalized (CC0+CC1+2*CO) minus λ × normalized stress
    // Greedy wear-leveling: min–max testability gain minus λ × max segment avg stress
    // along chain in circuit index order (requires stress + segment_window > 0).
    SCOAP_CO_WEAR_LEVELING,
    SCOAP_COMBINED_WEAR_LEVELING,
};

// SCOAP-based testability preservation proxy (not exact fault coverage).
enum class CoverageProxyMode {
    CO,               // sum(CO_sel) / sum(CO_all)
    CONTROLLABILITY,  // sum(CC0+CC1_sel) / sum(CC0+CC1_all)
    COMBINED,         // sum(CC0+CC1+2*CO sel) / sum(same all)
};

struct CoverageProxyResult {
    double proxy = 0.0;  // in [0,1] when denominators positive
    double loss  = 0.0;  // 1 - proxy
};

CoverageProxyResult computeCoverageProxy(const ScanData &data,
                                         const std::vector<int> &selected_indices,
                                         CoverageProxyMode mode);

// Select `k` FF indices from data.ffs using the given strategy.
// Returns sorted list of selected indices (circuit order).
// Wear modes require stressByFF with size data.numFF (full-scan per-FF stress scores).
// *_WEAR_LEVELING modes require stressByFF and segment_window > 0 (chain order = sorted FF index).
std::vector<int> selectFFs(const ScanData &data, int k,
                            SelectionMode mode = SelectionMode::SCOAP_CO,
                            unsigned seed = 42,
                            const std::vector<double> *stressByFF = nullptr,
                            double lambda = 0.5,
                            int segment_window = 0);

struct SweepConfig {
    bool        csv_stdout = false;
    std::string summary_csv_path;
    double      wear_lambda = 0.5;    // stress penalty weight for *_wear modes
    CoverageProxyMode coverage_proxy_mode = CoverageProxyMode::COMBINED;
    unsigned    random_seed = 42;
    std::string circuit_name;
    // Sliding-window segment stress along selected chain (0 = disabled for sweep rows)
    int         segment_window = 0;
};

// Sweep partial scan ratios and print a comparison table.
// Ratios: list of fractions in (0,1], e.g. {0.25, 0.5, 0.75, 1.0}
void sweepPartialScan(const ScanData &data,
                      const std::vector<double> &ratios,
                      SelectionMode mode,
                      const SweepConfig &cfg);

// Sweep coverage estimation across ratios, comparing all three modes.
// Prints a table: ratio | K | CO coverage | Combined coverage | Random coverage
void sweepCoverage(const ScanData &data,
                   const std::vector<double> &ratios,
                   bool csv = false,
                   unsigned seed = 42);

} // namespace ScanForge
