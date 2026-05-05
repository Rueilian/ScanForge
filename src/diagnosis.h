#pragma once
// ScanForge — diagnosis.h
// Scan chain diagnosis via stuck-at fault simulation in the shift-out domain.
//
// Fault model (scan-path, shift-out):
//   A stuck-at fault at chain position j means the FF at position j always
//   drives its stuck value during shift-out.  During the shift-out sequence the
//   stuck value propagates toward SI, so ALL chain positions 0..j produce the
//   stuck value instead of their captured PPO.  A fault is detected by a test
//   pattern when ≥1 bit in positions 0..j of the shift-out differs from the
//   stuck value (ignoring X / don't-care bits).

#include "scan_chain.h"
#include <string>
#include <vector>

namespace ScanForge {

enum class FaultType { SA0 = 0, SA1 = 1 };

struct FaultCandidate {
    int         chain_pos;       // 0-indexed position in the scan chain
    int         ff_global_idx;   // index into ScanData::ffs
    std::string ff_name;
    FaultType   fault_type;

    int    detected_by;     // number of patterns that detect this fault
    int    total_patterns;
    double detection_rate;  // detected_by / total_patterns

    bool        diagnosable;    // detected AND has a unique detection signature
    std::string alias_group;    // non-empty label shared by aliased faults
};

struct DiagnosisReport {
    std::vector<FaultCandidate> faults; // 2*K entries, ordered by (chain_pos, SA0/SA1)

    int    total_faults;        // 2 * K
    int    detected_faults;     // faults with detected_by >= 1
    int    diagnosable_faults;  // detected AND uniquely identifiable
    int    alias_group_count;   // number of alias groups
    double fault_coverage;      // detected_faults / total_faults
    double diagnosis_coverage;  // diagnosable_faults / total_faults
};

// Per-pattern, per-position mismatch bitmap for one injected fault.
struct FaultInjectionResult {
    int         ff_chain_pos;
    std::string ff_name;
    FaultType   fault_type;

    // mismatches[p][i] = true  →  pattern p observes a mismatch at chain pos i
    std::vector<std::vector<bool>> mismatches;
    int affected_patterns;  // patterns with ≥1 mismatch
    int total_mismatches;   // total mismatch bits across all patterns
};

// Build the complete fault dictionary for the given chain.
DiagnosisReport buildFaultDictionary(const ScanData &data,
                                     const std::vector<int> &chain);

// Inject one fault and return the detailed mismatch map.
FaultInjectionResult injectFault(const ScanData &data,
                                 const std::vector<int> &chain,
                                 int fault_pos,
                                 FaultType ftype);

// Parse "FFname:SA0" or "FFname:SA1".  Returns false on parse error.
bool parseFaultSpec(const std::string &spec,
                    const ScanData &data,
                    const std::vector<int> &chain,
                    int &out_pos, FaultType &out_type);

// Human-readable reports.
void printDiagnosisReport(const DiagnosisReport &report,
                          const ScanData &data,
                          const std::vector<int> &chain);

void printFaultInjection(const FaultInjectionResult &r,
                         const ScanData &data,
                         const std::vector<int> &chain);

// Write fault dictionary to CSV.  Returns false on I/O error.
bool writeDiagnosisCsv(const DiagnosisReport &report,
                       const std::string &path);

} // namespace ScanForge
