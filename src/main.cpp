// ScanForge — main.cpp
// CLI entry point for scan chain analysis and partial scan sweep.

#include "scan_chain.h"
#include "partial_scan.h"
#include "segment_stress.h"
#include "diagnosis.h"
#include <iostream>
#include <iomanip>
#include <string>
#include <vector>
#include <cstdlib>
#include <cmath>

static std::string basenameSf(const std::string &path)
{
    std::size_t slash = path.find_last_of("/\\");
    std::string base = (slash == std::string::npos) ? path : path.substr(slash + 1);
    std::size_t dot = base.rfind('.');
    if (dot != std::string::npos && dot > 0)
        base = base.substr(0, dot);
    return base.empty() ? "circuit" : base;
}

static void usage(const char *prog)
{
    std::cout <<
        "Usage: " << prog << " [options] <scan_data.sf>\n"
        "\n"
        "Options:\n"
        "  --diagnose            Scan chain fault dictionary (SA0/SA1 per FF)\n"
        "  --inject-fault <spec> Inject one fault, e.g. U_G6:SA1\n"
        "  --diagnose-csv <path> Write fault dictionary CSV\n"
        "  (no options)          Full scan analysis\n"
        "  --sweep               Sweep partial scan ratios 25/50/75/100%\n"
        "  --coverage            Coverage estimate sweep (compares CO/Combined/Random)\n"
        "  --fine                Use fine-grained sweep (5% steps) with --sweep/--coverage\n"
        "  --csv                 With --coverage: CSV to stdout. With --sweep: same as\n"
        "                        --summary-csv - (CSV to stdout) unless --summary-csv is set\n"
        "  --summary-csv <path>  With --sweep: write tradeoff / coverage-proxy sweep CSV\n"
        "  --stress-csv <path>   Write per-FF scan stress metrics to CSV (full/partial run)\n"
        "  --segment-csv <path>  Write segment-level stress CSV (requires --segment-window > 0)\n"
        "  --segment-window <n>  Sliding window size for segment stress (default: 0 = off)\n"
        "  --partial <ratio>     Partial scan at given ratio (0.0–1.0)\n"
        "  --mode <co|combined|random|co_wear|combined_wear|\n"
        "                        co_wear_leveling|combined_wear_leveling>\n"
        "                        FF selection strategy (default: co)\n"
        "  --lambda <x>          Stress penalty weight for *_wear / *_wear_leveling\n"
        "                        (default: 0.5)\n"
        "  --coverage-proxy <co|combined|controllability>\n"
        "                        SCOAP proxy for sweep CSV (default: combined)\n"
        "  -h, --help            Print this help\n"
        "\n"
        "  <scan_data.sf>  Data file exported by FAN_ATPG's 'add_scan_chains -o' command.\n";
}

static const char *modeDisplayName(ScanForge::SelectionMode mode)
{
    switch (mode) {
    case ScanForge::SelectionMode::SCOAP_CO:           return "co";
    case ScanForge::SelectionMode::SCOAP_COMBINED:     return "combined";
    case ScanForge::SelectionMode::RANDOM:             return "random";
    case ScanForge::SelectionMode::SCOAP_CO_WEAR:      return "co_wear";
    case ScanForge::SelectionMode::SCOAP_COMBINED_WEAR: return "combined_wear";
    case ScanForge::SelectionMode::SCOAP_CO_WEAR_LEVELING: return "co_wear_leveling";
    case ScanForge::SelectionMode::SCOAP_COMBINED_WEAR_LEVELING: return "combined_wear_leveling";
    default:                                           return "co";
    }
}

