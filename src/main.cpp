// ScanForge — main.cpp
// CLI entry point: reads a .sf data file and runs scan chain analysis.

#include "scan_chain.h"
#include <iostream>

int main(int argc, char *argv[])
{
    if (argc < 2) {
        std::cerr << "Usage: scanforge <scan_data.sf>\n"
                  << "\n"
                  << "  <scan_data.sf>  Circuit + pattern data exported by FAN_ATPG's\n"
                  << "                  'add_scan_chains -o <file>' command.\n";
        return 1;
    }

    ScanForge::ScanData data;
    if (!ScanForge::parseScanData(argv[1], data))
        return 1;

    ScanForge::ScanResult result = ScanForge::simulate(data);
    ScanForge::printReport(result, data);

    return 0;
}
