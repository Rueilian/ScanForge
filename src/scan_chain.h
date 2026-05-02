#pragma once
// ScanForge — scan_chain.h
// Data structures and interface for scan chain simulation.

#include <string>
#include <vector>

namespace ScanForge {

// Logic values matching FAN_ATPG's CoreNs::Value
enum Value { L = 0, H = 1, X = 2, D = 3, B = 4, Z = 5 };

struct FFInfo {
    std::string name;
    int         cc0;  // SCOAP 0-controllability  (higher = harder)
    int         cc1;  // SCOAP 1-controllability  (higher = harder)
    int         co;   // SCOAP observability      (higher = harder)
};

struct Pattern {
    std::vector<Value> ppi; // scan-in values (FF initial state)
    std::vector<Value> ppo; // captured values (FF next state after test)
};

struct ScanData {
    int                   numFF;
    std::vector<FFInfo>   ffs;
    std::vector<Pattern>  patterns;
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
bool parseScanData(const std::string &path, ScanData &out);

// Simulate scan-shift sequence for a given ordered subset of FF indices.
// Chain order: SI → chain[0] → chain[1] → ... → chain[K-1] → SO
ScanResult simulate(const ScanData &data, const std::vector<int> &chain);

// Convenience: simulate full scan (all FFs in circuit order)
inline ScanResult simulateFull(const ScanData &data)
{
    std::vector<int> chain(data.numFF);
    for (int i = 0; i < data.numFF; ++i) chain[i] = i;
    return simulate(data, chain);
}

struct CoverageResult {
    int    applicablePatterns; // patterns where all required FFs are in chain
    int    totalPatterns;
    double patternCoverage;    // applicablePatterns / totalPatterns
    double scoap_weighted;     // sum(1/CO_i for scanned FFs) / sum(1/CO_i for all FFs)
                               // approximates fault coverage based on observability
    double estimatedCoverage;  // == scoap_weighted (primary metric for partial scan)
};

// Estimate fault coverage for a given partial scan chain.
// A pattern is "applicable" if every FF with a non-X PPI value is in the chain
// (i.e., every FF that needs a specific value can be loaded via scan).
// Returns an estimate: applicable patterns / total patterns.
CoverageResult estimateCoverage(const ScanData &data,
                                const std::vector<int> &chain);

// Print a human-readable report to stdout.
void printReport(const ScanResult &result, const ScanData &data,
                 const std::vector<int> &chain);

} // namespace ScanForge
