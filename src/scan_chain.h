#pragma once
// ScanForge — scan_chain.h
// Data structures and interface for scan chain simulation.

#include <string>
#include <vector>

namespace ScanForge {

// Logic values matching FAN_ATPG's CoreNs::Value
enum Value { L = 0, H = 1, X = 2, D = 3, B = 4, Z = 5 };

struct Pattern {
    std::vector<Value> ppi; // scan-in values (FF initial state)
    std::vector<Value> ppo; // captured values (FF next state after test)
};

struct ScanData {
    int                      numFF;
    std::vector<std::string> ffNames;
    std::vector<Pattern>     patterns;
};

struct FFResult {
    std::string name;
    long long   toggles;
};

struct ScanResult {
    int               numFF;
    int               numPatterns;
    long long         totalShiftCycles;
    long long         totalToggles;
    double            switchingActivity;
    std::vector<FFResult> perFF;
};

// Parse a .sf file produced by FAN_ATPG's add_scan_chains command.
// Returns false on error.
bool parseScanData(const std::string &path, ScanData &out);

// Simulate scan-shift sequence for all patterns.
// Chain order: SI → FF[0] → FF[1] → ... → FF[N-1] → SO
ScanResult simulate(const ScanData &data);

// Print a human-readable report to stdout.
void printReport(const ScanResult &result, const ScanData &data);

} // namespace ScanForge
