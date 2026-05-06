// ScanForge — verilog_netlist.cpp
// Structural Verilog: flip-flop instances + combinational fanout → one FF→FF edge per
// Q-to-D path through non-FF logic (paths do not traverse other FFs' Q outputs).

#include "scan_chain.h"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <iostream>
#include <queue>
#include <sstream>
#include <unordered_map>
#include <unordered_set>
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
        return !out.empty();
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
        ++pos;
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

    static bool isKeywordNoise(const std::string &low)
    {
        return low == "posedge" || low == "negedge" || low == "or" || low == "and" ||
               low == "buf" || low == "wire" || low == "input" || low == "output" ||
               low == "assign" || low == "reg" || low == "logic" || low == "function" ||
               low == "nand" || low == "nor" || low == "xor" || low == "xnor" || low == "not";
    }
};

// Nets referenced in an expression: recurse into {…} and (…) so assign RHS/LHS
// concatenations contribute fanout (e.g. assign {y_hi,y_lo} = {a,b}).
void collectNetIdsFromExpr(const std::string &expr, std::vector<std::string> &out)
{
    Parser p{expr, 0};
    while (!p.eof()) {
        std::string num;
        if (p.parseVerilogNumber(num))
            continue;
        p.skipWs();
        if (p.eof())
            break;
        char c = p.s[p.pos];
        if (c == '{') {
            ++p.pos;
            int depth = 1;
            std::size_t start = p.pos;
            while (p.pos < p.s.size() && depth > 0) {
                if (p.s[p.pos] == '{')
                    ++depth;
                else if (p.s[p.pos] == '}')
                    --depth;
                if (depth > 0)
                    ++p.pos;
                else
                    break;
            }
            std::string inner = p.s.substr(start, p.pos - start);
            if (p.pos < p.s.size() && p.s[p.pos] == '}')
                ++p.pos;
            for (const auto &part : splitTopLevelCommas(inner))
                collectNetIdsFromExpr(trimWs(part), out);
            continue;
        }
        if (c == '(') {
            ++p.pos;
            int depth = 1;
            std::size_t start = p.pos;
            while (p.pos < p.s.size() && depth > 0) {
                if (p.s[p.pos] == '(')
                    ++depth;
                else if (p.s[p.pos] == ')')
                    --depth;
                if (depth > 0)
                    ++p.pos;
                else
                    break;
            }
            std::string inner = p.s.substr(start, p.pos - start);
            if (p.pos < p.s.size() && p.s[p.pos] == ')')
                ++p.pos;
            collectNetIdsFromExpr(inner, out);
            continue;
        }
        if (c == '[') {
            ++p.pos;
            int depth = 1;
            while (p.pos < p.s.size() && depth > 0) {
                if (p.s[p.pos] == '[')
                    ++depth;
                else if (p.s[p.pos] == ']')
                    --depth;
                ++p.pos;
            }
            continue;
        }
        if (c == '~' || c == '^' || c == '+' || c == '-' || c == '*' || c == '/' || c == '?' ||
            c == ':') {
            ++p.pos;
            continue;
        }
        if (c == '!') {
            if (p.pos + 1 < p.s.size() && p.s[p.pos + 1] == '=')
                p.pos += 2;
            else
                ++p.pos;
            continue;
        }
        if (c == '&') {
            if (p.pos + 1 < p.s.size() && p.s[p.pos + 1] == '&')
                p.pos += 2;
            else
                ++p.pos;
            continue;
        }
        if (c == '|') {
            if (p.pos + 1 < p.s.size() && p.s[p.pos + 1] == '|')
                p.pos += 2;
            else
                ++p.pos;
            continue;
        }
        if (c == '<') {
            if (p.pos + 1 < p.s.size() &&
                (p.s[p.pos + 1] == '=' || p.s[p.pos + 1] == '<'))
                p.pos += 2;
            else
                ++p.pos;
            continue;
        }
        if (c == '>') {
            if (p.pos + 1 < p.s.size() && p.s[p.pos + 1] == '=')
                p.pos += 2;
            else
                ++p.pos;
            continue;
        }
        if (c == '=') {
            if (p.pos + 1 < p.s.size() && p.s[p.pos + 1] == '=')
                p.pos += 2;
            else
                ++p.pos;
            continue;
        }
        std::string id;
        if (p.parseIdent(id)) {
            std::string low = lowerCopy(id);
            if (Parser::isKeywordNoise(low))
                continue;
            out.push_back(id);
        } else
            ++p.pos;
    }
}

