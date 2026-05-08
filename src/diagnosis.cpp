// ScanForge — diagnosis.cpp
// Scan chain diagnosis: stuck-at fault simulation, fault dictionary, alias analysis.

#include "diagnosis.h"

#include <algorithm>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>

namespace ScanForge {

namespace {

inline bool isBinary(Value v)            { return v == L || v == H; }
inline Value stuckValue(FaultType ft)    { return (ft == FaultType::SA1) ? H : L; }
inline bool  isMismatch(Value golden, FaultType ft)
{
    return isBinary(golden) && (golden != stuckValue(ft));
}

// Shift-in fault at j: we intended to load PPI[chain[j..K-1]] but got stuck_val.
// A pattern detects it if ∃ i ≥ j : PPI[chain[i]] ≠ stuck_val (and not X).
// We return a per-pattern bool vector.
std::vector<bool> shiftInDetection(const ScanData &data,
                                   const std::vector<int> &chain,
                                   int fault_pos, FaultType ftype)
{
    int K = (int)chain.size();
    int P = (int)data.patterns.size();
    std::vector<bool> det(P, false);
    for (int p = 0; p < P; ++p) {
        const auto &pat = data.patterns[p];
        for (int i = fault_pos; i < K; ++i) {
            int   ffIdx = chain[i];
            Value ppi   = (ffIdx < (int)pat.ppi.size()) ? pat.ppi[ffIdx] : X;
            if (isMismatch(ppi, ftype)) { det[p] = true; break; }
        }
    }
    return det;
}

} // namespace

// ---------------------------------------------------------------------------
// injectFault
// ---------------------------------------------------------------------------

FaultInjectionResult injectFault(const ScanData &data,
                                 const std::vector<int> &chain,
                                 int fault_pos,
                                 FaultType ftype)
{
    int K = (int)chain.size();
    int P = (int)data.patterns.size();

    FaultInjectionResult r;
    r.ff_chain_pos     = fault_pos;
    r.fault_type       = ftype;
    r.ff_name          = (fault_pos >= 0 && fault_pos < K)
                         ? data.ffs[chain[fault_pos]].name : "?";
    r.mismatches.assign(P, std::vector<bool>(K, false));
    r.affected_patterns = 0;
    r.total_mismatches  = 0;

    if (fault_pos < 0 || fault_pos >= K) return r;

    // SA fault at position j ONLY corrupts the shift-out observation at position j.
    // (During shift-out, FF[j]'s stuck value is output when it reaches SO after K-1-j
    // cycles; earlier FFs already left SO before the stuck value propagates to them.)
    int ffIdx = chain[fault_pos];
    for (int p = 0; p < P; ++p) {
        const auto &pat = data.patterns[p];
        Value golden = (ffIdx < (int)pat.ppo.size()) ? pat.ppo[ffIdx] : X;
        if (isMismatch(golden, ftype)) {
            r.mismatches[p][fault_pos] = true;
            ++r.total_mismatches;
            ++r.affected_patterns;
        }
    }
    return r;
}

// ---------------------------------------------------------------------------
// buildFaultDictionary
// ---------------------------------------------------------------------------

DiagnosisReport buildFaultDictionary(const ScanData &data,
                                     const std::vector<int> &chain)
{
    int K = (int)chain.size();
    int P = (int)data.patterns.size();

    struct Entry { FaultCandidate fc; std::string sig; };
    std::vector<Entry> entries;
    entries.reserve(2 * K);

    for (int j = 0; j < K; ++j) {
        for (int ftInt = 0; ftInt <= 1; ++ftInt) {
            FaultType ft = (ftInt == 0) ? FaultType::SA0 : FaultType::SA1;
            auto inj     = injectFault(data, chain, j, ft);          // shift-out
            auto siDet   = shiftInDetection(data, chain, j, ft);     // shift-in

            FaultCandidate fc;
            fc.chain_pos          = j;
            fc.ff_global_idx      = chain[j];
            fc.ff_name            = data.ffs[chain[j]].name;
            fc.fault_type         = ft;
            fc.detected_shift_out = inj.affected_patterns;  // exact pos j
            fc.total_patterns     = P;
            fc.diagnosable        = false;
            fc.alias_group        = "";

            // Shift-out signature: pattern detects iff PPO[chain[j]] ≠ stuck_val
            std::string so_sig(P, '0');
            for (int p = 0; p < P; ++p)
                if (inj.mismatches[p][j]) so_sig[p] = '1';

            // Shift-in signature: pattern detects iff ∃ i ≥ j: PPI[chain[i]] ≠ stuck_val
            std::string si_sig(P, '0');
            int siCount = 0;
            for (int p = 0; p < P; ++p) {
                if (siDet[p]) { si_sig[p] = '1'; ++siCount; }
            }
            fc.detected_shift_in = siCount;

            // Union for detection coverage
            int combined = 0;
            for (int p = 0; p < P; ++p)
                if (so_sig[p] == '1' || si_sig[p] == '1') ++combined;
            fc.detected_by    = combined;
            fc.detection_rate = (P > 0) ? (double)combined / P : 0.0;

            // Alias key = (SO_sig, SI_sig): faults are distinguishable if either differs
            entries.push_back({fc, so_sig + "|" + si_sig});
        }
    }

    // Alias analysis: group detected faults with identical signatures
    std::map<std::string, std::vector<int>> sigToIdx;
    for (int i = 0; i < (int)entries.size(); ++i)
        if (entries[i].fc.detected_by > 0)
            sigToIdx[entries[i].sig].push_back(i);

    int nextGroup = 0;
    int aliasCnt  = 0;
    for (auto &kv : sigToIdx) {
        if (kv.second.size() == 1) {
            entries[kv.second[0]].fc.diagnosable = true;
        } else {
            std::string gname = "G" + std::to_string(nextGroup++);
            for (int idx : kv.second) {
                entries[idx].fc.alias_group  = gname;
                entries[idx].fc.diagnosable  = false;
            }
            ++aliasCnt;
        }
    }

    DiagnosisReport report;
    report.alias_group_count  = aliasCnt;
    report.total_faults       = 2 * K;
    report.detected_faults    = 0;
    report.diagnosable_faults = 0;

    for (auto &e : entries) {
        if (e.fc.detected_by    > 0) ++report.detected_faults;
        if (e.fc.diagnosable)        ++report.diagnosable_faults;
        report.faults.push_back(e.fc);
    }

    report.fault_coverage     = (report.total_faults > 0)
                                ? (double)report.detected_faults    / report.total_faults : 0.0;
    report.diagnosis_coverage = (report.total_faults > 0)
                                ? (double)report.diagnosable_faults / report.total_faults : 0.0;
    return report;
}

// ---------------------------------------------------------------------------
// parseFaultSpec
// ---------------------------------------------------------------------------

bool parseFaultSpec(const std::string &spec,
                    const ScanData &data,
                    const std::vector<int> &chain,
                    int &out_pos, FaultType &out_type)
{
    auto colon = spec.rfind(':');
    if (colon == std::string::npos) {
        std::cerr << "Error: --inject-fault spec must be \"FFname:SA0\" or \"FFname:SA1\"\n";
        return false;
    }
    std::string ffname  = spec.substr(0, colon);
    std::string ftstr   = spec.substr(colon + 1);

    if      (ftstr == "SA0") out_type = FaultType::SA0;
    else if (ftstr == "SA1") out_type = FaultType::SA1;
    else {
        std::cerr << "Error: fault type must be SA0 or SA1, got \"" << ftstr << "\"\n";
        return false;
    }

    // Find FF in the chain
    for (int i = 0; i < (int)chain.size(); ++i) {
        if (data.ffs[chain[i]].name == ffname) {
            out_pos = i;
            return true;
        }
    }
    std::cerr << "Error: FF \"" << ffname << "\" not found in chain\n";
    std::cerr << "  Chain FFs:";
    for (int idx : chain) std::cerr << " " << data.ffs[idx].name;
    std::cerr << "\n";
    return false;
}

// ---------------------------------------------------------------------------
// printDiagnosisReport
// ---------------------------------------------------------------------------

void printDiagnosisReport(const DiagnosisReport &report,
                          const ScanData & /*data*/,
                          const std::vector<int> & /*chain*/)
{
    std::cout << "\n====================================================\n";
    std::cout << "  ScanForge — Scan Chain Diagnosis (Fault Dictionary)\n";
    std::cout << "====================================================\n";
    std::cout << "  Fault model : SA0/SA1 — combined shift-in + shift-out phases\n";
    std::cout << "  Total faults (2 per FF)   : " << report.total_faults        << "\n";
    std::cout << "  Detected (>=1 pattern)    : " << report.detected_faults     << "\n";
    std::cout << "  Uniquely diagnosable      : " << report.diagnosable_faults   << "\n";
    std::cout << "  Aliased fault groups      : " << report.alias_group_count    << "\n";
    std::cout << "  Fault coverage            : "
              << std::fixed << std::setprecision(1)
              << report.fault_coverage * 100.0      << "%\n";
    std::cout << "  Diagnosis coverage        : "
              << report.diagnosis_coverage * 100.0  << "%\n\n";

    // Table header
    std::cout << "  " << std::left  << std::setw(5)  << "Pos"
                      << std::setw(20) << "FF Name"
              << std::right << std::setw(5)  << "Type"
                            << std::setw(7)  << "Det"
                            << std::setw(6)  << "SO"
                            << std::setw(6)  << "SI"
                            << std::setw(8)  << "Rate%"
                            << std::setw(13) << "Diagnosable"
                            << std::setw(10) << "AliasGrp"
              << "\n";
    std::cout << "  " << std::string(74, '-') << "\n";

    for (const auto &fc : report.faults) {
        std::string diag_str;
        if      (fc.diagnosable)       diag_str = "YES";
        else if (fc.detected_by > 0)   diag_str = "ALIAS";
        else                           diag_str = "undetected";

        std::cout << "  " << std::left  << std::setw(5)  << fc.chain_pos
                          << std::setw(20) << fc.ff_name
                  << std::right << std::setw(5)  << (fc.fault_type == FaultType::SA1 ? "SA1" : "SA0")
                                << std::setw(7)  << fc.detected_by
                                << std::setw(6)  << fc.detected_shift_out
                                << std::setw(6)  << fc.detected_shift_in
                                << std::setw(8)  << std::fixed << std::setprecision(1)
                                << fc.detection_rate * 100.0
                                << std::setw(13) << diag_str
                                << std::setw(10) << (fc.alias_group.empty() ? "-" : fc.alias_group)
                  << "\n";
    }
    std::cout << "====================================================\n";
    std::cout << "  Det=combined, SO=shift-out detections, SI=shift-in detections\n";
    std::cout << "  'undetected' = fault masked by all test patterns\n";
    std::cout << "====================================================\n";
}

// ---------------------------------------------------------------------------
// printFaultInjection
// ---------------------------------------------------------------------------

void printFaultInjection(const FaultInjectionResult &r,
                         const ScanData &data,
                         const std::vector<int> &chain)
{
    int K = (int)chain.size();
    int P = (int)data.patterns.size();

    std::cout << "\n====================================================\n";
    std::cout << "  ScanForge — Fault Injection Analysis\n";
    std::cout << "====================================================\n";
    std::cout << "  Injected fault  : " << r.ff_name
              << "  (chain pos " << r.ff_chain_pos << ")"
              << "  [" << (r.fault_type == FaultType::SA1 ? "SA1" : "SA0") << "]\n";
    std::cout << "  Affects shift-out position  : " << r.ff_chain_pos << " (exact)\n";
    std::cout << "  Affected patterns           : "
              << r.affected_patterns << " / " << P << "\n";
    std::cout << "  Total mismatch bits         : " << r.total_mismatches << "\n";

    if (r.affected_patterns == 0) {
        std::cout << "\n  (Fault is fully masked — no test pattern detects it)\n";
    } else {
        std::cout << "\n  Pattern | Mismatched FFs (expected ≠ stuck value)\n";
        std::cout << "  " << std::string(60, '-') << "\n";
        for (int p = 0; p < P; ++p) {
            bool any = false;
            for (int i = 0; i < K; ++i) if (r.mismatches[p][i]) { any = true; break; }
            if (!any) continue;
            std::cout << "  Pat[" << std::setw(3) << p << "] |";
            for (int i = 0; i < K; ++i) {
                if (r.mismatches[p][i])
                    std::cout << " " << data.ffs[chain[i]].name << "(p" << i << ")";
            }
            std::cout << "\n";
        }
    }
    std::cout << "====================================================\n";
}

// ---------------------------------------------------------------------------
// writeDiagnosisCsv
// ---------------------------------------------------------------------------

bool writeDiagnosisCsv(const DiagnosisReport &report, const std::string &path)
{
    std::ofstream out(path);
    if (!out) return false;
    out << "chain_pos,ff_name,fault_type,detected_by,detected_shift_out,detected_shift_in,"
           "total_patterns,detection_rate,diagnosable,alias_group\n";
    out << std::fixed << std::setprecision(6);
    for (const auto &fc : report.faults) {
        out << fc.chain_pos << ","
            << fc.ff_name << ","
            << (fc.fault_type == FaultType::SA1 ? "SA1" : "SA0") << ","
            << fc.detected_by << ","
            << fc.detected_shift_out << ","
            << fc.detected_shift_in << ","
            << fc.total_patterns << ","
            << fc.detection_rate << ","
            << (fc.diagnosable ? 1 : 0) << ","
            << (fc.alias_group.empty() ? "-" : fc.alias_group) << "\n";
    }
    return (bool)out;
}

} // namespace ScanForge
