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

struct SeqEdge {
    int from = 0; // FF index [0, numFF)
    int to   = 0;
};

struct ScanData {
    int                   numFF;
    std::vector<FFInfo>   ffs;
    std::vector<Pattern>  patterns;
    // Sequential FF dependency edges (direct Q→D FF links from mergeSequentialEdgesFromVerilog()).
    std::vector<SeqEdge>  seq_edges;
    bool                  seq_netlist_loaded = false;
};

struct FFStress {
    std::string name;
    int         index = 0;

    long long toggle_count = 0;
    long long one_count    = 0;
    long long zero_count   = 0;

    int current_value   = -1;  // 0/1 while in a run; -1 = no prior binary sample
    int current_run_len = 0;
    int max_run_0       = 0;
    int max_run_1       = 0;

    double toggle_rate   = 0.0;
    double duty_1        = 0.0;
    double duty_0        = 0.0;
    double bias_score      = 0.0;
    double max_run_score   = 0.0;
    double stress_score    = 0.0;
};

struct SegmentStress {
    int     segment_id = 0;
    int     start_idx  = 0;  // position along current scan chain (inclusive)
    int     end_idx    = 0;  // inclusive

    double sum_stress = 0.0;
    double avg_stress = 0.0;
    double max_stress = 0.0;

    bool is_hotspot = false;
};

struct SegmentSummary {
    double max_segment_stress  = 0.0;  // max_j segment_avg[j]
    double mean_segment_stress = 0.0;
    double segment_variance    = 0.0;  // population Var(segment_avg[j])
    int    hotspot_count       = 0;
};

struct ScanResult {
    int               numFF;
    int               numPatterns;
    long long         totalShiftCycles;
    long long         totalToggles;
    double            switchingActivity;
    std::vector<FFStress> perFF;

    // Segment-level stress (sliding window along chain order); filled by segment profiler
    double                      max_segment_stress  = 0.0;
    double                      segment_variance    = 0.0;
    int                         hotspot_count       = 0;
    int                         segment_window_used = 0;  // effective W = min(requested, K)
    std::vector<SegmentStress>  segments;
};

// Parse a .sf file produced by FAN_ATPG's add_scan_chains command.
bool parseScanData(const std::string &path, ScanData &out);

// Parse only header through FF metadata (NUM_FF, FF_NAMES, SCOAP); stops at
// PATTERNS without loading PPI/PPO. SCOAP line optional (defaults to zeros). For fast
// sequential-graph-only workflows.
bool parseScanDataHeader(const std::string &path, ScanData &out);

// Populate data.seq_edges from a structural Verilog netlist: flip-flop instances whose
// cell names match common *_dff* patterns; edges added when another FF's Q net drives
// this FF's D net (direct connection only). FF instance names must match .sf FF_NAMES.
bool mergeSequentialEdgesFromVerilog(ScanData &data, const std::string &verilog_path);

// Simulate scan-shift sequence for a given ordered subset of FF indices.
// Chain order: SI → chain[0] → chain[1] → ... → chain[K-1] → SO
ScanResult simulate(const ScanData &data, const std::vector<int> &chain);

// Per-FF stress_score (same formula as post-simulate FFStress::stress_score) for a
// full-scan chain in circuit order — used for wear-aware selection without CSV.
std::vector<double> fullScanStressScores(const ScanData &data);

// Aggregate stress metrics over selected FF indices using precomputed per-FF scores.
struct StressAgg {
    double maxStress      = 0.0;
    double variance       = 0.0;
    double imbalance      = 0.0;  // max / mean among selected
    double meanStress     = 0.0;
};
StressAgg aggregateStressForChain(const std::vector<double> &stressByFF,
                                  const std::vector<int> &chain);

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

// Write per-FF stress metrics (after simulate). Returns false on I/O error.
bool writeStressCsv(const ScanResult &result, const std::string &path);

// Populate segment fields on `r` from `r.perFF` (chain order). `window` <= 0 clears segment data.
void applySegmentProfile(ScanResult &r, int window);

} // namespace ScanForge
