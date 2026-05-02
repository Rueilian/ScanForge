// ScanForge — scan_chain.cpp
// Core scan chain simulation and reporting logic.

#include "scan_chain.h"

#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>

namespace ScanForge {

// ---------------------------------------------------------------------------
// Parser
// ---------------------------------------------------------------------------

bool parseScanData(const std::string &path, ScanData &out)
{
    std::ifstream f(path);
    if (!f) {
        std::cerr << "Error: cannot open " << path << "\n";
        return false;
    }

    std::string line;
    if (!std::getline(f, line) || line.substr(0, 9) != "SCAN_DATA") {
        std::cerr << "Error: " << path << " is not a valid .sf file\n";
        return false;
    }

    out.numFF    = 0;
    out.ffs      = {};
    out.patterns = {};
    int expectedPatterns = 0;

    while (std::getline(f, line)) {
        if (line.empty()) continue;
        std::istringstream ss(line);
        std::string tok;
        ss >> tok;

        if (tok == "NUM_FF") {
            ss >> out.numFF;
            out.ffs.resize(out.numFF);
        } else if (tok == "FF_NAMES") {
            for (int i = 0; i < out.numFF; ++i)
                ss >> out.ffs[i].name;
        } else if (tok == "SCOAP") {
            for (int i = 0; i < out.numFF; ++i)
                ss >> out.ffs[i].cc0 >> out.ffs[i].cc1 >> out.ffs[i].co;
        } else if (tok == "PATTERNS") {
            ss >> expectedPatterns;
            out.patterns.reserve(expectedPatterns);
        } else if (tok == "PPI") {
            Pattern pat;
            int v;
            while (ss >> v)
                pat.ppi.push_back(static_cast<Value>(v));
            out.patterns.push_back(std::move(pat));
        } else if (tok == "PPO") {
            if (out.patterns.empty()) continue;
            int v;
            while (ss >> v)
                out.patterns.back().ppo.push_back(static_cast<Value>(v));
        }
    }

    if (out.numFF == 0 || (int)out.ffs.size() != out.numFF) {
        std::cerr << "Error: malformed .sf file — FF count mismatch\n";
        return false;
    }
    return true;
}

// ---------------------------------------------------------------------------
// Simulation
// ---------------------------------------------------------------------------

ScanResult simulate(const ScanData &data, const std::vector<int> &chain)
{
    int K = (int)chain.size();
    ScanResult res;
    res.numFF            = K;
    res.numPatterns      = (int)data.patterns.size();
    res.totalShiftCycles = 0;
    res.totalToggles     = 0;
    res.switchingActivity = 0.0;
    res.perFF.resize(K);
    for (int i = 0; i < K; ++i) {
        res.perFF[i].name    = data.ffs[chain[i]].name;
        res.perFF[i].toggles = 0;
    }

    std::vector<Value> chainState(K, X);

    for (const auto &pat : data.patterns) {
        if (pat.ppi.empty()) continue;

        // Shift in chain[K-1]'s PPI first → chain[0]'s PPI last
        for (int shift = K - 1; shift >= 0; --shift) {
            int   ffIdx  = chain[shift];
            Value newBit = (ffIdx < (int)pat.ppi.size()) ? pat.ppi[ffIdx] : X;

            for (int i = K - 1; i > 0; --i) {
                Value incoming = chainState[i - 1];
                if (chainState[i] != X && incoming != X && chainState[i] != incoming) {
                    ++res.perFF[i].toggles;
                    ++res.totalToggles;
                }
                chainState[i] = incoming;
            }
            if (chainState[0] != X && newBit != X && chainState[0] != newBit) {
                ++res.perFF[0].toggles;
                ++res.totalToggles;
            }
            chainState[0] = newBit;
            ++res.totalShiftCycles;
        }

        if (!pat.ppo.empty())
            for (int i = 0; i < K; ++i) {
                int ffIdx = chain[i];
                chainState[i] = (ffIdx < (int)pat.ppo.size()) ? pat.ppo[ffIdx] : X;
            }
    }

    if (K > 0 && res.totalShiftCycles > 0)
        res.switchingActivity =
            (double)res.totalToggles / ((long long)K * res.totalShiftCycles);

    return res;
}

// ---------------------------------------------------------------------------
// Report
// ---------------------------------------------------------------------------

void printReport(const ScanResult &r, const ScanData &data,
                 const std::vector<int> &chain)
{
    std::cout << "====================================================\n";
    std::cout << "  ScanForge — Scan Chain Analysis Report\n";
    std::cout << "====================================================\n";
    std::cout << "  Total FFs in circuit : " << data.numFF       << "\n";
    std::cout << "  FFs in chain (K)     : " << r.numFF          << "\n";
    std::cout << "  Scan ratio           : " << std::fixed << std::setprecision(1)
              << (data.numFF > 0 ? 100.0 * r.numFF / data.numFF : 0.0) << "%\n";
    std::cout << "  Test patterns        : " << r.numPatterns     << "\n";
    std::cout << "  Total shift cycles   : " << r.totalShiftCycles << "\n";
    std::cout << "  Total toggles        : " << r.totalToggles    << "\n";
    std::cout << "  Switching activity   : " << std::fixed << std::setprecision(4)
              << r.switchingActivity << "\n";
    std::cout << "\n  Scan chain order (SI →";
    for (int idx : chain)
        std::cout << " " << data.ffs[idx].name << " →";
    std::cout << " SO)\n";
    bool hasSCOAP = (data.ffs[0].cc0 + data.ffs[0].cc1 + data.ffs[0].co) > 0;
    std::cout << "\n  Per-FF details:\n";
    if (hasSCOAP)
        std::cout << "    " << std::left << std::setw(20) << "Name"
                  << std::right << std::setw(7) << "CC0"
                  << std::setw(7) << "CC1"
                  << std::setw(7) << "CO"
                  << std::setw(10) << "Toggles" << "\n";
    else
        std::cout << "    " << std::left << std::setw(20) << "Name"
                  << std::right << std::setw(10) << "Toggles" << "\n";
    for (int i = 0; i < r.numFF; ++i) {
        int idx = chain[i];
        std::cout << "    [" << std::setw(3) << i << "] "
                  << std::left << std::setw(18) << data.ffs[idx].name;
        if (hasSCOAP)
            std::cout << std::right
                      << std::setw(7) << data.ffs[idx].cc0
                      << std::setw(7) << data.ffs[idx].cc1
                      << std::setw(7) << data.ffs[idx].co;
        std::cout << std::right << std::setw(10) << r.perFF[i].toggles << "\n";
    }
    std::cout << "====================================================\n";
}

} // namespace ScanForge

