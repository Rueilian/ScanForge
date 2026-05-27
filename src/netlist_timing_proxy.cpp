#include "netlist_timing_proxy.h"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <functional>
#include <iostream>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace ScanForge {

namespace {

struct GateArc {
    std::string output_net;
    std::vector<std::string> input_nets;
};

struct FFArc {
    std::string inst_name;
    std::string q_net;
    std::string d_net;
};

std::string trim(const std::string &s)
{
    std::size_t begin = 0;
    while (begin < s.size() && std::isspace(static_cast<unsigned char>(s[begin])))
        ++begin;
    std::size_t end = s.size();
    while (end > begin && std::isspace(static_cast<unsigned char>(s[end - 1])))
        --end;
    return s.substr(begin, end - begin);
}

bool isOutputPinName(const std::string &pin)
{
    return pin == "ZN" || pin == "Z" || pin == "Q" || pin == "QN" || pin == "Y";
}

bool isSequentialCell(const std::string &cell_type)
{
    return cell_type.find("DFF") != std::string::npos;
}

void parseInstance(const std::string &stmt,
                   std::vector<GateArc> &gates,
                   std::vector<FFArc> &ffs)
{
    std::string s = trim(stmt);
    if (s.empty())
        return;
    if (s.compare(0, 6, "module") == 0 || s.compare(0, 9, "endmodule") == 0)
        return;
    if (s.compare(0, 5, "input") == 0 || s.compare(0, 6, "output") == 0 ||
        s.compare(0, 4, "wire") == 0 || s.compare(0, 6, "assign") == 0)
        return;

    std::size_t lp = s.find('(');
    if (lp == std::string::npos)
        return;
    std::string header = trim(s.substr(0, lp));
    std::istringstream hs(header);
    std::string cell_type;
    std::string inst_name;
    hs >> cell_type >> inst_name;
    if (cell_type.empty() || inst_name.empty())
        return;

    std::unordered_map<std::string, std::string> pin_to_net;
    std::size_t pos = lp;
    while (true) {
        std::size_t dot = s.find('.', pos);
        if (dot == std::string::npos)
            break;
        std::size_t lpar = s.find('(', dot);
        std::size_t rpar = s.find(')', lpar);
        if (lpar == std::string::npos || rpar == std::string::npos)
            break;
        std::string pin = trim(s.substr(dot + 1, lpar - dot - 1));
        std::string net = trim(s.substr(lpar + 1, rpar - lpar - 1));
        pin_to_net[pin] = net;
        pos = rpar + 1;
    }

    if (isSequentialCell(cell_type)) {
        auto q_it = pin_to_net.find("Q");
        auto d_it = pin_to_net.find("D");
        if (q_it != pin_to_net.end() && d_it != pin_to_net.end())
            ffs.push_back({inst_name, q_it->second, d_it->second});
        return;
    }

    GateArc gate;
    for (const auto &kv : pin_to_net) {
        if (isOutputPinName(kv.first)) {
            gate.output_net = kv.second;
        } else if (kv.first != "CK" && kv.first != "CLK" &&
                   kv.first != "SE" && kv.first != "SI" && kv.first != "RN" &&
                   kv.first != "SN") {
            gate.input_nets.push_back(kv.second);
        }
    }
    if (!gate.output_net.empty() && !gate.input_nets.empty())
        gates.push_back(std::move(gate));
}

} // namespace

bool buildTimingProxyFromNetlist(const std::string &netlist_path,
                                 const ScanData &data,
                                 TimingRanking &out)
{
    std::ifstream in(netlist_path);
    if (!in) {
        std::cerr << "Error: cannot open netlist: " << netlist_path << "\n";
        return false;
    }

    std::vector<GateArc> gates;
    std::vector<FFArc> ff_arcs;

    std::string line;
    std::string stmt;
    while (std::getline(in, line)) {
        std::string t = trim(line);
        if (t.empty() || t.compare(0, 2, "//") == 0)
            continue;
        stmt += ' ';
        stmt += t;
        if (t.find(';') == std::string::npos)
            continue;
        parseInstance(stmt, gates, ff_arcs);
        stmt.clear();
    }

    if (ff_arcs.empty()) {
        std::cerr << "Error: no scan FF instances found in netlist: "
                  << netlist_path << "\n";
        return false;
    }

    std::unordered_set<std::string> ff_q_nets;
    std::unordered_map<std::string, std::vector<std::string>> driver_inputs;
    for (const auto &ff : ff_arcs)
        ff_q_nets.insert(ff.q_net);
    for (const auto &gate : gates)
        driver_inputs[gate.output_net] = gate.input_nets;

    std::unordered_map<std::string, double> memo_depth;
    std::unordered_set<std::string> active;
    std::function<double(const std::string &)> depthOf = [&](const std::string &net) -> double {
        auto memo_it = memo_depth.find(net);
        if (memo_it != memo_depth.end())
            return memo_it->second;
        if (ff_q_nets.count(net)) {
            memo_depth[net] = 0.0;
            return 0.0;
        }
        auto drv_it = driver_inputs.find(net);
        if (drv_it == driver_inputs.end()) {
            memo_depth[net] = 0.0;
            return 0.0;
        }
        if (active.count(net)) {
            memo_depth[net] = 0.0;
            return 0.0;
        }
        active.insert(net);
        double best = 0.0;
        for (const auto &src : drv_it->second)
            best = std::max(best, depthOf(src));
        active.erase(net);
        memo_depth[net] = best + 1.0;
        return memo_depth[net];
    };

    std::unordered_map<std::string, double> score_by_name;
    for (const auto &ff : ff_arcs)
        score_by_name[ff.inst_name] = depthOf(ff.d_net);

    out.score_by_ff.assign(data.numFF, 0.0);
    out.entries_desc.clear();
    out.entries_desc.reserve(data.numFF);
    for (int i = 0; i < data.numFF; ++i) {
        const std::string &name = data.ffs[i].name;
        auto it = score_by_name.find(name);
        if (it == score_by_name.end()) {
            std::cerr << "Error: FF \"" << name
                      << "\" from .sf data not found in netlist FF instances\n";
            return false;
        }
        out.score_by_ff[i] = it->second;
        out.entries_desc.push_back({i, name, it->second});
    }

    std::sort(out.entries_desc.begin(), out.entries_desc.end(),
              [](const TimingRankingEntry &a, const TimingRankingEntry &b) {
                  if (a.score != b.score)
                      return a.score > b.score;
                  return a.ff_index < b.ff_index;
              });
    return true;
}

} // namespace ScanForge
