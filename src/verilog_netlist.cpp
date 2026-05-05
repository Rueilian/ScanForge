// ScanForge — verilog_netlist.cpp
// Lightweight structural Verilog: flip-flop instances → one combinational-stage FF edge
// per inferred Q→D link (no transitive edges across intermediate FFs).

#include "scan_chain.h"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <iostream>
#include <sstream>
#include <unordered_map>
#include <vector>

namespace ScanForge {

namespace {

std::string readWholeFile(const std::string &path)
{
    std::ifstream f(path, std::ios::in | std::ios::binary);
    if (!f) return {};
    return std::string(std::istreambuf_iterator<char>(f), std::istreambuf_iterator<char>());
}

std::string stripComments(const std::string &in)
{
    std::string o;
    o.reserve(in.size());
    for (std::size_t i = 0; i < in.size();) {
        if (in[i] == '/' && i + 1 < in.size()) {
            if (in[i + 1] == '/') {
                while (i < in.size() && in[i] != '\n')
                    ++i;
                continue;
            }
            if (in[i + 1] == '*') {
                i += 2;
                while (i + 1 < in.size() && !(in[i] == '*' && in[i + 1] == '/'))
                    ++i;
                i = (i + 1 < in.size()) ? i + 2 : in.size();
                continue;
            }
        }
        o.push_back(in[i++]);
    }
    return o;
}

static inline void toLowerInPlace(std::string &s)
{
    for (char &c : s)
        c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
}

std::string lowerCopy(std::string s)
{
    toLowerInPlace(s);
    return s;
}

bool isLikelyFFCell(const std::string &cell)
{
    std::string l = lowerCopy(cell);
    if (l == "dff")
        return true;
    // Match DFF_X1, DFFB, etc.
    if (l.find("dff") != std::string::npos)
        return true;
    static const char *frag[] = {"_dff", "_dfxtp", "_dff_", "dffsr", "sdff", "_sdlatch"};
    for (const char *p : frag) {
        if (l.find(p) != std::string::npos)
            return true;
    }
    return false;
}

bool isClockPort(const std::string &port)
{
    std::string l = lowerCopy(port);
    return l == "clk" || l == "clock" || l == "cp" || l == "ck" || l == "c";
}

bool isResetPort(const std::string &port)
{
    std::string l = lowerCopy(port);
    return l == "reset" || l == "rst" || l == "rn" || l == "cdn" || l == "sdn";
}

bool isDataPort(const std::string &port)
{
    std::string l = lowerCopy(port);
    return l == "d" || l == "dn" || l == "di" || l == "din" || l == "data" ||
           l == "next" || l == "in" || l == "si" || l == "t" || l == "j" || l == "k";
}

bool isQPort(const std::string &port)
{
    std::string l = lowerCopy(port);
    return l == "q" || l == "so";
}

std::string trimWs(std::string s)
{
    while (!s.empty() && std::isspace(static_cast<unsigned char>(s.front())))
        s.erase(s.begin());
    while (!s.empty() && std::isspace(static_cast<unsigned char>(s.back())))
        s.pop_back();
    return s;
}

// Split port list at commas not inside (), [], {}.
std::vector<std::string> splitTopLevelCommas(const std::string &blob)
{
    std::vector<std::string> parts;
    int depth = 0;
    std::size_t start = 0;
    for (std::size_t i = 0; i < blob.size(); ++i) {
        char c = blob[i];
        if (c == '(' || c == '[' || c == '{')
            ++depth;
        else if (c == ')' || c == ']' || c == '}')
            depth = std::max(0, depth - 1);
        else if (c == ',' && depth == 0) {
            parts.push_back(trimWs(blob.substr(start, i - start)));
            start = i + 1;
        }
    }
    parts.push_back(trimWs(blob.substr(start)));
    while (!parts.empty() && parts.back().empty())
        parts.pop_back();
    return parts;
}

struct Parser {
    const std::string &s;
    std::size_t        pos = 0;

