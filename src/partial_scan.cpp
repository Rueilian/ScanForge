// ScanForge — partial_scan.cpp
// FF selection strategies for partial scan based on SCOAP metrics.

#include "partial_scan.h"
#include "scan_chain.h"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <random>
#include <string>

namespace ScanForge {

namespace {

const double kNormEps = 1e-12;

void minMaxRange(const std::vector<double> &v, double &mn, double &mx)
{
    mn = mx = 0.0;
    if (v.empty()) return;
    mn = mx = v[0];
    for (double x : v) {
        if (x < mn) mn = x;
        if (x > mx) mx = x;
    }
}

double normalizeVal(double x, double mn, double mx)
{
    return (x - mn) / (mx - mn + kNormEps);
}

} // namespace

std::vector<int> selectFFs(const ScanData &data, int k,
                            SelectionMode mode, unsigned seed,
                            const std::vector<double> *stressByFF,
                            double lambda)
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

    const bool wear =
        (mode == SelectionMode::SCOAP_CO_WEAR ||
         mode == SelectionMode::SCOAP_COMBINED_WEAR);
    bool stressOk = wear && stressByFF && (int)stressByFF->size() == N;

    std::vector<double> rawTest(N);
    for (int i = 0; i < N; ++i) {
        const auto &ff = data.ffs[i];
        if (mode == SelectionMode::SCOAP_CO || mode == SelectionMode::SCOAP_CO_WEAR)
            rawTest[i] = ff.co;
        else // SCOAP_COMBINED or SCOAP_COMBINED_WEAR
            rawTest[i] = ff.cc0 + ff.cc1 + 2.0 * ff.co;
    }

    double tMin, tMax;
    minMaxRange(rawTest, tMin, tMax);

    std::vector<double> score(N);
    if (!stressOk) {
        for (int i = 0; i < N; ++i)
            score[i] = rawTest[i];
    } else {
        double sMin, sMax;
        minMaxRange(*stressByFF, sMin, sMax);
        for (int i = 0; i < N; ++i) {
            double nt = normalizeVal(rawTest[i], tMin, tMax);
            double ns = normalizeVal((*stressByFF)[i], sMin, sMax);
            score[i] = nt - lambda * ns;
        }
    }

    std::stable_sort(indices.begin(), indices.end(),
        [&](int a, int b){ return score[a] > score[b]; });

    indices.resize(k);
    std::sort(indices.begin(), indices.end()); // restore circuit order
    return indices;
}

static const char *selectionModeCliName(SelectionMode mode)
{
    switch (mode) {
    case SelectionMode::SCOAP_CO:           return "co";
    case SelectionMode::SCOAP_COMBINED:     return "combined";
    case SelectionMode::RANDOM:             return "random";
    case SelectionMode::SCOAP_CO_WEAR:      return "co_wear";
    case SelectionMode::SCOAP_COMBINED_WEAR: return "combined_wear";
    default:                                return "co";
    }
}

void sweepPartialScan(const ScanData &data,
                      const std::vector<double> &ratios,
                      SelectionMode mode,
                      double lambda)
{
    int N = data.numFF;

    std::vector<double> fullStress = fullScanStressScores(data);
    const std::vector<double> *stressPtr = nullptr;
    if (mode == SelectionMode::SCOAP_CO_WEAR ||
        mode == SelectionMode::SCOAP_COMBINED_WEAR)
        stressPtr = &fullStress;

    std::cout << "\n====================================================\n";
    std::cout << "  ScanForge — Partial Scan Sweep";
    if (mode == SelectionMode::SCOAP_CO_WEAR ||
        mode == SelectionMode::SCOAP_COMBINED_WEAR)
        std::cout << " (" << selectionModeCliName(mode) << ", λ=" << std::fixed
                  << std::setprecision(2) << lambda << ")";
    else
        std::cout << " (" << selectionModeCliName(mode) << ")";
    std::cout << "\n";
    std::cout << "  Circuit FFs: " << N
              << "   Patterns: " << data.patterns.size() << "\n";
    std::cout << "====================================================\n";

    std::vector<double> stressForTbl = fullStress;

    std::cout << std::left
              << std::setw(10) << "Ratio"
              << std::setw(8)  << "K"
              << std::setw(14) << "Toggles"
              << std::setw(14) << "Activity"
              << std::setw(12) << "MaxStress"
              << std::setw(12) << "StressVar"
              << std::setw(15) << "StressImbal"
              << "Selected FFs\n";
    std::cout << std::string(95, '-') << "\n";

    for (double r : ratios) {
        int k = std::max(1, (int)std::round(r * N));
        auto chain = selectFFs(data, k, mode, 42u, stressPtr, lambda);
        auto res   = simulate(data, chain);
        auto agg   = aggregateStressForChain(stressForTbl, chain);

        std::cout << std::fixed << std::setprecision(0)
                  << std::left  << std::setw(9)  << (r * 100) + 0.5
                  << "% "
                  << std::left  << std::setw(8)  << k
                  << std::left  << std::setw(14) << res.totalToggles
                  << std::left  << std::setw(14) << std::setprecision(4) << res.switchingActivity
                  << std::left  << std::setw(12) << std::setprecision(4) << agg.maxStress
                  << std::left  << std::setw(12) << std::setprecision(4) << agg.variance
                  << std::left  << std::setw(15) << std::setprecision(4) << agg.imbalance;
        int shown = std::min((int)chain.size(), 6);
        for (int i = 0; i < shown; ++i)
            std::cout << data.ffs[chain[i]].name << (i + 1 < shown ? "," : "");
        if ((int)chain.size() > shown)
            std::cout << ",...";
        std::cout << "\n";
    }
    std::cout << "====================================================\n";
}