int main(int argc, char *argv[])
{
    if (argc < 2) { usage(argv[0]); return 1; }

    std::string sfPath;
    std::string stressCsvPath;
    std::string segmentCsvPath;
    std::string summaryCsvPath;
    std::string diagCsvPath;
    std::string injectFaultSpec;
    bool        doSweep    = false;
    bool        doCoverage = false;
    bool        doFine     = false;
    bool        doCSV      = false;
    bool        doDiagnose = false;
    double      partialR   = -1.0;
    double      lambda     = 0.5;
    ScanForge::SelectionMode mode = ScanForge::SelectionMode::SCOAP_CO;
    ScanForge::CoverageProxyMode proxyMode = ScanForge::CoverageProxyMode::COMBINED;
    int         segmentWindow = 0;

    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if      (a == "-h" || a == "--help") { usage(argv[0]); return 0; }
        else if (a == "--sweep")    { doSweep    = true; }
        else if (a == "--coverage") { doCoverage = true; }
        else if (a == "--fine")     { doFine     = true; }
        else if (a == "--csv")      { doCSV      = true; }
        else if (a == "--diagnose") { doDiagnose = true; }
        else if (a == "--inject-fault" && i+1 < argc) { injectFaultSpec = argv[++i]; }
        else if (a == "--diagnose-csv" && i+1 < argc) { diagCsvPath = argv[++i]; }
        else if (a == "--stress-csv" && i+1 < argc) { stressCsvPath = argv[++i]; }
        else if (a == "--segment-csv" && i+1 < argc) { segmentCsvPath = argv[++i]; }
        else if (a == "--segment-window" && i+1 < argc) { segmentWindow = std::atoi(argv[++i]); }
        else if (a == "--summary-csv" && i+1 < argc) { summaryCsvPath = argv[++i]; }
        else if (a == "--partial" && i+1 < argc) { partialR = std::atof(argv[++i]); }
        else if (a == "--lambda" && i+1 < argc) { lambda = std::atof(argv[++i]); }
        else if (a == "--coverage-proxy" && i+1 < argc) {
            std::string p = argv[++i];
            if      (p == "co") proxyMode = ScanForge::CoverageProxyMode::CO;
            else if (p == "controllability")
                proxyMode = ScanForge::CoverageProxyMode::CONTROLLABILITY;
            else
                proxyMode = ScanForge::CoverageProxyMode::COMBINED;
        }
        else if (a == "--mode" && i+1 < argc) {
            std::string m = argv[++i];
            if      (m == "combined")      mode = ScanForge::SelectionMode::SCOAP_COMBINED;
            else if (m == "random")        mode = ScanForge::SelectionMode::RANDOM;
            else if (m == "co_wear")       mode = ScanForge::SelectionMode::SCOAP_CO_WEAR;
            else if (m == "combined_wear") mode = ScanForge::SelectionMode::SCOAP_COMBINED_WEAR;
            else if (m == "co_wear_leveling")
                mode = ScanForge::SelectionMode::SCOAP_CO_WEAR_LEVELING;
            else if (m == "combined_wear_leveling")
                mode = ScanForge::SelectionMode::SCOAP_COMBINED_WEAR_LEVELING;
            else if (m == "co")            mode = ScanForge::SelectionMode::SCOAP_CO;
            else {
                std::cerr << "Error: unknown --mode \"" << m << "\" "
                             "(expected co|combined|random|co_wear|combined_wear|"
                             "co_wear_leveling|combined_wear_leveling)\n";
                return 1;
            }
        }
        else if (a[0] != '-') { sfPath = a; }
        else { std::cerr << "Unknown option: " << a << "\n"; return 1; }
    }

    if (sfPath.empty()) { std::cerr << "Error: no .sf file specified\n"; return 1; }
    if (!segmentCsvPath.empty() && segmentWindow <= 0) {
        std::cerr << "Error: --segment-csv requires --segment-window > 0\n";
        return 1;
    }
    if ((mode == ScanForge::SelectionMode::SCOAP_CO_WEAR_LEVELING ||
         mode == ScanForge::SelectionMode::SCOAP_COMBINED_WEAR_LEVELING) &&
        segmentWindow <= 0) {
        std::cerr << "Error: *_wear_leveling modes require --segment-window > 0\n";
        return 1;
    }

    ScanForge::ScanData data;
    if (!ScanForge::parseScanData(sfPath, data)) return 1;

    // Build ratio list
    std::vector<double> ratios;
    if (doFine) {
        for (int p = 5; p <= 100; p += 5) ratios.push_back(p / 100.0);
    } else {
        ratios = {0.25, 0.50, 0.75, 1.0};
    }

    // Diagnosis / fault injection (uses full chain; --partial ignored)
    if (doDiagnose || !injectFaultSpec.empty()) {
        std::vector<int> chain(data.numFF);
        for (int i = 0; i < data.numFF; ++i) chain[i] = i;

        if (doDiagnose) {
            auto report = ScanForge::buildFaultDictionary(data, chain);
            ScanForge::printDiagnosisReport(report, data, chain);
            if (!diagCsvPath.empty()) {
                if (ScanForge::writeDiagnosisCsv(report, diagCsvPath))
                    std::cout << "  Fault dictionary CSV written to: " << diagCsvPath << "\n";
                else
                    std::cerr << "Error: cannot write diagnosis CSV: " << diagCsvPath << "\n";
            }
        }
        if (!injectFaultSpec.empty()) {
            int fpos = 0;
            ScanForge::FaultType ftype = ScanForge::FaultType::SA1;
            if (!ScanForge::parseFaultSpec(injectFaultSpec, data, chain, fpos, ftype))
                return 1;
            auto inj = ScanForge::injectFault(data, chain, fpos, ftype);
            ScanForge::printFaultInjection(inj, data, chain);
        }
        return 0;
    }

    if (doCoverage) {        if (!stressCsvPath.empty())
            std::cerr << "Warning: --stress-csv is ignored with --coverage\n";
        if (!segmentCsvPath.empty())
            std::cerr << "Warning: --segment-csv is ignored with --coverage\n";
        if (segmentWindow > 0)
            std::cerr << "Warning: --segment-window is ignored with --coverage\n";
        if (!summaryCsvPath.empty())
            std::cerr << "Warning: --summary-csv is ignored with --coverage\n";
        ScanForge::sweepCoverage(data, ratios, doCSV);
    } else if (doSweep) {
        if (!stressCsvPath.empty())
            std::cerr << "Warning: --stress-csv is ignored with --sweep\n";
        if (!segmentCsvPath.empty())
            std::cerr << "Warning: --segment-csv is ignored with --sweep "
                         "(use full/partial run to export segment CSV)\n";
        ScanForge::SweepConfig scfg;
        scfg.circuit_name = basenameSf(sfPath);
        scfg.wear_lambda = lambda;
        scfg.coverage_proxy_mode = proxyMode;
        scfg.segment_window = segmentWindow;
        if (!summaryCsvPath.empty()) {
            scfg.summary_csv_path = summaryCsvPath;
            scfg.csv_stdout = false;
        } else if (doCSV) {
            scfg.csv_stdout = true;
        }
        ScanForge::sweepPartialScan(data, ratios, mode, scfg);
    } else if (partialR > 0.0 && partialR < 1.0) {
        int k = std::max(1, (int)std::round(partialR * data.numFF));

        const std::vector<double> *stressPtr = nullptr;
        std::vector<double>        stressProf;
        if (mode == ScanForge::SelectionMode::SCOAP_CO_WEAR ||
            mode == ScanForge::SelectionMode::SCOAP_COMBINED_WEAR ||
            mode == ScanForge::SelectionMode::SCOAP_CO_WEAR_LEVELING ||
            mode == ScanForge::SelectionMode::SCOAP_COMBINED_WEAR_LEVELING) {
            stressProf = ScanForge::fullScanStressScores(data);
            stressPtr = &stressProf;
        }

        auto chain = ScanForge::selectFFs(data, k, mode, 42u, stressPtr, lambda, segmentWindow);
        auto agg = ScanForge::aggregateStressForChain(stressPtr ? stressProf
            : ScanForge::fullScanStressScores(data), chain);

        std::cout << std::fixed << std::setprecision(2);
        std::cout << "Partial scan ratio: " << partialR << "\n";
        std::cout << "Mode: " << modeDisplayName(mode) << "\n";
        if (mode == ScanForge::SelectionMode::SCOAP_CO_WEAR ||
            mode == ScanForge::SelectionMode::SCOAP_COMBINED_WEAR ||
            mode == ScanForge::SelectionMode::SCOAP_CO_WEAR_LEVELING ||
            mode == ScanForge::SelectionMode::SCOAP_COMBINED_WEAR_LEVELING)
            std::cout << "Lambda: " << std::setprecision(2) << lambda << "\n";
        std::cout << "Selected FFs: " << k << " / " << data.numFF << "\n";

        auto result = ScanForge::simulate(data, chain);
        if (segmentWindow > 0)
            ScanForge::applySegmentProfile(result, segmentWindow);
        std::cout << "Switching Activity: " << std::setprecision(4) << result.switchingActivity << "\n";
        std::cout << "Max Stress: " << std::setprecision(4) << agg.maxStress << "\n";
        std::cout << "Stress Variance: " << agg.variance << "\n";
        std::cout << "Stress Imbalance: " << agg.imbalance << "\n";

        ScanForge::printReport(result, data, chain);
        if (segmentWindow > 0 && !result.segments.empty()) {
            std::cout << "  Max segment stress (avg over W=" << result.segment_window_used
                      << "): " << std::fixed << std::setprecision(4)
                      << result.max_segment_stress << "\n";
            std::cout << "  Segment variance: " << result.segment_variance << "\n";
            std::cout << "  Hotspot segments: " << result.hotspot_count << "\n";
        }
        if (!stressCsvPath.empty()) {
            if (ScanForge::writeStressCsv(result, stressCsvPath))
                std::cout << "  Stress CSV written to: " << stressCsvPath << "\n";
            else
                std::cerr << "Error: cannot write stress CSV: " << stressCsvPath << "\n";
        }
        if (!segmentCsvPath.empty()) {
            if (ScanForge::writeSegmentCsv(result.segments, segmentCsvPath))
                std::cout << "  Segment CSV written to: " << segmentCsvPath << "\n";
            else
                std::cerr << "Error: cannot write segment CSV: " << segmentCsvPath << "\n";
        }
        auto cov = ScanForge::estimateCoverage(data, chain);
        std::cout << "  Estimated coverage: "
                  << cov.applicablePatterns << "/" << cov.totalPatterns
                  << " patterns applicable ("
                  << std::fixed << std::setprecision(1)
                  << cov.estimatedCoverage * 100 << "%)\n";
        auto px = ScanForge::computeCoverageProxy(data, chain, proxyMode);
        std::cout << "  Coverage proxy (" << (proxyMode == ScanForge::CoverageProxyMode::CO ? "co" :
              proxyMode == ScanForge::CoverageProxyMode::CONTROLLABILITY ? "controllability" : "combined")
                  << "): " << std::fixed << std::setprecision(4)
                  << px.proxy << "  (loss " << px.loss << ")\n";
    } else {
        // Full scan
        std::vector<int> chain(data.numFF);
        for (int i = 0; i < data.numFF; ++i) chain[i] = i;
        auto result = ScanForge::simulate(data, chain);
        if (segmentWindow > 0)
            ScanForge::applySegmentProfile(result, segmentWindow);
        ScanForge::printReport(result, data, chain);
        if (segmentWindow > 0 && !result.segments.empty()) {
            std::cout << "  Max segment stress (avg over W=" << result.segment_window_used
                      << "): " << std::fixed << std::setprecision(4)
                      << result.max_segment_stress << "\n";
            std::cout << "  Segment variance: " << result.segment_variance << "\n";
            std::cout << "  Hotspot segments: " << result.hotspot_count << "\n";
        }
        if (!stressCsvPath.empty()) {
            if (ScanForge::writeStressCsv(result, stressCsvPath))
                std::cout << "  Stress CSV written to: " << stressCsvPath << "\n";
            else
                std::cerr << "Error: cannot write stress CSV: " << stressCsvPath << "\n";
        }
        if (!segmentCsvPath.empty()) {
            if (ScanForge::writeSegmentCsv(result.segments, segmentCsvPath))
                std::cout << "  Segment CSV written to: " << segmentCsvPath << "\n";
            else
                std::cerr << "Error: cannot write segment CSV: " << segmentCsvPath << "\n";
        }
    }

    return 0;
}