// LHS nets for assign: single net or concatenation {n1,n2,...}.
std::vector<std::string> assignLhsNetList(const std::string &lhsTrimmed)
{
    std::string lhs = trimWs(lhsTrimmed);
    std::vector<std::string> nets;
    if (!lhs.empty() && lhs.front() == '{') {
        if (lhs.size() < 2 || lhs.back() != '}')
            return nets;
        std::string inner = trimWs(lhs.substr(1, lhs.size() - 2));
        for (const auto &part : splitTopLevelCommas(inner)) {
            std::string one;
            if (Parser{part, 0}.firstNetToken(part, one))
                nets.push_back(one);
        }
        return nets;
    }
    std::string one;
    if (Parser{lhs, 0}.firstNetToken(lhs, one))
        nets.push_back(one);
    return nets;
}

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

bool portNameIsLikelyOutput(const std::string &port)
{
    std::string l = lowerCopy(port);
    if (l == "y" || l == "z" || l == "zn" || l == "o" || l == "out" || l == "q" ||
        l == "s" || l == "so" || l == "co" || l == "sum" || l == "cout" || l == "y1" ||
        l == "f")
        return true;
    if (!l.empty() && l[0] == 'y' && l.size() <= 3)
        return true;
    return false;
}

bool portNameIsLikelyInput(const std::string &port)
{
    std::string l = lowerCopy(port);
    if (l == "a" || l == "b" || l == "c" || l == "d" || l == "e" || l == "in" || l == "i" ||
        l == "i0" || l == "i1" || l == "a1" || l == "a2" || l == "b1" || l == "b2" ||
        l == "dat" || l == "d0" || l == "d1" || l == "s" || l == "sel" || l == "ci" ||
        l == "cin" || l == "a0" || l == "b0")
        return true;
    if (l.size() == 2 && l[0] == 'a' && std::isdigit(static_cast<unsigned char>(l[1])))
        return true;
    if (l.size() == 2 && l[0] == 'b' && std::isdigit(static_cast<unsigned char>(l[1])))
        return true;
    return false;
}

// Fanout[u]: nets reachable in one combinational step from net u (u drives gate inputs →
// gate outputs). Uses OR-semantics: if any input of a multi-input gate is u, output is listed
// (over-approx for AND/OR; common for “may affect” reachability).
void addCombFanoutEdge(std::unordered_map<std::string, std::vector<std::string>> &fanout,
                       const std::string &from,
                       const std::string &to)
{
    if (from.empty() || to.empty() || from == to)
        return;
    auto &v = fanout[from];
    v.push_back(to);
}

void dedupeFanout(std::unordered_map<std::string, std::vector<std::string>> &fanout)
{
    for (auto &kv : fanout) {
        auto &v = kv.second;
        std::sort(v.begin(), v.end());
        v.erase(std::unique(v.begin(), v.end()), v.end());
    }
}