void sweepCoverage(const ScanData &data,
                   const std::vector<double> &ratios,
                   bool csv,
                   unsigned seed)
{
    int N = data.numFF;

    if (csv) {
        std::cout << "ratio,K,co_scoap_cov,combined_scoap_cov,random_scoap_cov,"
                     "co_ratio,combined_ratio,random_ratio\n";
    } else {
        std::cout << "\n====================================================\n";
        std::cout << "  ScanForge — Coverage Estimate Sweep\n";
        std::cout << "  Circuit FFs: " << N
                  << "   Patterns: " << data.patterns.size() << "\n";
        std::cout << "  SCOAP-weighted: sum(CO_i of scanned FFs) / sum(all CO_i)\n";
        std::cout << "  Baseline(CO ratio): K / N  (uniform-weight reference)\n";
        std::cout << "====================================================\n";
        std::cout << std::left
                  << std::setw(9)  << "Ratio"
                  << std::setw(6)  << "K"
                  << std::setw(18) << "CO(scoap)"
                  << std::setw(18) << "Combined(scoap)"
                  << std::setw(18) << "Random(scoap)"
                  << "Baseline\n";
        std::cout << std::string(77, '-') << "\n";
    }

    for (double r : ratios) {
        int k = std::max(1, (int)std::round(r * N));

        auto chainCO   = selectFFs(data, k, SelectionMode::SCOAP_CO,       seed, nullptr, 0.5);
        auto chainComb = selectFFs(data, k, SelectionMode::SCOAP_COMBINED,  seed, nullptr, 0.5);
        auto chainRand = selectFFs(data, k, SelectionMode::RANDOM,          seed, nullptr, 0.5);

        auto covCO   = estimateCoverage(data, chainCO);
        auto covComb = estimateCoverage(data, chainComb);
        auto covRand = estimateCoverage(data, chainRand);
        double baseline = (N > 0) ? (double)k / N : 0.0;

        if (csv) {
            std::cout << std::fixed << std::setprecision(2) << r << ","
                      << k << ","
                      << std::setprecision(4) << covCO.scoap_weighted   << ","
                      << covComb.scoap_weighted << ","
                      << covRand.scoap_weighted << ","
                      << covCO.patternCoverage  << ","
                      << covComb.patternCoverage << ","
                      << covRand.patternCoverage << "\n";
        } else {
            auto pct = [](double v){ return std::to_string((int)(v*100+0.5)) + "%"; };
            std::cout << std::fixed << std::setprecision(0)
                      << std::left << std::setw(8) << (std::to_string((int)(r*100+0.5)) + "%")
                      << std::left << std::setw(6) << k
                      << std::setprecision(1)
                      << std::left << std::setw(18) << pct(covCO.scoap_weighted)
                      << std::left << std::setw(18) << pct(covComb.scoap_weighted)
                      << std::left << std::setw(18) << pct(covRand.scoap_weighted)
                      << pct(baseline) << "\n";
        }
    }
    if (!csv)
        std::cout << "====================================================\n";
}

} // namespace ScanForge
