// ScanForge — partial_scan.cpp
// FF selection strategies for partial scan based on SCOAP metrics.

#include "partial_scan.h"
#include "scan_chain.h"

#include <algorithm>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <random>

namespace ScanForge {

std::vector<int> selectFFs(const ScanData &data, int k,
                            SelectionMode mode, unsigned seed)
{
    int N = data.numFF;
    if (k <= 0) k = 0;
    if (k > N)  k = N;

    std::vector<int> indices(N);
    std::iota(indices.begin(), indices.end(), 0);

    if (mode == SelectionMode::RANDOM) {
        std::mt19937 rng(seed);
        std::shuffle(indices.begin(), indices.end(), rng);
        indices.resize(k);
        std::sort(indices.begin(), indices.end()); // restore circuit order
        return indices;
    }

    // Score each FF; higher score = harder to test = higher priority for scanning
    std::vector<double> score(N);
    for (int i = 0; i < N; ++i) {
        const auto &ff = data.ffs[i];
        if (mode == SelectionMode::SCOAP_CO)
            score[i] = ff.co;
        else // SCOAP_COMBINED
            score[i] = ff.cc0 + ff.cc1 + 2.0 * ff.co;
    }

    // Sort by descending score (ties broken by index)
    std::stable_sort(indices.begin(), indices.end(),
        [&](int a, int b){ return score[a] > score[b]; });

    indices.resize(k);
    std::sort(indices.begin(), indices.end()); // restore circuit order
    return indices;
}

void sweepPartialScan(const ScanData &data,
                      const std::vector<double> &ratios,
                      SelectionMode mode)
{
    int N = data.numFF;
    const char *modeStr =
        (mode == SelectionMode::SCOAP_CO)       ? "SCOAP-CO" :
        (mode == SelectionMode::SCOAP_COMBINED) ? "SCOAP-Combined" : "Random";

    std::cout << "\n====================================================\n";
    std::cout << "  ScanForge — Partial Scan Sweep (" << modeStr << ")\n";
    std::cout << "  Circuit FFs: " << N
              << "   Patterns: " << data.patterns.size() << "\n";
    std::cout << "====================================================\n";
    std::cout << std::left
              << std::setw(10) << "Ratio"
              << std::setw(8)  << "K"
              << std::setw(16) << "ShiftCycles"
              << std::setw(12) << "Toggles"
              << std::setw(16) << "SwitchActivity"
              << "Selected FFs\n";
    std::cout << std::string(80, '-') << "\n";

    for (double r : ratios) {
        int k = std::max(1, (int)std::round(r * N));
        auto chain = selectFFs(data, k, mode);
        auto res   = simulate(data, chain);

        std::cout << std::fixed << std::setprecision(0)
                  << std::left  << std::setw(9)  << (r * 100) + 0.5
                  << "% "
                  << std::left  << std::setw(8)  << k
                  << std::left  << std::setw(16) << res.totalShiftCycles
                  << std::left  << std::setw(12) << res.totalToggles
                  << std::left  << std::setw(16) << std::setprecision(4) << res.switchingActivity;
        // Print selected FF names (truncated if many)
        int shown = std::min((int)chain.size(), 6);
        for (int i = 0; i < shown; ++i)
            std::cout << data.ffs[chain[i]].name << (i+1<shown ? "," : "");
        if ((int)chain.size() > shown)
            std::cout << ",...";
        std::cout << "\n";
    }
    std::cout << "====================================================\n";
}

} // namespace ScanForge
