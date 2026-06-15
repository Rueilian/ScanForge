// ScanForge — scan_chain.cpp
// Core scan chain simulation and reporting logic.

#include "scan_chain.h"

#include <algorithm>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>

namespace ScanForge {

namespace {

// Duty / run-length metrics treat non-H as logic-0 (L, X, D, …) so every
// shift cycle contributes exactly one {0,1} sample (see one_count + zero_count).
inline int dutyBit(Value v)
{
    return (v == H) ? 1 : 0;
}

inline void flushOpenRun(FFStress &s)
{
    if (s.current_value >= 0 && s.current_run_len > 0) {
        if (s.current_value == 1)
            s.max_run_1 = std::max(s.max_run_1, s.current_run_len);
        else
            s.max_run_0 = std::max(s.max_run_0, s.current_run_len);
    }
    s.current_value   = -1;
    s.current_run_len = 0;
}

inline bool valueToggles(Value oldV, Value newV)
{
    return oldV != X && newV != X && oldV != newV;
}

void finalizeStressMetrics(ScanResult &res)
{
    long long C = res.totalShiftCycles;
    if (C <= 0) return;

    for (auto &s : res.perFF) {
        s.toggle_rate = (double)s.toggle_count / (double)C;
        s.duty_1      = (double)s.one_count / (double)C;
        s.duty_0      = (double)s.zero_count / (double)C;
        s.bias_score    = std::abs(s.duty_1 - 0.5);
        s.max_run_score = (double)std::max(s.max_run_0, s.max_run_1) / (double)C;
        s.stress_score  = s.toggle_rate;
    }
}

} // namespace

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
    out.seq_edges.clear();
    out.seq_netlist_loaded = false;
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

bool parseScanDataHeader(const std::string &path, ScanData &out)
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
    out.seq_edges.clear();
    out.seq_netlist_loaded = false;
    bool saw_scoap = false;

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
            saw_scoap = true;
            for (int i = 0; i < out.numFF; ++i)
                ss >> out.ffs[i].cc0 >> out.ffs[i].cc1 >> out.ffs[i].co;
        } else if (tok == "PATTERNS") {
            break;
        }
    }

    if (out.numFF == 0 || (int)out.ffs.size() != out.numFF) {
        std::cerr << "Error: malformed .sf file — FF count mismatch\n";
        return false;
    }
    if (!saw_scoap) {
        for (auto &ff : out.ffs)
            ff.cc0 = ff.cc1 = ff.co = 0;
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
        res.perFF[i].name  = data.ffs[chain[i]].name;
        res.perFF[i].index = i;
    }

    // Scan-in from logic-0 (matches documented SI=0); known binary initial state.
    std::vector<Value> chainState(K, L);

    for (const auto &pat : data.patterns) {
        if (pat.ppi.empty()) continue;

        // Shift in chain[K-1]'s PPI first → chain[0]'s PPI last
        for (int shift = K - 1; shift >= 0; --shift) {
            int   ffIdx  = chain[shift];
            Value newBit = (ffIdx < (int)pat.ppi.size()) ? pat.ppi[ffIdx] : X;

            for (int i = K - 1; i > 0; --i) {
                Value incoming = chainState[i - 1];
                if (valueToggles(chainState[i], incoming)) {
                    ++res.perFF[i].toggle_count;
                    ++res.totalToggles;
                }
                chainState[i] = incoming;
            }
            if (valueToggles(chainState[0], newBit)) {
                ++res.perFF[0].toggle_count;
                ++res.totalToggles;
            }
            chainState[0] = newBit;
            ++res.totalShiftCycles;

            for (int i = 0; i < K; ++i) {
                FFStress &st = res.perFF[i];
                int       b  = dutyBit(chainState[i]);
                if (b == 1)
                    ++st.one_count;
                else
                    ++st.zero_count;

                if (st.current_value < 0) {
                    st.current_value   = b;
                    st.current_run_len = 1;
                } else if (b == st.current_value) {
                    ++st.current_run_len;
                } else {
                    if (st.current_value == 1)
                        st.max_run_1 = std::max(st.max_run_1, st.current_run_len);
                    else
                        st.max_run_0 = std::max(st.max_run_0, st.current_run_len);
                    st.current_value   = b;
                    st.current_run_len = 1;
                }
            }
        }

        for (int i = 0; i < K; ++i)
            flushOpenRun(res.perFF[i]);

        if (!pat.ppo.empty())
            for (int i = 0; i < K; ++i) {
                int ffIdx = chain[i];
                chainState[i] = (ffIdx < (int)pat.ppo.size()) ? pat.ppo[ffIdx] : X;
            }
    }

    for (int i = 0; i < K; ++i)
        flushOpenRun(res.perFF[i]);

    finalizeStressMetrics(res);

    if (K > 0 && res.totalShiftCycles > 0)
        res.switchingActivity =
            (double)res.totalToggles / ((long long)K * res.totalShiftCycles);

    return res;
}

std::vector<double> fullScanStressScores(const ScanData &data)
{
    std::vector<int> chain(data.numFF);
    for (int i = 0; i < data.numFF; ++i)
        chain[i] = i;
    ScanResult res = simulate(data, chain);
    std::vector<double> out(data.numFF);
    for (int i = 0; i < data.numFF; ++i)
        out[i] = res.perFF[i].stress_score;
    return out;
}