    void skipWs()
    {
        while (pos < s.size() &&
               std::isspace(static_cast<unsigned char>(s[pos])))
            ++pos;
    }

    bool eof() const { return pos >= s.size(); }

    bool parseIdent(std::string &out)
    {
        skipWs();
        if (eof())
            return false;
        if (s[pos] == '\\') {
            ++pos;
            std::size_t start = pos;
            while (pos < s.size() &&
                   !std::isspace(static_cast<unsigned char>(s[pos])))
                ++pos;
            out = s.substr(start, pos - start);
            return !out.empty();
        }
        if (!std::isalpha(static_cast<unsigned char>(s[pos])) && s[pos] != '_')
            return false;
        std::size_t start = pos;
        while (pos < s.size() &&
               (std::isalnum(static_cast<unsigned char>(s[pos])) || s[pos] == '_' ||
                s[pos] == '$'))
            ++pos;
        out = s.substr(start, pos - start);
        return true;
    }

    bool consume(char c)
    {
        skipWs();
        if (!eof() && s[pos] == c) {
            ++pos;
            return true;
        }
        return false;
    }

    // Parse from current '(' including nested parens; leaves pos after ')'.
    bool parseParenGroup(std::string &inner)
    {
        skipWs();
        if (eof() || s[pos] != '(')
            return false;
        ++pos;
        int depth = 1;
        std::size_t start = pos;
        while (pos < s.size() && depth > 0) {
            if (s[pos] == '(')
                ++depth;
            else if (s[pos] == ')')
                --depth;
            if (depth > 0)
                ++pos;
            else
                break;
        }
        if (depth != 0 || pos >= s.size())
            return false;
        inner = s.substr(start, pos - start);
        ++pos; // skip ')'
        return true;
    }

    void skipOptionalAttributeParen()
    {
        skipWs();
        if (eof() || s[pos] != '(')
            return;
        int depth = 1;
        ++pos;
        while (pos < s.size() && depth > 0) {
            if (s[pos] == '(')
                ++depth;
            else if (s[pos] == ')')
                --depth;
            ++pos;
        }
    }

    bool parseVerilogNumber(std::string &out)
    {
        skipWs();
        if (eof())
            return false;
        char c = s[pos];
        if (!std::isdigit(static_cast<unsigned char>(c)) && c != '\'')
            return false;
        std::size_t start = pos;
        if (std::isdigit(static_cast<unsigned char>(c))) {
            while (pos < s.size() &&
                   std::isdigit(static_cast<unsigned char>(s[pos])))
                ++pos;
            if (pos < s.size() && s[pos] == '\'') {
                ++pos;
                if (pos < s.size() &&
                    (std::isalnum(static_cast<unsigned char>(s[pos])) || s[pos] == '?'))
                    ++pos;
                while (pos < s.size() &&
                       std::isalnum(static_cast<unsigned char>(s[pos])))
                    ++pos;
            }
        } else if (c == '\'') {
            ++pos;
            if (pos < s.size())
                ++pos;
            while (pos < s.size() &&
                   std::isalnum(static_cast<unsigned char>(s[pos])))
                ++pos;
        }
        out = s.substr(start, pos - start);
        return true;
    }