// Parse primitive or generic gate: cell inst ( .p(expr), ... ) or cell inst (a,b,y);
// Returns false if not a gate instance (caller skips).
bool parseGateInstance(Parser &p, std::string &cellLower,
                       std::vector<std::pair<std::string, std::string>> &namedNets,
                       std::vector<std::string> &positionalNets)
{
    std::size_t save = p.pos;
    std::string cell;
    if (!p.parseIdent(cell))
        return false;
    if (isLikelyFFCell(cell)) {
        p.pos = save;
        return false;
    }
    cellLower = lowerCopy(cell);

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

    namedNets.clear();
    positionalNets.clear();

    if (portsBlob.find('.') != std::string::npos) {
        Parser pp{portsBlob, 0};
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
            if (Parser{inner, 0}.firstNetToken(inner, sig))
                namedNets.push_back({pname, sig});
            pp.skipWs();
            pp.consume(',');
        }
        return true;
    }

    for (const auto &part : splitTopLevelCommas(portsBlob)) {
        std::string sig;
        if (Parser{part, 0}.firstNetToken(part, sig))
            positionalNets.push_back(sig);
    }
    return true;
}

bool isBuiltinVerilogPrimitive(const std::string &cellLower)
{
    static const char *builtins[] = {
        "and",  "nand", "or",   "nor",  "xor", "xnor", "not", "buf",  "bufif0", "bufif1",
        "nmos", "pmos", "tran", "rtran", "pullup", "pulldown", "tranif0", "tranif1"};
    for (const char *b : builtins) {
        if (cellLower == b)
            return true;
    }
    return false;
}

// User-defined module: unknown port direction — connect every parsed net to every other
// (may-affect over-approx for combinational black boxes).
void registerBlackBoxFanout(const std::vector<std::pair<std::string, std::string>> &namedNets,
                            std::unordered_map<std::string, std::vector<std::string>> &fanout)
{
    std::vector<std::string> nets;
    nets.reserve(namedNets.size());
    for (const auto &pr : namedNets) {
        if (!pr.second.empty())
            nets.push_back(pr.second);
    }
    std::sort(nets.begin(), nets.end());
    nets.erase(std::unique(nets.begin(), nets.end()), nets.end());
    for (std::size_t i = 0; i < nets.size(); ++i) {
        for (std::size_t j = 0; j < nets.size(); ++j) {
            if (i == j) continue;
            addCombFanoutEdge(fanout, nets[i], nets[j]);
        }
    }
}

void registerGateFanout(const std::string &cellLower,
                        const std::vector<std::pair<std::string, std::string>> &namedNets,
                        const std::vector<std::string> &positionalNets,
                        std::unordered_map<std::string, std::vector<std::string>> &fanout)
{
    std::vector<std::string> ins;
    std::vector<std::string> outs;

    if (!namedNets.empty()) {
        for (const auto &pr : namedNets) {
            const std::string &pn = pr.first;
            const std::string &nt = pr.second;
            if (portNameIsLikelyOutput(pn))
                outs.push_back(nt);
            else if (portNameIsLikelyInput(pn) || !portNameIsLikelyOutput(pn))
                ins.push_back(nt);
        }
        if (outs.empty() && !isBuiltinVerilogPrimitive(cellLower)) {
            registerBlackBoxFanout(namedNets, fanout);
            return;
        }
        if (outs.empty() && !ins.empty()) {
            if (cellLower == "not" || cellLower == "buf" || cellLower == "inv") {
                if (namedNets.size() >= 2) {
                    ins.clear();
                    outs.clear();
                    for (const auto &pr : namedNets) {
                        std::string l = lowerCopy(pr.first);
                        if (l == "a" || l == "in" || l == "i" || l == "d")
                            ins.push_back(pr.second);
                        else if (l == "y" || l == "z" || l == "zn" || l == "o" || l == "q")
                            outs.push_back(pr.second);
                    }
                }
            }
        }
    } else if (!positionalNets.empty()) {
        // Verilog built-in primitives: (output, input, ...) e.g. buf(y,a), and(y,a,b).
        if (positionalNets.size() < 2)
            return;
        outs.push_back(positionalNets[0]);
        for (std::size_t i = 1; i < positionalNets.size(); ++i)
            ins.push_back(positionalNets[i]);
    }

    if (outs.empty() || ins.empty())
        return;

    for (const std::string &inNet : ins) {
        for (const std::string &outNet : outs)
            addCombFanoutEdge(fanout, inNet, outNet);
    }
}

