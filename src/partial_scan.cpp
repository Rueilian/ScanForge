// ScanForge — partial_scan.cpp
// FF selection strategies for partial scan based on SCOAP metrics.

#include "partial_scan.h"
#include "scan_chain.h"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <random>
#include <string>

namespace ScanForge {

namespace {

constexpr double kEps = 1e-12;

// Tradeoff score weights (dimensionless ranking aid; tune for reports).
constexpr double kScoreA = 1.0;   // weight on coverage_proxy
constexpr double kScoreB = 0.5;   // normalized activity penalty
constexpr double kScoreC = 0.5;   // normalized max_stress penalty
constexpr double kScoreD = 0.25;  // normalized stress_variance penalty

double sumCoAll(const ScanData &data)
{
    double s = 0.0;
    for (const auto &ff : data.ffs) s += std::max(0, ff.co);
    return s;
}

double sumCcAll(const ScanData &data)
{
    double s = 0.0;
    for (const auto &ff : data.ffs)
        s += std::max(0, ff.cc0) + std::max(0, ff.cc1);
    return s;
}

double sumCombinedAll(const ScanData &data)
{
    double s = 0.0;
    for (const auto &ff : data.ffs) {
        double c = ff.cc0 + ff.cc1 + 2.0 * ff.co;
        s += c;
    }
    return s;
}

void stressAggFromResult(const ScanResult &res,
                         double &max_stress,
                         double &stress_var,
                         double &stress_imbalance)
{
    max_stress = 0.0;
    stress_var = 0.0;
    stress_imbalance = 0.0;
    int K = res.numFF;
    if (K <= 0) return;

    double sum = 0.0;
    for (const auto &s : res.perFF) {
        max_stress = std::max(max_stress, s.stress_score);
        sum += s.stress_score;
    }
    double mean = sum / (double)K;
    for (const auto &s : res.perFF) {
        double d = s.stress_score - mean;
        stress_var += d * d;
    }
    stress_var /= (double)K;
    stress_imbalance = (mean > kEps) ? (max_stress / mean - 1.0) : 0.0;
}

struct SweepRowRaw {
    double ratio = 0.0;
    int    k = 0;
    double coverage_proxy = 0.0;
    double coverage_loss = 0.0;
    long long toggles = 0;
    double activity = 0.0;
    double max_stress = 0.0;
    double stress_var = 0.0;
    double stress_imbalance = 0.0;
};

bool paretoMaxCovMinStress(const std::vector<SweepRowRaw> &rows, std::size_t i)
{
    for (std::size_t j = 0; j < rows.size(); ++j) {
        if (i == j) continue;
        bool ge_cov = rows[j].coverage_proxy >= rows[i].coverage_proxy - kEps;
        bool le_st  = rows[j].max_stress <= rows[i].max_stress + kEps;
        bool strict = (rows[j].coverage_proxy > rows[i].coverage_proxy + kEps)
                     || (rows[j].max_stress < rows[i].max_stress - kEps);
        if (ge_cov && le_st && strict) return false;
    }
    return true;
}

bool paretoMaxCovMinActivity(const std::vector<SweepRowRaw> &rows, std::size_t i)
{
    for (std::size_t j = 0; j < rows.size(); ++j) {
        if (i == j) continue;
        bool ge_cov = rows[j].coverage_proxy >= rows[i].coverage_proxy - kEps;
        bool le_ac  = rows[j].activity <= rows[i].activity + kEps;
        bool strict = (rows[j].coverage_proxy > rows[i].coverage_proxy + kEps)
                     || (rows[j].activity < rows[i].activity - kEps);
        if (ge_cov && le_ac && strict) return false;
    }
    return true;
}

std::string modeTag(SelectionMode mode)
{
    switch (mode) {
    case SelectionMode::SCOAP_CO: return "co";
    case SelectionMode::SCOAP_COMBINED: return "combined";
    case SelectionMode::SCOAP_COMBINED_WEAR: return "combined_wear";
    case SelectionMode::RANDOM: return "random";
    }
    return "unknown";
}

} // namespace

CoverageProxyResult computeCoverageProxy(const ScanData &data,
                                         const std::vector<int> &selected_indices,
                                         CoverageProxyMode mode)
{
    CoverageProxyResult out;
    double denom = 0.0;
    double num   = 0.0;

    switch (mode) {
    case CoverageProxyMode::CO:
        denom = sumCoAll(data);
        for (int idx : selected_indices) {
            if (idx >= 0 && idx < data.numFF)
                num += std::max(0, data.ffs[idx].co);
        }
        break;
    case CoverageProxyMode::CONTROLLABILITY:
        denom = sumCcAll(data);
        for (int idx : selected_indices) {
            if (idx >= 0 && idx < data.numFF) {
                const auto &ff = data.ffs[idx];
                num += std::max(0, ff.cc0) + std::max(0, ff.cc1);
            }
        }
        break;
    case CoverageProxyMode::COMBINED:
        denom = sumCombinedAll(data);
        for (int idx : selected_indices) {
            if (idx >= 0 && idx < data.numFF) {
                const auto &ff = data.ffs[idx];
                num += ff.cc0 + ff.cc1 + 2.0 * ff.co;
            }
        }
        break;
    }

    if (denom <= kEps) {
        out.proxy = 0.0;
        out.loss  = 1.0;
        return out;
    }
    out.proxy = std::max(0.0, std::min(1.0, num / denom));
    out.loss  = 1.0 - out.proxy;
    return out;
}

std::vector<int> selectFFs(const ScanData &data, int k,
                            SelectionMode mode, unsigned seed,
                            double wear_lambda,
                            const std::vector<double> *ff_stress_scores)
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
        std::sort(indices.begin(), indices.end());
        return indices;
    }

    if (mode == SelectionMode::SCOAP_COMBINED_WEAR) {
        if (!ff_stress_scores || (int)ff_stress_scores->size() != N) {
            std::cerr << "Warning: combined_wear needs full-scan stress vector; "
                         "falling back to SCOAP-Combined ranking.\n";
            mode = SelectionMode::SCOAP_COMBINED;
            wear_lambda = 0.0;
        }
    }

    std::vector<double> score(N);
    if (mode == SelectionMode::SCOAP_COMBINED_WEAR && wear_lambda > 0.0
        && ff_stress_scores && (int)ff_stress_scores->size() == N) {
        double maxS = 0.0;
        for (double s : *ff_stress_scores)
            maxS = std::max(maxS, s);
        if (maxS < kEps) maxS = 1.0;
        for (int i = 0; i < N; ++i) {
            const auto &ff = data.ffs[i];
            double comb = ff.cc0 + ff.cc1 + 2.0 * ff.co;
            double normStress = (*ff_stress_scores)[i] / maxS;
            score[i] = comb - wear_lambda * normStress;
        }
    } else {
        for (int i = 0; i < N; ++i) {
            const auto &ff = data.ffs[i];
            if (mode == SelectionMode::SCOAP_CO)
                score[i] = ff.co;
            else
                score[i] = ff.cc0 + ff.cc1 + 2.0 * ff.co;
        }
    }

    std::stable_sort(indices.begin(), indices.end(),
        [&](int a, int b){ return score[a] > score[b]; });

    indices.resize(k);
    std::sort(indices.begin(), indices.end());
    return indices;
}