    // First hierarchical identifier token in an expression (skip constants).
    bool firstNetToken(std::string expr, std::string &net)
    {
        Parser sub{expr, 0};
        sub.skipWs();
        while (!sub.eof()) {
            std::string id;
            std::string num;
            if (sub.parseVerilogNumber(num))
                continue;
            if (sub.consume('(') || sub.consume('{') || sub.consume('['))
                continue;
            if (sub.consume(')') || sub.consume('}') || sub.consume(']') ||
                sub.consume(',') || sub.consume(';') || sub.consume(':'))
                continue;
            if (sub.parseIdent(id)) {
                std::string low = lowerCopy(id);
                if (low == "posedge" || low == "negedge" || low == "or" ||
                    low == "and" || low == "buf")
                    continue;
                net = id;
                return true;
            }
            ++sub.pos;
        }
        return false;
    }
};

// Positional ports: ISCAS dff (CK, reset, Q, D) or (clk, D, Q).
void inferPortsPositional(const std::string &portsBlob, std::string &dnet, std::string &qnet)
{
    auto parts = splitTopLevelCommas(portsBlob);
    if (parts.empty())
        return;

    if (portsBlob.find('.') != std::string::npos)
        return;

    const std::size_t n = parts.size();
    if (n >= 4) {
        qnet = trimWs(parts[n - 2]);
        dnet = trimWs(parts[n - 1]);
        return;
    }
    if (n == 3) {
        dnet = trimWs(parts[1]);
        qnet = trimWs(parts[2]);
    }
}

struct FFInst {
    std::string inst;
    std::string d_net;
    std::string q_net;
};

bool parseFfInstance(Parser &p, FFInst &out)
{
    std::size_t save = p.pos;
    std::string cell;
    if (!p.parseIdent(cell) || !isLikelyFFCell(cell)) {
        p.pos = save;
        return false;
    }

    p.skipWs();
    if (!p.eof() && p.s[p.pos] == '#') {
        ++p.pos;
        p.skipWs();
        std::string junk;
        if (!p.parseParenGroup(junk)) {
            p.pos = save;
            return false;
        }
    }

    std::string inst;
    if (!p.parseIdent(inst)) {
        p.pos = save;
        return false;
    }

    std::string portsBlob;
    if (!p.parseParenGroup(portsBlob)) {
        p.pos = save;
        return false;
    }

    Parser pp{portsBlob, 0};
    std::string dnet, qnet;
    while (true) {
        pp.skipWs();
        if (pp.eof())
            break;
        if (!pp.consume('.')) {
            ++pp.pos;
            continue;
        }
        std::string pname;
        if (!pp.parseIdent(pname))
            break;
        std::string inner;
        if (!pp.parseParenGroup(inner))
            break;

        std::string sig;
        if (!Parser{inner, 0}.firstNetToken(inner, sig))
            continue;
        if (isClockPort(pname) || isResetPort(pname))
            continue;
        if (isDataPort(pname))
            dnet = sig;
        else if (isQPort(pname))
            qnet = sig;

        pp.skipWs();
        pp.consume(',');
    }

    std::string pq, pd;
    inferPortsPositional(portsBlob, pd, pq);
    if (dnet.empty())
        dnet = pd;
    if (qnet.empty())
        qnet = pq;

    out.inst  = inst;
    out.d_net = dnet;
    out.q_net = qnet;
    return !inst.empty();
}

void scanFfInstances(const std::string &body, std::vector<FFInst> &out)
{
    Parser p{body, 0};
    while (!p.eof()) {
        FFInst fi;
        if (parseFfInstance(p, fi))
            out.push_back(std::move(fi));
        else
            ++p.pos;
    }
}

} // namespace

bool mergeSequentialEdgesFromVerilog(ScanData &data, const std::string &path)
{
    std::string raw = readWholeFile(path);
    if (raw.empty()) {
        std::cerr << "Error: cannot read Verilog netlist " << path << "\n";
        return false;
    }

    std::string src = stripComments(raw);
    std::vector<FFInst> insts;
    scanFfInstances(src, insts);

    std::unordered_map<std::string, int> ff_by_name;
    ff_by_name.reserve(static_cast<std::size_t>(data.numFF) * 2);
    for (int i = 0; i < data.numFF; ++i)
        ff_by_name[data.ffs[i].name] = i;

    std::unordered_map<std::string, int> net_q_driver;
    int unmatched_inst = 0;
    int matched_by_name = 0;

    for (const auto &fi : insts) {
        auto it = ff_by_name.find(fi.inst);
        if (it == ff_by_name.end()) {
            ++unmatched_inst;
            continue;
        }
        ++matched_by_name;
        int idx = it->second;
        if (!fi.q_net.empty())
            net_q_driver[fi.q_net] = idx;
    }

    std::vector<SeqEdge> new_edges;
    for (const auto &fi : insts) {
        auto it = ff_by_name.find(fi.inst);
        if (it == ff_by_name.end())
            continue;
        int to = it->second;
        if (fi.d_net.empty())
            continue;
        auto dit = net_q_driver.find(fi.d_net);
        if (dit == net_q_driver.end())
            continue;
        int from = dit->second;
        if (from == to)
            continue;
        new_edges.push_back(SeqEdge{from, to});
    }

    std::sort(new_edges.begin(), new_edges.end(),
              [](const SeqEdge &a, const SeqEdge &b) {
                  if (a.from != b.from) return a.from < b.from;
                  return a.to < b.to;
              });
    new_edges.erase(std::unique(new_edges.begin(), new_edges.end(),
                                [](const SeqEdge &a, const SeqEdge &b) {
                                    return a.from == b.from && a.to == b.to;
                                }),
                     new_edges.end());

    if (new_edges.empty() && data.numFF > 0 &&
        (int)insts.size() == data.numFF && matched_by_name == 0) {
        std::cerr << "Note: flip-flop instance names in the netlist do not match .sf FF_NAMES; "
                     "mapping the first " << data.numFF
                  << " dff-like instances to FF_NAMES in file order.\n";
        net_q_driver.clear();
        for (int j = 0; j < data.numFF; ++j) {
            if (!insts[static_cast<std::size_t>(j)].q_net.empty())
                net_q_driver[insts[static_cast<std::size_t>(j)].q_net] = j;
        }
        for (int j = 0; j < data.numFF; ++j) {
            const auto &fi = insts[static_cast<std::size_t>(j)];
            if (fi.d_net.empty())
                continue;
            auto dit = net_q_driver.find(fi.d_net);
            if (dit == net_q_driver.end())
                continue;
            int from = dit->second;
            if (from == j)
                continue;
            new_edges.push_back(SeqEdge{from, j});
        }
        std::sort(new_edges.begin(), new_edges.end(),
                  [](const SeqEdge &a, const SeqEdge &b) {
                      if (a.from != b.from) return a.from < b.from;
                      return a.to < b.to;
                  });
        new_edges.erase(std::unique(new_edges.begin(), new_edges.end(),
                                    [](const SeqEdge &a, const SeqEdge &b) {
                                        return a.from == b.from && a.to == b.to;
                                    }),
                          new_edges.end());
    }

    const std::size_t edges_from_this_netlist = new_edges.size();

    std::vector<SeqEdge> merged = data.seq_edges;
    merged.insert(merged.end(), new_edges.begin(), new_edges.end());

    std::sort(merged.begin(), merged.end(),
              [](const SeqEdge &a, const SeqEdge &b) {
                  if (a.from != b.from) return a.from < b.from;
                  return a.to < b.to;
              });
    merged.erase(std::unique(merged.begin(), merged.end(),
                             [](const SeqEdge &a, const SeqEdge &b) {
                                 return a.from == b.from && a.to == b.to;
                             }),
                 merged.end());

    data.seq_edges      = std::move(merged);
    data.seq_netlist_loaded = true;

    if (unmatched_inst > 0 && matched_by_name > 0) {
        std::cerr << "Note: " << unmatched_inst
                  << " flip-flop-like cell(s) had instance names not in .sf FF_NAMES "
                     "(ignored).\n";
    }
    std::cerr << "Sequential FF graph: " << data.seq_edges.size()
              << " directed edge(s) (one per inferred Q→D link through combinational logic "
                 "only; " << edges_from_this_netlist << " from this netlist).\n";
    if (data.seq_edges.empty() && !insts.empty()) {
        std::cerr << "Hint: many gate-level netlists (e.g. ISCAS s27) connect each FF D pin "
                     "through combinational logic, so there are no FF-to-FF wires and this "
                     "count is zero. Use a netlist with explicit FF-to-FF nets, or a "
                     "structural flow where Q and D share the same net name.\n";
    }
    return true;
}

} // namespace ScanForge
