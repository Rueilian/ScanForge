// ScanForge — main.cpp
// CLI entry point for scan chain analysis and partial scan sweep.

#include "scan_chain.h"
#include "partial_scan.h"
#include <iostream>
#include <string>
#include <vector>
#include <cstdlib>
#include <cmath>

static void usage(const char *prog)
{
    std::cout <<
        "Usage: " << prog << " [options] <scan_data.sf>\n"
        "\n"
        "Options:\n"
        "  (no options)          Full scan analysis\n"
        "  --sweep               Sweep partial scan ratios 25/50/75/100%%\n"
        "  --partial <ratio>     Partial scan at given ratio (0.0–1.0)\n"
        "  --mode <co|combined|random>\n"
        "                        FF selection strategy (default: co)\n"
        "  -h, --help            Print this help\n"
        "\n"
        "  <scan_data.sf>  Data file exported by FAN_ATPG's 'add_scan_chains -o' command.\n";
}

int main(int argc, char *argv[])
{
    if (argc < 2) { usage(argv[0]); return 1; }

    std::string sfPath;
    bool        doSweep  = false;
    double      partialR = -1.0;
    ScanForge::SelectionMode mode = ScanForge::SelectionMode::SCOAP_CO;

    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "-h" || a == "--help") { usage(argv[0]); return 0; }
        else if (a == "--sweep")  { doSweep = true; }
        else if (a == "--partial" && i+1 < argc) { partialR = std::atof(argv[++i]); }
        else if (a == "--mode" && i+1 < argc) {
            std::string m = argv[++i];
            if (m == "combined") mode = ScanForge::SelectionMode::SCOAP_COMBINED;
            else if (m == "random") mode = ScanForge::SelectionMode::RANDOM;
            else mode = ScanForge::SelectionMode::SCOAP_CO;
        }
        else if (a[0] != '-') { sfPath = a; }
        else { std::cerr << "Unknown option: " << a << "\n"; return 1; }
    }

    if (sfPath.empty()) { std::cerr << "Error: no .sf file specified\n"; return 1; }

    ScanForge::ScanData data;
    if (!ScanForge::parseScanData(sfPath, data)) return 1;

    if (doSweep) {
        ScanForge::sweepPartialScan(data, {0.25, 0.50, 0.75, 1.0}, mode);
    } else if (partialR > 0.0 && partialR < 1.0) {
        int k = std::max(1, (int)std::round(partialR * data.numFF));
        auto chain = ScanForge::selectFFs(data, k, mode);
        auto result = ScanForge::simulate(data, chain);
        ScanForge::printReport(result, data, chain);
    } else {
        // Full scan
        std::vector<int> chain(data.numFF);
        for (int i = 0; i < data.numFF; ++i) chain[i] = i;
        auto result = ScanForge::simulate(data, chain);
        ScanForge::printReport(result, data, chain);
    }

    return 0;
}
