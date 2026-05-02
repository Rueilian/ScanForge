// ScanForge — scan_chain.cpp
// Core scan chain simulation and reporting logic.

#include "scan_chain.h"

#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>

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
    // Check header
    if (!std::getline(f, line) || line.substr(0, 9) != "SCAN_DATA") {
        std::cerr << "Error: " << path << " is not a valid .sf file\n";
        return false;
    }

    out.numFF    = 0;
    out.ffNames  = {};
    out.patterns = {};

    int expectedPatterns = 0;

    while (std::getline(f, line)) {
        if (line.empty()) continue;
        std::istringstream ss(line);
        std::string tok;
        ss >> tok;

        if (tok == "NUM_FF") {
            ss >> out.numFF;
        } else if (tok == "FF_NAMES") {
            out.ffNames.clear();
            std::string name;
            while (ss >> name)
                out.ffNames.push_back(name);
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

    if (out.numFF == 0 || (int)out.ffNames.size() != out.numFF) {
        std::cerr << "Error: malformed .sf file — FF count mismatch\n";
        return false;
    }
    return true;
}

// ---------------------------------------------------------------------------
// Simulation
// ---------------------------------------------------------------------------

ScanResult simulate(const ScanData &data)
{
    int N = data.numFF;
    ScanResult res;
    res.numFF           = N;
    res.numPatterns     = (int)data.patterns.size();
    res.totalShiftCycles = 0;
    res.totalToggles    = 0;
    res.switchingActivity = 0.0;
    res.perFF.resize(N);
    for (int i = 0; i < N; ++i) {
        res.perFF[i].name    = data.ffNames[i];
        res.perFF[i].toggles = 0;
    }

    // Chain state initialised to X (unknown)
    std::vector<Value> chainState(N, X);

    for (const auto &pat : data.patterns) {
        if (pat.ppi.empty()) continue;

        // Shift in PPI[N-1] first → PPI[0] last so FF[i] = PPI[i] after N shifts.
        for (int shift = N - 1; shift >= 0; --shift) {
            Value newBit = pat.ppi[shift];

            // Propagate: FF[N-1] ← FF[N-2] ← ... ← FF[0] ← newBit
            for (int i = N - 1; i > 0; --i) {
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

        // After functional capture the chain holds PPO values
        if (!pat.ppo.empty())
            for (int i = 0; i < N; ++i)
                chainState[i] = pat.ppo[i];
    }

    if (N > 0 && res.totalShiftCycles > 0)
        res.switchingActivity =
            (double)res.totalToggles / ((long long)N * res.totalShiftCycles);

    return res;
}

// ---------------------------------------------------------------------------
// Report
// ---------------------------------------------------------------------------

void printReport(const ScanResult &r, const ScanData &data)
{
    std::cout << "====================================================\n";
    std::cout << "  ScanForge — Scan Chain Analysis Report\n";
    std::cout << "====================================================\n";
    std::cout << "  Flip-flops       : " << r.numFF           << "\n";
    std::cout << "  Test patterns    : " << r.numPatterns     << "\n";
    std::cout << "  Total shift cyc. : " << r.totalShiftCycles << "\n";
    std::cout << "  Total toggles    : " << r.totalToggles    << "\n";
    std::cout << "  Switching activity: " << std::fixed << std::setprecision(4)
              << r.switchingActivity << "\n";
    std::cout << "\n  Scan chain order (SI →";
    for (const auto &name : data.ffNames)
        std::cout << " " << name << " →";
    std::cout << " SO)\n";
    std::cout << "\n  Per-FF toggle count:\n";
    for (int i = 0; i < r.numFF; ++i)
        std::cout << "    [" << std::setw(3) << i << "] "
                  << r.perFF[i].name << ": " << r.perFF[i].toggles << "\n";
    std::cout << "====================================================\n";
}

} // namespace ScanForge