void scanCombInstances(const std::string &body,
                       std::unordered_map<std::string, std::vector<std::string>> &fanout)
{
    Parser p{body, 0};
    while (!p.eof()) {
        std::string cellLower;
        std::vector<std::pair<std::string, std::string>> named;
        std::vector<std::string> pos;
        std::size_t save = p.pos;
        if (parseGateInstance(p, cellLower, named, pos)) {
            registerGateFanout(cellLower, named, pos, fanout);
            continue;
        }
        p.pos = save;
        ++p.pos;
    }
}

// assign lhs = rhs ;  (lhs may be concatenation {a,b})
bool parseAssignStatement(Parser &p, std::string &lhsBlob, std::string &rhsBlob)
{
    std::size_t save = p.pos;
    std::string kw;
    if (!p.parseIdent(kw) || lowerCopy(kw) != "assign") {
        p.pos = save;
        return false;
    }
    p.skipWs();
    std::size_t start = p.pos;
    int depth = 0;
    while (!p.eof()) {
        if (p.s[p.pos] == '(' || p.s[p.pos] == '[' || p.s[p.pos] == '{')
            ++depth;
        else if (p.s[p.pos] == ')' || p.s[p.pos] == ']' || p.s[p.pos] == '}')
            depth = std::max(0, depth - 1);
        else if (depth == 0 && p.s[p.pos] == '=') {
            lhsBlob = trimWs(p.s.substr(start, p.pos - start));
            ++p.pos;
            std::size_t rstart = p.pos;
            while (!p.eof() && p.s[p.pos] != ';')
                ++p.pos;
            rhsBlob = trimWs(p.s.substr(rstart, p.pos - rstart));
            if (assignLhsNetList(lhsBlob).empty()) {
                p.pos = save;
                return false;
            }
            if (p.eof() || p.s[p.pos] != ';') {
                p.pos = save;
                return false;
            }
            ++p.pos;
            return true;
        }
        ++p.pos;
    }
    p.pos = save;
    return false;
}

void scanAssigns(const std::string &body,
                 std::unordered_map<std::string, std::vector<std::string>> &fanout)
{
    Parser p{body, 0};
    while (!p.eof()) {
        std::string lhsBlob, rhs;
        if (parseAssignStatement(p, lhsBlob, rhs)) {
            std::vector<std::string> lhsNets = assignLhsNetList(lhsBlob);
            std::vector<std::string> rhsNets;
            collectNetIdsFromExpr(rhs, rhsNets);
            std::sort(rhsNets.begin(), rhsNets.end());
            rhsNets.erase(std::unique(rhsNets.begin(), rhsNets.end()), rhsNets.end());
            for (const std::string &inNet : rhsNets) {
                for (const std::string &outNet : lhsNets)
                    addCombFanoutEdge(fanout, inNet, outNet);
            }
            continue;
        }
        ++p.pos;
    }
}