StressAgg aggregateStressForChain(const std::vector<double> &stressByFF,
                                    const std::vector<int> &chain)
{
    StressAgg r;
    if (chain.empty() || stressByFF.empty())
        return r;

    double sum = 0.0;
    int      cnt = 0;
    for (int idx : chain) {
        if (idx >= 0 && idx < (int)stressByFF.size()) {
            double s = stressByFF[idx];
            sum += s;
            ++cnt;
            if (s > r.maxStress)
                r.maxStress = s;
        }
    }
    if (cnt == 0)
        return r;

    r.meanStress = sum / cnt;
    double varSum = 0.0;
    for (int idx : chain) {
        if (idx >= 0 && idx < (int)stressByFF.size()) {
            double d = stressByFF[idx] - r.meanStress;
            varSum += d * d;
        }
    }
    r.variance = varSum / cnt;
    if (r.meanStress > 1e-300)
        r.imbalance = r.maxStress / r.meanStress;
    return r;
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
    long long sumPer = 0;
    for (const auto &ff : r.perFF) sumPer += ff.toggle_count;
    std::cout << "  Sum of per-FF toggles: " << sumPer << "\n";
    if (sumPer != r.totalToggles)
        std::cout << "  (warning: per-FF sum != total toggles)\n";
    std::cout << "  Switching activity   : " << std::fixed << std::setprecision(4)
              << r.switchingActivity << "\n";
    if (!r.perFF.empty()) {
        int   bestIdx = 0;
        double bestS  = r.perFF[0].stress_score;
        for (int i = 1; i < r.numFF; ++i) {
            if (r.perFF[i].stress_score > bestS) {
                bestS  = r.perFF[i].stress_score;
                bestIdx = i;
            }
        }
        std::cout << "  Max stress FF        : " << r.perFF[bestIdx].name << "\n";
        std::cout << "  Max stress score     : " << std::fixed << std::setprecision(4)
                  << bestS << "\n";
    }
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
        std::cout << std::right << std::setw(10) << r.perFF[i].toggle_count << "\n";
    }
    std::cout << "====================================================\n";
}

bool writeStressCsv(const ScanResult &result, const std::string &path)
{
    std::ofstream out(path);
    if (!out) return false;

    out << "index,ff_name,toggle_count,toggle_rate,one_count,zero_count,"
           "duty_1,duty_0,bias_score,max_run_0,max_run_1,max_run_score,stress_score\n";
    out << std::fixed << std::setprecision(6);
    for (int i = 0; i < result.numFF; ++i) {
        const FFStress &s = result.perFF[i];
        out << s.index << ',' << s.name << ','
            << s.toggle_count << ','
            << s.toggle_rate << ','
            << s.one_count << ','
            << s.zero_count << ','
            << s.duty_1 << ','
            << s.duty_0 << ','
            << s.bias_score << ','
            << s.max_run_0 << ','
            << s.max_run_1 << ','
            << s.max_run_score << ','
            << s.stress_score << '\n';
    }
    return (bool)out;
}

CoverageResult estimateCoverage(const ScanData &data,
                                const std::vector<int> &chain)
{
    std::vector<bool> inChain(data.numFF, false);
    for (int idx : chain) inChain[idx] = true;

    // --- Pattern-applicability metric ---
    // A pattern is applicable if every FF needing a specific value is in chain.
    int applicable = 0;
    for (const auto &pat : data.patterns) {
        bool ok = true;
        for (int i = 0; i < data.numFF; ++i) {
            if (pat.ppi[i] != X && !inChain[i]) { ok = false; break; }
        }
        if (ok) ++applicable;
    }

    // --- SCOAP-weighted observability coverage ---
    // Each FF contributes proportionally to how hard it is to observe without scan:
    //   weight_i = CO_i  (higher CO → harder to observe → more benefit from scanning)
    // coverage = sum(CO_i for scanned FFs) / sum(CO_i for all FFs)
    // Falls back to uniform weighting (= K/N) if no SCOAP data available.
    double totalWeight = 0.0, chainWeight = 0.0;
    bool hasSCOAP = false;
    for (int i = 0; i < data.numFF; ++i) {
        if (data.ffs[i].co > 0) hasSCOAP = true;
        double w = hasSCOAP ? (double)data.ffs[i].co : 1.0;
        totalWeight += w;
        if (inChain[i]) chainWeight += w;
    }
    // Re-traverse once SCOAP flag is known
    if (hasSCOAP) {
        totalWeight = chainWeight = 0.0;
        for (int i = 0; i < data.numFF; ++i) {
            totalWeight += data.ffs[i].co;
            if (inChain[i]) chainWeight += data.ffs[i].co;
        }
    }
    double scoap_w = totalWeight > 0.0 ? chainWeight / totalWeight : 0.0;

    CoverageResult r;
    r.applicablePatterns = applicable;
    r.totalPatterns      = (int)data.patterns.size();
    r.patternCoverage    = r.totalPatterns > 0
                           ? (double)applicable / r.totalPatterns : 0.0;
    r.scoap_weighted     = scoap_w;
    r.estimatedCoverage  = scoap_w;   // primary metric
    return r;
}

} // namespace ScanForge
