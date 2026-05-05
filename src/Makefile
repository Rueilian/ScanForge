CXX      := g++
CXXFLAGS := -std=c++14 -O2 -Wall -Wextra
TARGET   := scanforge
SRCS     := main.cpp scan_chain.cpp partial_scan.cpp segment_stress.cpp diagnosis.cpp
OBJS     := $(SRCS:.cpp=.o)

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) -o $@ $^

%.o: %.cpp scan_chain.h segment_stress.h partial_scan.h diagnosis.h
	$(CXX) $(CXXFLAGS) -c -o $@ $<

clean:
	rm -f $(OBJS) $(TARGET)