std::vector<SeqEdge> combReachableFfEdges(
    int numFF,
    const std::unordered_map<std::string, int> &ff_by_name,
    const std::vector<FFInst> &insts,
    const std::unordered_map<std::string, std::vector<std::string>> &fanout)
{
    std::unordered_map<std::string, int> net_to_q_ff; // net → FF whose Q drives that net
    // One D net can feed multiple FFs (e.g. broadcast or scan-SI sharing same wire).
    std::unordered_map<std::string, std::vector<int>> net_to_d_ffs; // net → FFs whose D is that net
    std::vector<std::string> ff_q_net(static_cast<std::size_t>(numFF));
    std::vector<std::string> ff_d_net(static_cast<std::size_t>(numFF));

    for (const auto &fi : insts) {
        auto it = ff_by_name.find(fi.inst);
        if (it == ff_by_name.end())
            continue;
        int idx = it->second;
        if (!fi.q_net.empty()) {
            net_to_q_ff[fi.q_net] = idx;
            ff_q_net[static_cast<std::size_t>(idx)] = fi.q_net;
        }
        if (!fi.d_net.empty()) {
            net_to_d_ffs[fi.d_net].push_back(idx);
            ff_d_net[static_cast<std::size_t>(idx)] = fi.d_net;
        }
    }

    std::vector<SeqEdge> edges;

    for (int src = 0; src < numFF; ++src) {
        const std::string &start = ff_q_net[static_cast<std::size_t>(src)];
        if (start.empty())
            continue;

        std::queue<std::string> q;
        std::unordered_set<std::string> vis;
        q.push(start);
        vis.insert(start);

        while (!q.empty()) {
            std::string u = q.front();
            q.pop();

            auto dit = net_to_d_ffs.find(u);
            if (dit != net_to_d_ffs.end()) {
                for (int dst : dit->second) {
                    if (dst != src)
                        edges.push_back(SeqEdge{src, dst});
                }
            }

            auto fit = fanout.find(u);
            if (fit == fanout.end())
                continue;
            for (const std::string &v : fit->second) {
                if (vis.count(v))
                    continue;
                // Do not expand through another FF's Q output net (sequential boundary).
                auto qit = net_to_q_ff.find(v);
                if (qit != net_to_q_ff.end() && qit->second != src)
                    continue;
                vis.insert(v);
                q.push(v);
            }
        }
    }

    std::sort(edges.begin(), edges.end(), [](const SeqEdge &a, const SeqEdge &b) {
        if (a.from != b.from) return a.from < b.from;
        return a.to < b.to;
    });
    edges.erase(std::unique(edges.begin(), edges.end(),
                            [](const SeqEdge &a, const SeqEdge &b) {
                                return a.from == b.from && a.to == b.to;
                            }),
                edges.end());
    return edges;
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

    std::unordered_map<std::string, std::vector<std::string>> fanout;
    scanCombInstances(src, fanout);
    scanAssigns(src, fanout);
    dedupeFanout(fanout);

    std::vector<SeqEdge> new_edges = combReachableFfEdges(data.numFF, ff_by_name, insts, fanout);

    int unmatched_inst = 0;
    int matched_by_name = 0;
    for (const auto &fi : insts) {
        auto it = ff_by_name.find(fi.inst);
        if (it == ff_by_name.end())
            ++unmatched_inst;
        else
            ++matched_by_name;
    }

    if (new_edges.empty() && data.numFF > 0 && (int)insts.size() == data.numFF &&
        matched_by_name == 0) {
        std::cerr << "Note: flip-flop instance names in the netlist do not match .sf FF_NAMES; "
                     "mapping the first " << data.numFF
                  << " dff-like instances to FF_NAMES in file order.\n";
        ff_by_name.clear();
        for (int j = 0; j < data.numFF; ++j)
            ff_by_name[insts[static_cast<std::size_t>(j)].inst] = j;
        new_edges = combReachableFfEdges(data.numFF, ff_by_name, insts, fanout);
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

    data.seq_edges          = std::move(merged);
    data.seq_netlist_loaded = true;

    if (unmatched_inst > 0 && matched_by_name > 0) {
        std::cerr << "Note: " << unmatched_inst
                  << " flip-flop-like cell(s) had instance names not in .sf FF_NAMES "
                     "(ignored).\n";
    }
    std::cerr << "Sequential FF graph: " << data.seq_edges.size()
              << " directed edge(s) (combinational reachability from each FF's Q to others' "
                 "D; " << edges_from_this_netlist << " from this netlist).\n";
    if (data.seq_edges.empty() && !insts.empty()) {
        std::cerr << "Hint: no Q→D paths through parsed assign / primitives / named module "
                     "ports. Zero edges if the netlist uses only unsupported constructs.\n";
    }
    return true;
}

} // namespace ScanForge