void sweepPartialScan(const ScanData &data,
                      const std::vector<double> &ratios,
                      SelectionMode mode,
                      const SweepConfig &cfg)
{
    int N = data.numFF;
    const char *modeStr =
        (mode == SelectionMode::SCOAP_CO)            ? "SCOAP-CO" :
        (mode == SelectionMode::SCOAP_COMBINED)    ? "SCOAP-Combined" :
        (mode == SelectionMode::SCOAP_COMBINED_WEAR) ? "SCOAP-Combined+Wear" :
                                                       "Random";

    std::vector<double> wearStress;
    if (mode == SelectionMode::SCOAP_COMBINED_WEAR) {
        auto fullRes = simulateFull(data);
        wearStress.resize(N);
        for (int i = 0; i < N && i < fullRes.numFF; ++i)
            wearStress[i] = fullRes.perFF[i].stress_score;
    }

    std::vector<SweepRowRaw> rawRows;
    rawRows.reserve(ratios.size());

    for (double r : ratios) {
        int k = std::max(1, (int)std::round(r * N));
        const std::vector<double> *stressPtr =
            (mode == SelectionMode::SCOAP_COMBINED_WEAR) ? &wearStress : nullptr;
        auto chain = selectFFs(data, k, mode, cfg.random_seed,
                              cfg.wear_lambda, stressPtr);
        auto res = simulate(data, chain);

        double maxs = 0.0, var = 0.0, imb = 0.0;
        stressAggFromResult(res, maxs, var, imb);

        auto cov = computeCoverageProxy(data, chain, cfg.coverage_proxy_mode);

        SweepRowRaw row;
        row.ratio = r;
        row.k = k;
        row.coverage_proxy = cov.proxy;
        row.coverage_loss = cov.loss;
        row.toggles = res.totalToggles;
        row.activity = res.switchingActivity;
        row.max_stress = maxs;
        row.stress_var = var;
        row.stress_imbalance = imb;
        rawRows.push_back(row);
    }

    double maxAct = 0.0, maxMaxS = 0.0, maxVar = 0.0;
    for (const auto &row : rawRows) {
        maxAct  = std::max(maxAct, row.activity);
        maxMaxS = std::max(maxMaxS, row.max_stress);
        maxVar  = std::max(maxVar, row.stress_var);
    }
    if (maxAct < kEps) maxAct = 1.0;
    if (maxMaxS < kEps) maxMaxS = 1.0;
    if (maxVar < kEps) maxVar = 1.0;

    std::ostream *csvOut = nullptr;
    std::ofstream csvFile;
    const bool writeCsv = cfg.csv_stdout || !cfg.summary_csv_path.empty();
    if (writeCsv) {
        if (!cfg.summary_csv_path.empty()) {
            csvFile.open(cfg.summary_csv_path);
            if (!csvFile) {
                std::cerr << "Error: cannot open summary CSV: "
                          << cfg.summary_csv_path << "\n";
            } else {
                csvOut = &csvFile;
            }
        } else if (cfg.csv_stdout) {
            csvOut = &std::cout;
        }
        if (csvOut) {
            *csvOut << "circuit,mode,lambda,coverage_proxy_mode,ratio,k,"
                       "coverage_proxy,coverage_loss,toggles,activity,"
                       "max_stress,stress_variance,stress_imbalance,tradeoff_score,"
                       "pareto_cov_maxstress,pareto_cov_activity\n";
        }
    }

    const bool showHuman = !writeCsv;
    const bool csvToFile = writeCsv && csvOut && csvOut != &std::cout;

    if (showHuman) {
        std::cout << "\n====================================================\n";
        std::cout << "  ScanForge — Partial Scan Sweep (" << modeStr << ")\n";
        std::cout << "  Circuit FFs: " << N
                  << "   Patterns: " << data.patterns.size() << "\n";
        if (mode == SelectionMode::SCOAP_COMBINED_WEAR)
            std::cout << "  Wear lambda: " << std::fixed << std::setprecision(4)
                      << cfg.wear_lambda << "\n";
        std::cout << "  Coverage proxy: SCOAP testability preservation "
                     "(not exact fault coverage)\n";
        std::cout << "====================================================\n";
        std::cout << std::left
                  << std::setw(8)  << "Ratio"
                  << std::setw(6)  << "K"
                  << std::setw(12) << "CovProxy"
                  << std::setw(12) << "CovLoss"
                  << std::setw(14) << "Toggles"
                  << std::setw(12) << "Activity"
                  << std::setw(10) << "MaxStr"
                  << std::setw(10) << "StrVar"
                  << std::setw(10) << "StrImb"
                  << std::setw(10) << "Score"
                  << "Pareto(ms/act)\n";
        std::cout << std::string(110, '-') << "\n";
    }

    std::string circuit = cfg.circuit_name.empty() ? "circuit" : cfg.circuit_name;
    std::string mtag = modeTag(mode);
    const char *cpTag =
        (cfg.coverage_proxy_mode == CoverageProxyMode::CO)           ? "co" :
        (cfg.coverage_proxy_mode == CoverageProxyMode::CONTROLLABILITY) ? "controllability" :
                                                                          "combined";

    for (std::size_t i = 0; i < rawRows.size(); ++i) {
        const auto &row = rawRows[i];
        double nAct = row.activity / maxAct;
        double nMs  = row.max_stress / maxMaxS;
        double nVar = row.stress_var / maxVar;
        double trade = kScoreA * row.coverage_proxy
                     - kScoreB * nAct
                     - kScoreC * nMs
                     - kScoreD * nVar;

        int p_ms = paretoMaxCovMinStress(rawRows, i) ? 1 : 0;
        int p_ac = paretoMaxCovMinActivity(rawRows, i) ? 1 : 0;

        if (csvOut) {
            *csvOut << std::fixed << std::setprecision(6)
                    << circuit << ',' << mtag << ','
                    << cfg.wear_lambda << ',' << cpTag << ','
                    << row.ratio << ',' << row.k << ','
                    << row.coverage_proxy << ',' << row.coverage_loss << ','
                    << row.toggles << ','
                    << row.activity << ','
                    << row.max_stress << ','
                    << row.stress_var << ','
                    << row.stress_imbalance << ','
                    << trade << ','
                    << p_ms << ',' << p_ac << '\n';
        }

        if (showHuman) {
            std::cout << std::fixed << std::setprecision(0)
                      << std::left << std::setw(7) << (row.ratio * 100) + 0.5 << "% "
                      << std::left << std::setw(6) << row.k
                      << std::setprecision(4)
                      << std::left << std::setw(12) << row.coverage_proxy
                      << std::left << std::setw(12) << row.coverage_loss
                      << std::left << std::setw(14) << row.toggles
                      << std::left << std::setw(12) << row.activity
                      << std::left << std::setw(10) << row.max_stress
                      << std::left << std::setw(10) << row.stress_var
                      << std::left << std::setw(10) << row.stress_imbalance
                      << std::left << std::setw(10) << trade
                      << p_ms << '/' << p_ac << "\n";
        }
    }

    if (showHuman) {
        std::cout << "====================================================\n";
        std::cout << "  Pareto: pareto_cov_maxstress / pareto_cov_activity "
                     "(1 = on frontier in this sweep)\n";
        std::cout << "  Tradeoff score: heuristic blend (see source weights kScore*)\n";
    } else if (csvToFile) {
        std::cout << "  Summary CSV written to: " << cfg.summary_csv_path << "\n";
    }
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

        auto chainCO   = selectFFs(data, k, SelectionMode::SCOAP_CO,       seed);
        auto chainComb = selectFFs(data, k, SelectionMode::SCOAP_COMBINED,  seed);
        auto chainRand = selectFFs(data, k, SelectionMode::RANDOM,          seed);

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
